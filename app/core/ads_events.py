"""
Eventos de valor hacia las plataformas de anuncios — SERVER-SIDE.

Por qué existe
--------------
Hasta hoy (2026-08-19) la app no emitía ninguna señal a Google ni a Meta: la
única conversión que Google Ads podía optimizar era "page view", porque era
literalmente lo único que llegaba. Con eso, la puja compra vistas baratas en
vez de clientes. Auditoría completa en `~/Documents/Claude/Ants/auditoria_medicion_dev.md`.

Los eventos de INSTALACIÓN (first_open, sign_up) tienen que ir en el cliente y
esperan a la build 1.0.8. Los eventos de DINERO, que son los que de verdad
mandan en la puja, se pueden emitir desde aquí YA: el backend ya sabe quién
pagó, cuánto y en qué moneda, y lo sabe igual de bien venga de la web (Stripe)
o de las tiendas (RevenueCat). Además server-side no depende del navegador, ni
del bloqueo de cookies, ni del permiso de seguimiento de iOS.

Reglas de la casa que este módulo respeta
-----------------------------------------
- **Nunca rompe un cobro.** Todo va en hilo aparte y todo error se traga. Si
  Meta está caída o el token caducó, el webhook de pago sigue su curso como si
  este módulo no existiera. Es la única forma responsable de colgar telemetría
  de un camino que mueve dinero de clientes reales.
- **Inerte hasta que haya credenciales.** Sin `META_DATASET_ID` +
  `META_CAPI_TOKEN` en el entorno no se envía nada y no se registra ruido. Hoy
  la cuenta de Meta todavía no tiene conjunto de datos creado, así que se
  despliega apagado y se enciende solo cuando el founder lo cree en consola.
- **Moneda estandarizada en EUR** (decisión de estrategia).
- **PII hasheada.** A Meta va el SHA-256 del email en minúsculas, nunca el
  email en claro, que es lo que exige su API.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.request
from typing import Optional

# ── Configuración (todo por entorno; ausente = módulo inerte) ────────────────
META_DATASET_ID = os.getenv("META_DATASET_ID", "").strip()
META_CAPI_TOKEN = os.getenv("META_CAPI_TOKEN", "").strip()
META_TEST_CODE = os.getenv("META_TEST_EVENT_CODE", "").strip()  # solo para Test Events
META_API_VERSION = os.getenv("META_API_VERSION", "v21.0").strip()

_TIMEOUT = 4  # segundos; nunca bloquea un webhook más que esto


def meta_activo() -> bool:
    return bool(META_DATASET_ID and META_CAPI_TOKEN)


def _sha256(valor: str) -> str:
    return hashlib.sha256(valor.strip().lower().encode("utf-8")).hexdigest()


def _enviar_meta(payload: dict) -> None:
    """Hace el POST. Corre en un hilo; cualquier fallo muere aquí."""
    url = (
        f"https://graph.facebook.com/{META_API_VERSION}/"
        f"{META_DATASET_ID}/events?access_token={META_CAPI_TOKEN}"
    )
    datos = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=datos, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            cuerpo = r.read(400).decode("utf-8", "replace")
        print(f"[ads] Meta OK {payload['data'][0]['event_name']} → {cuerpo}")
    except Exception as e:  # noqa: BLE001 — a propósito: esto jamás propaga
        print(f"[ads] Meta FALLO {payload['data'][0].get('event_name')}: {e}")


def _evento_meta(
    nombre: str,
    email: Optional[str],
    user_id: Optional[str],
    valor: Optional[float],
    moneda: str,
    origen: str,
    event_id: Optional[str],
) -> None:
    user_data = {}
    if email:
        user_data["em"] = [_sha256(email)]
    if user_id:
        user_data["external_id"] = [_sha256(str(user_id))]
    if not user_data:
        # Sin ninguna señal de identidad Meta descarta el evento; no gastamos
        # la llamada.
        print(f"[ads] {nombre} sin identidad, no se envía")
        return

    evento = {
        "event_name": nombre,
        "event_time": int(time.time()),
        "action_source": "app" if origen in ("ios", "android") else "website",
        "user_data": user_data,
    }
    # event_id permite a Meta deduplicar si algún día el cliente manda el mismo
    # evento. Aquí lo alimentamos con la clave idempotente del pago.
    if event_id:
        evento["event_id"] = str(event_id)
    if origen == "web":
        evento["event_source_url"] = "https://thedogsmind.net"
    if valor is not None:
        evento["custom_data"] = {"value": round(float(valor), 2), "currency": moneda}

    payload = {"data": [evento]}
    if META_TEST_CODE:
        payload["test_event_code"] = META_TEST_CODE
    _enviar_meta(payload)


def _en_hilo(fn, *args) -> None:
    try:
        threading.Thread(target=fn, args=args, daemon=True).start()
    except Exception as e:  # noqa: BLE001
        print(f"[ads] no se pudo lanzar el hilo: {e}")


# ── API pública ─────────────────────────────────────────────────────────────
def track_subscribe(
    *,
    email: Optional[str],
    user_id: Optional[str],
    valor_eur: float,
    origen: str,
    plan_id: str = "",
    event_id: Optional[str] = None,
    renovacion: bool = False,
) -> None:
    """
    Alta de suscripción (o renovación). Es el evento de dinero principal del
    modelo vigente. `origen` ∈ {"web", "ios", "android"} — decide si Meta lo
    cuenta como conversión de web o de app.

    No lanza nunca. Llamar dentro del webhook, después del commit.
    """
    if not meta_activo():
        return
    nombre = "Subscribe"
    print(f"[ads] {nombre}{' (renovación)' if renovacion else ''} plan={plan_id} "
          f"origen={origen} {valor_eur}EUR")
    _en_hilo(_evento_meta, nombre, email, user_id, valor_eur, "EUR", origen, event_id)


def track_purchase(
    *,
    email: Optional[str],
    user_id: Optional[str],
    valor_eur: float,
    origen: str,
    event_id: Optional[str] = None,
) -> None:
    """Compra suelta de créditos. Evento de valor secundario."""
    if not meta_activo():
        return
    print(f"[ads] Purchase origen={origen} {valor_eur}EUR")
    _en_hilo(_evento_meta, "Purchase", email, user_id, valor_eur, "EUR", origen, event_id)
