"""
Paseos (World Wide Dog Walking) — cobro del uso.

POST /walks/charge — cobra el paseo al usuario autenticado y devuelve el saldo.

Precio: 0,1 tokens = 10 créditos por planificación de rutas (precio de salida
fijado por el founder el 2026-07-30; lo revisará según el uso real). Regla de
fondo: ningún uso es gratis, aunque el coste de infraestructura sea ~0 — los
mapas son OpenStreetMap/OSRM, lo que se cobra es el servicio.

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

WALK_TOKEN_COST = 0.1  # 10 créditos


@router.post("/charge")
def charge_walk(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    saldo = deduct_token(authorization, db, amount=WALK_TOKEN_COST, require_auth=True)
    return {"ok": True, "tokens": saldo, "credits": int(round((saldo or 0) * 100))}
