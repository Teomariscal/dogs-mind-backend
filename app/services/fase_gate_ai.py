"""
Puerta de fase — evalua si un caso puede pasar a la fase siguiente.

Espejo de `seguimiento_ai.py` en estructura (mismo cliente, mismo modelo, misma
devolucion de tokens para el tracking de coste), pero la salida es JSON
estricto en vez de markdown: la app enciende o apaga un boton con ella.

Founder, 19-oct-2026: *"un cuestionario en el que busquemos que no haya ninguna
bandera de regresion y que sean banderas de progreso suficientes como para
pasar a fase 2"*.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from pydantic import BaseModel

from app.config import get_settings
from app.core.anthropic_client import get_anthropic_client
from app.core.prompts.fase_gate import prompt_de


class CuestionarioFase(BaseModel):
    """Lo que contesta el dueño al pedir el paso de fase.

    Son pocas preguntas a proposito: el grueso de la evidencia lo pone el
    historial de ejercicios, que la app ya tiene. Preguntarle al dueño lo que
    la app ya sabe es cobrarle un coste de respuesta por nada.
    """
    dias_trabajados: int = 0
    ejercicios_completos: bool = False
    ve_mejoria: bool = False
    criterio_observado: Optional[str] = None      # que ha medido y cuanto
    ha_empeorado_algo: Optional[str] = None       # lo que el dueño note a peor
    dificultades: Optional[str] = None
    extra: Optional[str] = None


class VeredictoFase(BaseModel):
    avanza: bool
    banderas_regresion: list[str]
    banderas_progreso: list[str]
    confianza: str
    mensaje: str
    que_hacer_ahora: list[str]
    input_tokens: int = 0
    output_tokens: int = 0


_CONFIANZAS = {"alta", "media", "baja"}


def _bloque_historial(historial: list[dict[str, Any]], lang: str) -> str:
    """El historial REAL de ejercicios, que es la mitad de la evidencia.

    Founder: *"cuando haga una consulta a Teo, utilice los datos del
    seguimiento de los ejercicios"*. Sin esto el modelo decide solo con lo que
    el dueño dice de si mismo, que es justo lo que menos fiable es.
    """
    if not historial:
        return {
            "en": "DAILY EXERCISE HISTORY: none recorded. Treat this as insufficient data.",
            "it": "STORICO ESERCIZI QUOTIDIANI: nessuno registrato. Consideralo dato insufficiente.",
        }.get(lang, "HISTORIAL DE EJERCICIOS DIARIOS: ninguno registrado. Tratalo como datos insuficientes.")

    cabecera = {
        "en": "DAILY EXERCISE HISTORY (what actually happened, day by day):",
        "it": "STORICO ESERCIZI QUOTIDIANI (cosa e successo davvero, giorno per giorno):",
    }.get(lang, "HISTORIAL DE EJERCICIOS DIARIOS (lo que paso de verdad, dia a dia):")

    lineas = [cabecera]
    for d in historial[-30:]:          # un mes es de sobra; mas es ruido y coste
        fecha = d.get("date") or d.get("fecha") or "?"
        if not d.get("is_complete", d.get("completo", False)):
            lineas.append(f"- {fecha}: (sin reportar)")
            continue
        res = d.get("exercises_results") or d.get("ejercicios") or []
        if isinstance(res, list) and res:
            trozos = []
            for e in res[:4]:
                if isinstance(e, dict):
                    t = str(e.get("title") or e.get("titulo") or "")[:60]
                    hecho = e.get("done", e.get("hecho"))
                    nota = str(e.get("result") or e.get("resultado") or "")[:80]
                    marca = "hecho" if hecho else "no hecho"
                    trozos.append(f"{t} [{marca}]" + (f" -> {nota}" if nota else ""))
                else:
                    trozos.append(str(e)[:80])
            lineas.append(f"- {fecha}: " + " | ".join(trozos) + _cola(d))
        else:
            lineas.append(f"- {fecha}: (reportado, sin detalle)" + _cola(d))
    return "\n".join(lineas)


def _cola(d: dict[str, Any]) -> str:
    """Como vio el dueño al perro y que anoto. Aqui es donde asoman las
    banderas de regresion; en la lista de ejercicios no asoman nunca."""
    trozos = []
    est = d.get("dog_state")
    if est:
        trozos.append(f"perro: {est}")
    obs = (d.get("observation") or "").strip()
    if obs:
        trozos.append(f"nota: {obs[:200]}")
    return ("  (" + "; ".join(trozos) + ")") if trozos else ""


def _mensaje_usuario(plan_fase: str, fase_actual: int, fases_totales: int,
                     dog_name: str, cuestionario: CuestionarioFase,
                     historial: list[dict[str, Any]], lang: str) -> str:
    etiquetas = {
        "en": ("CURRENT PHASE OF THE PLAN", "OWNER'S QUESTIONNAIRE",
               "Days worked", "All exercises completed", "Sees improvement",
               "Criterion observed", "Anything worse", "Difficulties", "Extra",
               "yes", "no", "(not stated)",
               "Decide whether {d} can move from phase {a} to phase {b} of {t}."),
        "it": ("FASE ATTUALE DEL PIANO", "QUESTIONARIO DEL PROPRIETARIO",
               "Giorni lavorati", "Tutti gli esercizi completati", "Vede miglioramento",
               "Criterio osservato", "Qualcosa e peggiorato", "Difficolta", "Extra",
               "si", "no", "(non indicato)",
               "Decidi se {d} puo passare dalla fase {a} alla fase {b} di {t}."),
    }.get(lang, ("FASE ACTUAL DEL PLAN", "CUESTIONARIO DEL DUEÑO",
                 "Dias trabajados", "Ejercicios completos", "Ve mejoria",
                 "Criterio observado", "Algo a peor", "Dificultades", "Extra",
                 "si", "no", "(no indicado)",
                 "Decide si {d} puede pasar de la fase {a} a la fase {b} de {t}."))

    (t_fase, t_cues, l_dias, l_ej, l_mej, l_crit, l_peor, l_dif, l_extra,
     si, no, vacio, plantilla) = etiquetas

    def b(v):
        return si if v else no

    return (
        plantilla.format(d=dog_name or "el perro", a=fase_actual,
                         b=min(fase_actual + 1, fases_totales), t=fases_totales)
        + "\n\n"
        + f"{t_fase}\n\n{plan_fase.strip()}\n\n"
        + _bloque_historial(historial, lang) + "\n\n"
        + f"{t_cues}\n"
        + f"- {l_dias}: {cuestionario.dias_trabajados}\n"
        + f"- {l_ej}: {b(cuestionario.ejercicios_completos)}\n"
        + f"- {l_mej}: {b(cuestionario.ve_mejoria)}\n"
        + f"- {l_crit}: {cuestionario.criterio_observado or vacio}\n"
        + f"- {l_peor}: {cuestionario.ha_empeorado_algo or vacio}\n"
        + f"- {l_dif}: {cuestionario.dificultades or vacio}\n"
        + f"- {l_extra}: {cuestionario.extra or vacio}\n"
    )


def _json_de(texto: str) -> dict[str, Any]:
    """Saca el objeto JSON aunque venga con ``` o con texto alrededor."""
    t = (texto or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.IGNORECASE | re.MULTILINE).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    ini, fin = t.find("{"), t.rfind("}")
    if ini == -1 or fin <= ini:
        raise ValueError("la respuesta no contiene un objeto JSON")
    return json.loads(t[ini:fin + 1])


def _lista(v: Any, tope: int = 6) -> list[str]:
    if not isinstance(v, list):
        return []
    fuera = []
    for x in v:
        s = str(x).strip()
        if s:
            fuera.append(s[:300])
        if len(fuera) >= tope:
            break
    return fuera


def evaluar_paso_de_fase(
    plan_fase: str,
    fase_actual: int,
    fases_totales: int,
    dog_name: str,
    cuestionario: CuestionarioFase,
    historial: list[dict[str, Any]],
    lang: str = "es",
) -> VeredictoFase:
    """Decide si se abre la fase siguiente. No persiste nada."""
    settings = get_settings()
    client = get_anthropic_client()
    l = (lang or "es").lower()

    resp = client.messages.create(
        model=settings.clinical_model,
        max_tokens=1500,
        system=[{"type": "text", "text": prompt_de(l),
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": _mensaje_usuario(
            plan_fase, fase_actual, fases_totales, dog_name, cuestionario, historial, l)}],
    )
    texto = "".join(b.text for b in resp.content if hasattr(b, "text"))
    datos = _json_de(texto)

    regresion = _lista(datos.get("banderas_regresion"))
    progreso = _lista(datos.get("banderas_progreso"))
    confianza = str(datos.get("confianza", "baja")).strip().lower()
    if confianza not in _CONFIANZAS:
        confianza = "baja"

    avanza = bool(datos.get("avanza", False))

    # LA ASIMETRIA SE IMPONE AQUI, NO SE LE PIDE AL MODELO QUE LA RESPETE.
    # El prompt se lo dice, pero un prompt no es una garantia: si el modelo
    # devuelve avanza=true con una bandera de regresion encima, o con confianza
    # baja, gana el codigo. Dejar pasar a un perro que no ha consolidado la
    # fase monta la siguiente sobre nada.
    if regresion or confianza == "baja":
        avanza = False
    if not progreso:
        avanza = False
    if fase_actual >= fases_totales:
        avanza = False            # ya esta en la ultima: no hay a donde pasar

    usage = resp.usage
    return VeredictoFase(
        avanza=avanza,
        banderas_regresion=regresion,
        banderas_progreso=progreso,
        confianza=confianza,
        mensaje=str(datos.get("mensaje", "")).strip()[:1200],
        que_hacer_ahora=_lista(datos.get("que_hacer_ahora")),
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
        output_tokens=getattr(usage, "output_tokens", 0) or 0,
    )
