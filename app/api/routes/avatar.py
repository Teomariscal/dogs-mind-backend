from typing import Optional
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, HTTPException, Header, Depends
from sqlalchemy.orm import Session

from app.models.avatar import AvatarChatRequest, AvatarChatResponse
from app.services.avatar_ai import chat
from app.database import get_db
from app.core.token_utils import deduct_token
from app.core.usage_tracker import log_usage
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
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Send a message to one of the Aigent avatars (Claude Haiku 4.5).
    Costs 0.10 tokens per message. Requires login.
    Admins and collaborators are exempt.
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
        return result
    except Exception as e:
        background_tasks.add_task(
            log_usage,
            user_id=user_id_for_logs,
            endpoint="/avatar/chat",
            model=get_settings().avatar_model,
            tokens_charged=0.10,
            success="error",
            notes=f"avatar={request.avatar_id} | {str(e)[:150]}",
        )
        raise HTTPException(status_code=500, detail=str(e))
