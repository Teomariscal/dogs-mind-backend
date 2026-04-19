from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Depends
from sqlalchemy.orm import Session

from app.models.avatar import AvatarChatRequest, AvatarChatResponse
from app.services.avatar_ai import chat
from app.database import get_db
from app.core.token_utils import deduct_token

router = APIRouter(prefix="/avatar", tags=["avatar"])


@router.post("/chat", response_model=AvatarChatResponse)
def avatar_chat(
    request: AvatarChatRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Send a message to the Teo avatar (Claude Haiku 4.5).
    Costs 0.10 tokens per message. Requires login.
    Admins and collaborators are exempt.
    """
    if request.messages[-1].role != "user":
        raise HTTPException(
            status_code=422, detail="Last message must have role='user'."
        )
    deduct_token(authorization, db, amount=0.10, require_auth=True)
    try:
        return chat(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
