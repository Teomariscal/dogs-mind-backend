"""
Suscripciones — estado, activación tras compra y webhook de RevenueCat.

Endpoints:
- GET  /subscription/status    → catálogo de planes + estado del usuario
- POST /subscription/activate  → la app confirma una compra (IAP) y abona créditos

Las renovaciones y cancelaciones las trae el webhook que YA existe en
payments.py (/webhooks/revenuecat), que tiene idempotencia atómica por
`Payment.stripe_session_id = rc_<event_id>` y bloqueo de fila. No se duplica
aquí: este módulo solo aporta el catálogo, el estado y la activación inmediata.

Los créditos del plan se abonan UNA vez por ciclo: la clave del ciclo se guarda
en `users.subscription_last_grant`, así un reintento no duplica saldo.

Mientras SUBS_PAYWALL_ENABLED esté apagado, /status responde igual pero nadie
tiene el acceso bloqueado (`allowed: true`, reason `paywall_off`).

Reglas del modelo: app/core/subscriptions.py
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.core import subscriptions as subs
from app.database import get_db
from app.models.user import User

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/subscription", tags=["subscriptions"])


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() + "Z" if dt else None


def _public_plans() -> list:
    """Catálogo tal cual lo consume la pantalla de planes."""
    out = []
    base = None
    for p in subs.plans():
        if p.get("id") == "basico":
            base = p
    for p in subs.plans():
        credits = int(p.get("credits", 0))
        price = float(p.get("price", 0) or 0)
        per_euro = credits / price if price else 0
        ahorro = 0
        if base and base.get("price"):
            base_ratio = int(base["credits"]) / float(base["price"])
            if base_ratio:
                ahorro = round((1 - (base_ratio / per_euro)) * 100) if per_euro else 0
        out.append({
            **p,
            "credits_per_euro": round(per_euro),
            # Cuánto más barato sale el crédito respecto al Básico (regla del founder:
            # el escalón se mide contra el Básico, no contra el plan anterior).
            "savings_vs_basic_pct": max(0, ahorro),
            "full_consults": round(credits / 320, 1),
        })
    return out


# ── GET /subscription/status ────────────────────────────────────────────────
@router.get("/status")
def subscription_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    state = subs.access_state(current_user)
    plan = subs.plan_by_id(state.get("plan") or "")
    return {
        "paywall_enabled": state["paywall_enabled"],
        "allowed": state["allowed"],
        "reason": state["reason"],
        "message": None if state["allowed"] else subs.paywall_message(state),
        "credits": state["credits"],
        "tokens": state["tokens"],
        "credits_per_token": subs.CREDITS_PER_TOKEN,
        "legacy": state["legacy"],
        "legacy_threshold_credits": int(subs.ANALYSIS_TOKENS * subs.CREDITS_PER_TOKEN),
        "trial": {
            "days": subs.TRIAL_DAYS,
            "welcome_credits": subs.WELCOME_CREDITS,
            "active": state["trial_active"],
            "days_left": state["trial_days_left"],
            "ends_at": _iso(state["trial_ends_at"]),
        },
        "subscription": {
            "plan": state["plan"],
            "plan_name": (plan or {}).get("name", {}).get("es") if plan else None,
            "status": state["subscription_status"],
            "store": getattr(current_user, "subscription_store", None),
            "expires_at": _iso(state["subscription_expires_at"]),
            "active": subs.subscription_active(current_user),
        },
        "plans": _public_plans(),
    }


# ── POST /subscription/activate ─────────────────────────────────────────────
class ActivateIn(BaseModel):
    plan_id: Optional[str] = Field(None, description="basico|medio|pro|max")
    product_id: Optional[str] = Field(None, description="id de producto de la tienda")
    store: str = Field("apple", description="apple|google|stripe")
    transaction_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    is_trial: bool = False


def _grant_cycle(user: User, plan: dict, db: Session, cycle_key: str, status_value: str,
                 store: str, expires_at: Optional[datetime]) -> dict:
    """Abona los créditos del ciclo si no se han abonado ya. Idempotente."""
    already = (user.subscription_last_grant or "") == cycle_key
    plan_tokens = float(plan["credits"]) / subs.CREDITS_PER_TOKEN

    user.subscription_plan = plan["id"]
    user.subscription_status = status_value
    user.subscription_store = store
    user.subscription_expires_at = expires_at
    if not user.subscription_started_at:
        user.subscription_started_at = datetime.utcnow()

    granted = 0.0
    if not already:
        user.tokens = float(user.tokens or 0) + plan_tokens
        user.subscription_last_grant = cycle_key
        granted = plan_tokens

    db.commit()
    db.refresh(user)
    _log.info(
        "subscription: %s → plan=%s status=%s store=%s cycle=%s granted=%.2ftk saldo=%.2ftk",
        user.email, plan["id"], status_value, store, cycle_key, granted, float(user.tokens),
    )
    return {
        "ok": True,
        "already_granted": already,
        "granted_credits": int(granted * subs.CREDITS_PER_TOKEN),
        "credits": int(round(float(user.tokens) * subs.CREDITS_PER_TOKEN)),
        "plan": plan["id"],
        "status": status_value,
        "expires_at": _iso(expires_at),
    }


@router.post("/activate")
def activate_subscription(
    body: ActivateIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    La app llama aquí tras una compra correcta (RevenueCat ya ha validado el
    recibo con la tienda). El webhook es la fuente de verdad de las renovaciones;
    esto es lo que hace que el usuario vea sus créditos al instante.
    """
    plan = subs.plan_by_id(body.plan_id or "") or subs.plan_by_product_id(body.product_id or "")
    if not plan:
        raise HTTPException(status_code=400, detail="Plan desconocido.")

    expires = body.expires_at or (datetime.utcnow() + timedelta(days=30))
    cycle_key = f"{body.store}:{plan['id']}:{expires.strftime('%Y%m%d%H%M')}"
    status_value = "trialing" if body.is_trial else "active"
    return _grant_cycle(current_user, plan, db, cycle_key, status_value, body.store, expires)

# ── POST /subscription/redeem-code ──────────────────────────────────────────
class CodigoIn(BaseModel):
    code: str = Field(..., min_length=3, max_length=64)


@router.post("/redeem-code")
def redeem_team_code(
    body: CodigoIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Canjea el código de equipo: la cuenta queda EXENTA del muro para siempre,
    sin suscripción y sin caducidad. Pensado para el equipo y los invitados
    del founder (2026-08-04).

    No regala créditos: quita el muro. Los créditos se siguen descontando
    igual, así que el consumo se mide (regla: ningún uso es gratis).
    """
    esperado = subs.team_code()
    if not esperado:
        raise HTTPException(status_code=503, detail="No hay ningún código activo.")
    if (body.code or "").strip().upper() != esperado:
        raise HTTPException(status_code=400, detail="Ese código no es válido.")

    if subs.is_exempt(current_user):
        return {"ok": True, "ya_activo": True,
                "message": "Tu cuenta ya tenía acceso de equipo."}

    current_user.subscription_status = "exempt"
    current_user.subscription_plan = "equipo"
    current_user.subscription_store = "codigo"
    current_user.subscription_expires_at = None
    if not current_user.subscription_started_at:
        current_user.subscription_started_at = datetime.utcnow()
    db.commit()
    _log.info("subscription: %s → EXENTO por código de equipo", current_user.email)
    return {"ok": True, "ya_activo": False,
            "message": "Listo. Tu cuenta tiene acceso de equipo, sin suscripción."}
