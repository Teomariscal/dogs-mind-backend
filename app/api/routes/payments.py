import os
import uuid
import stripe
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.payment import Payment
from app.api.routes.auth import get_current_user

router = APIRouter(tags=["payments"])

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

APP_URL = os.environ.get("APP_URL", "https://thedogsmindbeta.netlify.app")

# Retorno de Stripe multi-dominio (2026-08-04): la misma API sirve a varios
# frontends (thedogsmind.net y abacompanion.net). Si el Origin de la petición
# está en la allowlist de CORS, el usuario vuelve a SU web tras pagar; si no,
# se usa APP_URL como hasta ahora (cero cambio para el tráfico existente).
def _return_base(origin: str | None) -> str:
    try:
        from app.main import _ALLOWED_ORIGINS
        o = (origin or "").strip().rstrip("/")
        if o and o in _ALLOWED_ORIGINS and o.startswith("https://"):
            return o
    except Exception:
        pass
    return APP_URL

# Packs disponibles (1 token ≈ €1 → análisis=3tok, chat=0.25tok, avatar=0.10tok)
PACKS = {
    5:  {"tokens": 5,  "amount_cents": 499,  "label": "5 Tokens Dogs Mind"},
    20: {"tokens": 20, "amount_cents": 1600, "label": "20 Tokens Dogs Mind"},
    60: {"tokens": 60, "amount_cents": 4200, "label": "60 Tokens Dogs Mind"},
}

# ── Profesional flow ─────────────────────────────────────────────────────────
# Pago único anual de la membresía Profesional (20 €) + opcionalmente el pack
# promo de 60 tokens al 10 % de descuento (37,80 € en lugar de 42 €). Los
# price_id se crean con scripts/create_stripe_products.py y se inyectan en
# Railway (env vars). El webhook hace 3 cosas al confirmarse el pago:
#   1. user.account_type = 'professional'
#   2. acredita 10 tokens (cortesía membresía)
#   3. si with_bundle=True → acredita 60 tokens más
#
# Invariantes (decisión Teo + CFO 2026-05-04):
#   - Pago único, no suscripción auto-renovable (Apple-friendly cuando suba IAP).
#   - Bundle disponible SOLO al activar la membresía, no en compras posteriores.
#   - Una cuenta ya profesional no puede volver a "comprar" la membresía.
PRICE_PRO_MEMBERSHIP   = os.environ.get("STRIPE_PRICE_PRO_MEMBERSHIP", "").strip()
PRICE_PRO_TOKEN_BUNDLE = os.environ.get("STRIPE_PRICE_PRO_TOKEN_BUNDLE", "").strip()

PRO_MEMBERSHIP_TOKENS = 10  # tokens cortesía al activar Profesional
PRO_BUNDLE_TOKENS     = 60  # tokens del pack promo si compra bundle

# ── Invitación cortesía Profesional ──────────────────────────────────────────
# Sistema paralelo al de embajador (auth.py AMBASSADOR_CODE). Permite a Teo
# invitar selectos a registrarse como Profesional SIN PAGAR los 20€ de membresía.
# El usuario invitado recibe account_type='professional' + PRO_MEMBERSHIP_TOKENS
# (10) tokens cortesía. Puede comprar packs de tokens después como cualquier
# Pro pagador. Membresía permanente (no caduca).
PRO_INVITE_CODE = os.environ.get("PRO_INVITE_CODE", "").strip()

# ── Promo Profesional GRATIS (toggleable por env var) ────────────────────────
# Mientras esta env var sea true, CUALQUIER usuario autenticado puede activar
# Profesional sin pagar los 20€ vía POST /payments/pro-activate-promo. NO recibe
# tokens cortesía extra: mantiene únicamente los tokens que tiene por su signup
# (el welcome bonus normal). El frontend consulta GET /payments/pro-promo-status
# (público, sin auth) para saber si pintar el botón "Activar GRATIS · Promo" en
# lugar del flujo Stripe. Para terminar la promo: PRO_PROMO_FREE=false (o sin
# definir) en Railway → redeploy del backend → frontend detecta automáticamente
# y vuelve al flujo Stripe normal sin redeploy de frontend.
#
# IMPORTANTE: este flujo es paralelo al de PRO_INVITE_CODE (BOCALAN-AMB) y NO
# lo sustituye. Los embajadores siguen entrando con código + reciben sus
# PRO_MEMBERSHIP_TOKENS. La promo abierta es para captación durante el lanzamiento.
PRO_PROMO_FREE = os.environ.get("PRO_PROMO_FREE", "").strip().lower() in ("1", "true", "yes", "on")

