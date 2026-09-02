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
