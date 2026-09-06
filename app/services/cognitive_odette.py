"""
Motor del informe cognitivista de Odette. Dos pasadas y una puerta de una vía.

  PASADA 1 — ANÁLISIS ABA, OCULTO. El prompt clínico de siempre con la RAG A.
  Es el ARNÉS: de aquí salen los criterios numéricos, las fases, su orden, las
  salvaguardas LIMA y las prioridades clínicas. Sin él la prosa cognitivista se
  queda sin suelo medible. Nunca se enseña.

  PASADA 2 — INFORME DE ODETTE. Coge ese análisis ya centrado, lo lleva al
  corpus cognitivista (RAG B) y lo redacta con sus ocho secciones. Puede cambiar
  el marco, el énfasis y la extensión; NO puede cambiar una cifra, una fase ni
  el orden, ni salir clínicamente más débil.

  LA PUERTA, DE UNA SOLA VÍA (founder, 6-sep-2026):
   · hacia dentro — que no entre nada ABA en lo que ve el veterinario: se pide
     en el prompt y ADEMÁS se audita la salida con la lista negra. Pedirlo no
     basta.
   · hacia fuera — que no salga nada cognitivista a lo conductual. Es lo más
     importante, y no se vigila aquí: `scripts/sin-fugas.py` y `sin-fugas-vivo.js`.

Si la vía cognitivista no consigue una salida utilizable, NUNCA se degrada a la
conductual (founder, 2026-07-08): antes un error y la devolución del cobro.
"""
import logging
import re
from typing import Optional

from app.config import get_settings
from app.core.anthropic_client import create_message_resilient
from app.core.prompts.clinical import CLINICAL_SYSTEM_PROMPT
from app.core.prompts.cognitive_odette import PASADA_1_AVISO, PASADA_2_INFORME
from app.models.anamnesis_cognitiva import AnamnesiCognitivaInput
from app.services.cognitive_blacklist import find_blacklisted
from app.services.italian_cognitive import (
    CognitiveReexpressionError,
    cognitive_path_applies,
    # Privada a propósito compartida: quitar el aparato de fuentes es una
    # transformación de SEGURIDAD — los títulos del corpus conductual delatan el
    # motor ABA igual que un término prohibido (caso real, PDF de Achille,
    # 2026-07-09). Mejor un import feo que dos copias que se separen.
    _strip_source_apparatus,
)
from app.services.rag import build_rag_context_block, retrieve, retrieve_cognitive

_log = logging.getLogger("cognitive_odette")

INTENTOS = 3


# ── El cuestionario, hecho texto ─────────────────────────────────────────
_ETIQUETAS = [
    ("specie_razza",            "Specie e razza"),
    ("nome",                    "Nome"),
    ("eta",                     "Età"),
    ("sterilizzato",            "Castrato/sterilizzato e a che età"),
    ("motivo_visita",           "Motivo della visita"),
    ("comportamenti_notati",    "Comportamenti notati"),
    ("nucleo_familiare",        "Nucleo familiare, altri animali e bambini"),
    ("motivo_adozione",         "Motivo dell'adozione"),
    ("vita_prima_adozione",     "Vita prima dell'adozione"),
    ("alimentazione",           "Alimentazione"),
    ("viaggi",                  "Come affronta i viaggi"),
    ("separazioni",             "Come affronta le separazioni"),
    ("veterinario",             "Come affronta il veterinario"),
    ("luoghi_pubblici",         "Comportamento in luoghi pubblici"),
    ("relazioni_altri_animali", "Relazioni con altri animali"),
    ("traumi",                  "Traumi subiti"),
    ("patologie",               "Patologie e sintomi"),
    ("farmaci",                 "Farmaci"),
    ("ambienti",                "Ambienti a disposizione"),
    ("emozioni_prevalenti",     "Emozioni prevalenti secondo il tutore"),
    ("cosa_gli_piace_fare",     "Cosa gli piace fare"),
    ("esercizi_che_sa",         "Esercizi che sa fare"),
    ("cosa_ti_piace_fare",      "Cosa piace fare al tutore con lui"),
    ("giochi",                  "Giochi"),
    ("attivita_fisica",         "Attività fisica"),
    ("giornata_tipo",           "Giornata tipo, con orari"),
    ("altri_professionisti",    "Altri professionisti consultati"),
    ("cosa_vuoi_imparare",      "Cosa vuole imparare il tutore"),
    ("ha_aggredito",            "Ha aggredito qualcuno / segnalazioni ASL"),
]


def _a_texto(a: AnamnesiCognitivaInput) -> str:
    filas = []
    for campo, etiqueta in _ETIQUETAS:
        v = getattr(a, campo, None)
        if v is None or v == "" or v == []:
            continue
        if isinstance(v, list):
            v = ", ".join(str(x) for x in v)
        v = getattr(v, "value", v)          # Enum → su valor
        filas.append(f"{etiqueta}: {v}")
    return "\n".join(filas)


def _texto_de(response) -> str:
    out = ""
    for bloque in response.content:
        if bloque.type == "text":
            out += bloque.text
    return out.strip()


