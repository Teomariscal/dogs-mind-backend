"""
Vía cognitivista italiana — pasada 2 (re-expresión) con gate de lista negra.

Puertas (todas deben cumplirse, si no devuelve None = "no aplica"):
  1. flag `IT_COGNITIVE` encendido
  2. lang == 'it'
  3. account_type == 'professional'
  4. stance == 'cognitive'  (el botón que elige el veterinario)

Si aplica:
  • recupera contexto de la RAG B (corpus cognitivista: glosario + obra eje + casos)
  • reescribe el texto ABA congelado (pasada 1) al marco cognitivo
  • ESCANEA la salida contra la lista negra; si sobrevive un término conductual,
    regenera. Agotados los reintentos → lanza CognitiveReexpressionError.

DECISIÓN DEL FOUNDER: si la pasada 2 falla, NUNCA se degrada a la salida conductual
(el veterinario italiano no puede ver ABA ni por accidente). El endpoint captura la
excepción → error + refund del token.
"""

from typing import Optional

from app.config import get_settings
from app.core.anthropic_client import create_message_resilient
from app.core.prompts.italian_cognitive import ITALIAN_COGNITIVE_SYSTEM_PROMPT
from app.services.cognitive_blacklist import find_blacklisted
from app.services.rag import retrieve_cognitive, build_rag_context_block

MAX_ATTEMPTS = 3


class CognitiveReexpressionError(Exception):
    """La re-expresión cognitiva no pudo producir un texto limpio de léxico ABA."""


def cognitive_path_applies(
    *,
    lang: Optional[str],
    account_type: Optional[str],
    stance: Optional[str],
) -> bool:
    """Las cuatro puertas. Falla cerrado: ante la duda, NO se aplica la vía cognitiva."""
    settings = get_settings()
    if not getattr(settings, "it_cognitive_enabled", False):
        return False
    if (lang or "").strip().lower() != "it":
        return False
    if (account_type or "").strip().lower() != "professional":
        return False
    if (stance or "").strip().lower() != "cognitive":
        return False
    return True


def apply_cognitive_reexpression(
    text: str,
    *,
    query: str = "",
    kind: str = "analysis",
) -> str:
    """
    Reescribe `text` (ABA congelado) al marco cognitivo usando la RAG B.
    Lanza CognitiveReexpressionError si no consigue una salida limpia.
    El caller ya ha comprobado las puertas con cognitive_path_applies().
    """
    settings = get_settings()

    if not text or not text.strip():
        raise CognitiveReexpressionError("Empty source text for cognitive re-expression.")

    # Contexto del corpus cognitivista (eje = obra "Vivir con el perro"; complemento =
    # glosario, casos reali, papers). Si la RAG B está vacía o cae, seguimos: el prompt
    # ya lleva el glosario esencial embebido.
    try:
        chunks = retrieve_cognitive(query or text[:1500])
        corpus_block = build_rag_context_block(chunks)
    except Exception:
        corpus_block = ""

    max_tokens = 8000 if kind == "intervention" else 6000

    base_user_message = (
        (f"{corpus_block}\n\n" if corpus_block else "")
        + "TESTO CLINICO DA RIESPRIMERE nel quadro cognitivo-zooantropologico "
        "(mantieni struttura, fasi, criteri numerici e eseguibilità; cambia il lessico, "
        "non le decisioni cliniche):\n"
        '"""\n'
        f"{text}\n"
        '"""'
    )

    last_hits: list[str] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        user_message = base_user_message
        if last_hits:
            user_message += (
                "\n\nATTENZIONE — il tuo tentativo precedente conteneva termini VIETATI: "
                + ", ".join(last_hits)
                + ". Riscrivi da capo eliminandoli completamente, senza perdere "
                "nessun criterio numerico, nessuna fase e nessuna istruzione eseguibile."
            )

        try:
            response = create_message_resilient(
                model=settings.clinical_model,
                fallback_model=settings.clinical_fallback_model,
                max_tokens=max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": ITALIAN_COGNITIVE_SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_message}],
            )
        except Exception as e:
            if attempt == MAX_ATTEMPTS:
                raise CognitiveReexpressionError(f"LLM call failed: {e}") from e
            continue

        if getattr(response, "stop_reason", None) == "max_tokens":
            last_hits = []
            if attempt == MAX_ATTEMPTS:
                raise CognitiveReexpressionError("Cognitive re-expression truncated.")
            continue

        out = ""
        for block in response.content:
            if block.type == "text":
                out += block.text
        out = out.strip()

        if not out:
            if attempt == MAX_ATTEMPTS:
                raise CognitiveReexpressionError("Cognitive re-expression returned empty.")
            continue

        hits = find_blacklisted(out)
        if not hits:
            return out
        last_hits = hits

    raise CognitiveReexpressionError(
        "Cognitive re-expression still contained forbidden behavioral terms after "
        f"{MAX_ATTEMPTS} attempts: {', '.join(last_hits)}"
    )
