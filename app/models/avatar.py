from typing import Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class AvatarChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(
        ...,
        description="Full conversation history. Last message must be role=user.",
        min_length=1,
    )
    avatar_id: str = Field(
        default="niaz",
        description="Avatar key: niaz | mario | leo | katja | ale | borja",
    )
    lang: Optional[str] = Field(
        default="es",
        description="UI language: 'es' or 'en'. Avatar responds in this language by default.",
    )


class AvatarChatResponse(BaseModel):
    reply: str
    input_tokens: int
    output_tokens: int