def _es_cucciolo(eta: str) -> bool:
    """Cucciolo → PROGETTO EDUCATIVO; adulto → PERCORSO RIEDUCATIVO."""
    e = (eta or "").lower()
    m = re.search(r"(\d+)\s*ann", e)
    if m:
        return int(m.group(1)) < 1
    if "ann" in e:                      # "un anno", sin cifra
        return False
    return "mes" in e or "settiman" in e or "cucciol" in e


# ═══════════════════════════════════════════════════════════════════════
def _pasada_1_aba(texto_anamnesi: str) -> str:
    """El arnés: análisis clínico ABA con la RAG A. Nunca se enseña."""
    settings = get_settings()
    try:
        rag_a = build_rag_context_block(retrieve(texto_anamnesi[:1500]))
    except Exception:
        rag_a = ""

    mensaje = (
        PASADA_1_AVISO + "\n\n"
        + (f"{rag_a}\n\n" if rag_a else "")
        + "QUESTIONARIO ANAMNESTICO:\n\"\"\"\n" + texto_anamnesi + "\n\"\"\"\n\n"
        + "Produci l'analisi clinica del caso seguendo il formato definito nelle "
          "tue istruzioni. Scrivi in italiano."
    )
    r = create_message_resilient(
        model=settings.clinical_model,
        fallback_model=settings.clinical_fallback_model,
        max_tokens=6000,
        system=[{"type": "text", "text": CLINICAL_SYSTEM_PROMPT,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": mensaje}],
    )
    salida = _texto_de(r)
    if not salida:
        raise CognitiveReexpressionError("El análisis ABA oculto no devolvió nada.")
    return salida


def redactar_relazione(
    anamnesi: AnamnesiCognitivaInput,
    *,
    account_type: Optional[str],
) -> tuple[str, str, str]:
    """Devuelve (relazione, tipo, analisis_oculto). Lanza si no aplica o no sale limpio."""
    settings = get_settings()

    # ── LA PUERTA. Antes que nada y sin excepciones. ────────────────────
    if not cognitive_path_applies(
        lang=anamnesi.lang,
        account_type=account_type,
        stance=anamnesi.stance,
    ):
        raise PermissionError("La vía cognitivista no aplica a esta petición.")

    texto_anamnesi = _a_texto(anamnesi)
    if not texto_anamnesi.strip():
        raise CognitiveReexpressionError("Anamnesi vacía.")

    # ── PASADA 1 — el arnés ABA, oculto ─────────────────────────────────
    analisis = _pasada_1_aba(texto_anamnesi)

    # ── Corpus cognitivista (RAG B). Si cae, se sigue: el prompt lleva el
    #    glosario esencial embebido.
    try:
        corpus = build_rag_context_block(
            retrieve_cognitive(anamnesi.motivo_visita or texto_anamnesi[:1500]))
    except Exception:
        corpus = ""

    tipo = "progetto_educativo" if _es_cucciolo(anamnesi.eta) else "percorso_rieducativo"
    pista = ("Si tratta di un CUCCIOLO: il titolo è PROGETTO EDUCATIVO."
             if tipo == "progetto_educativo" else
             "Si tratta di un ADULTO: il titolo è PERCORSO RIEDUCATIVO.")

    base = (
        (f"{corpus}\n\n" if corpus else "")
        + pista + "\n\n"
        + "ANALISI CLINICA DI PARTENZA (non mostrarla, non citarla, non "
          "riprodurne il lessico — è la base clinica da rispettare):\n"
        + "\"\"\"\n" + analisis + "\n\"\"\"\n\n"
        + "QUESTIONARIO ANAMNESTICO DEL TUTORE (per i dati anagrafici, la "
          "giornata tipo, le emozioni riferite e cosa vuole imparare):\n"
        + "\"\"\"\n" + texto_anamnesi + "\n\"\"\""
    )

    # ── PASADA 2 — el informe. Se AUDITA, no basta con pedirlo. ─────────
    mejor: Optional[str] = None
    mejor_restos: list = []
    restos: list = []

    for _ in range(INTENTOS):
        mensaje = base
        if restos:
            mensaje += ("\n\nATTENZIONE — il tentativo precedente conteneva termini "
                        "VIETATI: " + ", ".join(restos) + ". Riscrivi da capo "
                        "eliminandoli, senza perdere nessun criterio numerico né "
                        "nessuna istruzione eseguibile.")
        try:
            r2 = create_message_resilient(
                model=settings.clinical_model,
                fallback_model=settings.clinical_fallback_model,
                max_tokens=8000,
                system=[{"type": "text", "text": PASADA_2_INFORME,
                         "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": mensaje}],
            )
        except Exception:
            continue

        if getattr(r2, "stop_reason", None) == "max_tokens":
            continue

        salida = _strip_source_apparatus(_texto_de(r2))
        if not salida:
            continue

        restos = find_blacklisted(salida)
        if not restos:
            return salida, tipo, analisis

        if mejor is None or len(restos) < len(mejor_restos):
            mejor, mejor_restos = salida, restos

    if mejor is not None:
        _log.warning("Informe cognitivista entregado con restos conductuales: %s",
                     ", ".join(mejor_restos))
        return mejor, tipo, analisis

    raise CognitiveReexpressionError(
        f"No se obtuvo un informe utilizable tras {INTENTOS} intentos.")
