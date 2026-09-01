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

        # ── PARTNER: acceso libre con tope de coste (founder 2026-08-04) ────
        # Tope: 8 €/mes de coste NUESTRO = 380 tokens al mes (0,021 €/token).
        # Mientras le quede cupo no gasta su saldo ni ve el muro. Agotado el
        # cupo, cae a la norma general: gasta sus créditos o espera al mes que
        # viene. El contador se reinicia solo al cambiar de mes natural.
        # Fail-open: si algo falla aquí, el usuario sigue por el camino normal.
        if (getattr(user, "role", "user") or "user") == "partner":
            try:
                from datetime import datetime as _dt
                import os as _os

                cupo = float(_os.environ.get("PARTNER_MONTHLY_TOKENS", "380"))
                mes = _dt.utcnow().strftime("%Y-%m")
                if (user.partner_month or "") != mes:
                    user.partner_month = mes
                    user.partner_spent = 0
                gastado = float(user.partner_spent or 0)
                if gastado + amount <= cupo:
                    user.partner_spent = gastado + amount
                    db.commit()
                    _log.info("partner: %s −%.2f del cupo (%.2f/%.0f este mes)",
                              user.email, amount, gastado + amount, cupo)
                    return float(user.tokens)
                _log.info("partner: %s AGOTÓ el cupo del mes (%.2f/%.0f) — pasa a saldo normal",
                          user.email, gastado, cupo)
            except Exception as exc:  # noqa: BLE001
                _log.exception("partner: fallo evaluando el cupo — sigo normal (%s)", exc)

        # ── CORPORATE: bolsa de la institución (founder 2026-08-04) ─────────
        # El afiliado (p. ej. alumno) gasta de la bolsa de su universidad, no
        # de su bolsillo. Si agota su cupo o la bolsa se acaba, NO se le corta
        # en seco: cae a la norma general y compra o espera.
        # Fail-open: cualquier fallo aquí y sigue por el camino normal.
        if getattr(user, "corporate_id", None) and \
           (getattr(user, "corporate_status", "") or "") == "active":
            try:
                from app.models.corporate import Corporate

                corp = db.query(Corporate).filter(
                    Corporate.id == user.corporate_id).with_for_update().first()
                if corp and corp.vigente():
                    cupo = float(corp.member_cap_tokens or 0)
                    usado = float(user.corporate_spent or 0)
                    dentro_de_cupo = (cupo <= 0) or (usado + amount <= cupo)
                    if dentro_de_cupo and corp.bolsa_restante() >= amount:
                        corp.pool_spent = float(corp.pool_spent or 0) + amount
                        user.corporate_spent = usado + amount
                        db.commit()
                        _log.info("corporate: %s −%.2f de %s (bolsa %.2f/%.2f)",
                                  user.email, amount, corp.code,
                                  float(corp.pool_spent), float(corp.pool_tokens))
                        return float(user.tokens)
                    _log.info("corporate: %s sin cupo o bolsa agotada en %s — pasa a su saldo",
                              user.email, corp.code)
                elif corp:
                    _log.info("corporate: acuerdo %s caducado — %s pasa a su saldo",
                              corp.code, user.email)
            except Exception as exc:  # noqa: BLE001
                _log.exception("corporate: fallo evaluando la bolsa — sigo normal (%s)", exc)

        # ── Muro de suscripción (10-ago-2026) ───────────────────────────────
        # Con SUBS_PAYWALL_ENABLED apagado esto no niega nada a nadie.
        # Reglas (prueba de 3 días, saldo heredado, exenciones): core/subscriptions.py
        # Fail-open a propósito: si algo peta calculando el estado, el usuario
        # PASA. Bloquear a un cliente que paga por un bug del muro es peor que
        # dejar pasar un análisis de más.
        try:
            from app.core import subscriptions as _subs

            estado = _subs.access_state(user, amount=amount)
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
            raise HTTPException(status_code=402, detail="Sin créditos. Recarga para continuar.")

        user.tokens = float(user.tokens) - amount
        db.commit()
        _log.info("deduct_token: −%.2f → %s (remaining: %.2f)", amount, user.email, float(user.tokens))
        return float(user.tokens)

    except HTTPException:
        raise
    except Exception as exc:
        _log.exception("deduct_token: unexpected error — %s", exc)
        if require_auth:
            raise HTTPException(status_code=500, detail="Error al verificar el saldo.")
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

        # Devolver a la MISMA caja de la que se cobró (2026-08-06). Antes esto
        # sumaba siempre al saldo personal: al partner y al alumno corporativo
        # se les descontaba del cupo o de la bolsa de su institución y nunca se
        # les restituía, mientras se les regalaba saldo que no habían gastado.
        if (getattr(user, "role", "user") or "user") == "partner" and \
           float(getattr(user, "partner_spent", 0) or 0) >= amount:
            user.partner_spent = float(user.partner_spent) - amount
            db.commit()
            _log.info("refund_token: +%.2f al CUPO de partner %s", amount, user.email)
            return float(user.tokens)

        if getattr(user, "corporate_id", None) and \
           (getattr(user, "corporate_status", "") or "") == "active" and \
           float(getattr(user, "corporate_spent", 0) or 0) >= amount:
            from app.models.corporate import Corporate

            corp = db.query(Corporate).filter(Corporate.id == user.corporate_id).first()
            user.corporate_spent = float(user.corporate_spent) - amount
            if corp:
                corp.pool_spent = max(0.0, float(corp.pool_spent or 0) - amount)
            db.commit()
            _log.info("refund_token: +%.2f a la BOLSA de %s (%s)", amount,
                      corp.code if corp else "?", user.email)
            return float(user.tokens)

        user.tokens = float(user.tokens) + amount
        db.commit()
        _log.info("refund_token: +%.2f → %s (balance: %.2f)", amount, user.email, float(user.tokens))
        return float(user.tokens)
    except Exception as exc:
        _log.exception("refund_token: failed to refund %.2f — %s", amount, exc)
        return None
