"""
Endpoint del flujo "Entrenamiento específico" — POST /training-analysis.

Recibe los 9 campos de la plantilla (validados por TrainingConsultInput),
verifica audiencia (Pro fase 2.0), cobra 3 tokens (igual que /analysis ABC),
llama al servicio Sonnet 4.6 + system prompt validado, y devuelve markdown
del análisis técnico + plan operante por fases.

Cero impacto sobre /analysis (flujo behavior): rutas independientes, schemas
independientes, prompts independientes. Comparten solo cliente Anthropic,
sistema de tokens, helpers (refund, raise_http_for_anthropic, log_usage).

Audiencia (decidido founder 2026-05-29):
  - Fase 2.0: solo Pro (account_type='professional'). 403 para particular.
  - Fase 2.1 (futuro, ~3 semanas): abrir a todos vía env var
    TRAINING_CONSULT_AUDIENCE = "pro_only" | "all".

Idempotencia: no es idempotente (cada POST genera un análisis nuevo y cobra).
El cliente debe gestionar UX para no enviar dos veces (botón disabled durante
la carga, igual que /analysis).

Persistencia: si el cliente pasa case_id, persiste el output como CaseEntry
type="abc" sobre el Case (reusando infra existente). Si no, no persiste —
el cliente puede llamar /cases/migrate después para crear el Case.
"""

import os
import logging
from typing import Optional, List, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Header, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import get_settings
from app.core.token_utils import deduct_token, refund_token
from app.core.anthropic_error import raise_http_for_anthropic
from app.core.usage_tracker import log_usage
from app.core.case_persistence import persist_to_case_safely, get_user_from_authorization
from app.services.training_consult_ai import generate_training_consult


_log = logging.getLogger(__name__)

router = APIRouter(prefix="/training-analysis", tags=["training-consult"])


# Coste tokens (igual que /analysis ABC clínico, decisión founder 2026-05-29).
TRAINING_CONSULT_TOKEN_COST = 3.0

# Audiencia. Fase 2.0 = solo Pro. Para abrir a todos en Fase 2.1, basta cambiar
# la env var TRAINING_CONSULT_AUDIENCE a "all" en Railway. Cero redeploy.
TRAINING_CONSULT_AUDIENCE = (os.environ.get("TRAINING_CONSULT_AUDIENCE", "pro_only")).lower().strip()


# ── Schemas Pydantic ──────────────────────────────────────────────────────
class TrainingConsultInput(BaseModel):
    """Los 9 campos de la plantilla de Entrenamiento Específico."""
    dog_name: str = Field(..., min_length=1, max_length=80)
    breed: str = Field(..., min_length=1, max_length=120, description="Tipología racial: Border Collie, Malinois, mestizo, podenco, etc.")
    age: str = Field(..., min_length=1, max_length=40, description="Edad libre, p.ej. '2 años', '6 meses'")
    dog_level: Literal["basico", "medio", "avanzado"]
    handler_level: Literal["basico", "medio", "avanzado"]
    reinforcers: List[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="Opciones: pelota, mordedor, comida, caricias, nada le motiva. Multi-select hasta 3 (frontend); el backend tolera hasta 5 para futura ampliación.",
    )
    goal: str = Field(..., min_length=4, max_length=1000, description="Habilidad o ejercicio específico que se quiere mejorar")
    context: Literal["pista", "interior", "calle"]
    uses_clicker: bool = Field(..., description="¿Usa clicker habitualmente?")
    lang: Literal["es", "en"] = "es"

    @field_validator("reinforcers")
    @classmethod
    def validate_reinforcers(cls, v: List[str]) -> List[str]:
        """Limpia espacios + valida que las opciones estén en el set permitido."""
        allowed = {"pelota", "mordedor", "comida", "caricias", "nada le motiva"}
        cleaned = [r.strip().lower() for r in v if r and r.strip()]
        invalid = [r for r in cleaned if r not in allowed]
        if invalid:
            raise ValueError(
                f"Reforzadores inválidos: {invalid}. Permitidos: {sorted(allowed)}"
            )
        # "nada le motiva" es excluyente
        if "nada le motiva" in cleaned and len(cleaned) > 1:
            raise ValueError(
                "'nada le motiva' es excluyente: no puede marcarse junto a otros reforzadores."
            )
        return cleaned


