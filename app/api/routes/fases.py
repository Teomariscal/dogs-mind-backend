"""
FASES DEL PLAN — estado y puerta de paso.

    GET  /cases/{id}/fase           -> en que fase esta y si puede pedir el paso
    POST /cases/{id}/fase/evaluar   -> consulta a Teo con el cuestionario

Founder, 19-oct-2026: *"cuando has realizado todos los ejercicios y
consideramos que ha terminado la fase 1, una consulta con Teo para ver si
puedes pasar a fase 2. Y hay un cuestionario en el que busquemos que no haya
ninguna bandera de regresion y que sean banderas de progreso suficientes."*

La fase NO se puede mover a mano desde el cliente. Solo la mueve este endpoint,
y solo con veredicto favorable. Si el cliente pudiera escribir `current_phase`,
la puerta no seria una puerta.
"""
from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.fases import parsear as parsear_fases, texto_de_fase
from app.database import get_db
from app.models.case import Case, CaseEntry
from app.models.user import User
from app.api.routes.auth import get_current_user
from app.api.routes.cases import (
    _get_owned_case, _charge_user_tokens, MAX_ENTRIES_PER_CASE,
)
from app.services.fase_gate_ai import (
    CuestionarioFase, evaluar_paso_de_fase,
)

router = APIRouter(prefix="/cases", tags=["fases"])

# Coste de la consulta de paso de fase. Es una llamada Sonnet con el plan de la
# fase + hasta 30 dias de historial, mas corta que un seguimiento completo
# (max_tokens 1500 frente a 4000) y sin RAG.
#
# REGLA DURA del repo: ninguna funcion cobra 0. Este numero es provisional y
# LO FIJA EL FOUNDER; esta puesto para no incumplir la regla mientras lo
# decide, no porque yo haya decidido el precio.
FASE_GATE_TOKEN_COST = 0.5

# Dias minimos trabajados antes de poder pedir el paso. No es un castigo: es
# que con menos no hay datos con los que decidir, y el veredicto saldria
# "confianza baja" igualmente, cobrando.
MIN_DIAS_PARA_PEDIR = 5


# ── Esquemas ────────────────────────────────────────────────────────────────
class EstadoFase(BaseModel):
    tiene_fases: bool
    fase_actual: int
    fases_totales: int
    titulo: Optional[str] = None
    dias_reportados_en_fase: int
    dias_minimos: int
    puede_pedir_evaluacion: bool
    es_ultima_fase: bool
    # Para el aviso de dias saltados. Se calcula AQUI y no en el cliente: el
    # cliente no sabe cuantos dias lleva el caso ni cuando fue el ultimo, y
    # adivinarlo seria avisar a quien no toca.
    dias_registrados_total: int = 0
    dias_desde_ultimo: int = 0
    avisar_huecos: bool = False


class CuestionarioEntrada(BaseModel):
    dias_trabajados: int = Field(0, ge=0, le=400)
    ejercicios_completos: bool = False
    ve_mejoria: bool = False
    criterio_observado: Optional[str] = Field(None, max_length=1500)
    ha_empeorado_algo: Optional[str] = Field(None, max_length=1500)
    dificultades: Optional[str] = Field(None, max_length=1500)
    extra: Optional[str] = Field(None, max_length=1000)


class VeredictoRespuesta(BaseModel):
    avanza: bool
    fase_actual: int
    fases_totales: int
    banderas_regresion: list[str]
    banderas_progreso: list[str]
    confianza: str
    mensaje: str
    que_hacer_ahora: list[str]
    tokens_restantes: float


# ── Helpers ─────────────────────────────────────────────────────────────────
def _plan_del_caso(case: Case, db: Session) -> str:
    intv = db.query(CaseEntry).filter(
        CaseEntry.case_id == case.id,
        CaseEntry.type == "intervention",
    ).order_by(desc(CaseEntry.created_at)).first()
    return (intv.content or "").strip() if intv else ""


