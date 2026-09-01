"""
Códigos de invitación a un plan, por tiempo limitado.

Casos del founder (2026-08-04):
  · Caso 3 — EMBAJADOR: un mes de plan Medio. Si da feedback, se le renueva
    con un código nuevo cada mes; si no, el siguiente mes lo paga él.
  · Caso 4 — INVITADO: un mes de plan Básico, particular o profesional.

Cómo funciona, en una línea: el código concede los créditos del plan y una
vigencia; al terminar, la cuenta vuelve sola a su estado normal y el usuario
compra o espera. Nunca se le retira nada de lo que ya tenía.

Por qué UN código por mes y no una renovación automática: es la palanca que
pidió el founder. El embajador que aporta feedback recibe un código nuevo; el
que no, simplemente no lo recibe y pasa a pagar. Sin bajas incómodas ni
cancelaciones que gestionar.

Cada código es de UN SOLO USO y va ligado al plan, para que no circule.
"""

import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.core import subscriptions as subs
from app.database import get_db
from app.models.invite import Invite
from app.models.user import User

_log = logging.getLogger(__name__)

router = APIRouter(tags=["invites"])

PREFIJOS = {"embajador": "TDMEMB", "invitado": "TDMINV"}


def _nuevo_codigo(tipo: str) -> str:
    alfabeto = string.ascii_uppercase + string.digits
    cuerpo = "".join(secrets.choice(alfabeto) for _ in range(6))
    return f"{PREFIJOS.get(tipo, 'TDM')}-{cuerpo}"


# ── Canje ───────────────────────────────────────────────────────────────────
class CanjeIn(BaseModel):
    code: str = Field(..., min_length=4, max_length=40)


@router.post("/invites/redeem")
def canjear(
    body: CanjeIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    codigo = body.code.strip().upper()
    inv = db.query(Invite).filter(Invite.code == codigo).with_for_update().first()
    if not inv:
        raise HTTPException(status_code=404, detail="Ese código no existe.")
    abierto = (inv.tipo or "") == "abierto"

    # Los codigos ABIERTOS no se gastan: los usa cualquiera que los tenga, tantas
    # veces como haga falta. Lo unico que los frena es 'activo' (founder,
    # 1-sep-2026). Los normales siguen siendo de un solo uso.
    if getattr(inv, "activo", True) is False:
        raise HTTPException(status_code=410, detail="Ese código ya no está activo.")
    if not abierto and inv.used_by_id:
        raise HTTPException(status_code=409, detail="Ese código ya se ha usado.")
    if inv.expires_at and datetime.utcnow() > inv.expires_at:
        raise HTTPException(status_code=410, detail="Ese código ha caducado.")

    plan = subs.plan_by_id(inv.plan_id)
    if not plan:
        raise HTTPException(status_code=500, detail="El plan del código ya no existe.")

    dias = int(inv.days or 30)
    hasta = datetime.utcnow() + timedelta(days=dias)
    creditos = float(plan["credits"]) / subs.CREDITS_PER_TOKEN

    # Canjear dos veces el mismo mes no regala el doble: se mira el ciclo.
    ciclo = "invitacion:%s:%s" % (plan["id"], hasta.strftime("%Y%m"))
    ya_este_ciclo = (current_user.subscription_last_grant or "") == ciclo

    # Concede los créditos del plan y deja la suscripción viva ese tiempo.
    # NO renueva sola: al vencer, la cuenta vuelve a la norma general.
    # Hasta cuando dura la invitacion. meses=None -> sin tope (equipo);
    # meses=N -> N abonos mensuales y se acaba (founder, 1-sep-2026).
    meses = getattr(inv, "meses", 1)
    current_user.invite_until = None if meses is None else (
        datetime.utcnow() + timedelta(days=30 * int(meses)))

    if not ya_este_ciclo:
        current_user.tokens = float(current_user.tokens or 0) + creditos
        current_user.subscription_last_grant = ciclo
    current_user.subscription_plan = plan["id"]
    current_user.subscription_status = "active"
    current_user.subscription_store = "invitacion"
    current_user.subscription_expires_at = hasta
    if not current_user.subscription_started_at:
        current_user.subscription_started_at = datetime.utcnow()
    # Un codigo abierto NO cambia el tipo de cuenta: vale igual a un profesional
    # y a un particular, y cada uno se queda como esta.
    if not abierto and inv.account_type == "professional":
        current_user.account_type = "professional"

    if not abierto:
        inv.used_by_id = current_user.id
        inv.used_at = datetime.utcnow()
    db.commit()
    _log.info("invite: %s canjeado por %s → plan=%s %sd",
              codigo, current_user.email, plan["id"], dias)

    nombre = (plan.get("name") or {}).get("es", plan["id"])
    return {
        "ok": True,
        "plan": plan["id"],
        "plan_name": nombre,
        "days": dias,
        "credits": int(plan["credits"]),
        "expires_at": hasta.isoformat() + "Z",
        "message": f"Listo. Tienes el plan {nombre} durante {dias} días, "
                   f"con {plan['credits']} créditos.",
    }


# ── Administración ──────────────────────────────────────────────────────────
class GenerarIn(BaseModel):
    tipo: str = Field("embajador", description="embajador | invitado")
    plan_id: Optional[str] = None      # por defecto: medio para embajador, basico para invitado
    days: int = 30
    cantidad: int = 1
    account_type: str = "particular"
    nota: Optional[str] = None
    valido_dias: int = 60              # cuánto tiempo puede canjearse el código


@router.post("/admin/invites")
def generar(
    body: GenerarIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if (current_user.role or "user") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin.")
    plan_id = body.plan_id or ("medio" if body.tipo == "embajador" else "basico")
    if not subs.plan_by_id(plan_id):
        raise HTTPException(status_code=400, detail="Plan desconocido.")

    codigos = []
    for _ in range(max(1, min(200, body.cantidad))):
        inv = Invite(
            code=_nuevo_codigo(body.tipo),
            tipo=body.tipo,
            plan_id=plan_id,
            days=body.days,
            account_type=body.account_type,
            note=body.nota,
            expires_at=datetime.utcnow() + timedelta(days=body.valido_dias),
        )
        db.add(inv)
        codigos.append(inv.code)
    db.commit()
    return {"ok": True, "plan": plan_id, "days": body.days, "codes": codigos}


@router.get("/admin/invites")
def listar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if (current_user.role or "user") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin.")
    filas = []
    for i in db.query(Invite).order_by(Invite.created_at.desc()).limit(200).all():
        u = db.query(User).filter(User.id == i.used_by_id).first() if i.used_by_id else None
        filas.append({
            "code": i.code, "tipo": i.tipo, "plan": i.plan_id, "days": i.days,
            "usado_por": u.email if u else None,
            "usado_el": i.used_at.isoformat() + "Z" if i.used_at else None,
            "caduca": i.expires_at.isoformat() + "Z" if i.expires_at else None,
            "nota": i.note,
        })
    return {"invites": filas}