# ── RevenueCat IAP (iOS) — paralelo a Stripe (guideline 3.1.1) ────────────────
# Las compras dentro del binario iOS van por In-App Purchase vía RevenueCat. Este
# bloque NO toca el flujo Stripe (web): es additive y aislado. RevenueCat envía un
# POST a /webhooks/revenuecat por cada evento. Verificación = header Authorization
# con secreto compartido configurado en el dashboard de RevenueCat (Project >
# Integrations > Webhooks) y en Railway (REVENUECAT_WEBHOOK_AUTH). El app_user_id
# del evento == User.id (el frontend llama Purchases.logIn(str(user.id))).
# Idempotencia: reutilizamos Payment.stripe_session_id guardando "rc_<event_id>"
# (columna unique) → cero migración de DB.
REVENUECAT_WEBHOOK_AUTH = os.environ.get("REVENUECAT_WEBHOOK_AUTH", "").strip()

# store identifier (product_id que envía RevenueCat) → tokens a acreditar
RC_TOKEN_PRODUCTS = {
    "net.thedogsmind.tokens.5":  5,
    "net.thedogsmind.tokens.20": 20,
    "net.thedogsmind.tokens.60": 60,
}
RC_PRO_PRODUCT = "net.thedogsmind.pro.yearly"


class CheckoutRequest(BaseModel):
    pack: int  # 5, 20 o 60


# ── Crear sesión de pago ───────────────────────────────────────────────────────
@router.post("/payments/checkout")
def create_checkout(
    req: CheckoutRequest,
    origin: Optional[str] = Header(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pack = PACKS.get(req.pack)
    if not pack:
        raise HTTPException(status_code=400, detail="Pack inválido. Elige 5, 20 o 60.")

    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="STRIPE_SECRET_KEY no configurada en el servidor")

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "unit_amount": pack["amount_cents"],
                    "product_data": {"name": pack["label"]},
                },
                "quantity": 1,
            }],
            metadata={
                "user_id": str(current_user.id),
                "tokens":  str(pack["tokens"]),
            },
            customer_email=current_user.email,
            success_url=f"{_return_base(origin)}?payment=success&tokens={pack['tokens']}",
            cancel_url=f"{_return_base(origin)}?payment=cancelled",
        )
    except stripe.error.AuthenticationError:
        raise HTTPException(status_code=500, detail="STRIPE_SECRET_KEY inválida. Revisa la variable en Railway.")
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=500, detail=f"Error de Stripe: {str(e)}")

    # Registrar pago pendiente
    payment = Payment(
        user_id=current_user.id,
        stripe_session_id=session.id,
        tokens=pack["tokens"],
        amount_cents=pack["amount_cents"],
        status="pending",
    )
    db.add(payment)
    db.commit()

    return {"checkout_url": session.url}


# ── Suscripción por Stripe (web) ──────────────────────────────────────────────
class PlanCheckoutRequest(BaseModel):
    plan_id: str  # basico | medio | pro | max


