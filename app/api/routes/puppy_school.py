"""
Endpoint de "Escuela Cachorros" — POST /puppy-school.

Recibe la anamnesis del cachorro, cobra créditos, genera el plan de crianza y
educación temprana y lo devuelve en markdown.

Mismo patrón que /training-analysis: rutas, schema y prompt independientes;
comparte cliente Anthropic, sistema de créditos, refund y log de uso. Cero
impacto sobre /analysis ni sobre /training-analysis.

Audiencia: TODOS (es un flujo de tutor, no profesional).

Persistencia: si el cliente pasa case_id, guarda el plan como CaseEntry.
"""

import logging
from datetime import date
from typing import Optional, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.anthropic_error import raise_http_for_anthropic
from app.core.case_persistence import persist_to_case_safely, get_user_from_authorization
from app.core.token_utils import deduct_token, refund_token
from app.core.usage_tracker import log_usage
from app.database import get_db
from app.services.puppy_school_ai import generate_puppy_plan

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/puppy-school", tags=["puppy-school"])

# Precio de salida: 1,5 tokens = 150 créditos, igual que Entrenamiento
# Específico (un solo paso, sin análisis funcional previo). El founder lo
# revisará al alza o a la baja según el uso real, como hizo con el paseo.
# Dos salidas, dos precios:
#   · Plan de crianza y educación → 1,5 tk = 150 créditos (como Entrenamiento).
#   · Análisis funcional del problema → 3 tk = 300 créditos, el mismo precio que
#     el análisis funcional del resto de la app; es el mismo trabajo clínico.
PUPPY_SCHOOL_TOKEN_COST = 1.5
PUPPY_ABC_TOKEN_COST = 3.0


# Áreas de trabajo (lista del founder). El tutor elige UNA para empezar.
AREAS = {
    "esfinteres":        "control de esfínteres, aprender a ser limpio",
    "destrozos":         "evitar destrozos por falta de estimulación",
    "vinculo":           "trabajar un vínculo sano",
    "socializacion":     "socialización y estimulación sensorial",
    "otros_perros":      "conducta con otros perros",
    "veterinario":       "conducta en la clínica veterinaria",
    "educacion_basica":  "educación básica",
    "altas_capacidades": "escuela de altas capacidades: estimular al máximo su potencial genético",
}


# Dónde duerme (founder 2026-08-02: el sitio sí, las horas no — no son medibles).
DONDE_DUERME = {
    "zona_propia":        "en su cama o su zona propia, en una habitación común",
    "habitacion_familia": "en la habitación de alguien de la familia",
    "cama_sofa":          "en la cama o el sofá, con alguien de la familia",
    "transportin":        "en transportín o jaula",
    "fuera":              "fuera de casa: terraza, jardín o garaje",
    "sin_sitio":          "sin sitio fijo, cada noche en un lugar",
}


# Separación de la madre y la camada. En pilares, no en número: el tutor de un
# adoptado casi nunca sabe la semana exacta, y lo que cambia el plan es si fue
# antes de las 7 semanas (riesgo para inhibición de la mordida y autorregulación).
DESTETE = {
    "antes_7":  "se separó ANTES de las 7 semanas (factor de riesgo para la inhibición de la mordida y la autorregulación)",
    "sobre_8":  "se separó alrededor de las 8 semanas",
    "despues_8": "se separó después de las 8 semanas",
    "no_sabe":  "el tutor no sabe a qué edad se separó",
}


class PuppySchoolInput(BaseModel):
    """Anamnesis de Escuela Cachorros — campos definidos por el founder."""
    dog_name: str = Field(..., min_length=1, max_length=80)
    birth_date: date = Field(..., description="Fecha de nacimiento (dato permanente del perro)")
    # La edad NO se recalcula al leer el registro: se guarda la que tenía el día
    # de la consulta (decisión del founder 2026-08-02). El formulario la
    # prerrellena desde la fecha de nacimiento, pero el tutor puede corregirla
    # —útil cuando es adoptado y la fecha es aproximada.
    edad_semanas: int = Field(..., ge=0, le=104,
                              description="Edad EN SEMANAS el día de la consulta")
    breed: str = Field(..., min_length=1, max_length=120, description="Tipología racial")
    origen: Literal["adoptado", "criadero"]
    otros_perros: bool = Field(..., description="¿Convive con otros perros?")
    edades_otros_perros: str = Field("", max_length=200,
                                     description="Solo si convive con otros perros")
    paseos_dia: int = Field(..., ge=0, le=12, description="Paseos al día")
    donde_duerme: Literal["zona_propia", "habitacion_familia", "cama_sofa",
                          "transportin", "fuera", "sin_sitio"]
    destete: Literal["antes_7", "sobre_8", "despues_8", "no_sabe"]
    horas_solo: int = Field(..., ge=0, le=16, description="Horas que pasa solo al día")
    semanas_en_casa: int = Field(..., ge=0, le=104, description="Desde cuándo está en casa")
    ninos: bool = Field(..., description="¿Hay niños en casa?")
    edades_ninos: str = Field("", max_length=200, description="Solo si hay niños")
    objetivo: Literal["prevenir", "problema"] = Field(
        ..., description="Prevenir y educar | Solucionar un problema de conducta")
    area: Literal[
        "esfinteres", "destrozos", "vinculo", "socializacion",
        "otros_perros", "veterinario", "educacion_basica", "altas_capacidades",
    ]
    conducta_problema: str = Field("", max_length=1500,
                                   description="Solo si objetivo = problema")
    vacunacion_completa: bool = Field(
        ..., description="Calendario completo, heptavalente hace más de una semana")
    lang: Literal["es", "en", "it"] = "es"

    @field_validator("conducta_problema")
    @classmethod
    def problema_descrito(cls, v: str, info) -> str:
        if (info.data.get("objetivo") == "problema") and len((v or "").strip()) < 10:
            raise ValueError("Describe la conducta problema con algo más de detalle.")
        return (v or "").strip()

    @field_validator("birth_date")
    @classmethod
    def fecha_coherente(cls, v: date) -> date:
        hoy = date.today()
        if v > hoy:
            raise ValueError("La fecha de nacimiento no puede ser futura.")
        if (hoy - v).days > 730:
            raise ValueError("Escuela Cachorros es para perros de hasta 2 años.")
        return v



