"""
Daily Follow-up router — feature de seguimiento diario tipo Duolingo.

Wizard ampliado 2026-05-09: 30 tasks batch (commit A) → check-in on-demand
con 2-5 ejercicios (último wellness) + 1 pregunta educativa por día.

Endpoints (todos requieren JWT, todos verifican Case.user_id == current_user.id):

  POST  /cases/{id}/daily-followup/init      → activa daily_followup + classify diagnosis (sin batch)
  GET   /cases/{id}/daily-followup/today     → check-in del día (genera on-demand si no existe)
  POST  /cases/{id}/daily-followup           → submit (exercises_results + theory_answer_index)
  PUT   /cases/{id}/daily-followup/enable    → toggle ON
  PUT   /cases/{id}/daily-followup/disable   → toggle OFF
  GET   /cases/{id}/daily-followup/tasks     → DEPRECATED (array vacío)

Streak rule:
  - Día "rellenado" = is_complete=True (todos los ejercicios + pregunta tienen respuesta).
  - 2 días seguidos NO rellenados rompen el streak.
  - 1 día suelto no rompe.
  - Acertar/fallar la pregunta no afecta (la app muestra la correcta — es educativa).

Spec: ~/.claude/projects/.../memory/project_dogs_mind_daily_followup.md.
"""