class TrainingConsultResponse(BaseModel):
    """Respuesta del endpoint."""
    analysis: str = Field(..., description="Markdown del análisis funcional ABA + plan operante por fases")
    sources: list = Field(default_factory=list, description="Fragmentos de literatura RAG citados [1], [2], …")
    input_tokens: int
    output_tokens: int
    cache_hit: bool = False
    case_type: Literal["training"] = "training"


# ── Endpoint ──────────────────────────────────────────────────────────────
@router.post("", response_model=TrainingConsultResponse)
def create_training_consult(
    payload: TrainingConsultInput,
    background_tasks: BackgroundTasks,
    case_id: Optional[str] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Genera análisis + plan operante por fases para UN ejercicio específico
    que el guía quiere enseñar a su perro.

    Cobra TRAINING_CONSULT_TOKEN_COST tokens (3.0, igual que /analysis ABC).
    Refund automático si Anthropic falla.

    Audiencia: Fase 2.0 solo Pro (account_type='professional'). Particular
    recibe 403. Para abrir a todos: env var TRAINING_CONSULT_AUDIENCE=all.

    Persistencia opcional: si pasa case_id, persiste como CaseEntry type="abc"
    sobre el Case. Si no, el cliente debe gestionarlo después.
    """
    # 1. Auth + gate Pro (Fase 2.0). Se hace ANTES del deduct para no cobrar al
    #    particular que no tiene acceso. require_auth=True garantiza 401 si no JWT.
    user = get_user_from_authorization(authorization, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Autenticación requerida.")

    if TRAINING_CONSULT_AUDIENCE == "pro_only":
        if (user.account_type or "particular").lower() != "professional":
            raise HTTPException(
                status_code=403,
                detail=(
                    "El módulo de Entrenamiento Específico está disponible "
                    "actualmente solo para cuentas Profesionales. "
                    "Próximamente estará abierto a todos los usuarios."
                ),
            )

    # 2. Cobrar tokens (refund garantizado si falla LLM).
    deduct_token(authorization, db, amount=TRAINING_CONSULT_TOKEN_COST, require_auth=True)

    try:
        result = generate_training_consult(
            dog_name=payload.dog_name,
            breed=payload.breed,
            age=payload.age,
            dog_level=payload.dog_level,
            handler_level=payload.handler_level,
            reinforcers=payload.reinforcers,
            goal=payload.goal,
            context=payload.context,
            uses_clicker=payload.uses_clicker,
            lang=payload.lang,
        )

        # 3. Cost tracking fire-and-forget.
        background_tasks.add_task(
            log_usage,
            user_id=user.id,
            endpoint="/training-analysis",
            model=get_settings().clinical_model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            tokens_charged=TRAINING_CONSULT_TOKEN_COST,
            success="ok",
        )

        # 4. Persistencia opcional (no rompe respuesta si falla).
        if case_id:
            persist_to_case_safely(
                case_id, user, db,
                entry_type="abc",
                content=result.analysis_markdown,
                meta={
                    "endpoint": "/training-analysis",
                    "case_type": "training",
                    "goal": payload.goal,
                    "context": payload.context,
                    "dog_level": payload.dog_level,
                    "handler_level": payload.handler_level,
                },
                ai_model=get_settings().clinical_model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                tokens_charged=TRAINING_CONSULT_TOKEN_COST,
                update_summary_abc=True,
            )

        return TrainingConsultResponse(
            analysis=result.analysis_markdown,
            sources=[s.model_dump() for s in result.sources],
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cache_hit=result.cache_hit,
        )
    except Exception as e:
        # Refund: no cobramos al usuario por errores de IA/red.
        refund_token(authorization, db, amount=TRAINING_CONSULT_TOKEN_COST)
        background_tasks.add_task(
            log_usage,
            user_id=user.id,
            endpoint="/training-analysis",
            model=get_settings().clinical_model,
            tokens_charged=TRAINING_CONSULT_TOKEN_COST,
            success="error",
            notes=str(e)[:200],
        )
        raise_http_for_anthropic(e)
