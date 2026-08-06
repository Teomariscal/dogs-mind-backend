"""
Avatar AI service — Claude Haiku 4.5.

Each avatar has its own personality system prompt.
The client maintains and sends the full conversation history on each request.

2026-05-10 — Web search tool habilitado para los Aigents lifestyle (Mario,
Ale, Niaz, Borja, Leo, Katja). Cecilia e Iris quedan EXCLUIDAS porque
sus boundaries ya derivan al flujo clínico (Cecilia) o al apoyo emocional
sin datos externos (Iris). Coste: ~$10/1k searches en Anthropic; max 3
por turno acota el riesgo.
"""

import random

from app.config import get_settings
from app.core.anthropic_client import get_anthropic_client
from app.core.prompts.avatar import AVATAR_PROMPTS, AVATAR_SYSTEM_PROMPT
from app.models.avatar import AvatarChatRequest, AvatarChatResponse


# Aigents que NO deben usar web_search:
#   • cecilia: tiene RAG clínica + boundary clínico, no debe redirigir a web.
#   • iris:    rol de apoyo emocional, no datos externos.
_AIGENTS_WITHOUT_WEB_SEARCH = {"cecilia", "iris"}


def chat(request: AvatarChatRequest) -> AvatarChatResponse:
    settings = get_settings()
    client = get_anthropic_client()

    # Select the system prompt for the requested avatar
    system_prompt = AVATAR_PROMPTS.get(request.avatar_id, AVATAR_SYSTEM_PROMPT)
    from app.services.tea_pilot import apply_tea_override
    system_prompt = apply_tea_override(system_prompt, *[getattr(m, 'content', '') for m in request.messages])

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

    # ── Easter egg Niaz TDAH (programa de Razón Variable VR-4) ────────────
    # En vez de un FR fijo (cada N exacto), aplicamos un VR-4: probabilidad
    # independiente 1/4 en cada pregunta del usuario. Da una media de un
    # despiste cada 4 preguntas pero con variabilidad real — a veces toca
    # 2 cerca, a veces pasan 6 sin disparar. Más natural y menos predecible.
    # Saltamos la primera pregunta para que el saludo inicial sea limpio.
    if request.avatar_id == "niaz":
        user_msg_count = sum(1 for m in request.messages if m.role == "user")
        if user_msg_count >= 2 and random.random() < 0.25:
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

    # web_search tool habilitado para Aigents lifestyle. Server-managed por
    # Anthropic (no necesitamos manejar los turnos manualmente — el SDK
    # devuelve text blocks finales con el resumen). Margen de tokens más
    # alto para dar espacio al modelo a resumir 1-3 resultados con detalle.
    use_web_search = request.avatar_id not in _AIGENTS_WITHOUT_WEB_SEARCH

    # Modelo por avatar: Cecilia (ABA pura) va en Sonnet para ser inquebrantable;
    # el resto en Haiku. Fallback al modelo global si el id no está mapeado.
    per_id_models = getattr(settings, "avatar_models_per_id", {}) or {}
    avatar_model = per_id_models.get(request.avatar_id, settings.avatar_model)

    create_kwargs = {
        "model": avatar_model,
        # 350 para Aigents sin web_search (calibración estricta del prompt).
        # 500 para Aigents con web_search (margen para listar resultados
        # concretos con nombre + ciudad/precio sin truncar).
        # Subido de 350/500 (2026-08-06): 350 es un tope duro para texto
            # conversacional y en la rama de búsqueda web los bloques de
            # herramienta consumen del mismo presupuesto, dejando la respuesta
            # final cortada a media línea.
            "max_tokens": 1200 if use_web_search else 800,
        "system": system_prompt,
        "messages": messages,
    }
    if use_web_search:
        create_kwargs["tools"] = [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 3,
        }]

    response = client.messages.create(**create_kwargs)

    reply_text = ""
    for block in response.content:
        if block.type == "text":
            reply_text += block.text

    return AvatarChatResponse(
        reply=reply_text,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
