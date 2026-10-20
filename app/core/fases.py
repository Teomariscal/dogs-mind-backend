"""
Partir un plan de intervencion en sus FASES.

NO SE INVENTA EL FORMATO: esto esta medido contra los 374 planes que hay en
produccion el 19-oct-2026. Lo que de verdad escribe el motor:

    ## FASE 1 — Carga emocional positiva de la zona (Semanas 1–3)
    ### Fase 2 — Construccion de la espera sentado en la salida
    FASE 1 — Desensibilizacion al contexto estatico (Semanas 1 a 3)
    ## PHASE 1 — Reinforcer Restoration & Calm Foundation (Weeks 1–2)

Reparto real de esos 374:

    con fases .......... 341 (91 %)      sin fases ... 33
    3 fases ............ 288
    2 fases ............. 51
    1 fase ............... 2
    4 fases .............. 0   <-- ninguno
    prefijo '##' ....... 169   '###' ... 122   sin prefijo ... 50

Por eso este parser es TOLERANTE y el numero de fases es el que traiga el plan,
no un cuatro fijo. La version anterior (y la gemela del frontend) exigia
exactamente cuatro fases y encabezado sin almohadillas, asi que no reconocia NI
UN SOLO plan real: el dueño nunca veia la pantalla por fases y los ejercicios
diarios se generaban leyendo el plan entero. De ahi que salieran mezclados.

Founder, 19-oct-2026: *"los ejercicios que se plantean sean de una fase... la
fase 2 no puede llegar antes de terminar la fase 1, y es el seguimiento el que
dicta los ejercicios a realizar"*.

El gemelo en el frontend es `dmPF._parsear` (index.html). Si los dos dejan de
coincidir, el dueño ve una fase en pantalla y el motor le genera ejercicios de
otra. Cualquier cambio aqui se copia alli, y al reves.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

#  ^  almohadillas opcionales (0-4)
#     negritas opcionales (**FASE 1**)
#     FASE / PHASE / FASI, cualquier caja
#     numero arabe o romano
#     separador OPCIONAL: em/en dash, guion, dos puntos, punto -- o ninguno,
#     porque tambien se escribe "FASE 1 (Semanas 1-3): titulo"
#     resto de la linea = titulo + semanas, en el orden que sea
RE_FASE = re.compile(
    r"^[ \t]*#{0,4}[ \t]*\*{0,2}[ \t]*"
    r"(?:FASE|PHASE|FASI)[ \t]*"
    r"(\d{1,2}|[IVX]{1,4})"
    r"[ \t]*\*{0,2}"
    r"(?:[ \t]*[—–\-:.][ \t]*)?"
    r"(.*?)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)

# Las señales a vigilar / notas finales van pegadas al final de la ultima fase.
RE_CIERRE = re.compile(
    r"^[ \t]*#{0,4}[ \t]*\*{0,2}[ \t]*"
    r"(?:SE(?:Ñ|N)ALES[^\n]*|SIGNS[^\n]*|SEGNALI[^\n]*"
    r"|CRITERIOS DE[^\n]*|NOTAS[^\n]*|NOTE[^\n]*)$",
    re.IGNORECASE | re.MULTILINE,
)

_ROMANOS = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}

# Una fase con menos texto que esto no es una fase: es una mencion de pasada
# ("vuelve al protocolo de Fase 2"). Medido: la fase real mas corta de
# produccion ronda los 200 caracteres.
MIN_CUERPO = 120


@dataclass
class Fase:
    n: int
    titulo: str      # "Carga emocional positiva de la zona (Semanas 1-3)"
    cuerpo: str

    @property
    def encabezado(self) -> str:
        return f"FASE {self.n} — {self.titulo}".strip(" —")


@dataclass
class PlanPorFases:
    cabecera: str
    fases: list[Fase]
    cierre: str

    @property
    def total(self) -> int:
        return len(self.fases)

    def fase(self, n: int) -> Fase | None:
        for f in self.fases:
            if f.n == n:
                return f
        return None


def _numero(crudo: str) -> int | None:
    crudo = crudo.strip().upper()
    if crudo.isdigit():
        v = int(crudo)
        return v if 1 <= v <= 12 else None
    return _ROMANOS.get(crudo)


def parsear(texto: str | None) -> PlanPorFases | None:
    """Devuelve las fases que traiga el plan, o None si no va por fases.

    None NO es un error: 33 de los 374 planes de produccion no llevan fases.
    Quien llama sigue con el plan entero, como siempre.
    """
    if not texto or not isinstance(texto, str):
        return None

    crudas = []
    for m in RE_FASE.finditer(texto):
        n = _numero(m.group(1))
        if n is None:
            continue
        crudas.append((n, (m.group(2) or "").strip(" *#"), m.start(), m.end()))
    if len(crudas) < 2:
        return None  # con una sola "fase" no hay nada que escalonar

    # Solo la PRIMERA aparicion de cada numero cuenta como encabezado, y los
    # numeros tienen que ir subiendo: "repite el protocolo de la Fase 2" desde
    # dentro de la fase 3 no abre una fase nueva.
    marcas = []
    for n, titulo, ini, fin in crudas:
        if marcas and n <= marcas[-1][0]:
            continue
        marcas.append((n, titulo, ini, fin))
    if len(marcas) < 2:
        return None

    cabecera = texto[: marcas[0][2]].strip()

    fases: list[Fase] = []
    for k, (n, titulo, _ini, fin) in enumerate(marcas):
        hasta = marcas[k + 1][2] if k + 1 < len(marcas) else len(texto)
        fases.append(Fase(n=n, titulo=titulo, cuerpo=texto[fin:hasta].strip()))

    # Una "fase" sin cuerpo suficiente era una mencion, no un encabezado.
    # La ultima se perdona: puede quedar corta tras recortarle el cierre.
    if any(len(f.cuerpo) < MIN_CUERPO for f in fases[:-1]):
        return None

    cierre = ""
    mc = RE_CIERRE.search(fases[-1].cuerpo)
    if mc:
        cierre = fases[-1].cuerpo[mc.start():].strip()
        fases[-1].cuerpo = fases[-1].cuerpo[: mc.start()].strip()

    return PlanPorFases(cabecera=cabecera, fases=fases, cierre=cierre)


def texto_de_fase(plan: str | None, n: int) -> str | None:
    """El trozo del plan de la fase `n`, con la cabecera comun por delante.

    Es lo que se le pasa al generador de ejercicios diarios EN LUGAR del plan
    entero. La cabecera (objetivo, idea del plan) va incluida porque da el PARA
    QUE; sin ella el modelo repite mecanica sin saber hacia donde va.

    None si el plan no va por fases o esa fase no existe: el que llama se queda
    con el plan completo, igual que hasta ahora.
    """
    p = parsear(plan)
    if p is None:
        return None
    f = p.fase(n)
    if f is None:
        return None
    trozos = [p.cabecera, f.encabezado, f.cuerpo]
    return "\n\n".join(t for t in trozos if t).strip()


def total_fases(plan: str | None) -> int:
    p = parsear(plan)
    return p.total if p else 0
