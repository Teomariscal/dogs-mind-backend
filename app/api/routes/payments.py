import os
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.payment import Payment
from app.api.routes.auth import get_current_user

router = APIRouter(tags=["payments"])

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

APP_URL = os.environ.get("APP_URL", "https://thedogsmindbeta.netlify.app")

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


class CheckoutRequest(BaseModel):
    pack: int  # 5, 20 o 60


# ── Crear sesión de pago ───────────────────────────────────────────────────────
@router.post("/payments/checkout")
def create_checkout(
    req: CheckoutRequest,
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
            success_url=f"{APP_URL}?payment=success&tokens={pack['tokens']}",
            cancel_url=f"{APP_URL}?payment=cancelled",
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


# ── Crear sesión de pago — flujo Profesional ──────────────────────────────────
class ProCheckoutRequest(BaseModel):
    with_bundle: bool = False  # añade el pack 60 tokens promo (37,80 €) opcional


@router.post("/payments/pro-checkout")
def create_pro_checkout(
    req: ProCheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Crea una Stripe Checkout Session para activar la cuenta Profesional.
    Pago único (no suscripción) — el webhook activa el tier al confirmarse.
    """
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
            success_url=f"{APP_URL}?payment=pro_success",
            cancel_url=f"{APP_URL}?payment=pro_cancelled",
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
