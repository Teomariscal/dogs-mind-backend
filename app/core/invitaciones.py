"""
CUANTO DURA DE VERDAD UNA INVITACION — fuente unica.

Founder, 21-oct-2026: *"no puede haber ningun fallo mas y me lo tienes que
garantizar por arquitectura"*.

EL FALLO QUE ESTO MATA, que acababa de cometer yo mismo ese dia:

    Cree PRO15-VW7DEQ con days=15 creyendo que daba 15 dias. Daba 45.

    Porque la duracion NO esta en `days`. `days` es lo que dura UN ciclo. Al
    vencer, `_renovar_invitacion` (subscriptions.py) le regala al usuario otros
    30 dias y otra tanda entera de creditos la proxima vez que abre la app, y
    lo repite mientras `invite_until` siga vivo — que son `30 * meses` dias.

    Es decir: dos columnas que no se parecen gobiernan el mismo numero, y
    leyendo cualquiera de las dos por separado se llega a una cifra falsa.

LA GARANTIA NO ES ACORDARSE. Es que exista UNA funcion que calcule el numero
real, que nadie lea `days` ni `meses` por su cuenta para responder "cuanto
dura", y que haya una comprobacion que recorra TODOS los codigos y falle si
alguno promete una cosa y hace otra.

El numero declarado vive en `gratuidad_declarada` (columna nueva). Si no
coincide con el calculado, el codigo esta mal y se dice. No se arregla solo:
arreglarlo solo esconderia el fallo, que es como llegamos hasta aqui.
"""
from __future__ import annotations

from dataclasses import dataclass

# Lo que `_renovar_invitacion` concede en cada renovacion automatica. Si algun
# dia cambia alli, cambia aqui: son el mismo numero y por eso esta nombrado.
DIAS_POR_RENOVACION = 30


@dataclass(frozen=True)
class Gratuidad:
    dias: int | None          # None = sin tope (equipo)
    autorrenueva: bool
    explicacion: str

    @property
    def infinita(self) -> bool:
        return self.dias is None


def gratuidad_real(days: int | None, meses: int | None) -> Gratuidad:
    """Cuantos dias de gratuidad da de verdad un codigo con esos dos campos.

    Es la UNICA forma admitida de responder "cuanto dura". Leer `days` a pelo
    es el fallo del 21-oct.
    """
    d = int(days or DIAS_POR_RENOVACION)

    # meses = None -> invite_until = None -> la renovacion no tiene tope nunca.
    if meses is None:
        return Gratuidad(None, True,
                         "sin tope: se renueva sola cada vez que vence, para siempre")

    m = int(meses)

    # meses = 0 -> invite_until = ahora mismo -> la renovacion NO llega a correr
    # ni una vez. Lo que dura es exactamente el primer ciclo.
    if m <= 0:
        return Gratuidad(d, False, f"{d} dias exactos y se acaba, sin renovacion")

    # meses >= 1 -> el primer ciclo dura `days`, y a partir de ahi se renueva
    # sola en tandas de 30 hasta que `invite_until` (30*m dias desde el canje)
    # se cumple. El tope manda: la gratuidad es 30*m, no `days`.
    total = DIAS_POR_RENOVACION * m
    if d >= total:
        return Gratuidad(d, False,
                         f"{d} dias: el primer ciclo ya pasa del tope de {total}, "
                         f"asi que no llega a renovarse")
    return Gratuidad(total, True,
                     f"{total} dias ({m} mes{'es' if m != 1 else ''}): el primer ciclo "
                     f"dura {d} y luego se renueva sola en tandas de "
                     f"{DIAS_POR_RENOVACION} hasta el tope")


def campos_para(dias_pedidos: int | None) -> tuple[int, int | None]:
    """El camino inverso: que (days, meses) hay que poner para que dure
    EXACTAMENTE lo que se quiere.

    Existe para que nadie tenga que deducirlo. Quien crea un codigo dice
    cuantos dias quiere, y esto devuelve los dos campos correctos.
    """
    if dias_pedidos is None:
        return DIAS_POR_RENOVACION, None            # equipo: sin tope
    d = int(dias_pedidos)
    if d <= 0:
        raise ValueError("una invitacion de cero dias no es una invitacion")
    if d % DIAS_POR_RENOVACION == 0:
        # Multiplo exacto de 30: se puede expresar como meses y renovar sola,
        # que es como estan los codigos historicos.
        return DIAS_POR_RENOVACION, d // DIAS_POR_RENOVACION
    # Cualquier otra duracion (15 dias, 45, 7...) solo se puede dar con un
    # unico ciclo y la renovacion apagada.
    return d, 0


def revisar(code: str, days: int | None, meses: int | None,
            declarada: int | None, es_equipo_sin_tope: bool = False) -> str | None:
    """Devuelve el problema si lo hay, o None si el codigo es coherente.

    `declarada` = los dias que el codigo DICE que da. None = no se declaro.
    """
    real = gratuidad_real(days, meses)

    if es_equipo_sin_tope:
        if not real.infinita:
            return (f"{code}: es un codigo de equipo pero NO es sin tope "
                    f"({real.explicacion})")
        return None

    if real.infinita:
        return (f"{code}: gratuidad SIN TOPE sin ser codigo de equipo. "
                f"Se renueva sola para siempre.")

    if declarada is None:
        return (f"{code}: no declara cuantos dias da. Da {real.dias} "
                f"({real.explicacion}), pero nadie lo ha escrito, asi que "
                f"nadie puede comprobar que sea lo que se queria.")

    if int(declarada) != real.dias:
        return (f"{code}: PROMETE {declarada} dias y DA {real.dias}. "
                f"{real.explicacion}")

    return None