@router.post("/payments/plan-checkout")
def create_plan_checkout(
    req: PlanCheckoutRequest,
    origin: Optional[str] = Header(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Checkout de suscripción mensual para la WEB. En iOS/Android la compra va por
    la tienda (RevenueCat) — aquí no.

    El price_id de Stripe se toma de la env var que declara el plan
    (STRIPE_PRICE_BASICO, …). Si no está configurada todavía, se responde 503
    con un mensaje claro en vez de crear un cobro a medias.
    """
    from app.core import subscriptions as _subs

    plan = _subs.plan_by_id(req.plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail="Plan desconocido.")
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="STRIPE_SECRET_KEY no configurada en el servidor")

    price_id = os.environ.get(plan.get("stripe_price_env", ""), "").strip()
    if not price_id:
        raise HTTPException(
            status_code=503,
            detail="Este plan aún no está disponible para pago por web. Suscríbete desde la app.",
        )

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            metadata={"user_id": str(current_user.id), "plan_id": plan["id"]},
            subscription_data={"metadata": {"user_id": str(current_user.id), "plan_id": plan["id"]}},
            customer_email=current_user.email,
            success_url=f"{_return_base(origin)}?sub=ok&plan={plan['id']}",
            cancel_url=f"{_return_base(origin)}?sub=cancelled",
        )
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=500, detail=f"Error de Stripe: {str(e)}")

    return {"checkout_url": session.url}


# ── Crear sesión de pago — flujo Profesional ──────────────────────────────────
class ProCheckoutRequest(BaseModel):
    with_bundle: bool = False  # añade el pack 60 tokens promo (37,80 €) opcional


@router.post("/payments/pro-checkout")
def create_pro_checkout(
    req: ProCheckoutRequest,
    origin: Optional[str] = Header(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Crea una Stripe Checkout Session para activar la cuenta Profesional.
    Pago único (no suscripción) — el webhook activa el tier al confirmarse.

    Salvaguarda promo: si PRO_PROMO_FREE=true en Railway, este endpoint queda
    deshabilitado (503) para que ningún flujo cobre durante la promo, incluso
    si el frontend tuviese un bug o un usuario hiciese curl directo. El cliente
    debe usar /payments/pro-activate-promo en su lugar.
    """
    # ── Salvaguarda: durante la promo GRATIS no se cobra a nadie ──
    if PRO_PROMO_FREE:
        raise HTTPException(
            status_code=503,
            detail="Promo Profesional GRATIS activa: la activación pasa por /payments/pro-activate-promo en lugar de Stripe.",
        )
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="STRIPE_SECRET_KEY no configurada en el servidor")
    if not PRICE_PRO_MEMBERSHIP:
        raise HTTPException(status_code=500, detail="STRIPE_PRICE_PRO_MEMBERSHIP no configurado")
    if req.with_bundle and not PRICE_PRO_TOKEN_BUNDLE:
        raise HTTPException(status_code=500, detail="STRIPE_PRICE_PRO_TOKEN_BUNDLE no configurado")
    if current_user.account_type == "professional":
        raise HTTPException(
            status_code=400,
            detail="Tu cuenta ya es Profesional. No es necesario volver a activarla.",
        )

    # Construir line_items según with_bundle
    line_items = [{"price": PRICE_PRO_MEMBERSHIP, "quantity": 1}]
    if req.with_bundle:
        line_items.append({"price": PRICE_PRO_TOKEN_BUNDLE, "quantity": 1})

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=line_items,
            metadata={
                "kind":         "pro_membership",
                "user_id":      str(current_user.id),
                "with_bundle":  "true" if req.with_bundle else "false",
            },
            customer_email=current_user.email,
            success_url=f"{_return_base(origin)}?payment=pro_success",
            cancel_url=f"{_return_base(origin)}?payment=pro_cancelled",
        )
    except stripe.error.AuthenticationError:
        raise HTTPException(status_code=500, detail="STRIPE_SECRET_KEY inválida. Revisa la variable en Railway.")
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=500, detail=f"Error de Stripe: {str(e)}")

    # Registrar pago pendiente. Reusamos el modelo Payment, los tokens del bundle
    # quedan reflejados en el `tokens` del Payment para histórico (la membresía
    # en sí no son tokens, pero registramos los tokens cortesía + bundle).
    expected_tokens = PRO_MEMBERSHIP_TOKENS + (PRO_BUNDLE_TOKENS if req.with_bundle else 0)
    expected_amount = 2000 + (3780 if req.with_bundle else 0)
    payment = Payment(
        user_id=current_user.id,
        stripe_session_id=session.id,
        tokens=expected_tokens,
        amount_cents=expected_amount,
        status="pending",
    )
    db.add(payment)
    db.commit()

    return {"checkout_url": session.url}


# ── Activación cortesía Profesional (sin pago, invite-only) ──────────────────
class ProCourtesyRequest(BaseModel):
    invite_code: str


# ── Rate limit anti brute-force del invite_code ──────────────────────────────
# Tracking in-memory de intentos fallidos (HTTP 403) por IP. Se limpia al
# reiniciar Railway (aceptable: atacante no puede forzar restart). Para deploys
# multi-instancia habría que usar Redis. Hoy 1 worker → suficiente.
#
# Política: 5 fallos por hora por IP. Tras superar, bloqueo con 429 hasta que
# expire la entrada más antigua (sliding window).
from collections import defaultdict as _defaultdict
from datetime import datetime as _dt, timedelta as _td

_COURTESY_FAILS: dict = _defaultdict(list)  # ip → list[datetime de fallos]
COURTESY_MAX_FAILS_PER_HOUR = 5


