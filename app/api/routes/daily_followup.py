"""
Daily Follow-up router — feature de seguimiento diario tipo Duolingo.

Endpoints (todos requieren JWT, todos verifican Case.user_id == current_user.id):

    POST   /cases/{id}/daily-followup/init      → generar 30 tasks (tras aceptar plan)
    GET    /cases/{id}/daily-followup/today     → task del día + estado
    POST   /cases/{id}/daily-followup           → registrar entry del día (wizard 4 pasos)
    PUT    /cases/{id}/daily-followup/enable    → toggle ON
    PUT    /cases/{id}/daily-followup/disable   → toggle OFF

Lógica de streak / badge / recovery vive en el handler POST.

Spec completa: ~/.claude/projects/.../memory/project_dogs_mind_daily_followup.md
"""

from __future__ import annotations
import uuid
import logging
from datetime import datetime, date, timedelta
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel, Field, field_validator

from app.database import get_db
from app.models.user import User
from app.models.case import (
    Case, CaseEntry, DailyFollowupEntry, CaseDailyTask,
    DOG_STATES, EXECUTION_QUALITIES, SKIP_REASONS,
)
from app.api.routes.auth import get_current_user
from app.services.daily_tasks_ai import generate_daily_tasks
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["daily-followup"])


# ── Constantes (invariantes del seguimiento diario) ─────────────────────────
SILVER_THRESHOLD = 3   # días consecutivos para badge plata
GOLD_THRESHOLD = 10    # días consecutivos para badge oro
GOLD_TOKEN_REWARD = 2.0  # tokens regalo al ganar oro (una vez por caso)
RECOVERY_GAP_HOURS = 48  # >48h sin rellenar → entra en recovery
TOTAL_TASKS_PER_CYCLE = 30
MAX_OBSERVATION_CHARS = 280


# ── Schemas Pydantic ────────────────────────────────────────────────────────
class DailyFollowupInit(BaseModel):
    """Body opcional para init: si no se envía, intenta tomar el plan del caso."""
    intervention_plan_text: Optional[str] = Field(
        None,
        description="Texto del plan a convertir en 30 tasks. Si vacío, se busca en case_entries type=intervention.",
        max_length=20000,
    )
    lang: Literal["es", "en"] = "es"


class DailyFollowupInitResponse(BaseModel):
    case_id: str
    tasks_generated: int
    daily_followup_enabled: bool


class DailyFollowupTaskToday(BaseModel):
    case_id: str
    daily_followup_enabled: bool
    already_filled_today: bool
    day_index: Optional[int]  # 1..30
    task_text: Optional[str]
    current_streak: int
    longest_streak: int
    current_badge: Optional[str]  # None | 'silver' | 'gold'
    in_recovery: bool


class DailyFollowupSubmit(BaseModel):
    task_completed: bool = Field(..., description="Marca de paso 1: hecha vs no esta vez")
    execution_quality: Optional[Literal["better", "expected", "hard"]] = Field(
        None, description="Solo si task_completed=True (paso 2 chips)"
    )
    skip_reason: Optional[Literal["no_time", "not_dog_moment", "forgot", "other"]] = Field(
        None, description="Solo si task_completed=False (paso 2 chips)"
    )
    dog_state: Literal["calm", "active", "nervous", "reactive", "other"] = Field(
        ..., description="Paso 3: estado del perro hoy"
    )
    observation: Optional[str] = Field(
        None, max_length=MAX_OBSERVATION_CHARS,
        description="Paso 4: observación libre opcional",
    )

    @field_validator("execution_quality")
    @classmethod
    def _eq_only_if_completed(cls, v, info):
        # No podemos cross-validar contra task_completed aquí (Pydantic v2 ValidationInfo);
        # se hará en el handler. Solo strip aquí.
        return v

    @field_validator("observation")
    @classmethod
    def _strip_obs(cls, v):
        if v is None:
            return None
        s = v.strip()
        return s or None


class DailyFollowupSubmitResponse(BaseModel):
    case_id: str
    saved: bool
    current_streak: int
    longest_streak: int
    current_badge: Optional[str]
    in_recovery: bool
    silver_just_earned: bool
    gold_just_earned: bool
    tokens_credited: float  # 0 o 2.0
    new_token_balance: Optional[float]


# ── Helpers ─────────────────────────────────────────────────────────────────
def _ownership_or_404(case_id: str, user: User, db: Session) -> Case:
    """Carga el caso si pertenece al usuario y no está soft-deleted."""
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
    """Devuelve el nombre del perro del caso (Dog propio o client_dog_name)."""
    if case.client_dog_name:
        return case.client_dog_name
    if case.dog_id:
        from app.models.dog import Dog
        d = db.query(Dog).filter(Dog.id == case.dog_id).first()
        if d and d.name:
            return d.name
    return "tu perro"


