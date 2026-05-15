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
from app.core.anthropic_client import get_anthropic_client
from app.core.prompts.intervention import INTERVENTION_SYSTEM_PROMPT
from app.models.intervention import InterventionRequest, InterventionResponse


def run_intervention_plan(request: InterventionRequest) -> InterventionResponse:
    """
    Generate a LIMA-based behavioral intervention plan.

    Receives the full FBA text + anamnesis and produces a structured
    3-phase intervention plan via Claude Sonnet 4.6.
    """
    settings = get_settings()
    client = get_anthropic_client()

    a = request.anamnesis

    # Build a concise anamnesis summary for the user message
    anamnesis_lines = [
        f"Dog: {a.dog_name}, {a.breed}, {a.dog_age}",
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

    response = client.messages.create(
        model=settings.clinical_model,
        max_tokens=3000,
        system=[
            {
                "type": "text",
                "text": INTERVENTION_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )

    plan_text = ""
    for block in response.content:
        if block.type == "text":
            plan_text += block.text

    cache_hit = (response.usage.cache_read_input_tokens or 0) > 0

    return InterventionResponse(
        plan=plan_text,
        cache_hit=cache_hit,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
