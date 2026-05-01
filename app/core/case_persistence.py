"""
Helpers para persistir entries en un Case desde los endpoints existentes
(/analysis, /intervention, /avatar/chat) cuando se pasa case_id opcional.

Diseño defensivo:
- Si case_id es None: no hace nada (comportamiento legacy intacto).
- Si case_id existe pero no pertenece al user: log warning y NO rompe (la
  respuesta IA al usuario llega bien; solo no se persiste).
- Si la persistencia falla por cualquier motivo (DB caída, etc.): log warning
  y NO rompe la respuesta. El usuario ya pagó tokens, recibe su análisis.
- Cuando persiste con éxito, regenera summary_full del caso para que la
  próxima consulta IA tenga el contexto fresco.
"""

from __future__ import annotations
import logging
import re as _re
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.case import Case, CaseEntry
from app.models.dog import Dog
from datetime import datetime

_log = logging.getLogger(__name__)

# Reusamos los regex de cases.py para extraer summaries simples
_MD_HEADER_RE = _re.compile(r"^[#>]+\s*", _re.MULTILINE)
_MD_BOLD_RE = _re.compile(r"\*\*([^*]+)\*\*")
_MD_ITALIC_RE = _re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_MD_CITATION_RE = _re.compile(r"\[(\d+(?:,\s*\d+)*)\]")
_MD_DECOR_RE = _re.compile(r"^[─═]{3,}$", _re.MULTILINE)
_WS_RE = _re.compile(r"\s+")


def _strip_md(text: str) -> str:
    if not text:
        return ""
    t = _MD_HEADER_RE.sub("", text)
    t = _MD_BOLD_RE.sub(r"\1", t)
    t = _MD_ITALIC_RE.sub(r"\1", t)
    t = _MD_CITATION_RE.sub("", t)
    t = _MD_DECOR_RE.sub("", t)
    t = _WS_RE.sub(" ", t).strip()
    return t


def _summarize(text: str, max_chars: int = 500) -> Optional[str]:
    clean = _strip_md(text or "")
    if not clean:
        return None
    if len(clean) <= max_chars:
        return clean
    cut = clean[:max_chars]
    last_period = cut.rfind(". ")
    if last_period > max_chars * 0.5:
        return cut[: last_period + 1]
    return cut.rstrip() + "…"