def _next_day_index(case_id: uuid.UUID, db: Session) -> int:
    """Próximo day_index (1..30+) basado en cuántas entries hay hoy o antes."""
    count = db.query(func.count(DailyFollowupEntry.id)).filter(
        DailyFollowupEntry.case_id == case_id
    ).scalar() or 0
    # day_index 1-based: si hay 0 entries, mañana es el 1.
    return count + 1


def _task_for_day(case_id: uuid.UUID, day_index: int, db: Session) -> Optional[str]:
    """Devuelve el texto de la task para day_index. Si supera 30, cicla
    al ronda siguiente (regeneración aún no implementada en v1, usa ronda 1)."""
    if day_index < 1:
        return None
    # Versión v1: día 31+ → cicla a la ronda 1 con (day_index-1) % 30 + 1.
    # Regeneración ronda 2+ se añade post-launch si los datos lo justifican.
    cycle_day = ((day_index - 1) % TOTAL_TASKS_PER_CYCLE) + 1
    task = db.query(CaseDailyTask).filter(
        CaseDailyTask.case_id == case_id,
        CaseDailyTask.day_index == cycle_day,
        CaseDailyTask.generation_round == 1,
    ).first()
    return task.task_text if task else None


def _today_local() -> date:
    """Fecha local del servidor. Para v1 asumimos UTC-day-bucket. v1.1 se
    pasará el timezone del usuario para evitar drift en zonas extremas."""
    return datetime.utcnow().date()


def _has_entry_today(case_id: uuid.UUID, db: Session) -> bool:
    today = _today_local()
    return db.query(
        db.query(DailyFollowupEntry).filter(
            DailyFollowupEntry.case_id == case_id,
            DailyFollowupEntry.day_local_date == today,
        ).exists()
    ).scalar()


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
    """Genera 30 tasks con Sonnet a partir del plan y activa daily_followup.
    Idempotente: si ya hay tasks generadas para este caso (round 1), no las regenera.
    """
    case = _ownership_or_404(case_id, user, db)

    # Si ya hay tasks generadas, idempotente: solo activar follow-up.
    existing_count = db.query(func.count(CaseDailyTask.id)).filter(
        CaseDailyTask.case_id == case.id,
        CaseDailyTask.generation_round == 1,
    ).scalar() or 0

    if existing_count >= TOTAL_TASKS_PER_CYCLE:
        if not case.daily_followup_enabled:
            case.daily_followup_enabled = True
            db.commit()
        return DailyFollowupInitResponse(
            case_id=str(case.id),
            tasks_generated=existing_count,
            daily_followup_enabled=case.daily_followup_enabled,
        )

    # Buscar el plan: si no se pasa explícito, lo tomamos del último entry
    # type='intervention' del caso.
    plan_text = (payload.intervention_plan_text or "").strip()
    if not plan_text:
        latest_intervention = db.query(CaseEntry).filter(
            CaseEntry.case_id == case.id,
            CaseEntry.type == "intervention",
        ).order_by(desc(CaseEntry.created_at)).first()
        if latest_intervention and latest_intervention.content:
            plan_text = latest_intervention.content
    if not plan_text:
        raise HTTPException(
            status_code=400,
            detail="No hay plan de intervención disponible para este caso. Acepta el plan antes de activar el seguimiento.",
        )

    dog_name = _get_dog_name(case, db)

    try:
        result = generate_daily_tasks(
            intervention_plan_text=plan_text,
            dog_name=dog_name,
            lang=payload.lang,
        )
    except Exception as e:
        logger.error(f"[daily-followup-init] LLM error case={case.id}: {e}")
        raise HTTPException(status_code=500, detail="No se pudieron generar las tareas.")

    # Persistir las 30 tasks (round=1).
    for i, task_text in enumerate(result.tasks, start=1):
        db.add(CaseDailyTask(
            case_id=case.id,
            day_index=i,
            task_text=task_text,
            generation_round=1,
        ))

    case.daily_followup_enabled = True
    db.commit()

    logger.info(
        f"[daily-followup-init] case={case.id} tasks=30 "
        f"in={result.input_tokens} out={result.output_tokens}"
    )

    return DailyFollowupInitResponse(
        case_id=str(case.id),
        tasks_generated=len(result.tasks),
        daily_followup_enabled=True,
    )