def _client_ip(request: Request) -> str:
    """IP del cliente, respetando X-Forwarded-For del proxy Railway."""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _courtesy_is_blocked(ip: str) -> tuple[bool, int]:
    """Devuelve (bloqueado, retry_after_segundos). Limpia entradas expiradas."""
    now = _dt.utcnow()
    cutoff = now - _td(hours=1)
    fails = [t for t in _COURTESY_FAILS.get(ip, []) if t > cutoff]
    _COURTESY_FAILS[ip] = fails
    if len(fails) >= COURTESY_MAX_FAILS_PER_HOUR:
        # Bloqueado hasta que expire la entrada más antigua
        oldest = fails[0]
        retry = int((oldest + _td(hours=1) - now).total_seconds())
        return True, max(retry, 60)
    return False, 0


def _courtesy_record_fail(ip: str) -> None:
    """Registra un intento fallido para el sliding window."""
    _COURTESY_FAILS[ip].append(_dt.utcnow())


@router.post("/payments/pro-activate-courtesy")
def pro_activate_courtesy(
    req: ProCourtesyRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Activa cuenta Profesional cortesía (sin pago Stripe). Requiere que el
    invite_code coincida con la env var PRO_INVITE_CODE.

    Flujo:
      1. Rate limit check (max 5 fallos/h por IP, anti brute-force).
      2. Validar que PRO_INVITE_CODE está configurado en el backend.
      3. Validar que el código enviado coincide (case-sensitive, trim espacios).
         Si NO coincide → registra fallo + 403.
      4. Rechazar si la cuenta ya es Profesional (idempotente, NO cuenta como fallo).
      5. Activar account_type='professional' y sumar PRO_MEMBERSHIP_TOKENS
         (10) tokens cortesía.
      6. Membresía permanente: NO se programa caducidad. Si gastan los tokens,
         pueden comprar packs como cualquier Pro pagador.

    Diseñado para 3B del producto: solo email+password al activarse, los datos
    de empresa (CIF, logo, ciudad…) se completan después desde el área Pro.

    Rate-limit (2026-05-16, anti brute-force):
      - 5 intentos fallidos (HTTP 403) por IP por hora → bloqueo 429
      - Solo cuentan fallos de credencial (403), no errores de servidor (503)
      - Intentos exitosos (200) no cuentan ni resetean el contador
      - Tracking en memoria del proceso (no Redis), se resetea al restart
    """
    ip = _client_ip(request)

    # 1. Rate limit (antes de cualquier procesamiento)
    blocked, retry_after = _courtesy_is_blocked(ip)
    if blocked:
        print(f"[Pro-Courtesy] RATE-LIMITED IP={ip} retry_after={retry_after}s")
        raise HTTPException(
            status_code=429,
            detail=f"Demasiados intentos fallidos. Espera {(retry_after // 60) + 1} minutos antes de volver a intentar.",
            headers={"Retry-After": str(retry_after)},
        )

    # 2. Servicio configurado
    if not PRO_INVITE_CODE:
        raise HTTPException(
            status_code=503,
            detail="Activación cortesía no disponible: PRO_INVITE_CODE no configurado en el servidor.",
        )

    # 3. Validar código
    if req.invite_code.strip() != PRO_INVITE_CODE:
        _courtesy_record_fail(ip)
        fail_count = len(_COURTESY_FAILS[ip])
        print(f"[Pro-Courtesy] INVALID CODE IP={ip} fails_in_window={fail_count}")
        raise HTTPException(
            status_code=403,
            detail="Código de invitación profesional inválido.",
        )

    # 4. Idempotencia (no cuenta como fallo: el usuario ya está bien, no es ataque)
    if current_user.account_type == "professional":
        raise HTTPException(
            status_code=400,
            detail="Tu cuenta ya es Profesional.",
        )
    current_user.account_type = "professional"
    current_user.tokens = float(current_user.tokens) + PRO_MEMBERSHIP_TOKENS
    db.commit()
    print(
        f"[Pro-Courtesy] {current_user.email} activado Profesional cortesía · "
        f"+{PRO_MEMBERSHIP_TOKENS} tokens · saldo={current_user.tokens}"
    )
    return {
        "ok": True,
        "account_type": "professional",
        "tokens": float(current_user.tokens),
        "credited": PRO_MEMBERSHIP_TOKENS,
    }


# ── Promo Profesional GRATIS ──────────────────────────────────────────────────
@router.get("/payments/pro-promo-status")
def pro_promo_status():
    """
    Endpoint público (sin auth) que indica si la promo Profesional GRATIS está
    activa en el backend. El frontend lo consulta al cargar s-pro-activate para
    decidir entre pintar el botón "Activar GRATIS · Promo" o el flujo Stripe.

    No expone nada sensible: solo un boolean. Útil para que el frontend pueda
    enseñar el copy adecuado SIN tener que esperar a clickar el botón.
    """
    return {"promo_active": PRO_PROMO_FREE}


@router.post("/payments/pro-activate-promo")
def pro_activate_promo(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Activa cuenta Profesional GRATIS durante la promo (sin código de invitación,
    sin Stripe). Disponible mientras PRO_PROMO_FREE=true en Railway.

    Diferencias respecto a /pro-activate-courtesy:
      - NO requiere invite_code (la promo es abierta).
      - NO suma PRO_MEMBERSHIP_TOKENS — el usuario mantiene únicamente los
        tokens que ya tiene por su signup (decisión Teo 2026-05-26: durante la
        promo solo regalamos el ESTATUS, no tokens extra).

    Flujo:
      1. Verificar que la promo está activa (PRO_PROMO_FREE).
      2. Idempotencia: si ya es Pro, 400.
      3. Activar account_type='professional'. NO tocar tokens.

    Cuando se acabe la promo: PRO_PROMO_FREE=false → este endpoint devuelve 503.
    Membresía permanente: NO se programa caducidad.
    """
    # 1. Servicio activo
    if not PRO_PROMO_FREE:
        raise HTTPException(
            status_code=503,
            detail="La promo Profesional GRATIS no está activa.",
        )

    # 2. Idempotencia
    if current_user.account_type == "professional":
        raise HTTPException(
            status_code=400,
            detail="Tu cuenta ya es Profesional.",
        )

    # 3. Activar (sin tocar tokens — solo el estatus, ver docstring)
    current_user.account_type = "professional"
    db.commit()
    print(
        f"[Pro-Promo] {current_user.email} activado Profesional GRATIS · "
        f"saldo tokens sin cambios={current_user.tokens}"
    )
    return {
        "ok": True,
        "account_type": "professional",
        "tokens": float(current_user.tokens),
        "credited": 0,
    }


# ── Webhook de Stripe (automático, <30 segundos) ───────────────────────────────
@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload   = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Firma de webhook inválida")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # ── Renovación mensual de una suscripción web ───────────────────────────
    if event["type"] == "invoice.paid":
        from datetime import datetime as _now, timedelta as _delta
        from app.core import subscriptions as _subs

        inv = event["data"]["object"]
        # La primera factura la cubre checkout.session.completed → no duplicar.
        if inv.get("billing_reason") == "subscription_create":
            return {"status": "ignored (alta ya acreditada)"}
        meta = (inv.get("subscription_details") or {}).get("metadata") or inv.get("metadata") or {}
        plan = _subs.plan_by_id(meta.get("plan_id", ""))
        user = db.query(User).filter(User.id == meta.get("user_id")).first() if meta.get("user_id") else None
        if not plan or not user:
            return {"status": "ignored"}
        clave = f"stripe:inv:{inv.get('id')}"
        if (user.subscription_last_grant or "") == clave:
            return {"status": "already processed"}
        user.subscription_status = "active"
        user.subscription_expires_at = _now.utcnow() + _delta(days=31)
        user.subscription_last_grant = clave
        user.tokens = float(user.tokens) + float(plan["credits"]) / _subs.CREDITS_PER_TOKEN
        db.commit()
        print(f"[Stripe-SUB] renovación {user.email} plan={plan['id']} saldo={user.tokens}")
        return {"status": "ok"}

    if event["type"] == "checkout.session.completed":
        session  = event["data"]["object"]
        metadata = session.get("metadata", {})
        kind     = metadata.get("kind", "")

        # Evitar duplicados (idempotencia — Stripe puede reintentar webhooks)
        existing = db.query(Payment).filter(
            Payment.stripe_session_id == session["id"],
            Payment.status == "paid",
        ).first()
        if existing:
            return {"status": "already processed"}

        # ── Suscripción mensual por web (modelo agosto 2026) ────────────────
        # Alta inicial. Las renovaciones llegan como invoice.paid (abajo).
        if metadata.get("plan_id"):
            from datetime import datetime as _now, timedelta as _delta
            from app.core import subscriptions as _subs

            plan = _subs.plan_by_id(metadata["plan_id"])
            user = db.query(User).filter(User.id == metadata.get("user_id")).first()
            if not plan or not user:
                return {"status": "ignored"}
            user.subscription_plan = plan["id"]
            user.subscription_status = "active"
            user.subscription_store = "stripe"
            user.subscription_expires_at = _now.utcnow() + _delta(days=31)
            user.subscription_started_at = user.subscription_started_at or _now.utcnow()
            user.subscription_last_grant = f"stripe:{session['id']}"
            user.tokens = float(user.tokens) + float(plan["credits"]) / _subs.CREDITS_PER_TOKEN
            pago = db.query(Payment).filter(Payment.stripe_session_id == session["id"]).first()
            if pago:
                pago.status = "paid"
            db.commit()
            print(f"[Stripe-SUB] {user.email} plan={plan['id']} +{plan['credits']}cr saldo={user.tokens}")
            return {"status": "ok"}

        # ── Flujo Profesional (membresía + opcional bundle) ─────────────────
        if kind == "pro_membership":
            user_id     = metadata.get("user_id")
            with_bundle = metadata.get("with_bundle", "false") == "true"
            if not user_id:
                return {"status": "ignored"}

            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"status": "user not found"}

            # 1. Activar tier Profesional
            user.account_type = "professional"
            # 2. Acreditar tokens cortesía + bundle (si aplica)
            credited = PRO_MEMBERSHIP_TOKENS + (PRO_BUNDLE_TOKENS if with_bundle else 0)
            user.tokens = float(user.tokens) + credited
            # 3. Marcar pago como completado
            payment = db.query(Payment).filter(
                Payment.stripe_session_id == session["id"],
            ).first()
            if payment:
                payment.status = "paid"
            db.commit()
            print(
                f"[Stripe-PRO] {user.email} activado Profesional · +{credited} tokens "
                f"(membresía=10{', bundle=60' if with_bundle else ''}) · saldo={user.tokens}"
            )
            return {"status": "ok"}

        # ── Flujo legacy (packs de tokens particular) ───────────────────────
        user_id = metadata.get("user_id")
        tokens  = int(metadata.get("tokens", 0))

        if not user_id or not tokens:
            return {"status": "ignored"}

        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.tokens += tokens
            payment = db.query(Payment).filter(
                Payment.stripe_session_id == session["id"],
            ).first()
            if payment:
                payment.status = "paid"
            db.commit()
            print(f"[Stripe] +{tokens} tokens → {user.email} (total: {user.tokens})")

    return {"status": "ok"}


