"""
Shared token deduction utility used by analysis and avatar endpoints.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

_log = logging.getLogger(__name__)

PRIVILEGED_ROLES = {"admin", "collaborator"}


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
