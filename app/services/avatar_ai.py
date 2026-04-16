"""
Avatar AI service — Claude Haiku 4.5.

Simple conversational assistant. No RAG. Receives the full conversation
history and returns the next assistant turn. The client is responsible for
maintaining and sending the full history on each request.
"""

from app.config import get_settings
from app.core.anthropic_client import get_anthropic_client
from app.core.prompts.avatar import AVATAR_SYSTEM_PROMPT
from app.models.avatar import AvatarChatRequest, AvatarChatResponse


def chat(request: AvatarChatRequest) -> AvatarChatResponse:
    settings = get_settings()
    client = get_anthropic_client()

    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    response = client.messages.create(
        model=settings.avatar_model,
        max_tokens=1024,
        system=AVATAR_SYSTEM_PROMPT,
        messages=messages,
    )

    reply_text = ""
    for block in response.content:
        if block.type == "text":
            reply_text += block.text

    return AvatarChatResponse(
        reply=reply_text,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
