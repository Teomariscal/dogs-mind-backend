"""
ANAMNESI COGNITIVA — modelo de la Dott.ssa Odette Abramovich.

SOLO vía italiana cognitivista. No comparte NI UN campo con `AnamnesisInput`:
son dos formularios distintos, y esa es justamente la garantía de aislamiento
más fuerte que hay. Dos esquemas que no se tocan no pueden filtrarse el uno en
el otro (founder, 6-sep-2026: "extrema cautela ... que no haya nunca ninguna
fuga cognitivista a la parte conductual").

La anamnesis conductual es ABC: antecedente, conducta, consecuencia. Ésta es
BIOGRÁFICA: de dónde viene el perro, por qué lo adoptaste, cómo es su día
entero, qué emociones predominan, qué quieres aprender tú. El perro como sujeto
con historia, no como un conjunto de contingencias.

Se dejan fuera cuatro preguntas del cuestionario original de Odette porque son
de su consulta privada y no de la app: datos de facturación y código fiscal,
cómo consiguió su contacto, y el consentimiento de datos (la app ya tiene el
suyo). Ver `SPEC_ANAMNESIS_COGNITIVISTA.md`.
"""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class AttivitaFisica(str, Enum):
    """Pregunta 27 del cuestionario — opción única."""
    passeggiata = "passeggiata"
    giochi_con_altri_animali = "giochi_con_altri_animali"
    giochi_con_te = "giochi_con_te"
    attivita_in_casa = "attivita_in_casa"
    attivita_in_liberta = "attivita_in_liberta"
    sport = "sport"
    altro = "altro"


class AnamnesiCognitivaInput(BaseModel):
    """El cuestionario de Odette, en el orden en que ella lo pregunta."""

    # ── Identificazione ──────────────────────────────────────────────────
    specie_razza: str = Field(..., description="Che animale porti alla visita, specie e razza")
    nome: str = Field(..., description="Come si chiama")
    eta: str = Field(..., description="Che età ha")
    sterilizzato: Optional[str] = Field(None, description="È castrato/sterilizzato e a che età")

    # ── Motivo della visita ──────────────────────────────────────────────
    motivo_visita: str = Field(..., description="Descrivi brevemente il motivo della visita")
    comportamenti_notati: List[str] = Field(
        default_factory=list,
        description="Vocalizzazione eccessiva · Deiezioni in luogo inadeguato · Distruzioni · "
                    "Aggressività · Ansia · Attacchi di panico · Stereotipie · Problemi al "
                    "guinzaglio o in libertà · Impetuosità · Iperattività · Inattività",
    )

    # ── Storia e contesto ────────────────────────────────────────────────
    nucleo_familiare: Optional[str] = Field(None, description="Da chi è composto, altri animali o bambini")
    motivo_adozione: Optional[str] = Field(None, description="Qual è stato il motivo dell'adozione")
    vita_prima_adozione: Optional[str] = Field(None, description="Provenienza, genitori, cosa si sa")
    alimentazione: Optional[str] = Field(None, description="Cosa mangia, quando e come; marche e quantità")

    # ── Come affronta il mondo ───────────────────────────────────────────
    viaggi: Optional[str] = Field(None, description="Come affronta i viaggi")
    separazioni: Optional[str] = Field(None, description="Come affronta le separazioni")
    veterinario: Optional[str] = Field(None, description="Come affronta le visite veterinarie")
    luoghi_pubblici: Optional[str] = Field(None, description="Come si comporta in bar, ristoranti")
    relazioni_altri_animali: Optional[str] = Field(None, description="Come sono le relazioni con altri animali")
    traumi: Optional[str] = Field(None, description="Ha subito traumi")

    # ── Salute ───────────────────────────────────────────────────────────
    patologie: List[str] = Field(
        default_factory=list,
        description="Dermatologici · Gastroenterici · Vie urinarie · Neurologici · Pica · "
                    "Interventi chirurgici · Altro",
    )
    farmaci: Optional[str] = Field(None, description="Che farmaci assume")

    # ── Vita quotidiana ──────────────────────────────────────────────────
    ambienti: List[str] = Field(
        default_factory=list,
        description="Zona giorno · Zona notte · Giardino · Balcone · Altro",
    )
    emozioni_prevalenti: List[str] = Field(
        default_factory=list,
        description="Gioia · Paura · Rabbia · Noia · Nostalgia · Tristezza · Ansia · Altro. "
                    "Una de las tres preguntas con más peso: no tiene equivalente en la "
                    "anamnesis conductual.",
    )
    cosa_gli_piace_fare: Optional[str] = Field(None, description="Cosa piace fare al tuo animale")
    esercizi_che_sa: Optional[str] = Field(None, description="Cosa sa fare in termini di esercizi")
    cosa_ti_piace_fare: Optional[str] = Field(None, description="Cosa piace fare a te con il tuo animale")
    giochi: Optional[str] = Field(None, description="Che giochi sa fare con te o in autonomia")
    attivita_fisica: Optional[AttivitaFisica] = Field(None, description="Che attività fisica svolge")
    giornata_tipo: Optional[str] = Field(
        None,
        description="Descrivi una giornata tipo con tutti i dettagli, orari e tempi. "
                    "Segunda pregunta de más peso: de aquí salen los hechos con hora.",
    )

    # ── Chiusura ─────────────────────────────────────────────────────────
    altri_professionisti: Optional[str] = Field(None, description="Hai già visto altri professionisti")
    cosa_vuoi_imparare: Optional[str] = Field(
        None,
        description="Cosa vuoi imparare nella visita. Tercera pregunta de más peso: "
                    "orienta el proyecto educativo.",
    )
    ha_aggredito: Optional[str] = Field(None, description="Ha mai aggredito qualcuno o è stato segnalato alla ASL")

    # ── Encuadre ─────────────────────────────────────────────────────────
    # Se exigen explícitamente aunque la puerta los vuelva a comprobar: que el
    # cuerpo los traiga hace que un cliente mal configurado falle en la puerta
    # y no a mitad del motor.
    lang: str = Field("it", description="Solo 'it'. La puerta rechaza cualquier otro valor.")
    stance: str = Field("cognitive", description="Solo 'cognitive'. La puerta rechaza cualquier otro valor.")


class AnamnesiCognitivaResponse(BaseModel):
    relazione: str = Field(..., description="La relación clínica completa, con la estructura de Odette")
    tipo: str = Field(..., description="'progetto_educativo' (cucciolo) o 'percorso_rieducativo' (adulto)")
    fatti: Optional[str] = Field(None, description="Los hechos observables de la pasada 1. Interno: no se enseña.")