class PuppySchoolResponse(BaseModel):
    plan: str
    sources: list = Field(default_factory=list)
    input_tokens: int
    output_tokens: int
    cache_hit: bool = False
    case_type: Literal["puppy"] = "puppy"
    tipo: Literal["educacion", "analisis_funcional"] = "educacion"


def _edad_texto(semanas: int) -> str:
    """Edad legible: en semanas hasta los 6 meses, luego en meses."""
    if semanas < 26:
        return f"{semanas} semanas"
    meses = round(semanas / 4.345)
    return f"{meses} meses ({semanas} semanas)"


@router.post("", response_model=PuppySchoolResponse)
def create_puppy_plan(
    payload: PuppySchoolInput,
    background_tasks: BackgroundTasks,
    case_id: Optional[str] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = get_user_from_authorization(authorization, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Autenticación requerida.")

    if payload.semanas_en_casa > payload.edad_semanas:
        raise HTTPException(
            status_code=422,
            detail="No puede llevar en casa más semanas de las que tiene.",
        )

    coste = PUPPY_ABC_TOKEN_COST if payload.objetivo == "problema" else PUPPY_SCHOOL_TOKEN_COST
    deduct_token(authorization, db, amount=coste, require_auth=True)

    # El modelo recibe etiquetas legibles, nunca las claves técnicas.
    datos = payload.model_dump()
    datos["edad_texto"] = _edad_texto(payload.edad_semanas)
    datos["birth_date"] = payload.birth_date.isoformat()
    datos["origen"] = ("adoptado" if payload.origen == "adoptado" else "de criadero")
    datos["area_texto"] = AREAS[payload.area]
    datos["donde_duerme_texto"] = DONDE_DUERME[payload.donde_duerme]
    datos["destete_texto"] = DESTETE[payload.destete]
    datos["ninos_texto"] = (
        f"sí, con edades: {payload.edades_ninos.strip() or 'sin especificar'}"
        if payload.ninos else "no hay niños en casa"
    )
    datos["objetivo_texto"] = ("prevenir y educar" if payload.objetivo == "prevenir"
                               else "solucionar un problema de conducta")
    datos["otros_perros_texto"] = (
        f"sí, y sus edades son: {payload.edades_otros_perros.strip() or 'sin especificar'}"
        if payload.otros_perros else "no, es el único perro de la casa"
    )
    datos["vacunacion_texto"] = (
        "calendario completo, con la heptavalente puesta hace más de una semana"
        if payload.vacunacion_completa else
        "calendario INCOMPLETO: no ha pasado más de una semana desde la heptavalente"
    )

    try:
        result = generate_puppy_plan(datos=datos, lang=payload.lang)

        background_tasks.add_task(
            log_usage,
            user_id=user.id,
            endpoint="/puppy-school",
            model=get_settings().clinical_model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            tokens_charged=coste,
            success="ok",
        )

        if case_id:
            persist_to_case_safely(
                case_id, user, db,
                entry_type="abc",
                content=result.plan_markdown,
                meta={"endpoint": "/puppy-school", "case_type": "puppy",
                      "birth_date": payload.birth_date.isoformat(),
                      # Edad congelada: la que tenía el día de la consulta.
                      "edad_semanas_en_consulta": payload.edad_semanas,
                      "fecha_consulta": date.today().isoformat(),
                      "objetivo": payload.objetivo, "area": payload.area},
                ai_model=get_settings().clinical_model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                tokens_charged=coste,
                update_summary_abc=True,
            )

        return PuppySchoolResponse(
            plan=result.plan_markdown,
            tipo=("analisis_funcional" if payload.objetivo == "problema" else "educacion"),
            sources=[s.model_dump() for s in result.sources],
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cache_hit=result.cache_hit,
        )
    except HTTPException:
        raise
    except Exception as e:
        refund_token(authorization, db, amount=coste)
        background_tasks.add_task(
            log_usage,
            user_id=user.id,
            endpoint="/puppy-school",
            model=get_settings().clinical_model,
            tokens_charged=coste,
            success="error",
        )
        _log.exception("puppy-school: fallo generando el plan — %s", e)
        raise_http_for_anthropic(e)
