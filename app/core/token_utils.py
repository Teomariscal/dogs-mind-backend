"""
Shared token deduction utility used by analysis and avatar endpoints.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

_log = logging.getLogger(__name__)

PRIVILEGED_ROLES = {"admin", "developer"}  # unlimited tokens, no deduction ever


def deduct_token(
    authorization: Optional[str],
    db: Session,
    amount: float = 1.0,
    require_auth: bool = False,
) -> Optional[float]:
    """
    Deduct `amount` tokens from the authenticated user.

    - If no JWT and require_auth=True  → raises 401.
    - If no JWT and require_auth=False → returns None (anonymous allowed).
    - If user role is admin/collaborator → skips deduction, returns balance.
    - If tokens < amount               → raises 402.
    """
    if not authorization or not authorization.startswith("Bearer "):
        if require_auth:
            raise HTTPException(
                status_code=401,
                detail="Inicia sesión para realizar un análisis.",
            )
        return None

    try:
        from app.api.routes.auth import decode_token
        from app.models.user import User

        user_id = decode_token(authorization.split(" ", 1)[1])
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            if require_auth:
                raise HTTPException(status_code=401, detail="Usuario no encontrado.")
            return None

        # Privileged users never spend tokens
        if getattr(user, "role", "user") in PRIVILEGED_ROLES:
            _log.info("deduct_token: privileged role=%s — skipping deduction for %s", user.role, user.email)
            return float(user.tokens)

        # ── Muro de suscripción (10-ago-2026) ───────────────────────────────
        # Con SUBS_PAYWALL_ENABLED apagado esto no niega nada a nadie.
        # Reglas (prueba de 3 días, saldo heredado, exenciones): core/subscriptions.py
        # Fail-open a propósito: si algo peta calculando el estado, el usuario
        # PASA. Bloquear a un cliente que paga por un bug del muro es peor que
        # dejar pasar un análisis de más.
        try:
            from app.core import subscriptions as _subs

            estado = _subs.access_state(user)
            bloqueado = not estado["allowed"]
            motivo = estado["reason"]
            mensaje = _subs.paywall_message(estado) if bloqueado else ""
        except Exception as exc:                      # noqa: BLE001
            _log.exception("deduct_token: fallo evaluando el muro — dejo pasar (%s)", exc)
            bloqueado, motivo, mensaje = False, "", ""

        if bloqueado:
            _log.info("deduct_token: muro → %s (%s)", user.email, motivo)
            raise HTTPException(status_code=402, detail=mensaje)

        if float(user.tokens) < amount:
            raise HTTPException(status_code=402, detail="Sin tokens. Recarga para continuar.")

        user.tokens = float(user.tokens) - amount
        db.commit()
        _log.info("deduct_token: −%.2f → %s (remaining: %.2f)", amount, user.email, float(user.tokens))
        return float(user.tokens)

    except HTTPException:
        raise
    except Exception as exc:
        _log.exception("deduct_token: unexpected error — %s", exc)
        if require_auth:
            raise HTTPException(status_code=500, detail="Error al verificar tokens.")
        return None


def refund_token(
    authorization: Optional[str],
    db: Session,
    amount: float = 1.0,
) -> Optional[float]:
    """
    Refund `amount` tokens to the authenticated user.

    Designed to roll back a `deduct_token` that succeeded immediately before an
    AI call that then failed. Preserves the invariant: the user is never
    charged for our errors.

    - No auth header  → silent no-op (anonymous flows).
    - Privileged role → silent no-op (they never spent anything to begin with).
    - Any DB/JWT error inside the refund → logged but NEVER raised. The caller
      is already in an error path; surfacing a refund error would mask the
      original Anthropic error to the user.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        from app.api.routes.auth import decode_token
        from app.models.user import User

        user_id = decode_token(authorization.split(" ", 1)[1])
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        if getattr(user, "role", "user") in PRIVILEGED_ROLES:
            return float(user.tokens)

        user.tokens = float(user.tokens) + amount
        db.commit()
        _log.info("refund_token: +%.2f → %s (balance: %.2f)", amount, user.email, float(user.tokens))
        return float(user.tokens)
    except Exception as exc:
        _log.exception("refund_token: failed to refund %.2f — %s", amount, exc)
        return None
