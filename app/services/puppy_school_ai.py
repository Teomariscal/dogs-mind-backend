"""
Servicio de "Escuela Cachorros" — plan de crianza y educación temprana.

Mismo patrón que training_consult_ai.py: RAG contra la clínica compartida →
mensaje de usuario con la anamnesis del cachorro → Sonnet con prompt cacheado.

Lo que lo diferencia: la query RAG y el prompt están anclados al tramo
evolutivo (periodo sensible, destete, vacunación incompleta, inhibición de la
mordida, higiene), no a un problema instaurado ni a una habilidad concreta.

Spec: memoria project_dogs_mind_puppy_school.md.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from app.config import get_settings
from app.core.anthropic_client import get_anthropic_client, create_message_resilient
from app.core.prompts.puppy_school import (
    PUPPY_SCHOOL_PROMPT_ES,
    PUPPY_SCHOOL_PROMPT_EN,
    PUPPY_SCHOOL_PROMPT_IT,
    PUPPY_ABC_PROMPT_ES,
    PUPPY_ABC_PROMPT_EN,
    PUPPY_ABC_PROMPT_IT,
)
from app.models.anamnesis import RetrievedChunk
from app.services.rag import retrieve, build_rag_context_block

logger = logging.getLogger(__name__)

# El plan cubre varias semanas y ocho bloques: necesita más aire que el de
# entrenamiento (2000). Aun así, el prompt pide concreción, no relleno.
MAX_OUTPUT_TOKENS = 3200
TEMPERATURE = 0.4
RAG_TOP_K = 5


@dataclass
class PuppySchoolResult:
    plan_markdown: str
    sources: list[RetrievedChunk] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_hit: bool = False


def _semanas(edad_semanas: int) -> str:
    """Etiqueta del tramo evolutivo, para meterla explícita en el input."""
    if edad_semanas < 12:
        return "ventana de socializacion ABIERTA (prioridad maxima)"
    if edad_semanas < 16:
        return "ventana de socializacion CERRANDOSE (urgencia alta)"
    return "ventana de socializacion YA CERRADA (exposicion gradual y contracondicionamiento)"


def _build_rag_query(*, breed: str, edad_semanas: int, area: str,
                     objetivo: str, problema: str, lang: str) -> str:
    """Query densa para Qdrant: tramo evolutivo + área elegida + problema si lo hay."""
    base_es = [
        "Desarrollo del cachorro, periodo sensible de socializacion, aprendizaje temprano.",
        "Habituacion, desensibilizacion, contracondicionamiento, reforzamiento positivo, LIMA.",
        f"Edad {edad_semanas} semanas. Tipologia racial: {breed}.",
        f"Area de trabajo: {area}.",
    ]
    base_en = [
        "Puppy development, sensitive socialisation period, early learning.",
        "Habituation, desensitisation, counterconditioning, positive reinforcement, LIMA.",
        f"Age {edad_semanas} weeks. Breed type: {breed}.",
        f"Working area: {area}.",
    ]
    base_it = [
        "Sviluppo del cucciolo, periodo sensibile di socializzazione, apprendimento precoce.",
        "Abituazione, desensibilizzazione, controcondizionamento, rinforzo positivo, LIMA.",
        f"Eta {edad_semanas} settimane. Tipologia: {breed}.",
        f"Area di lavoro: {area}.",
    ]
    partes = {"en": base_en, "it": base_it}.get(lang, base_es)
    if objetivo == "problema" and problema:
        partes.append(
            {"en": f"Reported problem behaviour: {problema}. Functional analysis, ABC.",
             "it": f"Comportamento problema riferito: {problema}. Analisi funzionale, ABC."}
            .get(lang, f"Conducta problema reportada: {problema}. Analisis funcional, ABC.")
        )
    return " ".join(partes)


def _build_input_block(d: dict, lang: str) -> str:
    """Anamnesis tal y como la definió el founder, en texto legible."""
    problema = (d.get("conducta_problema") or "").strip()
    if lang == "en":
        bloque = ("<puppy_intake>\n"
                  "PUPPY:\n"
                  f"  - Name: {d['dog_name']}\n"
                  f"  - Date of birth: {d['birth_date']}\n"
                  f"  - Age today: {d['edad_texto']}\n"
                  f"  - Breed type: {d['breed']}\n"
                  f"  - Origin: {d['origen']}\n"
                  f"  - Left mother and litter: {d['destete_texto']}\n"
                  f"  - Weeks living at home: {d['semanas_en_casa']}\n"
                  "\nHOME AND ROUTINE:\n"
                  f"  - Lives with other dogs: {d['otros_perros_texto']}\n"
                  f"  - Walks per day: {d['paseos_dia']}\n"
                  f"  - Sleeps: {d['donde_duerme_texto']}\n"
                  f"  - Hours alone per day: {d['horas_solo']}\n"
                  f"  - Children at home: {d['ninos_texto']}\n"
                  f"  - Vaccination: {d['vacunacion_texto']}\n"
                  "\nWHAT THE OWNER WANTS:\n"
                  f"  - Purpose: {d['objetivo_texto']}\n"
                  f"  - Area to start with: {d['area_texto']}\n")
        if problema:
            bloque += f"  - Problem behaviour, in the owner's words: {problema}\n"
        return bloque + "</puppy_intake>"
    if lang == "it":
        bloque = ("<puppy_intake>\n"
                  "CUCCIOLO:\n"
                  f"  - Nome: {d['dog_name']}\n"
                  f"  - Data di nascita: {d['birth_date']}\n"
                  f"  - Eta oggi: {d['edad_texto']}\n"
                  f"  - Tipologia: {d['breed']}\n"
                  f"  - Provenienza: {d['origen']}\n"
                  f"  - Separazione da madre e cucciolata: {d['destete_texto']}\n"
                  f"  - Settimane in casa: {d['semanas_en_casa']}\n"
                  "\nCASA E ROUTINE:\n"
                  f"  - Convive con altri cani: {d['otros_perros_texto']}\n"
                  f"  - Passeggiate al giorno: {d['paseos_dia']}\n"
                  f"  - Dorme: {d['donde_duerme_texto']}\n"
                  f"  - Ore da solo al giorno: {d['horas_solo']}\n"
                  f"  - Bambini in casa: {d['ninos_texto']}\n"
                  f"  - Vaccinazione: {d['vacunacion_texto']}\n"
                  "\nCOSA VUOLE IL PROPRIETARIO:\n"
                  f"  - Scopo: {d['objetivo_texto']}\n"
                  f"  - Area da cui iniziare: {d['area_texto']}\n")
        if problema:
            bloque += f"  - Comportamento problema, parole del proprietario: {problema}\n"
        return bloque + "</puppy_intake>"
    bloque = ("<puppy_intake>\n"
              "CACHORRO:\n"
              f"  - Nombre: {d['dog_name']}\n"
              f"  - Fecha de nacimiento: {d['birth_date']}\n"
              f"  - Edad hoy: {d['edad_texto']}\n"
              f"  - Tipologia racial: {d['breed']}\n"
              f"  - Procedencia: {d['origen']}\n"
              f"  - Separación de la madre y la camada: {d['destete_texto']}\n"
              f"  - Semanas que lleva en casa: {d['semanas_en_casa']}\n"
              "\nCASA Y RUTINA:\n"
              f"  - Convive con otros perros: {d['otros_perros_texto']}\n"
              f"  - Paseos al dia: {d['paseos_dia']}\n"
              f"  - Duerme: {d['donde_duerme_texto']}\n"
              f"  - Horas que pasa solo al día: {d['horas_solo']}\n"
              f"  - Niños en casa: {d['ninos_texto']}\n"
              f"  - Vacunacion: {d['vacunacion_texto']}\n"
              "\nQUE BUSCA EL TUTOR:\n"
              f"  - Objetivo: {d['objetivo_texto']}\n"
              f"  - Area por la que empezar: {d['area_texto']}\n")
    if problema:
        bloque += f"  - Conducta problema, en palabras del tutor: {problema}\n"
    return bloque + "</puppy_intake>"


def generate_puppy_plan(*, datos: dict, lang: str = "es") -> PuppySchoolResult:
    """
    Devuelve el plan en markdown. Lanza si Anthropic falla — el router hace
    el refund de créditos.
    """
    lang_norm = (lang or "es").lower()
    if lang_norm not in ("es", "en", "it"):
        lang_norm = "es"

    # Dos salidas dentro del MISMO formulario de cachorros (founder 2026-08-02):
    #   · "prevenir"  → plan de crianza y educación temprana.
    #   · "problema"  → análisis funcional leído con lente evolutiva.
    # Nunca se mezcla con el flujo de conducta de adultos: otra anamnesis,
    # otro prompt, otra ruta.
    es_problema = (datos.get("objetivo") == "problema")
    if es_problema:
        system_prompt = {"en": PUPPY_ABC_PROMPT_EN,
                         "it": PUPPY_ABC_PROMPT_IT}.get(lang_norm, PUPPY_ABC_PROMPT_ES)
    else:
        system_prompt = {"en": PUPPY_SCHOOL_PROMPT_EN,
                         "it": PUPPY_SCHOOL_PROMPT_IT}.get(lang_norm, PUPPY_SCHOOL_PROMPT_ES)

    query = _build_rag_query(
        breed=datos["breed"], edad_semanas=int(datos["edad_semanas"]),
        area=datos["area_texto"], objetivo=datos["objetivo"],
        problema=datos.get("conducta_problema", ""), lang=lang_norm,
    )
    chunks: list[RetrievedChunk] = retrieve(query, top_k=RAG_TOP_K)
    rag_block = build_rag_context_block(chunks)
    input_block = _build_input_block(datos, lang_norm)

    if lang_norm == "en":
        idioma = ("LANGUAGE: write the ENTIRE response in ENGLISH. Headings, bullets "
                  "and inline text in English only.")
        cierre = ("Use the retrieved literature above to ground your answer (do NOT show "
                  "[n] citations). Follow the structure in your system prompt exactly. "
                  "Plain, warm, concrete voice for a puppy owner." +
                  (" Decide first whether this is normal ontogeny or a real problem."
                   if es_problema else ""))
    elif lang_norm == "it":
        idioma = ("LINGUA: scrivi TUTTA la risposta in ITALIANO. Titoli, elenchi e testo "
                  "solo in italiano.")
        cierre = ("Usa la letteratura recuperata sopra per ancorare la risposta (NON mostrare "
                  "citazioni [n]). Segui esattamente la struttura del system prompt. "
                  "Voce piana, calda e concreta per un proprietario." +
                  (" Decidi prima se è ontogenesi normale o un problema reale."
                   if es_problema else ""))
    else:
        idioma = ("IDIOMA: toda la respuesta en ESPAÑOL. Encabezados, viñetas y texto "
                  "en español únicamente.")
        cierre = ("Usa la literatura recuperada arriba para anclar la respuesta (NO muestres "
                  "citas [n] en el texto). Sigue exactamente la estructura de tu system "
                  "prompt. Voz llana, cercana y concreta para un tutor de cachorro." +
                  (" Decide primero si es ontogenia normal o un problema real."
                   if es_problema else ""))

    user_text = f"{idioma}\n\n{rag_block}\n\n{input_block}\n\n{cierre}"

    settings = get_settings()
    get_anthropic_client()
    response = create_message_resilient(
        model=settings.clinical_model,
        fallback_model=settings.clinical_fallback_model,
        max_tokens=MAX_OUTPUT_TOKENS,
        temperature=TEMPERATURE,
        system=[{"type": "text", "text": system_prompt,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_text}],
    )

    raw = ""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            raw += block.text

    return PuppySchoolResult(
        plan_markdown=raw.strip(),
        sources=chunks,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        cache_hit=(response.usage.cache_read_input_tokens or 0) > 0,
    )