@router.get(
    "/{case_id}/daily-followup/today",
    response_model=DailyFollowupTaskToday,
)
def get_daily_followup_today(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Devuelve la task del día y el estado del seguimiento."""
    case = _ownership_or_404(case_id, user, db)

    already_filled = _has_entry_today(case.id, db)
    day_idx = _next_day_index(case.id, db)
    task_text = _task_for_day(case.id, day_idx, db) if case.daily_followup_enabled else None

    return DailyFollowupTaskToday(
        case_id=str(case.id),
        daily_followup_enabled=case.daily_followup_enabled,
        already_filled_today=already_filled,
        day_index=day_idx if (case.daily_followup_enabled and task_text) else None,
        task_text=task_text,
        current_streak=case.current_streak or 0,
        longest_streak=case.longest_streak or 0,
        current_badge=case.current_badge,
        in_recovery=bool(case.in_recovery),
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
    """Registra la entry del día y aplica la lógica de streak/badge/recovery.

    Lógica:
    - UNIQUE (case_id, today_local) impide doble registro.
    - Si gap > 48h desde last_filled_at: streak resetea, badge a None,
      in_recovery = True.
    - El nuevo registro suma 1 al streak.
    - Si streak alcanza 3 → badge silver. Si entra en recovery, "alcanzar 3"
      también restaura silver tras 2 días consecutivos en recovery (3 incl. hoy).
    - Si streak alcanza 10 y gold_token_reward_granted=False: badge gold,
      acreditar 2 tokens, gold_token_reward_granted=True.
    """
    case = _ownership_or_404(case_id, user, db)

    if not case.daily_followup_enabled:
        raise HTTPException(
            status_code=400,
            detail="El seguimiento diario está desactivado para este caso.",
        )

    # Validación cross-field: execution_quality solo si completed; skip_reason solo si NOT completed
    if payload.task_completed and payload.skip_reason is not None:
        raise HTTPException(status_code=422, detail="skip_reason no aplica si la tarea fue completada.")
    if (not payload.task_completed) and payload.execution_quality is not None:
        raise HTTPException(status_code=422, detail="execution_quality no aplica si la tarea no fue completada.")

    today = _today_local()

    # UNIQUE check defensivo (la BD tiene constraint, pero damos error claro)
    if _has_entry_today(case.id, db):
        raise HTTPException(
            status_code=409,
            detail="Ya registraste el seguimiento de hoy.",
        )

    # ── Lógica de streak / badge / recovery ────────────────────────────────
    now = datetime.utcnow()
    silver_just_earned = False
    gold_just_earned = False
    tokens_credited = 0.0

    # Detectar gap > 48h ANTES de incrementar.
    if case.last_filled_at:
        gap = now - case.last_filled_at
        if gap > timedelta(hours=RECOVERY_GAP_HOURS):
            # Reset por gap (recovery)
            case.current_streak = 0
            case.current_badge = None
            case.in_recovery = True

    # Incrementar streak
    new_streak = (case.current_streak or 0) + 1
    case.current_streak = new_streak
    if new_streak > (case.longest_streak or 0):
        case.longest_streak = new_streak

    # Badge silver: al alcanzar 3
    if new_streak == SILVER_THRESHOLD:
        if case.current_badge != "silver":
            silver_just_earned = True
        case.current_badge = "silver"
        # Si estaba en recovery, ya recuperó plata.
        case.in_recovery = False

    # Badge gold: al alcanzar 10
    if new_streak >= GOLD_THRESHOLD:
        if case.current_badge != "gold":
            case.current_badge = "gold"
        # Reward 2 tokens UNA vez por caso
        if not case.gold_token_reward_granted:
            tokens_credited = GOLD_TOKEN_REWARD
            case.gold_token_reward_granted = True
            user.tokens = float(user.tokens or 0) + GOLD_TOKEN_REWARD
            gold_just_earned = True
            logger.info(
                f"[daily-followup-gold] case={case.id} user={user.email} "
                f"+{GOLD_TOKEN_REWARD} tokens"
            )

    case.last_filled_at = now
    case.in_recovery = False if new_streak >= SILVER_THRESHOLD else case.in_recovery

    # Persist entry
    entry = DailyFollowupEntry(
        case_id=case.id,
        user_id=user.id,
        day_local_date=today,
        task_completed=payload.task_completed,
        execution_quality=payload.execution_quality,
        skip_reason=payload.skip_reason,
        dog_state=payload.dog_state,
        observation=payload.observation,
    )
    db.add(entry)
    db.commit()
    db.refresh(case)
    db.refresh(user)

    return DailyFollowupSubmitResponse(
        case_id=str(case.id),
        saved=True,
        current_streak=case.current_streak,
        longest_streak=case.longest_streak,
        current_badge=case.current_badge,
        in_recovery=bool(case.in_recovery),
        silver_just_earned=silver_just_earned,
        gold_just_earned=gold_just_earned,
        tokens_credited=tokens_credited,
        new_token_balance=float(user.tokens) if user.tokens is not None else None,
    )


@router.get("/{case_id}/daily-followup/tasks")
def list_daily_tasks(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Lista las 30 tasks generadas (round 1) de un caso. Útil para preview
    en frontend (commit B) y para que el usuario sepa qué viene los próximos días."""
    case = _ownership_or_404(case_id, user, db)
    tasks = db.query(CaseDailyTask).filter(
        CaseDailyTask.case_id == case.id,
        CaseDailyTask.generation_round == 1,
    ).order_by(CaseDailyTask.day_index).all()
    return {
        "case_id": str(case.id),
        "tasks": [
            {"day_index": t.day_index, "task_text": t.task_text}
            for t in tasks
        ],
    }


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
