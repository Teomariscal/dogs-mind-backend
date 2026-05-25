"""
Router del módulo "Inspiración Profesional" / Adiestramiento Avanzado.

POST /training/daily-session
  - Genera EXACTAMENTE 5 ejercicios de adiestramiento (Haiku 4.5) a partir de
    un objetivo del día + ajustes opcionales.
  - Auth obligatoria (get_current_user).
  - Gating: solo usuarios con account_type='professional' (403 si no).
  - Cobro de tokens ANTES de llamar a la IA, con refund si la IA falla.
  - Logueo de coste en usage_log vía BackgroundTasks (modelo Haiku).

Patrón calcado de app/api/routes/analysis.py (deduct → try IA → log ok /
except refund + log error → raise_http_for_anthropic).
"""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.api.routes.auth import get_current_user
from app.core.token_utils import deduct_token, refund_token
from app.core.usage_tracker import log_usage
from app.core.anthropic_error import raise_http_for_anthropic
from app.config import get_settings
from app.services.training_ai import generate_training_session

router = APIRouter(prefix="/training", tags=["training"])


# ── Pricing ───────────────────────────────────────────────────────────────────
# PENDIENTE confirmar precio con Teo (no tocar precios sin su OK).
# Placeholder 0.25 — NO es definitivo. Coste real Haiku por sesión (~1200 out
# tokens) es bajísimo; el precio final lo fija Teo cuando valide la feature.
TRAINING_SESSION_TOKEN_COST = 0.25  # PENDIENTE confirmar precio con Teo (no tocar precios sin su OK)


# ── Schemas Pydantic ──────────────────────────────────────────────────────────
class TrainingSessionRequest(BaseModel):
    objetivo: str = Field(
        ...,
        min_length=1,
        max_length=600,
        description="Objetivo de hoy (obligatorio). Qué se quiere entrenar.",
    )
    nivel_perro: str = Field("medio", description="basico | medio | avanzado")
    nivel_guias: str = Field("medio", description="basico | medio | avanzado")
    tiempo: Optional[int] = Field(None, description="Minutos disponibles: 15 | 30 | 45 | 60")
    donde: Optional[str] = Field(None, max_length=120, description="Dónde será la clase")
    recursos: Optional[List[str]] = Field(None, description="Recursos disponibles (clicker, comida…)")
    reforzadores: Optional[List[str]] = Field(None, description="Reforzadores válidos para el perro")
    lang: str = Field("es", description="'es' | 'en'")

    @field_validator("objetivo")
    @classmethod
    def _strip_objetivo(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("El objetivo no puede estar vacío.")
        return s

    @field_validator("nivel_perro", "nivel_guias")
    @classmethod
    def _valid_level(cls, v: str) -> str:
        s = (v or "medio").strip().lower()
        if s not in ("basico", "medio", "avanzado"):
            raise ValueError("Nivel inválido. Valores: basico | medio | avanzado")
        return s

    @field_validator("tiempo")
    @classmethod
    def _valid_tiempo(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v not in (15, 30, 45, 60):
            raise ValueError("Tiempo inválido. Valores: 15 | 30 | 45 | 60")
        return v

    @field_validator("donde")
    @classmethod
    def _strip_donde(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        s = v.strip()
        return s or None

    @field_validator("recursos", "reforzadores")
    @classmethod
    def _clean_list(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        cleaned = [str(x).strip() for x in v if x and str(x).strip()]
        # Cap defensivo: como máximo 20 items para evitar prompts enormes.
        return cleaned[:20]

    @field_validator("lang")
    @classmethod
    def _valid_lang(cls, v: str) -> str:
        s = (v or "es").strip().lower()
        return s if s in ("es", "en") else "es"


class TrainingExercise(BaseModel):
    instruccion: str
    explicacion: str


class TrainingSessionResponse(BaseModel):
    ejercicios: List[TrainingExercise]
    objetivo: str


@router.post("/daily-session", response_model=TrainingSessionResponse)
def create_daily_session(
    request: TrainingSessionRequest,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Genera 5 ejercicios de adiestramiento para la sesión de hoy (Haiku 4.5).

    Solo para usuarios profesionales (account_type='professional'). Cobra
    TRAINING_SESSION_TOKEN_COST tokens (placeholder, pendiente de confirmar con
    Teo); admins/developers exentos. Refund si la IA falla. Loguea coste en
    usage_log.
    """
    # ── Gating profesional ────────────────────────────────────────────────────
    if user.account_type != "professional":
        raise HTTPException(
            status_code=403,
            detail="Solo profesionales pueden usar el Adiestramiento Avanzado.",
        )

    # ── Cobro ANTES de la IA (patrón de la app) ──────────────────────────────
    deduct_token(authorization, db, amount=TRAINING_SESSION_TOKEN_COST, require_auth=True)

    user_id_for_logs: Optional[UUID] = getattr(user, "id", None)

    try:
        result = generate_training_session(
            objetivo=request.objetivo,
            nivel_perro=request.nivel_perro,
            nivel_guias=request.nivel_guias,
            tiempo=request.tiempo,
            donde=request.donde,
            recursos=request.recursos,
            reforzadores=request.reforzadores,
            lang=request.lang,
        )
        # ── Log de coste — fire-and-forget tras la response ──────────────────
        background_tasks.add_task(
            log_usage,
            user_id=user_id_for_logs,
            endpoint="/training/daily-session",
            model=get_settings().avatar_model,
            input_tokens=getattr(result, "input_tokens", None),
            output_tokens=getattr(result, "output_tokens", None),
            tokens_charged=TRAINING_SESSION_TOKEN_COST,
            success="ok",
        )
        return TrainingSessionResponse(
            ejercicios=[TrainingExercise(**ex) for ex in result.exercises],
            objetivo=request.objetivo,
        )
    except Exception as e:
        # Refund: el usuario no paga por errores de IA/red/parseo.
        refund_token(authorization, db, amount=TRAINING_SESSION_TOKEN_COST)
        background_tasks.add_task(
            log_usage,
            user_id=user_id_for_logs,
            endpoint="/training/daily-session",
            model=get_settings().avatar_model,
            tokens_charged=TRAINING_SESSION_TOKEN_COST,
            success="error",
            notes=str(e)[:200],
        )
        raise_http_for_anthropic(e)
