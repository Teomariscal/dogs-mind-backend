"""
Alta y baja de dispositivos, interruptor del usuario y la pasada diaria.

La app llama a `POST /push/devices` al arrancar sesion, despues de que el
usuario conceda el permiso del sistema. Si lo deniega no llama, no hay fila, y
no hay nada que mandarle: la app funciona igual, que es lo que exigen Apple y
Google.
"""

import os
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.push_device import PushDevice
from app.api.routes.auth import get_current_user
from app.core import push as push_core

router = APIRouter(prefix="/push", tags=["push"])


# ── Alta de dispositivo ──────────────────────────────────────────────────────
class RegistroDispositivo(BaseModel):
    token: str = Field(..., min_length=10, max_length=512)
    platform: Literal["ios", "android", "web"]
    # El idioma de la interfaz EN ESE MOMENTO. Es la unica via por la que
    # sabemos en que idioma escribirle: no esta en `users`, solo viaja en cada
    # peticion. Ver SPEC_PUSH_REACTIVACION.md.
    lang: Literal["es", "en", "it"] = "es"
    # IANA, de Intl.DateTimeFormat().resolvedOptions().timeZone. Sin esto no se
    # puede cumplir "nada de madrugadas" y el dispositivo queda fuera de los
    # envios hasta que la mande.
    tz: Optional[str] = Field(None, max_length=64)


@router.post("/devices")
def registrar_dispositivo(
    req: RegistroDispositivo,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Alta o refresco. Idempotente a proposito: la app la llama en CADA arranque,
    porque el token cambia solo (reinstalacion, restauracion, rotacion de FCM) y
    el idioma y la zona tambien.

    Si el token ya existe pero era de otra cuenta, la fila se REASIGNA en vez de
    duplicarse: un movil que cambia de usuario no puede seguir recibiendo los
    avisos del anterior.
    """
    dev = db.query(PushDevice).filter(PushDevice.token == req.token).first()
    if dev is None:
        dev = PushDevice(user_id=current_user.id, token=req.token)
        db.add(dev)

    dev.user_id = current_user.id
    dev.platform = req.platform
    dev.lang = req.lang
    dev.tz = (req.tz or "").strip() or dev.tz
    dev.active = True
    db.commit()

    return {"ok": True, "push_enabled": bool(current_user.push_enabled),
            "tz": dev.tz, "lang": dev.lang}


@router.delete("/devices/{token}")
def baja_dispositivo(
    token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Baja de UN aparato: el usuario revoco el permiso del sistema en ese movil.
    Se desactiva, no se borra, para saber que existio.
    """
    dev = (
        db.query(PushDevice)
        .filter(PushDevice.token == token, PushDevice.user_id == current_user.id)
        .first()
    )
    if dev:
        dev.active = False
        db.commit()
    return {"ok": True}


# ── Interruptor ──────────────────────────────────────────────────────────────
class Ajuste(BaseModel):
    enabled: bool


@router.get("/settings")
def leer_ajuste(current_user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    n = (db.query(PushDevice)
           .filter(PushDevice.user_id == current_user.id,
                   PushDevice.active == True)   # noqa: E712
           .count())
    return {"enabled": bool(current_user.push_enabled), "dispositivos": n}


@router.patch("/settings")
def cambiar_ajuste(
    req: Ajuste,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Apagarlas aqui vale para todos sus aparatos a la vez y sobrevive a
    reinstalaciones, al contrario que el permiso del sistema. Apple exige poder
    apagarlas desde dentro de la app.
    """
    current_user.push_enabled = bool(req.enabled)
    db.commit()
    return {"ok": True, "enabled": current_user.push_enabled}


# ── La pasada ────────────────────────────────────────────────────────────────
# Se dispara desde fuera (cron) con una clave propia, no con sesion de usuario:
# quien la llama es una maquina, no una persona. Un admin tambien puede, para
# poder mirarla en seco desde el panel.
PUSH_CRON_KEY = os.environ.get("PUSH_CRON_KEY", "").strip()


@router.post("/run")
def ejecutar_pasada(
    seco: bool = True,
    limite: int = 500,
    x_push_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    `seco=True` (por defecto) recorre seleccion, segmentos y topes SIN llamar a
    Google ni despertar a nadie. Se puede llamar las veces que haga falta.

    Por defecto en seco a proposito: un envio de verdad tiene que pedirse, no
    ocurrir por olvidar un parametro.
    """
    autorizado = False
    if PUSH_CRON_KEY and x_push_key == PUSH_CRON_KEY:
        autorizado = True
    elif authorization:
        try:
            from app.api.routes.auth import decode_token
            uid = decode_token(authorization.split(" ", 1)[1])
            u = db.query(User).filter(User.id == uid).first()
            autorizado = bool(u and u.role == "admin")
        except Exception:
            autorizado = False
    if not autorizado:
        raise HTTPException(status_code=403, detail="Acceso restringido.")

    return push_core.pasada(db, seco=seco, limite=limite)
