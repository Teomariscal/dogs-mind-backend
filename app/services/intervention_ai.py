"""
Intervention AI service — Claude Sonnet 4.6 with prompt caching.

Caching strategy:
  • The large intervention system prompt is sent as a system block with
    cache_control = {"type": "ephemeral"} (5-min TTL).
  • The user message contains the functional analysis text + anamnesis summary
    and is NOT cached (it changes per request).

The minimum cacheable prefix for claude-sonnet-4-6 is 2 048 tokens.
"""

from app.config import get_settings
from app.core.anthropic_client import get_anthropic_client, create_message_resilient
from app.core.prompts.intervention import INTERVENTION_SYSTEM_PROMPT
from app.core.prompts.petowner_intervention import PETOWNER_INTERVENTION_SYSTEM_PROMPT
from app.models.intervention import InterventionRequest, InterventionResponse


def run_intervention_plan(request: InterventionRequest, account_type=None) -> InterventionResponse:
    """
    Generate a LIMA-based behavioral intervention plan.

    Receives the full FBA text + anamnesis and produces a structured
    3-phase intervention plan via Claude Sonnet 4.6.
    """
    settings = get_settings()
    client = get_anthropic_client()

    # SALVAGUARDA: SOLO 'particular' → versión Pet Owner accesible. Cualquier otro
    # valor (professional, corporativo, None, vacío) → versión profesional completa.
    is_petowner = (account_type or "").strip().lower() == "particular"
    sys_prompt = PETOWNER_INTERVENTION_SYSTEM_PROMPT if is_petowner else INTERVENTION_SYSTEM_PROMPT

    a = request.anamnesis

    # Build a concise anamnesis summary for the user message
    _sex = "Male" if a.dog_sex == "male" else ("Female" if a.dog_sex == "female" else "Not provided")
    anamnesis_lines = [
        f"Dog: {a.dog_name}, {a.breed}, {a.dog_age}, Sex: {_sex}",
        f"Living: {a.living_environment.value}, {a.household_members} people in household",
    ]
    if a.children_present:
        anamnesis_lines.append("Children present in household.")
    if a.other_dogs:
        anamnesis_lines.append(f"Other dogs: {a.other_dogs_detail or 'yes'}")
    if a.chronic_disease:
        anamnesis_lines.append(f"Chronic disease: {a.chronic_disease_detail or 'yes'}")
    if a.urban_rural:
        anamnesis_lines.append(f"Environment: {a.urban_rural}")
    if a.daily_walks:
        anamnesis_lines.append(f"Daily walks: {a.walks_per_day or '?'}/day")
    if a.involves_aggression:
        anamnesis_lines.append(
            f"AGGRESSION INVOLVED — clinical priority. Threshold: {a.aggression_distance_cm or '?'} cm"
        )
    if a.previous_attempts:
        anamnesis_lines.append(f"Previous attempts: {a.previous_attempts}")

    anamnesis_summary = "\n".join(anamnesis_lines)

    # Bug fix 2026-05-15: respetar el idioma del usuario. Antes el plan
    # salia siempre en español aunque el user estuviera en EN. Mismo patron
    # que clinical_ai.py (linea 114-126).
    lang = (a.lang or "es").lower()
    if lang == "en":
        lang_instruction = (
            "\nCRITICAL LANGUAGE INSTRUCTION: Write the ENTIRE intervention plan "
            "in ENGLISH. All section headers, phases, exercises, instructions, "
            "examples and clinical commentary must be in English. Even though "
            "the system prompt is in English, the model has a tendency to reply "
            "in Spanish — explicitly use English throughout.\n"
        )
    else:
        lang_instruction = (
            "\nCRITICAL LANGUAGE INSTRUCTION: Write the ENTIRE intervention plan "
            "in SPANISH (español neutro/internacional). All section headers, "
            "phases, exercises and clinical commentary in Spanish.\n"
        )

    user_message = f"""Based on the following Functional Behavioral Analysis and case details, generate a complete behavioral intervention plan.{lang_instruction}
═══════════════════════════════════════════════════════════════════════════════
CASE SUMMARY
═══════════════════════════════════════════════════════════════════════════════
{anamnesis_summary}

═══════════════════════════════════════════════════════════════════════════════
FUNCTIONAL BEHAVIORAL ANALYSIS
═══════════════════════════════════════════════════════════════════════════════
{request.analysis_text}

Follow the output format defined in your instructions exactly. Produce the full intervention plan now.
"""

    def _call(extra: str = ""):
        return create_message_resilient(
            model=settings.clinical_model,
            fallback_model=settings.clinical_fallback_model,  # sube a Opus si Sonnet está 529
            max_tokens=8000,  # subido de 3000: planes largos (p.ej. Bardo) se cortaban. Sonnet 4.6 admite salida grande; el coste extra solo aplica si el plan lo usa.
            system=[
                {
                    "type": "text",
                    "text": sys_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_message + extra}],
        )

    response = _call()
    # REGLA DURA: el plan NUNCA debe quedar cortado. Si aun con la holgura tocó el
    # tope de tokens, regeneramos UNA vez pidiendo una versión completa más concisa.
    if getattr(response, "stop_reason", None) == "max_tokens":
        response = _call(
            "\n\nIMPORTANTE: tu respuesta anterior era demasiado larga y se cortó. "
            "Reescribe el plan COMPLETO pero MÁS CONCISO: resume y prioriza lo esencial "
            "para que quepa entero y termine con un cierre adecuado. NUNCA lo cortes."
        )

    plan_text = ""
    for block in response.content:
        if block.type == "text":
            plan_text += block.text

    # Legend Pet Owner (CTA a Profesional) — determinista, solo versión accesible.
    if is_petowner and plan_text.strip():
        _legend = (
            "\n\n———\nVersión Pet Owner · Para un plan más detallado y profundo, "
            "activa la versión Profesional."
            if lang != "en" else
            "\n\n———\nPet Owner version · For a more detailed, in-depth plan, "
            "activate the Professional version."
        )
        plan_text = plan_text.rstrip() + _legend

    cache_hit = (response.usage.cache_read_input_tokens or 0) > 0

    return InterventionResponse(
        plan=plan_text,
        cache_hit=cache_hit,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
