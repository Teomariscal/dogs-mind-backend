"""Respuestas largas que no dejan la conexion callada.

Un analisis clinico tarda unos 66 segundos y la respuesta llega entera al final,
asi que la conexion pasa mas de un minuto sin enviar un solo byte. Los proxies
que cortan por inactividad a los 60 s la matan, y el usuario ve "Error de
conexion" aunque el trabajo se haya hecho y cobrado bien.

Lo reporto un cliente de pago desde un portatil el 1-sep-2026. Medido ese dia
contra produccion:

    /training-analysis   45,2 s  -> a el le funcionaba
    /analysis            66,6 s  -> a el le fallaba siempre

Su corte estaba entre medias, casi seguro en los 60 exactos. Otra red aguanta
mas y por eso a unos usuarios les va y a otros no.

La solucion: si la cosa tarda mas de ESPERA_SIN_LATIDO, se empiezan a mandar
espacios cada CADA_LATIDO segundos hasta tener el resultado. Un JSON admite
espacios delante, asi que el cliente sigue haciendo res.json() y NO hay que
tocar la app — esto cubre iOS, Android y web a la vez, incluidas las versiones
ya instaladas, sin pasar por ninguna tienda.

El camino rapido no cambia: si termina dentro de la espera —una respuesta ya
cacheada tarda 0,17 s— se devuelve tal cual, con sus codigos de estado y sus
errores HTTP intactos.
"""

import asyncio
import json
from typing import Any, Callable

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

# Cuanto se espera en silencio antes del primer latido, y cada cuanto va uno.
# 20 s deja pasar por el camino normal casi todo lo que no es una generacion
# larga, y deja el silencio maximo muy por debajo del minuto que cortan los
# proxies.
ESPERA_SIN_LATIDO = 20
CADA_LATIDO = 5


async def con_latidos(trabajo: Callable[..., Any], *args, **kwargs):
    """Ejecuta `trabajo` en el threadpool de siempre sin dejar la conexion muda.

    `trabajo` es la funcion sincrona que ya existia: se le pasan sus argumentos
    tal cual y sigue corriendo en un solo hilo, asi que el cobro, el reintegro y
    la persistencia no cambian ni se tocan desde dos sitios a la vez.

    Devuelve lo que devuelva `trabajo` si termina pronto; si no, una respuesta en
    streaming con el mismo JSON al final.
    """
    tarea = asyncio.ensure_future(run_in_threadpool(trabajo, *args, **kwargs))
    try:
        return await asyncio.wait_for(asyncio.shield(tarea), timeout=ESPERA_SIN_LATIDO)
    except asyncio.TimeoutError:
        pass

    async def _flujo():
        while not tarea.done():
            yield b" "
            await asyncio.sleep(CADA_LATIDO)
        try:
            yield json.dumps(
                jsonable_encoder(tarea.result()), ensure_ascii=False
            ).encode("utf-8")
        except HTTPException as e:
            # Ya se mando un 200, asi que el codigo no se puede cambiar. El
            # cliente vera lo mismo que ve hoy cuando se corta, y el reintegro
            # ya lo hizo la funcion sincrona antes de lanzar.
            yield json.dumps(
                {"detail": e.detail}, ensure_ascii=False, default=str
            ).encode("utf-8")
        except Exception:
            yield json.dumps(
                {"detail": "No se ha podido completar la peticion."}
            ).encode("utf-8")

    return StreamingResponse(_flujo(), media_type="application/json")
