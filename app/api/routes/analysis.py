import json
import hashlib
import os
import tempfile
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, Header, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.anamnesis import AnamnesisInput, AnalysisResponse
from app.services.clinical_ai import run_clinical_analysis
from app.database import get_db
from app.core.safety import log_classification_sync
from app.core.usage_tracker import log_usage
from app.core.case_persistence import persist_to_case_safely, get_user_from_authorization
from app.core.anthropic_error import raise_http_for_anthropic
from app.core.latidos import con_latidos
from app.config import get_settings


def _extract_user_id(authorization: Optional[str]) -> Optional[UUID]:
    """Extrae user_id del Bearer token sin lanzar excepción (para shadow log)."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        from app.api.routes.auth import decode_token
        token = authorization.split(" ", 1)[1]
        return UUID(decode_token(token))
    except Exception:
        return None


def _anamnesis_text_for_safety(anam: AnamnesisInput) -> str:
    """Concatena campos libres de la anamnesis para clasificar (no incluye datos del perro estructurados)."""
    parts = []
    for fld in ("problem", "since", "where", "who", "history", "theory", "prior_event"):
        v = getattr(anam, fld, None)
        if v: parts.append(str(v))
    return " | ".join(parts)

router = APIRouter(prefix="/analysis", tags=["clinical-analysis"])


import re as _re
import logging as _logging
_log = _logging.getLogger(__name__)


def _strip_markdown(text: str) -> str:
    """Remove markdown symbols from AI replies before sending to client."""
    text = _re.sub(r'\*\*', '', text)                        # **bold**
    text = _re.sub(r'\*', '', text)                          # *italic*
    text = _re.sub(r'^#{1,6}\s+', '', text, flags=_re.M)    # ## headings
    text = _re.sub(r'`', '', text)                           # `code`
    text = _re.sub(r'^[–—]\s*$', '', text, flags=_re.M)     # lone em-dash lines
    text = _re.sub(r'\n{3,}', '\n\n', text)                  # max 2 newlines
    return text.strip()

from app.core.token_utils import deduct_token, refund_token

# Max video size accepted: 200 MB
MAX_VIDEO_BYTES = 200 * 1024 * 1024

# Vídeo: soft-truncate UX (Teo 2026-05-17):
# - ANALYSIS_VIDEO_DURATION_SEC: lo que realmente analizamos (8 frames de aquí).
# - MAX_VIDEO_DURATION_SEC: tope superior aceptado. Vídeos entre 10-20s se
#   aceptan pero solo se analizan los primeros 10s (UX amigable vs error puro).
# - Vídeos > 20s se rechazan (probable error del usuario, vídeo equivocado).
ANALYSIS_VIDEO_DURATION_SEC = 10.0
MAX_VIDEO_DURATION_SEC      = 20.0

# Pricing (Teo 2026-05-17): vídeo cobra +1 token sobre texto-only.
# Coste extra real Anthropic ~$0.011 → cobro extra 1 tok ≈ 0.80€ (margen 92%).
ANALYSIS_TEXT_TOKEN_COST  = 3.0
ANALYSIS_VIDEO_TOKEN_COST = 4.0

ALLOWED_VIDEO_TYPES = {
    "video/mp4", "video/quicktime", "video/x-msvideo",
    "video/x-matroska", "video/webm", "video/mpeg",
}


# ── Idempotencia de /analysis ────────────────────────────────────────────────
# MEDIDO 2026-08-31 contra produccion: /analysis tarda 68,5 s en responder 200.
# El WebView nativo corta antes, el usuario ve "error de conexion" y el cobro YA
# se hizo (deduct_token va antes de generar). Al reintentar se le vuelve a cobrar:
# un usuario real pago 9 tokens por un solo analisis el 1-ago-2026.
#
# Solucion: el servidor recuerda lo que genero. Se guarda con una huella de la
# anamnesis; si vuelve la MISMA anamnesis del MISMO usuario dentro de 24 h, se
# devuelve lo guardado al instante y SIN cobrar.
_CACHE_HORAS = 24


def _huella_anamnesis(anamnesis, user_id: Optional[str], sufijo: str = "") -> Optional[str]:
    """Huella estable de (usuario + anamnesis). None si no se puede calcular."""
    if not user_id:
        return None
    try:
        datos = anamnesis.model_dump() if hasattr(anamnesis, "model_dump") else anamnesis.dict()
        crudo = json.dumps(datos, sort_keys=True, default=str, ensure_ascii=False)
        return hashlib.sha256((str(user_id) + "|" + sufijo + "|" + crudo).encode("utf-8")).hexdigest()
    except Exception:
        return None


def _cache_leer(db, huella: Optional[str]):
    """Devuelve el resultado guardado, o None. Nunca lanza."""
    if not huella:
        return None
    try:
        fila = db.execute(
            text("select payload from analysis_cache "
                 "where fingerprint = :f "
                 "and created_at > now() - make_interval(hours => :h)"),
            {"f": huella, "h": _CACHE_HORAS},
        ).fetchone()
        return json.loads(fila[0]) if fila else None
    except Exception:
        return None


def _cache_guardar(db, huella: Optional[str], user_id: str, endpoint: str, payload: dict) -> None:
    """Guarda el resultado. Nunca lanza: si falla, el usuario ya tiene su analisis."""
    if not huella:
        return
    try:
        db.execute(
            text("insert into analysis_cache (fingerprint, user_id, endpoint, payload) "
                 "values (:f, :u, :e, :p) on conflict (fingerprint) do nothing"),
            {"f": huella, "u": str(user_id), "e": endpoint,
             "p": json.dumps(payload, default=str, ensure_ascii=False)},
        )
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def _analisis_sincrono(
    anamnesis: AnamnesisInput,
    background_tasks: BackgroundTasks,
    case_id: Optional[str],
    authorization: Optional[str],
    db: Session,
):
    """
    Run a Functional Behavioral Analysis (text-only anamnesis).

    Accepts the full anamnesis form, retrieves relevant knowledge from
    Qdrant, and returns a clinical ABC analysis generated by Claude
    Sonnet 4.6 with prompt caching active on the system prompt.
    Deducts 3 tokens from the authenticated user (requires login).
    Admins and collaborators are exempt from deduction.

    SHADOW SAFETY: lanza un classifier en background tras la respuesta
    (no añade latencia) que loguea categorías de riesgo en safety_log.
    """
    # ── Idempotencia: PRIMERO mirar, y solo cobrar si hay que generar ────────
    # Si al usuario se le corto la conexion y vuelve a pedir la MISMA anamnesis,
    # se le devuelve lo ya generado al instante y sin cobrarle otra vez.
    user_id_for_logs = _extract_user_id(authorization)
    _huella = _huella_anamnesis(anamnesis, user_id_for_logs)
    _guardado = _cache_leer(db, _huella)
    if _guardado is not None:
        try:
            return AnalysisResponse(**_guardado)
        except Exception:
            pass  # si el guardado no encaja con el modelo, se genera de nuevo

    deduct_token(authorization, db, amount=ANALYSIS_TEXT_TOKEN_COST, require_auth=True)
    # Shadow-mode safety classifier — no bloquea, solo loguea para análisis posterior
    safety_text = _anamnesis_text_for_safety(anamnesis)
    if safety_text:
        background_tasks.add_task(
            log_classification_sync,
            user_id=user_id_for_logs,
            endpoint="/analysis",
            input_text=safety_text,
        )
    # account_type → versión: 'particular' = Pet Owner accesible; resto/None = completa (salvaguarda).
    _acct = None
    try:
        _acct = getattr(get_user_from_authorization(authorization, db), "account_type", None)
    except Exception:
        _acct = None
    try:
        result = run_clinical_analysis(anamnesis, account_type=_acct)
        # Cost tracking — fire-and-forget tras la response
        background_tasks.add_task(
            log_usage,
            user_id=user_id_for_logs,
            endpoint="/analysis",
            model=get_settings().clinical_model,
            input_tokens=getattr(result, "input_tokens", None),
            output_tokens=getattr(result, "output_tokens", None),
            tokens_charged=ANALYSIS_TEXT_TOKEN_COST,
            success="ok",
        )
        # Persistencia opcional al caso (no rompe respuesta si falla)
        if case_id:
            user = get_user_from_authorization(authorization, db)
            persist_to_case_safely(
                case_id, user, db,
                entry_type="abc",
                content=getattr(result, "full_analysis", None) or getattr(result, "analysis", None) or "",
                meta={"endpoint": "/analysis"},
                ai_model=get_settings().clinical_model,
                input_tokens=getattr(result, "input_tokens", None),
                output_tokens=getattr(result, "output_tokens", None),
                tokens_charged=ANALYSIS_TEXT_TOKEN_COST,
                update_summary_abc=True,
            )
        # Se guarda ANTES de devolver: si el WebView corta ahora mismo, el
        # usuario recupera este analisis al reintentar, sin pagar otra vez.
        try:
            _cache_guardar(
                db, _huella, user_id_for_logs, "/analysis",
                result.model_dump() if hasattr(result, "model_dump") else result.dict(),
            )
        except Exception:
            pass
        return result
    except Exception as e:
        # Refund tokens — no cobramos al usuario por errores de IA/red.
        refund_token(authorization, db, amount=ANALYSIS_TEXT_TOKEN_COST)
        background_tasks.add_task(
            log_usage,
            user_id=user_id_for_logs,
            endpoint="/analysis",
            model=get_settings().clinical_model,
            tokens_charged=ANALYSIS_TEXT_TOKEN_COST,
            success="error",
            notes=str(e)[:200],
        )
        raise_http_for_anthropic(e)


@router.post("", response_model=None)
async def create_analysis(
    anamnesis: AnamnesisInput,
    background_tasks: BackgroundTasks,
    case_id: Optional[str] = Query(None, description="Si se pasa, persiste el ABC como entry del caso"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Igual que siempre, pero sin dejar la conexion callada 66 segundos.

    Ver app/core/latidos.py para el porque y las medidas.
    """
    return await con_latidos(
        _analisis_sincrono, anamnesis, background_tasks, case_id, authorization, db)


