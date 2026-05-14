"""
Generador del "Consejo del día" para s-home.

Llama Claude Haiku 4.5 con prompt experto en psicologia del aprendizaje
canino. Devuelve UNA frase corta (max ~28 palabras) sobre adiestramiento
aplicado, basada en principios cientificos (Skinner, condicionamiento
operante, refuerzo positivo, contracondicionamiento, desensibilizacion,
timing, etc.).

El backend cachea el resultado por (date, lang) para no regenerar en cada
request — todos los usuarios ven el MISMO consejo el mismo dia.
"""
from __future__ import annotations

import logging
from app.core.anthropic_client import get_anthropic_client
from app.config import get_settings

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT_ES = """Eres una etóloga experta en psicología del aprendizaje canino.
Generas EL CONSEJO DEL DÍA para una app de consultoría conductual canina.

REGLAS DURAS:
- UNA sola frase. Sin saltos de línea. Sin viñetas. Sin comillas.
- Máximo 28 palabras (cuenta antes de responder).
- Tono profesional, claro, accesible. No condescendiente, no infantil.
- El consejo debe basarse en principios científicos de psicología del aprendizaje:
  refuerzo positivo, contracondicionamiento, desensibilización sistemática,
  control de estímulos, manejo del timing, extinción, generalización, predictibilidad
  ambiental, motivación, umbrales, criterios incrementales, etc.
- Acción concreta o concepto aplicable que el dueño pueda implementar hoy.
- Evita clichés como "Recuerda que…", "Es importante…", "No olvides…".
- No menciones marcas, fármacos, ni recomiendes profesionales externos.
- No uses emojis.

Devuelve SOLO la frase, sin prefijo ni adorno."""


_SYSTEM_PROMPT_EN = """You are an ethologist expert in canine learning psychology.
You generate THE DAILY TIP for a canine behavior consultancy app.

HARD RULES:
- ONE single sentence. No line breaks. No bullets. No quotes.
- Maximum 28 words (count before responding).
- Professional, clear, accessible tone. Not condescending, not childish.
- The tip must be grounded in learning psychology principles: positive reinforcement,
  counterconditioning, systematic desensitization, stimulus control, timing,
  extinction, generalization, environmental predictability, motivation, thresholds,
  incremental criteria, etc.
- A concrete action or applicable concept the owner can implement today.
- Avoid clichés like "Remember that…", "It's important…", "Don't forget…".
- Do not mention brands, drugs, or recommend external professionals.
- No emojis.

Return ONLY the sentence, without prefix or decoration."""


_USER_PROMPT_ES = "Genera el consejo del día de hoy. Una frase concisa, basada en psicología del aprendizaje, aplicable al adiestramiento canino doméstico."
_USER_PROMPT_EN = "Generate today's daily tip. One concise sentence, grounded in learning psychology, applicable to household dog training."


def generate_daily_tip(lang: str = "es") -> str:
    """
    Genera el consejo del día via Haiku 4.5. Devuelve la frase generada.
    Lanza Exception si Anthropic falla — el caller debe manejar fallback.
    """
    lang = (lang or "es").lower()
    if lang not in ("es", "en"):
        lang = "es"

    system = _SYSTEM_PROMPT_ES if lang == "es" else _SYSTEM_PROMPT_EN
    user_msg = _USER_PROMPT_ES if lang == "es" else _USER_PROMPT_EN

    client = get_anthropic_client()
    settings = get_settings()

    response = client.messages.create(
        model=settings.avatar_model,  # Haiku 4.5
        max_tokens=120,
        temperature=0.9,  # variedad dia a dia
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )

    tip = response.content[0].text.strip()

    # Sanitizar: quitar comillas dobles/simples al inicio/final, quitar saltos
    tip = tip.strip('"\'').replace("\n", " ").replace("  ", " ").strip()

    # Validar longitud razonable
    if len(tip) < 20 or len(tip) > 400:
        logger.warning(f"[daily-tip] generated tip out of range len={len(tip)}: {tip[:80]}")

    return tip


# Fallback estatico si Haiku falla (lo que ya estaba en frontend mockup).
FALLBACK_TIP_ES = "El refuerzo positivo consistente es clave para el cambio conductual a largo plazo. Recompensa las acciones deseadas de inmediato."
FALLBACK_TIP_EN = "Consistent positive reinforcement is key to long-term behavior change. Reward desired actions immediately."


def get_fallback_tip(lang: str = "es") -> str:
    return FALLBACK_TIP_EN if (lang or "es").lower() == "en" else FALLBACK_TIP_ES
