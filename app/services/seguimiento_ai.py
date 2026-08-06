"""
Seguimiento AI service — Claude Sonnet 4.6 + RAG + prompt caching.

Procesa una consulta de seguimiento sobre un caso clínico abierto. El usuario
aporta datos estructurados (días, sesiones, evolución, criterio, descripción,
dificultades, motivo, info extra) y la IA Teo responde con una valoración
clínica que ajusta el plan o sugiere validaciones.

Devuelve también input_tokens / output_tokens para tracking de coste y
reconciliación con la invariante financiera (1,5 tokens cobrados al usuario).
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel

from app.config import get_settings
from app.core.anthropic_client import get_anthropic_client
from app.core.prompts.seguimiento import SEGUIMIENTO_SYSTEM_PROMPT
from app.services.rag import retrieve, build_rag_context_block


# ── Schemas internos ─────────────────────────────────────────────────────────
class SeguimientoFormData(BaseModel):
    """Campos exactos de la plantilla de seguimiento (definidos por producto)."""
    dias_tratamiento: int
    numero_sesiones: int
    ve_evolucion: bool
    criterio_medicion: Optional[str] = None
    descripcion_evolucion: Optional[str] = None
    dificultades: Optional[str] = None
    motivo_consulta_resumido: Optional[str] = None
    informacion_extra: Optional[str] = None


class SeguimientoResult(BaseModel):
    response_markdown: str
    input_tokens: int
    output_tokens: int
    cache_hit: bool


# ── Helpers de prompt ────────────────────────────────────────────────────────
def _build_user_message(case_summary_full: Optional[str], form: SeguimientoFormData, rag_block: str) -> str:
    """
    Compone el mensaje del usuario:
      1. Resumen del caso (summary_full)
      2. Formulario de seguimiento estructurado
      3. Contexto RAG retrieved (puede estar vacío si no hubo retrieval relevante)
    """
    summary = case_summary_full or "(Sin resumen del caso disponible — primer seguimiento o caso migrado.)"

    form_section = (
        "FORMULARIO DE SEGUIMIENTO\n"
        f"- Días de tratamiento: {form.dias_tratamiento}\n"
        f"- Número de sesiones: {form.numero_sesiones}\n"
        f"- ¿Ve evolución?: {'Sí' if form.ve_evolucion else 'No'}\n"
        f"- Criterio de medición: {form.criterio_medicion or '(no indicado)'}\n"
        f"- Descripción de la evolución: {form.descripcion_evolucion or '(no indicada)'}\n"
        f"- Dificultades en la aplicación: {form.dificultades or '(ninguna indicada)'}\n"
        f"- Motivo de esta consulta: {form.motivo_consulta_resumido or '(no indicado)'}\n"
        f"- Información extra: {form.informacion_extra or '(ninguna)'}\n"
    )

    return (
        "RESUMEN DEL CASO\n"
        "==================\n"
        f"{summary}\n\n"
        f"{form_section}\n"
        f"{rag_block}\n\n"
        "Genera la respuesta de seguimiento siguiendo el formato definido en tu prompt."
    )


def _build_rag_query(form: SeguimientoFormData) -> str:
    """Query corta para retrieval, basada en motivo + descripción + criterio."""
    parts = [
        form.motivo_consulta_resumido or "",
        form.descripcion_evolucion or "",
        form.criterio_medicion or "",
        form.dificultades or "",
    ]
    return " ".join(p for p in parts if p).strip()


# ── API pública del servicio ─────────────────────────────────────────────────
def run_seguimiento(case_summary_full: Optional[str], form: SeguimientoFormData) -> SeguimientoResult:
    """
    Ejecuta una consulta de seguimiento clínico y devuelve la respuesta IA.

    No persiste nada — la persistencia (CaseEntry + actualización de summary_full)
    se hace en el endpoint del router para mantener todas las invariantes
    transaccionales en un solo punto.
    """
    settings = get_settings()
    client = get_anthropic_client()

    # 1. RAG retrieval (puede no devolver nada si la query es vacía)
    rag_block = ""
    rag_query = _build_rag_query(form)
    if rag_query:
        try:
            chunks = retrieve(rag_query)
            if chunks:
                rag_block = build_rag_context_block(chunks)
        except Exception:
            # Si Qdrant falla, seguimos sin RAG. La respuesta clínica sigue siendo
            # válida basada en el resumen del caso + el formulario.
            rag_block = ""

    # 2. Construir prompt
    user_message = _build_user_message(case_summary_full, form, rag_block)
    from app.services.tea_pilot import apply_tea_override
    _seg_sys = apply_tea_override(
        SEGUIMIENTO_SYSTEM_PROMPT, case_summary_full,
        getattr(form, 'motivo_consulta_resumido', ''), getattr(form, 'descripcion_evolucion', ''),
        getattr(form, 'dificultades', ''), getattr(form, 'informacion_extra', ''),
    )

    # 3. Llamada Sonnet 4.6 con prompt caching del system prompt
    response = client.messages.create(
        model=settings.clinical_model,
        max_tokens=4000,   # subido de 2000 (2026-08-06): cobra 150 créditos  # invariante: cap de output (ver doc de pricing)
        system=[
            {
                "type": "text",
                "text": _seg_sys,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )

    # 4. Extraer respuesta y métricas
    response_text = "".join(
        block.text for block in response.content if hasattr(block, "text")
    )

    usage = response.usage
    cache_hit = bool(getattr(usage, "cache_read_input_tokens", 0) or 0)

    return SeguimientoResult(
        response_markdown=response_text,
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
        output_tokens=getattr(usage, "output_tokens", 0) or 0,
        cache_hit=cache_hit,
    )