# ── Webhook de RevenueCat (iOS IAP, automático) ───────────────────────────────
def _rc_marcar_fin_suscripcion(event, etype, app_user_id, db):
    """CANCELLATION/EXPIRATION/BILLING_ISSUE de un plan → actualiza el estado.

    NO toca el saldo: los créditos ya abonados son del usuario. El acceso sigue
    vivo hasta subscription_expires_at (access_state lo comprueba).
    """
    from datetime import datetime as _now
    from app.core import subscriptions as _subs

    product_id = (event.get("product_id", "") or "").split(":")[0]
    if not _subs.plan_by_product_id(product_id):
        return {"status": "ignored", "type": etype}
    try:
        uuid.UUID(str(app_user_id))
    except (ValueError, TypeError, AttributeError):
        return {"status": "invalid app_user_id"}
    user = db.query(User).filter(User.id == app_user_id).first()
    if not user:
        return {"status": "user not found"}

    user.subscription_status = {
        "CANCELLATION": "canceled",
        "BILLING_ISSUE": "in_grace",
        "SUBSCRIPTION_PAUSED": "canceled",
    }.get(etype, "expired")
    exp_ms = event.get("expiration_at_ms")
    if exp_ms:
        user.subscription_expires_at = _now.utcfromtimestamp(exp_ms / 1000.0)
    db.commit()
    print(f"[RevenueCat-SUB] {user.email} {etype} → {user.subscription_status} "
          f"(acceso hasta {user.subscription_expires_at})")
    return {"status": "ok", "subscription_status": user.subscription_status}


