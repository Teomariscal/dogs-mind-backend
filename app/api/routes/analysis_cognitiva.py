"""
POST /analysis/cognitiva — la relación clínica cognitivista de Odette.

Fichero APARTE a propósito. La vía conductual (`analysis.py`) no se toca ni una
línea: son dos caminos que no comparten ni modelo de entrada, ni prompts, ni
ruta. Ése es el aislamiento que pidió el founder el 6-sep-2026 ("extrema
cautela ... que no haya nunca ninguna fuga cognitivista a la parte conductual").

La puerta se comprueba DOS veces a propósito: aquí, para poder devolver un 403
claro y no cobrar; y otra vez dentro del motor, que falla cerrado por su cuenta
aunque alguien lo llamara desde otro sitio en el futuro.
"""
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.anthropic_error import raise_http_for_anthropic
from app.core.case_persistence import get_user_from_authorization
from app.core.latidos import con_latidos
from app.core.token_utils import deduct_token, refund_token
from app.core.usage_tracker import log_usage
from app.config import get_settings
from app.database import get_db
from app.models.anamnesis_cognitiva import AnamnesiCognitivaInput, AnamnesiCognitivaResponse
from app.services.cognitive_odette import redactar_relazione
from app.services.italian_cognitive import (
    CognitiveReexpressionError,
    cognitive_path_applies,
)

_log = logging.getLogger("analysis_cognitiva")

router = APIRouter(prefix="/analysis", tags=["cognitive-analysis"])

# Mismo coste que el análisis conductual: es el mismo trabajo clínico y el
# founder no quiere dos tarifas para la misma consulta.
COSTE_TOKENS = 3.0


def _sincrono(
    anamnesi: AnamnesiCognitivaInput,
    background_tasks: BackgroundTasks,
    authorization: Optional[str],
    db: Session,
):
    usuario = get_user_from_authorization(authorization, db) if authorization else None
    account_type = getattr(usuario, "account_type", None) if usuario else None
    user_id = str(getattr(usuario, "id", "")) if usuario else None

    # ── LA PUERTA, antes de cobrar ──────────────────────────────────────
    if not cognitive_path_applies(
        lang=anamnesi.lang,
        account_type=account_type,
        stance=anamnesi.stance,
    ):
        raise HTTPException(
            status_code=403,
            detail="Questa via è riservata all'analisi cognitivista italiana per account professionali.",
        )

    deduct_token(authorization, db, amount=COSTE_TOKENS, require_auth=True)

    try:
        relazione, tipo, analisis = redactar_relazione(anamnesi, account_type=account_type)
    except PermissionError:
        refund_token(authorization, db, amount=COSTE_TOKENS)
        raise HTTPException(status_code=403, detail="La via cognitivista non si applica.")
    except CognitiveReexpressionError as e:
        # Nunca se degrada a la salida conductual: antes error y devolución.
        refund_token(authorization, db, amount=COSTE_TOKENS)
        _log.warning("relación cognitivista fallida: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Non è stato possibile redigere la relazione. Riprova tra poco.",
        )
    except Exception as e:
        refund_token(authorization, db, amount=COSTE_TOKENS)
        background_tasks.add_task(
            log_usage, user_id=user_id, endpoint="/analysis/cognitiva",
            model=get_settings().clinical_model, tokens_charged=COSTE_TOKENS,
            success="error", notes=str(e)[:200],
        )
        raise_http_for_anthropic(e)

    background_tasks.add_task(
        log_usage, user_id=user_id, endpoint="/analysis/cognitiva",
        model=get_settings().clinical_model, tokens_charged=COSTE_TOKENS,
        success="ok", notes=tipo,
    )
    # `fatti` es la pasada 1 (el analisis ABA oculto): se devuelve para poder
    # AUDITARLA desde fuera. La app NO la pinta nunca.
    return AnamnesiCognitivaResponse(relazione=relazione, tipo=tipo, fatti=analisis)


@router.post("/cognitiva", response_model=None)
async def crear_relazione_cognitiva(
    anamnesi: AnamnesiCognitivaInput,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Dos pasadas y más de un minuto de trabajo: va con latidos como las demás."""
    return await con_latidos(_sincrono, anamnesi, background_tasks, authorization, db)
