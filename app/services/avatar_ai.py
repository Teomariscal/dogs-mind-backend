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

    # Append a hard language instruction based on the UI language
    lang = (request.lang or "es").lower()
    if lang == "en":
        system_prompt += (
            "\n\nCRITICAL: The user interface is in English. "
            "You MUST respond in English by default. "
            "Only switch to another language if the user explicitly writes in that language."
        )
    else:
        system_prompt += (
            "\n\nIMPORTANTE: La interfaz está en español. "
            "Responde en español por defecto. "
            "Solo cambia de idioma si el usuario escribe explícitamente en otro idioma."
        )

    # ── Easter egg Niaz TDAH ──────────────────────────────────────────────
    # Cada 3 preguntas del usuario, Niaz arranca su respuesta admitiendo
    # un despiste momentáneo (refleja su TDAH de forma divertida, no exagerada).
    if request.avatar_id == "niaz":
        user_msg_count = sum(1 for m in request.messages if m.role == "user")
        if user_msg_count > 0 and user_msg_count % 3 == 0:
            system_prompt += (
                "\n\n[NOTA INTERNA — momento TDAH] "
                "Para ESTA respuesta concreta, empieza con una frase corta y natural admitiendo "
                "que te has despistado un segundo pero estabas escuchando — varía la formulación "
                "(por ejemplo: 'Perdona, me distraje un instante, pero te estaba oyendo…', "
                "'Sorry, me fui un momento — te seguía escuchando, dime…', 'Espera, ¿qué decías? "
                "te estaba escuchando pero se me cruzó otra cosa…'). Después responde a la pregunta con normalidad. "
                "No exageres ni lo conviertas en muletilla — es un detalle de personalidad, no un sketch."
            )

    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    response = client.messages.create(
        model=settings.avatar_model,
        # Bajado de 600 → 350: el prompt del avatar ya pide calibración a la
        # pregunta. 350 tokens ≈ 250 palabras castellanas, suficiente para
        # un párrafo profundo cuando lo amerita; los saludos cortos no
        # rozan el techo. Red de seguridad por si el modelo se desborda.
        max_tokens=350,
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