@router.post("/webhooks/revenuecat")
async def revenuecat_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Webhook de RevenueCat para las compras In-App de iOS. Espejo del de Stripe:
    acredita tokens (packs consumibles) o activa Profesional (suscripción Pro)
    al confirmarse la compra. NO toca nada del flujo Stripe.

    Verificación: header Authorization == REVENUECAT_WEBHOOK_AUTH (secreto
    compartido configurado en RevenueCat dashboard + Railway). Fail-closed.

    Idempotencia: Payment.stripe_session_id = "rc_<event_id>" (unique). El crédito
    de tokens y la fila Payment van en la MISMA transacción → si hay carrera, el
    unique constraint revienta el insert y se hace rollback (cero doble crédito).

    Decisiones v1 (mirror Stripe, mínimo riesgo) — FLAGGED para el founder:
      - Packs de tokens: NON_RENEWING_PURCHASE → acredita tokens del producto.
      - Pro: INITIAL_PURCHASE/RENEWAL → account_type='professional'. Tokens
        cortesía (10) SOLO en INITIAL_PURCHASE (no en renovaciones), igual que Stripe.
      - EXPIRATION/CANCELLATION: v1 NO revoca Pro (parity con el Pro permanente de
        Stripe; evita revocar acceso por error). Se puede endurecer post-launch.
    """
    # 1. Verificación (fail-closed)
    if not REVENUECAT_WEBHOOK_AUTH:
        raise HTTPException(status_code=503, detail="REVENUECAT_WEBHOOK_AUTH no configurado en el servidor")
    if request.headers.get("authorization", "") != REVENUECAT_WEBHOOK_AUTH:
        raise HTTPException(status_code=401, detail="Webhook auth inválida")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Body JSON inválido")
    event = body.get("event", {}) or {}
    etype = event.get("type", "")
    event_id = event.get("id", "")
    app_user_id = event.get("app_user_id", "")
    product_id = (event.get("product_id", "") or "").split(":")[0]  # normaliza base-plan suffix

    # Solo eventos de compra que acreditan algo. El resto (TEST, CANCELLATION,
    # EXPIRATION, BILLING_ISSUE, etc.) se ignoran con 200 para que RC no reintente.
    # Fin de suscripción: marca el estado (no retira créditos — lo comprado es
    # del usuario) y deja que el acceso dure hasta expiration_at_ms.
    if etype in ("CANCELLATION", "EXPIRATION", "BILLING_ISSUE", "SUBSCRIPTION_PAUSED"):
        return _rc_marcar_fin_suscripcion(event, etype, app_user_id, db)

    if etype not in ("NON_RENEWING_PURCHASE", "INITIAL_PURCHASE", "RENEWAL"):
        return {"status": "ignored", "type": etype}
    if not event_id or not app_user_id:
        return {"status": "ignored"}

    # Validar formato UUID antes de tocar la DB (evita 500 con app_user_id basura)
    try:
        uuid.UUID(str(app_user_id))
    except (ValueError, TypeError, AttributeError):
        print(f"[RevenueCat] app_user_id no es UUID válido: {app_user_id!r}")
        return {"status": "invalid app_user_id"}

    # 2. Idempotencia
    rc_key = f"rc_{event_id}"
    if db.query(Payment).filter(Payment.stripe_session_id == rc_key).first():
        return {"status": "already processed"}

    # with_for_update: bloquea la fila del usuario hasta el commit → serializa
    # créditos concurrentes del MISMO usuario (evita lost-update en compras casi
    # simultáneas). No-op en SQLite (dev); efectivo en PostgreSQL (prod).
    user = db.query(User).filter(User.id == app_user_id).with_for_update().first()
    if not user:
        print(f"[RevenueCat] user no encontrado app_user_id={app_user_id} type={etype}")
        return {"status": "user not found"}

    credited = 0
    amount_cents = 0
    # ── Planes de suscripción (modelo agosto 2026) ───────────────────────────
    # Se comprueba ANTES que los packs: los ids de plan son propios
    # (tdm_*_mensual) y no colisionan con los packs ni con el Pro.
    from datetime import datetime as _now
    from app.core import subscriptions as _subs

    _plan = _subs.plan_by_product_id(product_id)
    if _plan:
        credited = float(_plan["credits"]) / _subs.CREDITS_PER_TOKEN
        amount_cents = int(round(float(_plan.get("price", 0)) * 100))
        _exp_ms = event.get("expiration_at_ms")
        _exp = _now.utcfromtimestamp(_exp_ms / 1000.0) if _exp_ms else None
        _trial = (event.get("period_type") or "").upper() == "TRIAL"
        user.subscription_plan = _plan["id"]
        user.subscription_status = "trialing" if _trial else "active"
        user.subscription_store = (event.get("store") or "app_store").lower()
        user.subscription_expires_at = _exp
        if not user.subscription_started_at:
            user.subscription_started_at = _now.utcnow()
        user.subscription_last_grant = rc_key
        # En TRIAL no se abonan los créditos del plan: el usuario ya tiene los
        # 500 de bienvenida. Se abonan al primer cobro real (RENEWAL/INITIAL no-trial).
        if _trial:
            credited = 0
        else:
            user.tokens = float(user.tokens) + credited
        print(f"[RevenueCat-SUB] {user.email} plan={_plan['id']} {etype} "
              f"trial={_trial} +{credited}tk saldo={user.tokens} exp={_exp}")
    elif product_id in RC_TOKEN_PRODUCTS:
        credited = RC_TOKEN_PRODUCTS[product_id]
        amount_cents = PACKS.get(credited, {}).get("amount_cents", 0)
        user.tokens = float(user.tokens) + credited
        print(f"[RevenueCat] +{credited} tokens → {user.email} ({product_id})")
    elif product_id == RC_PRO_PRODUCT:
        user.account_type = "professional"
        amount_cents = 2000
        if etype == "INITIAL_PURCHASE":
            credited = PRO_MEMBERSHIP_TOKENS
            user.tokens = float(user.tokens) + credited
        print(f"[RevenueCat-PRO] {user.email} Pro {etype} · +{credited} tokens · saldo={user.tokens}")
    else:
        print(f"[RevenueCat] producto desconocido product_id={product_id} type={etype}")
        return {"status": "unknown product"}

    # 3. Crédito + fila Payment en la misma transacción (idempotencia atómica)
    try:
        db.add(Payment(
            user_id=user.id,
            stripe_session_id=rc_key,
            tokens=int(round(credited)),
            amount_cents=int(amount_cents),
            status="paid",
        ))
        db.commit()
    except IntegrityError:
        # rc_key duplicado (carrera/retry del mismo evento) → ya procesado. El
        # rollback revierte también el crédito de tokens → cero doble cobro.
        db.rollback()
        print(f"[RevenueCat] evento duplicado (carrera/retry) event={event_id}")
        return {"status": "already processed"}
    except Exception as e:
        # Error inesperado (p.ej. DB transitoria) → 500 para que RevenueCat
        # REINTENTE el webhook (no perder el evento devolviendo 200 erróneo).
        db.rollback()
        print(f"[RevenueCat] ERROR inesperado event={event_id}: {e}")
        raise HTTPException(status_code=500, detail="error procesando webhook RevenueCat")

    return {"status": "ok", "credited": credited}


# ── Saldo actual (el frontend lo consulta al volver de Stripe) ────────────────
@router.get("/payments/balance")
def get_balance(current_user: User = Depends(get_current_user)):
    return {"tokens": current_user.tokens, "email": current_user.email}


# ── Gestión de roles (solo admin) ────────────────────────────────────────────
class SetRoleRequest(BaseModel):
    email: str
    role: str  # "user" | "collaborator" | "admin"

VALID_ROLES = ("user", "ambassador", "tech", "developer", "admin")
ROLE_TOKENS = {"ambassador": 8, "tech": 50}  # tokens gifted on role assignment

@router.post("/admin/set-role")
def set_role(
    req: SetRoleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo los administradores pueden cambiar roles.")
    if req.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Rol inválido. Usa: {', '.join(VALID_ROLES)}.")
    target = db.query(User).filter(User.email == req.email).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"Usuario '{req.email}' no encontrado.")
    old_role = target.role
    target.role = req.role
    # Auto-gift tokens when upgrading to ambassador or tech
    if req.role in ROLE_TOKENS and old_role not in ROLE_TOKENS:
        target.tokens = float(target.tokens) + ROLE_TOKENS[req.role]
    db.commit()
    return {"ok": True, "email": target.email, "role": target.role, "tokens": float(target.tokens)}


# ── Añadir tokens manualmente (solo admin) ───────────────────────────────────
class AddTokensRequest(BaseModel):
    email: str
    amount: float

@router.post("/admin/add-tokens")
def add_tokens(
    req: AddTokensRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo los administradores pueden añadir tokens.")
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor que 0.")
    target = db.query(User).filter(User.email == req.email).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"Usuario '{req.email}' no encontrado.")
    target.tokens = float(target.tokens) + req.amount
    db.commit()
    return {"ok": True, "email": target.email, "tokens": float(target.tokens)}


# ── Listar usuarios (solo admin) ─────────────────────────────────────────────
@router.get("/admin/users")
def list_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Acceso restringido.")
    users = db.query(User).order_by(User.created_at.desc()).all()
    return {"users": [
        {"email": u.email, "role": u.role, "tokens": float(u.tokens),
         "created_at": str(u.created_at)}
        for u in users
    ]}
