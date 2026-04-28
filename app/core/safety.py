"""
Input safety classifier — SHADOW MODE.

Pre-classifies user-submitted text (anamnesis, chat) using Claude Haiku
to detect risk categories that may need redirection to a professional
or emergency services:

- agresion_grave: serious aggression (bites with bleeding, hospitalizations)
- autolesion: dog self-harm (extreme tail-chasing, mutilation, OCD ingestion)
- emergencia_medica: medical emergency (seizures, bleeding, poisoning, etc.)
- envenenamiento_intencional: descriptions of intent to harm the dog/others
- crisis_humana: owner showing signs of severe emotional crisis

In SHADOW MODE this module ONLY logs to safety_log; it never blocks the
response. Once we have data on precision/recall over real traffic, we
will switch to gating responses for high-confidence positives by checking
`SafetyLog.action_taken == 'blocked'` upstream.

Design notes:
- Fail-open: any error in the classifier (timeout, network, parsing) just
  logs the error and lets the main analysis proceed normally.
- Runs as fire-and-forget background task; never adds latency to the main
  response.
- Truncates input to keep cost predictable (~1KB max sent to Haiku).
"""

import json
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.core.anthropic_client import get_anthropic_client
from app.config import get_settings
from app.database import SessionLocal
from app.models.safety_log import SafetyLog

logger = logging.getLogger(__name__)

# Truncate inputs to bound cost. Avg analysis text is <2KB so this rarely cuts.
MAX_INPUT_CHARS = 1500

# Haiku is fast/cheap; fits this guardrail role.
_settings = get_settings()
SAFETY_MODEL = _settings.avatar_model  # "claude-haiku-4-5"

CLASSIFIER_PROMPT = """Eres un clasificador de seguridad para una app de etología canina (Dogs Mind).

Tu tarea: analizar el texto que un dueño envía sobre su perro y detectar si contiene alguno de estos riesgos. Responde SIEMPRE con JSON válido y NADA MÁS.

Categorías (todas booleanas):
1. "agresion_grave": ataques con mordeduras profundas, sangrado, hospitalizaciones, agresión inminente a personas vulnerables (niños, ancianos)
2. "autolesion": el perro se autoinflige daño (tail-chasing extremo hasta sangre, automutilación, ingestión obsesiva de objetos peligrosos, lamido compulsivo con lesiones)
3. "emergencia_medica": síntomas que requieren veterinario URGENTE (convulsiones activas, sangrado abundante, signos de envenenamiento, dificultad respiratoria, colapso, parto complicado)
4. "envenenamiento_intencional": el dueño u otra persona expresa intención de dañar al perro o a otros animales
5. "crisis_humana": el dueño muestra crisis emocional grave en el texto (ideación de daño a sí mismo, desesperación extrema, riesgo de abandono violento del perro)

Formato de respuesta (JSON estricto, sin texto extra):
{
  "agresion_grave": false,
  "autolesion": false,
  "emergencia_medica": false,
  "envenenamiento_intencional": false,
  "crisis_humana": false,
  "score_global": 0.0,
  "razonamiento": "1-2 frases máximo explicando tu evaluación"
}

score_global: 0.0 si todas son false, 1.0 si hay riesgo claro y grave en al menos una categoría.

TEXTO A CLASIFICAR:
---
{INPUT}
---"""


def classify_text(text: str) -> dict:
    """
    Llama a Haiku con el classifier prompt y devuelve dict con la clasificación.
    Si algo falla, devuelve dict con campo 'error' y categorías a False.
    """
    truncated = (text or "")[:MAX_INPUT_CHARS]
    prompt = CLASSIFIER_PROMPT.replace("{INPUT}", truncated)

    fallback = {
        "agresion_grave": False,
        "autolesion": False,
        "emergencia_medica": False,
        "envenenamiento_intencional": False,
        "crisis_humana": False,
        "score_global": 0.0,
        "razonamiento": "(classifier unavailable, fail-open)",
        "error": None,
    }

    try:
        client = get_anthropic_client()
        msg = client.messages.create(
            model=SAFETY_MODEL,
            max_tokens=300,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = (msg.content[0].text or "").strip() if msg.content else ""
        # Algunos modelos envuelven JSON en ```json ... ``` — limpiamos
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        parsed = json.loads(raw)
        # Sanity: todos los campos esperados
        for key in ["agresion_grave", "autolesion", "emergencia_medica",
                    "envenenamiento_intencional", "crisis_humana"]:
            parsed.setdefault(key, False)
        parsed.setdefault("score_global", 0.0)
        parsed.setdefault("razonamiento", "")
        parsed["error"] = None
        return parsed
    except Exception as e:
        logger.warning("safety classifier failed (fail-open): %s", e, exc_info=False)
        fallback["error"] = str(e)[:500]
        return fallback


def log_classification_sync(
    user_id: Optional[UUID],
    endpoint: str,
    input_text: str,
):
    """
    Sync log function — abre su propia DB session porque corre fuera del
    request lifecycle. Se llama vía asyncio.to_thread / BackgroundTasks
    desde el endpoint, NO bloquea la response.
    """
    db = SessionLocal()
    try:
        cls = classify_text(input_text)
        log = SafetyLog(
            user_id=user_id,
            endpoint=endpoint,
            input_preview=(input_text or "")[:1000],
            classification=cls,
            score_global=float(cls.get("score_global") or 0.0),
            action_taken="shadow_log_only",  # FUTURO: cambiar a 'blocked' cuando activemos
            error=cls.get("error"),
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.warning("safety log write failed: %s", e, exc_info=False)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        try:
            db.close()
        except Exception:
            pass
