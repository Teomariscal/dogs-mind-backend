from fastapi import APIRouter, HTTPException
from app.models.avatar import AvatarChatRequest, AvatarChatResponse
from app.services.avatar_ai import chat

router = APIRouter(prefix="/avatar", tags=["avatar"])


@router.post("/chat", response_model=AvatarChatResponse)
def avatar_chat(request: AvatarChatRequest):
    """
    Send a message to the Teo avatar (Claude Haiku 4.5).

    The client must send the full conversation history on every request.
    The last message must have role=user.
    No RAG — the avatar only uses the conversation context.
    """
    if request.messages[-1].role != "user":
        raise HTTPException(
            status_code=422, detail="Last message must have role='user'."
        )
    try:
        return chat(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