def _historial_de_la_fase(case: Case, db: Session) -> list[dict[str, Any]]:
    """Los dias reportados DESDE que empezo la fase actual.

    No se le da a Teo el historial de todo el caso: si el perro lleva tres
    fases, lo de la fase 1 ya no dice nada sobre si cierra la 3.
    """
    from app.models.case import DailyFollowupEntry
    q = db.query(DailyFollowupEntry).filter(DailyFollowupEntry.case_id == case.id)
    if case.phase_started_at:
        q = q.filter(DailyFollowupEntry.created_at >= case.phase_started_at)
    filas = q.order_by(DailyFollowupEntry.day_local_date.asc()).all()
    fuera = []
    for f in filas:
        fuera.append({
            "date": str(f.day_local_date or ""),
            "is_complete": bool(f.is_complete),
            "exercises_results": f.exercises_results,
            "observation": (f.observation or "")[:300],
            "dog_state": f.dog_state,
        })
    return fuera


def _estado(case: Case, db: Session) -> EstadoFase:
    plan = _plan_del_caso(case, db)
    p = parsear_fases(plan)
    if p is None:
        t0, d0, a0 = _huecos(case, db)
        return EstadoFase(
            tiene_fases=False, fase_actual=0, fases_totales=0, titulo=None,
            dias_reportados_en_fase=0, dias_minimos=MIN_DIAS_PARA_PEDIR,
            puede_pedir_evaluacion=False, es_ultima_fase=False,
            dias_registrados_total=t0, dias_desde_ultimo=d0, avisar_huecos=a0,
        )
    total = p.total
    actual = min(max(case.current_phase or 1, 1), total)
    hist = _historial_de_la_fase(case, db)
    dias = sum(1 for d in hist if d["is_complete"])
    ultima = actual >= total
    f = p.fase(actual)
    total_dias, desde_ultimo, avisar = _huecos(case, db)
    return EstadoFase(
        tiene_fases=True, fase_actual=actual, fases_totales=total,
        titulo=(f.titulo if f else None),
        dias_reportados_en_fase=dias, dias_minimos=MIN_DIAS_PARA_PEDIR,
        puede_pedir_evaluacion=(not ultima and dias >= MIN_DIAS_PARA_PEDIR),
        es_ultima_fase=ultima,
        dias_registrados_total=total_dias, dias_desde_ultimo=desde_ultimo,
        avisar_huecos=avisar,
    )


# Dias seguidos sin anotar a partir de los cuales se avisa.
HUECO_AVISO = 3
# Dias ya anotados por debajo de los cuales NO se avisa: founder, 19-oct,
# *"sin una advertencia de que la cosa no va a funcionar, SI YA TIENES
# CONSTANCIA"*. A quien nunca ha trabajado no se le riñe por no trabajar.
CONSTANCIA_MINIMA = 3


def _huecos(case: Case, db: Session) -> tuple[int, int, bool]:
    """(dias anotados en todo el caso, dias desde el ultimo, hay que avisar)."""
    from app.models.case import DailyFollowupEntry
    filas = db.query(DailyFollowupEntry).filter(
        DailyFollowupEntry.case_id == case.id,
        DailyFollowupEntry.is_complete.is_(True),
    ).order_by(DailyFollowupEntry.day_local_date.desc()).all()
    if not filas:
        return 0, 0, False
    ultimo = filas[0].day_local_date
    desde = (date.today() - ultimo).days if ultimo else 0
    total = len(filas)
    return total, max(desde, 0), (total >= CONSTANCIA_MINIMA and desde >= HUECO_AVISO)


# ── Endpoints ───────────────────────────────────────────────────────────────
@router.get("/{case_id}/fase", response_model=EstadoFase)
def get_fase(case_id: str, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)):
    """En que fase va el caso. Gratis: es leer, no genera nada."""
    case = _get_owned_case(case_id, user, db)
    estado = _estado(case, db)
    # Sincroniza lo que sabemos del plan sin esperar al seguimiento diario.
    if estado.tiene_fases and (case.phase_total != estado.fases_totales
                               or case.current_phase != estado.fase_actual):
        case.phase_total = estado.fases_totales
        case.current_phase = estado.fase_actual
        if case.phase_started_at is None:
            case.phase_started_at = datetime.utcnow()
        db.commit()
    return estado


@router.post("/{case_id}/fase/evaluar", response_model=VeredictoRespuesta,
             status_code=status.HTTP_201_CREATED)