@router.post("/video", response_model=AnalysisResponse)
async def create_analysis_with_video(
    background_tasks: BackgroundTasks,
    anamnesis_json: str = Form(..., description="Full AnamnesisInput serialised as JSON"),
    video: UploadFile = File(..., description="Video of the dog's behavior (MP4, MOV, AVI…)"),
    video_caption: Optional[str] = Form(None, description="Optional owner description of what the video shows (feedback #2)"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Run a Functional Behavioral Analysis with an attached video.

    The video is stored to a temporary file, key frames are extracted
    with OpenCV (or ffmpeg as fallback), and the frames are passed to
    Claude alongside the written anamnesis for multi-modal analysis.

    Pricing (Teo 2026-05-17): cobra ANALYSIS_VIDEO_TOKEN_COST (4 tokens, +1
    sobre texto-only para captura justa del valor multimodal). Validación
    de duración ≤ MAX_VIDEO_DURATION_SEC (10s) — vídeos más largos se
    rechazan ANTES de cobrar (sin descuento al usuario).
    """
    # ── Validate content type ────────────────────────────────────────────────
    ct = (video.content_type or "").lower()
    if ct and ct not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported video format: {ct}. Use MP4, MOV, AVI or MKV.",
        )

    # ── Read & size-check the upload ─────────────────────────────────────────
    video_bytes = await video.read()
    if len(video_bytes) > MAX_VIDEO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Video too large ({len(video_bytes) // 1024 // 1024} MB). Max 200 MB.",
        )

    # ── Parse anamnesis ──────────────────────────────────────────────────────
    try:
        anamnesis_data = json.loads(anamnesis_json)
        anamnesis = AnamnesisInput(**anamnesis_data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid anamnesis JSON: {e}")

    # ── Write video to temp + duration check ANTES de cobrar ─────────────────
    # Política: si el vídeo dura más de MAX_VIDEO_DURATION_SEC, rechazar SIN
    # descontar tokens. Frontend valida también con metadata HTMLVideoElement.
    suffix = os.path.splitext(video.filename or "video.mp4")[1] or ".mp4"
    tmp_path = None
    _charged = False  # se vuelve True tras deduct_token exitoso → habilita refund en error
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(video_bytes)
            tmp_path = tmp.name

        from app.services.video_processor import extract_frames, get_duration_seconds
        duration = get_duration_seconds(tmp_path)
        # Tope superior: rechazar > MAX_VIDEO_DURATION_SEC (20s). Vídeos
        # entre ANALYSIS_VIDEO_DURATION_SEC (10s) y MAX se aceptan pero solo
        # se analizan los primeros 10s (soft truncate UX-friendly).
        if duration > 0 and duration > MAX_VIDEO_DURATION_SEC:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"El vídeo dura {duration:.1f}s. Máximo permitido: "
                    f"{MAX_VIDEO_DURATION_SEC:.0f}s. Recórtalo y vuelve a subirlo."
                ),
            )
        # Si duration == -1.0 (no se pudo medir) → aceptamos por defensa conservadora.

        # ── Deduct token (DESPUÉS de duration check, así no cobramos rechazos) ──
        deduct_token(authorization, db, amount=ANALYSIS_VIDEO_TOKEN_COST, require_auth=True)
        _charged = True

        # ── Shadow safety classifier (no bloquea, fire-and-forget) ───────────
        safety_text = _anamnesis_text_for_safety(anamnesis)
        if safety_text:
            background_tasks.add_task(
                log_classification_sync,
                user_id=_extract_user_id(authorization),
                endpoint="/analysis/video",
                input_text=safety_text,
            )

        try:
            # Pasar ANALYSIS_VIDEO_DURATION_SEC para soft-truncate al rango
            # [0, 10s]. Si el vídeo dura más, los frames se extraen solo del
            # principio (UX amigable: no rechazamos vídeos de 12-20s).
            frames = extract_frames(
                tmp_path,
                max_duration_sec=ANALYSIS_VIDEO_DURATION_SEC,
            )
        except RuntimeError as e:
            # Frame extraction failed — fall back to text-only analysis
            frames = []
            import logging
            logging.getLogger(__name__).warning(
                "Frame extraction failed, falling back to text-only: %s", e
            )

        # video_caption es input del usuario: se recorta a 300 chars (evita abuso de
        # tokens y limita superficie de prompt-injection; el prompt ya lo trata como
        # contexto no fiable que NO anula la evidencia visual).
        _acct_v = None
        try:
            _acct_v = getattr(get_user_from_authorization(authorization, db), "account_type", None)
        except Exception:
            _acct_v = None
        result = run_clinical_analysis(
            anamnesis,
            video_frames=frames or None,
            video_caption=((video_caption or "").strip()[:300]) or None,
            account_type=_acct_v,
        )
        # Cost tracking — fire-and-forget tras la response (antes /analysis/video
        # NO logueaba → coste multimodal era ciego en usage_log).
        background_tasks.add_task(
            log_usage,
            user_id=_extract_user_id(authorization),
            endpoint="/analysis/video",
            model=get_settings().clinical_model,
            input_tokens=getattr(result, "input_tokens", None),
            output_tokens=getattr(result, "output_tokens", None),
            tokens_charged=ANALYSIS_VIDEO_TOKEN_COST,
            success="ok",
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        # Refund SOLO si llegamos a cobrar (errores previos a deduct_token no
        # deben triggerar refund).
        if _charged:
            refund_token(authorization, db, amount=ANALYSIS_VIDEO_TOKEN_COST)
            background_tasks.add_task(
                log_usage,
                user_id=_extract_user_id(authorization),
                endpoint="/analysis/video",
                model=get_settings().clinical_model,
                tokens_charged=ANALYSIS_VIDEO_TOKEN_COST,
                success="error",
                notes=str(e)[:200],
            )
        raise_http_for_anthropic(e)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ── Chat / Plan refinement ────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    anamnesis: dict  # free-form dict — no strict validation needed for chat context
    original_analysis: str
    messages: List[ChatMessage]  # full conversation history incl. latest user message
    lang: Optional[str] = "es"   # 'es' or 'en' — UI language for the response

class ChatResponse(BaseModel):
    reply: str
    tokens_remaining: Optional[float] = None


CHAT_SYSTEM_PROMPT = """Eres la IA Analítica by Teo Mariscal, una inteligencia artificial especializada en conducta canina, \
creada para ayudar a etólogos y adiestradores a refinar planes de modificación de conducta.

Ya has realizado un Análisis Funcional ABC completo de este caso. Ahora el profesional quiere profundizar, \
corregir algún dato o pedir alternativas a pasos del plan que no son viables en la situación real del cliente.

Tu misión:
- Escuchar las aclaraciones o restricciones del profesional.
- Ajustar o completar el plan de intervención con esa nueva información.
- Ofrecer alternativas concretas, basadas en evidencia, cuando alguna recomendación original no sea aplicable.
- Mantener siempre un tono clínico, profesional y directo.
- No repetir el análisis completo salvo que te lo pidan expresamente; céntrate en la parte que hay que revisar.
- Si el profesional dice algo como "los perros viven juntos y no pueden separarse", propón protocolos de \
  convivencia y desensibilización que funcionen en esa restricción, sin volver a recomendar la separación.
- IMPORTANTE: No uses nunca markdown. Nada de ##, ###, **, *, `, — decorativo ni ningún símbolo de formato. \
  Escribe texto limpio con párrafos separados por saltos de línea. Para listas usa guión simple seguido de espacio.

Sé conciso y útil. {LANG_INSTRUCTION}"""

LANG_INSTRUCTION_ES = "Responde en español por defecto. Si el usuario te escribe en otro idioma, cambia a ese idioma."
LANG_INSTRUCTION_EN = "Respond in English by default. If the user writes to you in another language, switch to that language."


@router.post("/chat", response_model=ChatResponse)
def analysis_chat(
    req: ChatRequest,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Refinement chat — 0.25 tokens per exchange.

    Accepts the original anamnesis, the full analysis text, and the
    accumulated conversation history. Returns the AI's next reply.

    SHADOW SAFETY: clasifica el último mensaje del usuario en background
    (no bloquea, solo loguea para análisis posterior).
    """
    tokens_left = deduct_token(authorization, db, amount=0.25)

    # Shadow safety classifier sobre el último mensaje del usuario.
    # Fix audit 2026-05-17: antes leía req.history (atributo inexistente en
    # ChatRequest → siempre []), dejando la telemetry de safety en /chat ciega.
    # ChatRequest define `messages: List[ChatMessage]`. Apple Guideline 1.1.6.
    last_user_msg = ""
    try:
        for m in reversed(req.messages or []):
            if getattr(m, "role", "") == "user":
                last_user_msg = (getattr(m, "content", "") or "").strip()
                break
    except Exception:
        last_user_msg = ""
    if last_user_msg:
        background_tasks.add_task(
            log_classification_sync,
            user_id=_extract_user_id(authorization),
            endpoint="/analysis/chat",
            input_text=last_user_msg,
        )

    from app.core.anthropic_client import get_anthropic_client

    # Build context block with anamnesis + original analysis
    context = (
        f"=== FICHA DEL CASO ===\n{json.dumps(req.anamnesis, ensure_ascii=False, indent=2)}\n\n"
        f"=== ANÁLISIS ABC ORIGINAL ===\n{req.original_analysis}"
    )

    # Convert conversation history to Anthropic format
    messages = []
    # First turn: inject context as a user message followed by an ack so history is clean
    messages.append({
        "role": "user",
        "content": f"Aquí tienes el contexto completo del caso que ya analizaste:\n\n{context}",
    })
    messages.append({
        "role": "assistant",
        "content": "Entendido. Tengo el caso completo y el análisis previo. ¿En qué parte del plan quieres que trabajemos?",
    })
    # Append real conversation
    for m in req.messages:
        messages.append({"role": m.role, "content": m.content})

    client = get_anthropic_client()
    chat_model = "claude-sonnet-4-5"        # Sonnet 4.5 — fast & high quality for chat
    user_id_for_logs = _extract_user_id(authorization)
    # Inject UI language so Sonnet responds in the right language
    lang = (req.lang or "es").lower()
    lang_instr = LANG_INSTRUCTION_EN if lang == "en" else LANG_INSTRUCTION_ES
    system_prompt_localized = CHAT_SYSTEM_PROMPT.replace("{LANG_INSTRUCTION}", lang_instr)
    from app.services.tea_pilot import apply_tea_override
    system_prompt_localized = apply_tea_override(
        system_prompt_localized, str(req.anamnesis), req.original_analysis
    )
    try:
        # Límite subido de 1024 a 8000 (2026-08-06, reporte de Sofía D):
        # el chat de refinamiento del plan se cortaba SIEMPRE a media frase y la
        # usuaria gastaba créditos pidiendo "repíteme desde el punto X". Es la
        # misma regla dura que ya se aplicó al análisis (6000) y al plan (8000):
        # un plan NUNCA debe cortarse. El coste extra solo se paga si la
        # respuesta de verdad lo necesita.
        response = client.messages.create(
            model=chat_model,
            max_tokens=8000,
            system=system_prompt_localized,
            messages=messages,
        )
        reply = _strip_markdown(response.content[0].text)

        # Salvaguarda: si aun así llega al tope, se PIDE LA CONTINUACIÓN y se
        # une, en vez de devolver el texto mutilado y que el usuario pague otra
        # consulta para recuperarlo.
        if getattr(response, "stop_reason", None) == "max_tokens":
            try:
                seguimiento = client.messages.create(
                    model=chat_model,
                    max_tokens=8000,
                    system=system_prompt_localized,
                    messages=messages + [
                        {"role": "assistant", "content": response.content[0].text},
                        {"role": "user", "content":
                            "Continúa EXACTAMENTE donde lo dejaste, sin repetir nada "
                            "de lo ya escrito y sin introducción."},
                    ],
                )
                reply = reply + "\n" + _strip_markdown(seguimiento.content[0].text)
            except Exception:
                pass   # si la continuación falla, al menos va lo que había
        # Cost tracking — fire-and-forget
        background_tasks.add_task(
            log_usage,
            user_id=user_id_for_logs,
            endpoint="/analysis/chat",
            model=chat_model,
            input_tokens=getattr(response.usage, "input_tokens", None),
            output_tokens=getattr(response.usage, "output_tokens", None),
            tokens_charged=0.25,
            success="ok",
        )
    except Exception as e:
        # Refund: el usuario no paga por errores de IA/red.
        refund_token(authorization, db, amount=0.25)
        background_tasks.add_task(
            log_usage,
            user_id=user_id_for_logs,
            endpoint="/analysis/chat",
            model=chat_model,
            tokens_charged=0.25,
            success="error",
            notes=str(e)[:200],
        )
        raise_http_for_anthropic(e, fallback_msg=f"Error de IA: {e}")

    return ChatResponse(reply=reply, tokens_remaining=tokens_left)