def _build_summary_full(case: Case, db: Session) -> str:
    """Reconstruye summary_full del caso. Misma lógica que cases.py para coherencia."""
    parts = []

    # Identidad del perro vinculado
    if case.dog_id:
        dog = db.query(Dog).filter(
            Dog.id == case.dog_id,
            Dog.deleted_at.is_(None),
        ).first()
        if dog:
            edad = datetime.utcnow().year - dog.birth_year
            parts.append(
                f"PERRO: {dog.name}, raza {dog.breed}, "
                f"{edad} años, sexo {dog.sex}, "
                f"{'esterilizado' if dog.neutered else 'sin esterilizar'}"
            )

    parts.append(f"TÍTULO: {case.title}")
    if case.motivo_consulta:
        parts.append(f"MOTIVO: {case.motivo_consulta[:500]}")
    if case.summary_abc:
        parts.append(f"ABC: {case.summary_abc[:600]}")
    if case.summary_plan:
        parts.append(f"PLAN: {case.summary_plan[:600]}")

    # Últimos 5 seguimientos
    recent_seg = (
        db.query(CaseEntry)
        .filter(CaseEntry.case_id == case.id, CaseEntry.type == "seguimiento")
        .order_by(CaseEntry.created_at.desc())
        .limit(5)
        .all()
    )
    if recent_seg:
        recent_seg = list(reversed(recent_seg))
        seg_lines = ["SEGUIMIENTOS RECIENTES:"]
        for s in recent_seg:
            meta = s.meta or {}
            fecha = s.created_at.strftime("%Y-%m-%d")
            dias = meta.get("dias_tratamiento", "?")
            sesiones = meta.get("numero_sesiones", "?")
            evol = "Sí" if meta.get("ve_evolucion") else "No"
            criterio = (meta.get("criterio_medicion") or "")[:80]
            descripcion = (meta.get("descripcion_evolucion") or "")[:200]
            seg_lines.append(
                f"- [{fecha}] día {dias}, sesiones {sesiones}, evol={evol}"
                + (f", criterio: {criterio}" if criterio else "")
                + (f", desc: {descripcion}" if descripcion else "")
            )
        parts.append("\n".join(seg_lines))

    # Últimos 5 mensajes Cecilia tipo progress_tracking
    recent_progress = (
        db.query(CaseEntry)
        .filter(
            CaseEntry.case_id == case.id,
            CaseEntry.type == "chat_aigent",
        )
        .order_by(CaseEntry.created_at.desc())
        .limit(10)  # ~5 turnos (user+assistant)
        .all()
    )
    progress_filtered = [
        e for e in recent_progress
        if e.meta and isinstance(e.meta, dict)
        and e.meta.get("purpose") == "progress_tracking"
    ]
    if progress_filtered:
        progress_filtered = list(reversed(progress_filtered))
        prog_lines = ["AVANCES RECIENTES (chat Cecilia):"]
        for e in progress_filtered:
            meta = e.meta or {}
            role = meta.get("role", "?")
            content_short = (e.content or "")[:200]
            prog_lines.append(f"- [{e.created_at.strftime('%Y-%m-%d')}] {role}: {content_short}")
        parts.append("\n".join(prog_lines))

    return "\n\n".join(parts)


def persist_to_case_safely(
    case_id: Optional[str],
    user: Optional[User],
    db: Session,
    *,
    entry_type: str,                  # 'abc' | 'intervention' | 'chat_aigent' | 'seguimiento' | 'anamnesis'
    content: str,
    meta: Optional[Dict[str, Any]] = None,
    ai_model: Optional[str] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    tokens_charged: Optional[float] = None,
    update_summary_abc: bool = False,
    update_summary_plan: bool = False,
) -> Optional[str]:
    """
    Persiste una entry en el caso si case_id se pasa Y pertenece al user.

    Devuelve el id de la entry creada, o None si no se persistió por cualquier motivo.
    NUNCA propaga excepciones — la respuesta IA al usuario debe llegar siempre.
    """
    if not case_id or not user:
        return None
    try:
        case = db.query(Case).filter(
            Case.id == case_id,
            Case.user_id == user.id,
            Case.deleted_at.is_(None),
        ).first()
        if not case:
            _log.warning("persist_to_case_safely: case %s no pertenece a user %s o no existe", case_id, user.id)
            return None

        entry = CaseEntry(
            case_id=case.id,
            type=entry_type,
            content=content or "(sin contenido)",
            meta=meta,
            ai_model=ai_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            tokens_charged=tokens_charged,
        )
        db.add(entry)

        # Actualizar summaries del caso
        if update_summary_abc:
            case.summary_abc = _summarize(content, max_chars=600)
        if update_summary_plan:
            case.summary_plan = _summarize(content, max_chars=600)
        case.updated_at = datetime.utcnow()
        db.flush()

        # Regenerar summary_full incluyendo este nuevo contenido
        case.summary_full = _build_summary_full(case, db)
        db.commit()
        db.refresh(entry)
        return str(entry.id)
    except Exception as e:
        _log.warning("persist_to_case_safely failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return None


def get_user_from_authorization(authorization: Optional[str], db: Session) -> Optional[User]:
    """Helper para obtener User desde el Bearer token sin lanzar 401."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        from app.api.routes.auth import decode_token
        from app.models.user import User as UserModel
        user_id = decode_token(authorization.split(" ", 1)[1])
        return db.query(UserModel).filter(UserModel.id == user_id).first()
    except Exception:
        return None
