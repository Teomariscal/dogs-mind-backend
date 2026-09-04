"""
Paseos (World Wide Dog Walking) — cobro del uso.

POST /walks/charge — cobra el paseo al usuario autenticado y devuelve el saldo.

Precio: 0,25 tokens = 25 créditos por planificación de rutas (founder,
2-sep-2026). Subió de 10 a 25 al pasar a Google Maps: un paseo cuesta 0,0478 €
de API (1 geocoding + 1 places + 3 routes) y a 10 créditos se perdía dinero en
el plan Max y no cubría en Pro. A 25 el margen va de +0,06 € en Básico a
+0,03 € en Max.

El muro de suscripción se aplica solo (deduct_token pasa por access_state).
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.token_utils import deduct_token
from app.database import get_db

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/walks", tags=["walks"])

WALK_TOKEN_COST = 0.25  # 25 créditos


@router.post("/charge")
def charge_walk(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    saldo = deduct_token(authorization, db, amount=WALK_TOKEN_COST, require_auth=True)
    return {"ok": True, "tokens": saldo, "credits": int(round((saldo or 0) * 100))}


# ── Google Maps ───────────────────────────────────────────────────────────────
# SIEMPRE Google Maps, sin respaldo (founder, 2-sep-2026). OpenStreetMap queda
# anulado: fuera Overpass, OSRM y Nominatim.
#
# La clave vive SOLO aqui. El navegador no la ve: pide a estos tres endpoints y
# el servidor habla con Google. Asi la clave no se puede copiar de la app ni de
# la web, y el gasto queda medido en un unico sitio.
#
# Coste medido contra la API real el 2-sep-2026: 1 geocoding + 1 places + 3
# routes = 0,0478 EUR por paseo. De ahi que el paseo pasara de 10 a 25 creditos.
# OJO: los sitios se piden en UNA sola llamada con varios tipos. Pedir un tipo
# por llamada triplicaba el coste (0,107 EUR) y hacia perder dinero en todos los
# planes.

import os
import time as _time
import json as _json
import urllib.parse
import urllib.request

from fastapi import HTTPException
from pydantic import BaseModel, Field

_GKEY = (os.environ.get("GOOGLE_MAPS_API_KEY") or "").strip()
# Dos consultas por paseo en vez de una. Cada searchNearby devuelve como mucho 20
# sitios, y con todos los tipos juntos los parques se comian el cupo y no quedaba
# hueco para veterinarios ni senderos. Se separan en SERVICIOS y PAISAJE para que
# cada grupo tenga sus 20.
#
# "Me da igual la decision y el coste, quiero el mejor servicio" (founder,
# 4-sep-2026). Son 0,032 EUR mas por paseo; el negocio esta en la consulta y el
# paseo es reclamo, asi que se paga.
#
# Los tipos estan COMPROBADOS contra la API el 4-sep-2026 en Madrid y en
# Villamantilla (pueblo). Descartados: 'national_park' devolvia un bar, y
# 'drinking_water' no existe en Google —las fuentes de beber se pierden respecto
# a OpenStreetMap, es lo unico que empeora—.
_TIPOS_SERVICIOS = ["veterinary_care", "pet_store", "dog_park"]
_TIPOS_PAISAJE   = ["park", "garden", "hiking_area", "plaza", "historical_landmark"]
_TIPOS_SITIO = _TIPOS_SERVICIOS + _TIPOS_PAISAJE


def _google(url: str, cuerpo: Optional[dict] = None, mascara: Optional[str] = None) -> dict:
    """Llama a Google. Nunca devuelve la clave en el error."""
    if not _GKEY:
        raise HTTPException(status_code=503, detail="Mapas no disponibles ahora mismo.")
    cabeceras = {"Content-Type": "application/json"}
    if mascara:
        cabeceras["X-Goog-Api-Key"] = _GKEY
        cabeceras["X-Goog-FieldMask"] = mascara
    datos = _json.dumps(cuerpo).encode() if cuerpo is not None else None
    # Dos intentos con una espera corta. Un corte de red o un 5xx pasajero de
    # Google no puede dejar al usuario sin paseo: "que funcione siempre" es uno de
    # los tres criterios (founder, 4-sep-2026). Un 4xx no se reintenta porque es
    # culpa nuestra —peticion mal formada o clave— y reintentar solo hace perder
    # tiempo al usuario.
    ultimo = None
    for intento in (1, 2):
        peticion = urllib.request.Request(
            url, data=datos, method=("POST" if cuerpo is not None else "GET"), headers=cabeceras)
        try:
            with urllib.request.urlopen(peticion, timeout=12) as r:
                return _json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            _log.warning("google maps %s -> HTTP %s (intento %d)", url.split("/")[2], e.code, intento)
            if e.code < 500:
                break
            ultimo = e
        except Exception as e:
            _log.warning("google maps %s -> %s (intento %d)", url.split("/")[2], type(e).__name__, intento)
            ultimo = e
        if intento == 1:
            _time.sleep(0.8)
    raise HTTPException(status_code=502, detail="El mapa no responde. Inténtalo en un minuto.")


class Punto(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


@router.get("/buscar")
def buscar_lugar(q: str, authorization: Optional[str] = Header(None)):
    """Nombre de sitio -> coordenadas. Sustituye a Nominatim."""
    q = (q or "").strip()
    if len(q) < 2:
        raise HTTPException(status_code=400, detail="Escribe un lugar.")
    d = _google("https://maps.googleapis.com/maps/api/geocode/json?address="
                + urllib.parse.quote(q) + "&key=" + _GKEY)
    if d.get("status") != "OK" or not d.get("results"):
        raise HTTPException(status_code=404, detail="No hemos encontrado ese sitio.")
    r = d["results"][0]
    g = r["geometry"]["location"]
    return {"lat": g["lat"], "lon": g["lng"], "nombre": r.get("formatted_address", q)}


class SitiosIn(Punto):
    radio: int = Field(1600, ge=200, le=50000)


@router.post("/sitios")
def sitios_cerca(p: SitiosIn, authorization: Optional[str] = Header(None)):
    """Parques, zonas de perros, veterinarios y tiendas. Sustituye a Overpass.

    UNA sola llamada con los cuatro tipos: es la parte cara (32 USD/1.000).
    """
    def _busca(tipos):
        return _google(
            "https://places.googleapis.com/v1/places:searchNearby",
            {"includedTypes": tipos, "maxResultCount": 20,
             "locationRestriction": {"circle": {
                 "center": {"latitude": p.lat, "longitude": p.lon}, "radius": p.radio}}},
            "places.displayName,places.location,places.types").get("places", [])

    crudos = _busca(_TIPOS_SERVICIOS) + _busca(_TIPOS_PAISAJE)
    fuera, vistos = [], set()
    for s in crudos:
        loc = s.get("location") or {}
        if loc.get("latitude") is None:
            continue
        tipos = s.get("types") or []
        # El orden importa: un sitio puede ser varias cosas y gana la mas util.
        tipo = ("dog_park" if "dog_park" in tipos else
                "veterinary" if "veterinary_care" in tipos else
                "pet" if "pet_store" in tipos else
                "nature" if "hiking_area" in tipos else
                "jardin" if "garden" in tipos else
                "historico" if "historical_landmark" in tipos else
                "plaza" if "plaza" in tipos else "park")
        nombre = (s.get("displayName") or {}).get("text", "")
        clave = (round(loc["latitude"], 5), round(loc["longitude"], 5), nombre)
        if clave in vistos:           # las dos consultas pueden solaparse
            continue
        vistos.add(clave)
        fuera.append({"lat": loc["latitude"], "lon": loc["longitude"],
                      "nombre": nombre, "tipo": tipo})
    return {"sitios": fuera}


class RutaIn(BaseModel):
    puntos: list = Field(..., min_length=2, max_length=10,
                         description="[[lat,lon], …]. El primero es la salida y la vuelta.")


@router.post("/ruta")
def calcular_ruta(r: RutaIn, authorization: Optional[str] = Header(None)):
    """Ruta a pie que sale y vuelve al mismo punto. Sustituye a OSRM."""
    try:
        pts = [(float(a), float(b)) for a, b in r.puntos]
    except Exception:
        raise HTTPException(status_code=400, detail="Puntos mal formados.")
    salida = {"location": {"latLng": {"latitude": pts[0][0], "longitude": pts[0][1]}}}
    medias = [{"location": {"latLng": {"latitude": la, "longitude": lo}}} for la, lo in pts[1:]]
    d = _google(
        "https://routes.googleapis.com/directions/v2:computeRoutes",
        {"origin": salida, "destination": salida, "intermediates": medias,
         "travelMode": "WALK", "polylineQuality": "HIGH_QUALITY"},
        "routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline,"
        "routes.legs.steps.navigationInstruction,routes.legs.steps.distanceMeters")
    rutas = d.get("routes") or []
    if not rutas:
        raise HTTPException(status_code=404, detail="Por aquí no sale ruta a pie.")
    x = rutas[0]
    # Indicaciones: Google las da ya redactadas y en el idioma de la peticion, asi
    # que no hay que traducir maniobras a mano como con OSRM. Se descartan los
    # tramos de menos de 25 m, que son ruido ("continua 8 m").
    pasos = []
    for leg in (x.get("legs") or []):
        for st in (leg.get("steps") or []):
            texto = ((st.get("navigationInstruction") or {}).get("instructions") or "").strip()
            if texto and st.get("distanceMeters", 0) >= 25:
                pasos.append(texto)
    return {"metros": x.get("distanceMeters", 0),
            "segundos": int(str(x.get("duration", "0s")).rstrip("s") or 0),
            "trazado": (x.get("polyline") or {}).get("encodedPolyline", ""),
            "pasos": pasos}