from __future__ import annotations
import uuid
import logging
from datetime import datetime, date, timedelta
from typing import Optional, Literal, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.user import User
from app.models.case import (
    Case, CaseEntry, DailyFollowupEntry,
)
from app.api.routes.auth import get_current_user
from app.services.daily_followup_ai import (
    classify_diagnosis, generate_daily_checkin,
    DailyCheckin, ExerciseSpec, TheoryQuestionSpec,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases", tags=["daily-followup"])


# ── Constantes (invariantes del seguimiento diario) ─────────────────────────
SILVER_THRESHOLD = 3
GOLD_THRESHOLD = 10
GOLD_TOKEN_REWARD = 2.0
MAX_GAP_DAYS_TO_KEEP_STREAK = 2  # 1 día suelto no rompe; 2 saltos seguidos sí


# ── Schemas Pydantic ────────────────────────────────────────────────────────
class DailyFollowupInit(BaseModel):
    intervention_plan_text: Optional[str] = Field(None, max_length=20000)
    lang: Literal["es", "en"] = "es"


class DailyFollowupInitResponse(BaseModel):
    case_id: str
    daily_followup_enabled: bool
    diagnosis_type: Optional[str]


class ExerciseDTO(BaseModel):
    title: str
    instruction: str
    result_type: Literal["chips", "text"]
    result_chips: Optional[list[str]]
    is_wellness: bool


class TheoryQuestionDTO(BaseModel):
    question_type: Literal["theory", "compliance"]
    question: str
    options: list[str]
    correct_index: int
    explanation: str
    question_id: Optional[str]  # UUID de la TheoryQuestion en caché (None si freshly generated y aún sin persistir, pero el servicio siempre persiste)


class DailyFollowupTodayResponse(BaseModel):
    case_id: str
    daily_followup_enabled: bool
    day_index: int
    already_completed_today: bool
    in_recovery: bool
    current_streak: int
    longest_streak: int
    current_badge: Optional[str]
    exercises: list[ExerciseDTO]
    theory_question: TheoryQuestionDTO
    # Respuestas del usuario si el día ya está completado (None en placeholder
    # pendiente). Añadidos 2026-05-27 para que el frontend pueda rehidratar
    # chips/textareas al re-entrar al check-in completado — antes el usuario
    # veía los ejercicios "como si no los hubiera rellenado" porque la
    # response no incluía sus respuestas y `loadToday` reseteaba
    # `_state.results` a objetos vacíos.
    exercises_results: Optional[list[dict]] = None
    theory_answer_index: Optional[int] = None


class ExerciseResultIn(BaseModel):
    """Una respuesta del usuario por ejercicio (mismo orden que exercises_generated)."""
    result_chip_index: Optional[int] = Field(None, ge=0, le=2)
    result_text: Optional[str] = Field(None, max_length=400)


class DailyFollowupSubmit(BaseModel):
    exercises_results: list[ExerciseResultIn] = Field(..., min_length=2, max_length=5)
    theory_answer_index: int = Field(..., ge=0, le=2)


class DailyFollowupSubmitResponse(BaseModel):
    case_id: str
    saved: bool
    is_complete: bool
    current_streak: int
    longest_streak: int
    current_badge: Optional[str]
    in_recovery: bool
    silver_just_earned: bool
    gold_just_earned: bool
    tokens_credited: float
    new_token_balance: Optional[float]


# ── Helpers ─────────────────────────────────────────────────────────────────
def _ownership_or_404(case_id: str, user: User, db: Session) -> Case:
    try:
        case_uuid = uuid.UUID(case_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=404, detail="Caso no encontrado.")
    case = db.query(Case).filter(
        Case.id == case_uuid,
        Case.user_id == user.id,
        Case.deleted_at.is_(None),
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Caso no encontrado.")
    return case


def _get_dog_name(case: Case, db: Session) -> str:
    if case.client_dog_name:
        return case.client_dog_name
    if case.dog_id:
        from app.models.dog import Dog
        d = db.query(Dog).filter(Dog.id == case.dog_id).first()
        if d and d.name:
            return d.name
    return "tu perro"


def _today_local() -> date:
    """v1: UTC-day-bucket. v1.1 timezone explícito del usuario."""
    return datetime.utcnow().date()


def _get_plan_text(case: Case, db: Session) -> str:
    """Última intervención del caso, o cadena vacía si no hay."""
    intv = db.query(CaseEntry).filter(
        CaseEntry.case_id == case.id,
        CaseEntry.type == "intervention",
    ).order_by(desc(CaseEntry.created_at)).first()
    return (intv.content or "").strip() if intv else ""


def _build_history(case_id, db: Session, exclude_today: date) -> list[dict[str, Any]]:
    """Histórico de entries previas (excluyendo today) en orden cronológico.

    NOTA (variación de ejercicios, 2026-05-27): se INCLUYEN también los días
    con placeholder pendiente (is_complete=False). Antes filtrábamos por
    is_complete=True, lo que dejaba al coach sin saber qué propuso ayer
    cuando el tutor abría el plan pero no completaba el check-in. Resultado:
    el LLM recibía inputs idénticos varios días → ejercicios casi iguales.
    Ahora, en _format_history (daily_followup_ai.py), los días sin reportar
    aparecen como "(sin reportar)" — señal informativa válida para el coach
    y suficiente para que rote/varíe títulos. El streak sigue usando
    is_complete=True (regla intacta en _recompute_streak).
    """
    rows = db.query(DailyFollowupEntry).filter(
        DailyFollowupEntry.case_id == case_id,
        DailyFollowupEntry.day_local_date < exclude_today,
    ).order_by(DailyFollowupEntry.day_local_date.asc()).all()
    out = []
    # Calcular day_n relativo a la primera entry del histórico.
    first_date = rows[0].day_local_date if rows else None
    for r in rows:
        day_n = (r.day_local_date - first_date).days + 1 if first_date else 1
        out.append({
            "day_n": day_n,
            "exercises_generated": r.exercises_generated or [],
            "exercises_results": r.exercises_results or [],
            "observation": r.observation,
        })
    return out


def _compute_day_index(case_id, db: Session, today: date) -> int:
    """Día N actual = (today - primera_entry.day_local_date) + 1. Si no hay entries, día 1."""
    first = db.query(DailyFollowupEntry).filter(
        DailyFollowupEntry.case_id == case_id,
    ).order_by(DailyFollowupEntry.day_local_date.asc()).first()
    if not first:
        return 1
    delta = (today - first.day_local_date).days + 1
    return max(1, delta)


def _recompute_streak(case_id, db: Session, today: date) -> tuple[int, bool]:
    """
    Recalcula streak walking back desde today con la regla
    "1 día suelto no rompe; 2 saltos seguidos rompen".

    Retorna (streak_count, is_in_recovery).
    is_in_recovery = True si la entry más reciente is_complete=true tiene gap > MAX desde today
                     o si hay un gap actual al borde.
    """
    completes = db.query(DailyFollowupEntry).filter(
        DailyFollowupEntry.case_id == case_id,
        DailyFollowupEntry.is_complete.is_(True),
    ).order_by(DailyFollowupEntry.day_local_date.desc()).all()

    if not completes:
        return 0, False

    # Si la entry más reciente es de hace > MAX_GAP_DAYS_TO_KEEP_STREAK días desde today,
    # el streak está muerto y estamos en recovery.
    gap_to_today = (today - completes[0].day_local_date).days
    if gap_to_today > MAX_GAP_DAYS_TO_KEEP_STREAK:
        return 0, True

    # Walk back: contar consecutivas con gap <= MAX entre entradas.
    streak = 1
    for i in range(1, len(completes)):
        gap = (completes[i - 1].day_local_date - completes[i].day_local_date).days
        if gap <= MAX_GAP_DAYS_TO_KEEP_STREAK:
            streak += 1
        else:
            break

    return streak, False


# ── Endpoints ───────────────────────────────────────────────────────────────
@router.post(
    "/{case_id}/daily-followup/init",
    response_model=DailyFollowupInitResponse,
    status_code=status.HTTP_201_CREATED,
)
def init_daily_followup(
    case_id: str,
    payload: DailyFollowupInit,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Activa daily_followup y clasifica el diagnóstico (Haiku, ~$0.0001).

    Idempotente: si ya está activo y tiene diagnosis_type, no reclasifica.

    Si el cliente pasa `intervention_plan_text` en el body Y no existe
    aún `CaseEntry type='intervention'` para este caso (típico en casos
    legacy creados antes del hook acceptIntervention -> /init), creamos
    la entry con ese contenido. Así /today puede recuperar el plan
    posteriormente sin error.
    """
    case = _ownership_or_404(case_id, user, db)

    # Persistir CaseEntry intervention si llega plan_text y no existe.
    # Cubre el caso legacy donde acceptIntervention guardaba el plan solo
    # en localStorage del usuario, sin persistirlo en backend.
    body_plan = (payload.intervention_plan_text or "").strip()
    if body_plan:
        existing_interv = db.query(CaseEntry).filter(
            CaseEntry.case_id == case.id,
            CaseEntry.type == "intervention",
        ).first()
        if not existing_interv:
            db.add(CaseEntry(
                case_id=case.id,
                type="intervention",
                content=body_plan,
                meta={"source": "daily_followup_init_backfill"},
            ))
            db.commit()
            logger.info(f"[daily-followup-init] case={case.id} CaseEntry intervention creado desde body plan_text (legacy backfill)")

    # Si ya está activo y clasificado, idempotente
    if case.daily_followup_enabled and case.diagnosis_type:
        return DailyFollowupInitResponse(
            case_id=str(case.id),
            daily_followup_enabled=True,
            diagnosis_type=case.diagnosis_type,
        )

    plan_text = body_plan or _get_plan_text(case, db)
    if not plan_text:
        raise HTTPException(
            status_code=400,
            detail="No hay plan de intervención disponible para este caso.",
        )

    # Clasificar (idempotente: solo si no hay clasificación previa)
    if not case.diagnosis_type:
        try:
            case.diagnosis_type = classify_diagnosis(plan_text)
        except Exception as e:
            logger.warning(f"[daily-followup-init] classify_diagnosis failed case={case.id}: {e}")
            case.diagnosis_type = "other"

    case.daily_followup_enabled = True

    # Opción C — backfill oportunista de case.lang si está NULL y el cliente
    # envía un lang en el payload. Esto resuelve casos pre-feature sin tener
    # que correr una migración batch. Idempotente: solo si está NULL.
    if not case.lang and payload.lang in ("es", "en"):
        case.lang = payload.lang

    db.commit()
    db.refresh(case)

    logger.info(
        f"[daily-followup-init] case={case.id} diagnosis={case.diagnosis_type} enabled=True lang={case.lang}"
    )

    return DailyFollowupInitResponse(
        case_id=str(case.id),
        daily_followup_enabled=True,
        diagnosis_type=case.diagnosis_type,
    )


@router.get(
    "/{case_id}/daily-followup/today",
    response_model=DailyFollowupTodayResponse,
)
def get_daily_followup_today(
    case_id: str,
    lang: Literal["es", "en"] = "es",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Devuelve el check-in del día. Genera on-demand con el coach si no
    existe entry hoy (placeholder con is_complete=False). Si ya hay
    placeholder o entry completa hoy, devuelve los mismos ejercicios sin
    regenerar (idempotencia por día)."""
    case = _ownership_or_404(case_id, user, db)
    today = _today_local()

    # Streak / recovery snapshot (solo lectura).
    streak, in_recovery = _recompute_streak(case.id, db, today)
    # Si ha cambiado respecto a lo persistido, sincronizar. Solo lectura, así
    # que actualizamos cols del case para que el frontend vea coherente.
    if case.current_streak != streak or bool(case.in_recovery) != in_recovery:
        case.current_streak = streak
        case.in_recovery = in_recovery
        db.commit()

    today_entry = db.query(DailyFollowupEntry).filter(
        DailyFollowupEntry.case_id == case.id,
        DailyFollowupEntry.day_local_date == today,
    ).first()

    # Si ya completó hoy, no regenera; devuelve los mismos.
    if today_entry and today_entry.is_complete:
        return _today_response_from_entry(case, today_entry, today, db)

    # Si hay placeholder pendiente, devolver lo que ya generamos.
    if today_entry and today_entry.exercises_generated:
        return _today_response_from_entry(case, today_entry, today, db)

    # Necesitamos generar el check-in. Validar prerequisites.
    if not case.daily_followup_enabled:
        raise HTTPException(
            status_code=400,
            detail="El seguimiento diario está desactivado para este caso.",
        )
    plan_text = _get_plan_text(case, db)
    if not plan_text:
        raise HTTPException(
            status_code=400,
            detail="No hay plan de intervención disponible para este caso.",
        )
    if not case.diagnosis_type:
        # Reclasificación defensiva si por alguna razón init no la hizo.
        try:
            case.diagnosis_type = classify_diagnosis(plan_text)
            db.commit()
        except Exception:
            case.diagnosis_type = "other"

    dog_name = _get_dog_name(case, db)
    day_index = _compute_day_index(case.id, db, today)
    history = _build_history(case.id, db, exclude_today=today)

    # Opción C — lang fijo del caso prevalece sobre query-param.
    # Casos creados antes de la feature tienen case.lang=NULL → usa el query
    # (comportamiento previo, cero regresión).
    effective_lang = case.lang or lang or "es"

    try:
        checkin = generate_daily_checkin(
            db=db,
            case_id=case.id,
            plan_text=plan_text,
            dog_name=dog_name,
            diagnosis_type=case.diagnosis_type,
            day_index=day_index,
            history=history,
            lang=effective_lang,
            today=today,
        )
    except ValueError as e:
        logger.error(f"[daily-followup-today] coach validation error case={case.id}: {e}")
        raise HTTPException(status_code=502, detail="No se pudo generar el check-in del día.")
    except Exception as e:
        logger.error(f"[daily-followup-today] coach error case={case.id}: {e}")
        raise HTTPException(status_code=502, detail="Error al generar el check-in del día.")

    # Persistir placeholder (entry con exercises_generated, is_complete=false).
    if not today_entry:
        today_entry = DailyFollowupEntry(
            case_id=case.id,
            user_id=user.id,
            day_local_date=today,
            is_complete=False,
        )
        db.add(today_entry)
    today_entry.exercises_generated = [
        {
            "title": e.title,
            "instruction": e.instruction,
            "result_type": e.result_type,
            "result_chips": e.result_chips,
            "is_wellness": e.is_wellness,
        }
        for e in checkin.exercises
    ]
    today_entry.theory_question_id = (
        uuid.UUID(checkin.theory_question_cache_id) if checkin.theory_question_cache_id else None
    )
    db.commit()
    db.refresh(today_entry)

    return DailyFollowupTodayResponse(
        case_id=str(case.id),
        daily_followup_enabled=True,
        day_index=day_index,
        already_completed_today=False,
        in_recovery=bool(case.in_recovery),
        current_streak=case.current_streak or 0,
        longest_streak=case.longest_streak or 0,
        current_badge=case.current_badge,
        exercises=[
            ExerciseDTO(
                title=e.title, instruction=e.instruction,
                result_type=e.result_type, result_chips=e.result_chips,
                is_wellness=e.is_wellness,
            )
            for e in checkin.exercises
        ],
        theory_question=TheoryQuestionDTO(
            question_type=checkin.theory_question.question_type,
            question=checkin.theory_question.question,
            options=checkin.theory_question.options,
            correct_index=checkin.theory_question.correct_index,
            explanation=checkin.theory_question.explanation,
            question_id=checkin.theory_question_cache_id,
        ),
    )


def _today_response_from_entry(
    case: Case, entry: DailyFollowupEntry, today: date, db: Session,
) -> DailyFollowupTodayResponse:
    """Construye la response a partir de una entry existente (placeholder o completa)."""
    from app.models.case import TheoryQuestion
    exercises_data = entry.exercises_generated or []
    exercises = [
        ExerciseDTO(
            title=str(ex.get("title", "")),
            instruction=str(ex.get("instruction", "")),
            result_type=str(ex.get("result_type", "chips")),
            result_chips=ex.get("result_chips"),
            is_wellness=bool(ex.get("is_wellness", False)),
        )
        for ex in exercises_data
    ]
    theory: TheoryQuestionDTO
    if entry.theory_question_id:
        tq = db.query(TheoryQuestion).filter(TheoryQuestion.id == entry.theory_question_id).first()
        if tq:
            theory = TheoryQuestionDTO(
                question_type=tq.question_type,
                question=tq.question_text,
                options=list(tq.options) if tq.options else [],
                correct_index=tq.correct_index,
                explanation=tq.explanation,
                question_id=str(tq.id),
            )
        else:
            theory = TheoryQuestionDTO(
                question_type="theory", question="", options=[],
                correct_index=0, explanation="", question_id=None,
            )
    else:
        theory = TheoryQuestionDTO(
            question_type="theory", question="", options=[],
            correct_index=0, explanation="", question_id=None,
        )

    day_index = _compute_day_index(case.id, db, today)

    # Si el día ya está completado, devolver también las respuestas que dio
    # el usuario para que el frontend rehidrate la UI (chips marcados,
    # textareas con texto, opción de teoría seleccionada). Si la entry es
    # un placeholder pendiente, ambos campos van como None.
    completed = bool(entry.is_complete)
    results_payload = entry.exercises_results if completed else None
    theory_answer  = entry.theory_answer_index if completed else None

    return DailyFollowupTodayResponse(
        case_id=str(case.id),
        daily_followup_enabled=bool(case.daily_followup_enabled),
        day_index=day_index,
        already_completed_today=completed,
        in_recovery=bool(case.in_recovery),
        current_streak=case.current_streak or 0,
        longest_streak=case.longest_streak or 0,
        current_badge=case.current_badge,
        exercises=exercises,
        theory_question=theory,
        exercises_results=results_payload,
        theory_answer_index=theory_answer,
    )


@router.post(
    "/{case_id}/daily-followup",
    response_model=DailyFollowupSubmitResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_daily_followup(
    case_id: str,
    payload: DailyFollowupSubmit,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Marca la entry del día como completa y aplica streak/badge/recovery.

    Requiere haber llamado antes a GET /today (que crea el placeholder con
    exercises_generated). El número de exercises_results debe coincidir con
    el número de exercises_generated.
    """
    case = _ownership_or_404(case_id, user, db)
    if not case.daily_followup_enabled:
        raise HTTPException(
            status_code=400,
            detail="El seguimiento diario está desactivado para este caso.",
        )

    today = _today_local()
    entry = db.query(DailyFollowupEntry).filter(
        DailyFollowupEntry.case_id == case.id,
        DailyFollowupEntry.day_local_date == today,
    ).first()
    if not entry:
        raise HTTPException(
            status_code=400,
            detail="No hay check-in para hoy. Llama primero a GET /daily-followup/today.",
        )
    if entry.is_complete:
        raise HTTPException(
            status_code=409,
            detail="Ya completaste el seguimiento de hoy.",
        )
    generated = entry.exercises_generated or []
    if len(payload.exercises_results) != len(generated):
        raise HTTPException(
            status_code=422,
            detail=f"El número de respuestas ({len(payload.exercises_results)}) no "
                   f"coincide con el de ejercicios ({len(generated)}).",
        )

    # Validar correspondencia chip vs text contra exercises_generated.
    for i, (gen, res) in enumerate(zip(generated, payload.exercises_results)):
        rtype = gen.get("result_type", "chips")
        if rtype == "chips":
            if res.result_chip_index is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"Ejercicio {i+1}: result_chip_index requerido.",
                )
        elif rtype == "text":
            if not (res.result_text and res.result_text.strip()):
                raise HTTPException(
                    status_code=422,
                    detail=f"Ejercicio {i+1}: result_text requerido.",
                )

    # Persistir respuestas + marcar completa.
    entry.exercises_results = [
        {
            "result_chip_index": r.result_chip_index,
            "result_text": r.result_text.strip() if r.result_text else None,
        }
        for r in payload.exercises_results
    ]
    entry.theory_answer_index = payload.theory_answer_index
    entry.is_complete = True
    db.commit()
    db.refresh(entry)

    # Recalcular streak / badge / recovery con regla nueva.
    new_streak, in_recovery = _recompute_streak(case.id, db, today)
    silver_just_earned = False
    gold_just_earned = False
    tokens_credited = 0.0

    prev_badge = case.current_badge
    new_badge = prev_badge
    if new_streak >= GOLD_THRESHOLD:
        new_badge = "gold"
        if not case.gold_token_reward_granted:
            tokens_credited = GOLD_TOKEN_REWARD
            case.gold_token_reward_granted = True
            user.tokens = float(user.tokens or 0) + GOLD_TOKEN_REWARD
            gold_just_earned = True
            logger.info(
                f"[daily-followup-gold] case={case.id} user={user.email} +{GOLD_TOKEN_REWARD} tokens"
            )
    elif new_streak >= SILVER_THRESHOLD:
        if prev_badge != "silver" and prev_badge != "gold":
            silver_just_earned = True
        new_badge = "silver" if prev_badge != "gold" else prev_badge

    case.current_streak = new_streak
    case.current_badge = new_badge
    case.in_recovery = in_recovery
    if new_streak > (case.longest_streak or 0):
        case.longest_streak = new_streak
    case.last_filled_at = datetime.utcnow()

    db.commit()
    db.refresh(case)
    db.refresh(user)

    return DailyFollowupSubmitResponse(
        case_id=str(case.id),
        saved=True,
        is_complete=True,
        current_streak=case.current_streak,
        longest_streak=case.longest_streak,
        current_badge=case.current_badge,
        in_recovery=bool(case.in_recovery),
        silver_just_earned=silver_just_earned,
        gold_just_earned=gold_just_earned,
        tokens_credited=tokens_credited,
        new_token_balance=float(user.tokens) if user.tokens is not None else None,
    )


@router.put("/{case_id}/daily-followup/enable")
def enable_daily_followup(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = _ownership_or_404(case_id, user, db)
    if not case.daily_followup_enabled:
        case.daily_followup_enabled = True
        db.commit()
    return {"case_id": str(case.id), "daily_followup_enabled": True}


@router.put("/{case_id}/daily-followup/disable")
def disable_daily_followup(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = _ownership_or_404(case_id, user, db)
    if case.daily_followup_enabled:
        case.daily_followup_enabled = False
        db.commit()
    return {"case_id": str(case.id), "daily_followup_enabled": False}


@router.get("/{case_id}/daily-followup/tasks")
def list_daily_tasks_deprecated(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """DEPRECATED — el flujo batch (30 tasks pre-generadas) fue sustituido por
    generación on-demand del check-in del día. Mantenemos el path por
    compatibilidad: devolvemos array vacío sin error."""
    _ownership_or_404(case_id, user, db)
    return {"case_id": case_id, "tasks": [], "deprecated": True}
