from typing import Optional
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, HTTPException, Header, Depends, Query
from sqlalchemy.orm import Session

from app.models.avatar import AvatarChatRequest, AvatarChatResponse
from app.services.avatar_ai import chat
from app.database import get_db
from app.core.token_utils import deduct_token, refund_token
from app.core.usage_tracker import log_usage
from app.core.case_persistence import persist_to_case_safely, get_user_from_authorization
from app.core.anthropic_error import raise_http_for_anthropic
from app.config import get_settings

router = APIRouter(prefix="/avatar", tags=["avatar"])


def _extract_user_id_av(authorization: Optional[str]) -> Optional[UUID]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        from app.api.routes.auth import decode_token
        return UUID(decode_token(authorization.split(" ", 1)[1]))
    except Exception:
        return None


@router.post("/chat", response_model=AvatarChatResponse)
def avatar_chat(
    request: AvatarChatRequest,
    background_tasks: BackgroundTasks,
    case_id: Optional[str] = Query(None, description="Si se pasa, persiste el turno usuario+IA como entries del caso (chat_aigent)"),
    purpose: Optional[str] = Query(None, description="Purpose del chat dentro del caso: 'progress_tracking' o 'general_chat'"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Send a message to one of the Aigent avatars (Claude Haiku 4.5).
    Costs 0.10 tokens per message. Requires login.
    Admins and collaborators are exempt.

    Si se pasa case_id como query, el turno (último mensaje del usuario + respuesta
    de la IA) se persiste como entries tipo 'chat_aigent' del caso, con
    meta.aigent_id y meta.purpose para distinguir progresos clínicos de chat
    general dentro del caso.
    """
    if request.messages[-1].role != "user":
        raise HTTPException(
            status_code=422, detail="Last message must have role='user'."
        )
    deduct_token(authorization, db, amount=0.10, require_auth=True)
    user_id_for_logs = _extract_user_id_av(authorization)
    try:
        result = chat(request)
        background_tasks.add_task(
            log_usage,
            user_id=user_id_for_logs,
            endpoint="/avatar/chat",
            model=get_settings().avatar_model,
            input_tokens=getattr(result, "input_tokens", None),
            output_tokens=getattr(result, "output_tokens", None),
            tokens_charged=0.10,
            success="ok",
            notes=f"avatar={request.avatar_id}",
        )
        # Persistencia opcional al caso (no rompe respuesta si falla)
        if case_id:
            user = get_user_from_authorization(authorization, db)
            user_msg = (request.messages[-1].content if request.messages else "") or ""
            base_meta = {
                "aigent_id": getattr(request, "avatar_id", None),
                "purpose": purpose or "general_chat",
            }
            # Persistir mensaje del usuario (sin coste tokens — input usuario)
            persist_to_case_safely(
                case_id, user, db,
                entry_type="chat_aigent",
                content=user_msg,
                meta={**base_meta, "role": "user"},
            )
            # Persistir respuesta del Aigent (con cobro 0.10 tokens)
            persist_to_case_safely(
                case_id, user, db,
                entry_type="chat_aigent",
                content=getattr(result, "reply", None) or getattr(result, "content", None) or "",
                meta={**base_meta, "role": "assistant"},
                ai_model=get_settings().avatar_model,
                input_tokens=getattr(result, "input_tokens", None),
                output_tokens=getattr(result, "output_tokens", None),
                tokens_charged=0.10,
            )
        return result
    except Exception as e:
        # Refund: el usuario no paga por errores de IA/red.
        refund_token(authorization, db, amount=0.10)
        background_tasks.add_task(
            log_usage,
            user_id=user_id_for_logs,
            endpoint="/avatar/chat",
            model=get_settings().avatar_model,
            tokens_charged=0.10,
            success="error",
            notes=f"avatar={request.avatar_id} | {str(e)[:150]}",
        )
        raise_http_for_anthropic(e)