def evaluar_fase(case_id: str, payload: CuestionarioEntrada,
                 db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """Consulta a Teo: ¿puede este perro pasar a la fase siguiente?"""
    case = _get_owned_case(case_id, user, db)

    plan = _plan_del_caso(case, db)
    p = parsear_fases(plan)
    if p is None:
        raise HTTPException(status_code=409,
                            detail="Este plan no va por fases.")

    total = p.total
    actual = min(max(case.current_phase or 1, 1), total)
    if actual >= total:
        raise HTTPException(status_code=409,
                            detail="Ya estas en la ultima fase del plan.")

    historial = _historial_de_la_fase(case, db)
    dias = sum(1 for d in historial if d["is_complete"])
    if dias < MIN_DIAS_PARA_PEDIR:
        # No se cobra: no hay nada que evaluar todavia.
        raise HTTPException(
            status_code=409,
            detail=(f"Necesitas al menos {MIN_DIAS_PARA_PEDIR} dias de "
                    f"ejercicios registrados en esta fase. Llevas {dias}."),
        )

    if _contar_entries(case_id, db) >= MAX_ENTRIES_PER_CASE:
        raise HTTPException(status_code=429,
                            detail=f"Has alcanzado el maximo de {MAX_ENTRIES_PER_CASE} entradas en este caso.")

    # Invariante financiera: cobrar ANTES de llamar a la IA.
    nuevo_saldo = _charge_user_tokens(user, FASE_GATE_TOKEN_COST, db)

    plan_fase = texto_de_fase(plan, actual) or plan
    nombre = (case.client_dog_name or case.title or "").strip()
    lang = (case.lang or "es")

    try:
        v = evaluar_paso_de_fase(
            plan_fase=plan_fase, fase_actual=actual, fases_totales=total,
            dog_name=nombre, cuestionario=CuestionarioFase(**payload.model_dump()),
            historial=historial, lang=lang,
        )
    except Exception as e:
        # No se cobra por un error nuestro.
        user.tokens = float(user.tokens) + FASE_GATE_TOKEN_COST
        db.commit()
        raise HTTPException(status_code=502,
                            detail=f"No se pudo evaluar el paso de fase: {str(e)[:200]}")

    settings = get_settings()
    entry = CaseEntry(
        case_id=case.id,
        type="fase_gate",
        content=v.mensaje,
        meta={
            "fase_evaluada": actual, "fases_totales": total,
            "avanza": v.avanza, "confianza": v.confianza,
            "banderas_regresion": v.banderas_regresion,
            "banderas_progreso": v.banderas_progreso,
            "que_hacer_ahora": v.que_hacer_ahora,
            "cuestionario": payload.model_dump(),
            "dias_reportados": dias,
        },
        ai_model=settings.clinical_model,
        input_tokens=v.input_tokens,
        output_tokens=v.output_tokens,
        tokens_charged=FASE_GATE_TOKEN_COST,
    )
    db.add(entry)

    # LA FASE SOLO SE MUEVE AQUI, Y SOLO CON VEREDICTO FAVORABLE.
    if v.avanza:
        case.current_phase = actual + 1
        case.phase_started_at = datetime.utcnow()
    case.phase_total = total
    case.updated_at = datetime.utcnow()
    db.commit()

    try:
        from app.core.usage_tracker import log_usage
        log_usage(user_id=str(user.id), endpoint="/cases/fase/evaluar",
                  model=settings.clinical_model, input_tokens=v.input_tokens,
                  output_tokens=v.output_tokens,
                  tokens_charged=FASE_GATE_TOKEN_COST, success="ok")
    except Exception:
        pass

    return VeredictoRespuesta(
        avanza=v.avanza,
        fase_actual=case.current_phase,
        fases_totales=total,
        banderas_regresion=v.banderas_regresion,
        banderas_progreso=v.banderas_progreso,
        confianza=v.confianza,
        mensaje=v.mensaje,
        que_hacer_ahora=v.que_hacer_ahora,
        tokens_restantes=nuevo_saldo,
    )


def _contar_entries(case_id: str, db: Session) -> int:
    return db.query(CaseEntry).filter(CaseEntry.case_id == case_id).count()
