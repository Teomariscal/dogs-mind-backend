"""
Avatar AI service — Claude Haiku 4.5.

Each avatar has its own personality system prompt.
The client maintains and sends the full conversation history on each request.
"""

from app.config import get_settings
from app.core.anthropic_client import get_anthropic_client
from app.core.prompts.avatar import AVATAR_PROMPTS, AVATAR_SYSTEM_PROMPT
from app.models.avatar import AvatarChatRequest, AvatarChatResponse


def chat(request: AvatarChatRequest) -> AvatarChatResponse:
    settings = get_settings()
    client = get_anthropic_client()

    # Select the system prompt for the requested avatar
    system_prompt = AVATAR_PROMPTS.get(request.avatar_id, AVATAR_SYSTEM_PROMPT)

    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    response = client.messages.create(
        model=settings.avatar_model,
        max_tokens=600,
        system=system_prompt,
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
