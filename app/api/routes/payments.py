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
    20: {"tokens": 20, "amount_cents": 1999, "label": "20 Tokens Dogs Mind"},
    60: {"tokens": 60, "amount_cents": 5999, "label": "60 Tokens Dogs Mind"},
}


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
        user_id  = metadata.get("user_id")
        tokens   = int(metadata.get("tokens", 0))

        if not user_id or not tokens:
            return {"status": "ignored"}

        # Evitar duplicados
        existing = db.query(Payment).filter(
            Payment.stripe_session_id == session["id"],
            Payment.status == "paid"
        ).first()
        if existing:
            return {"status": "already processed"}

        # Sumar tokens al usuario
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.tokens += tokens
            # Marcar pago como completado
            payment = db.query(Payment).filter(
                Payment.stripe_session_id == session["id"]
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
ROLE_TOKENS = {"ambassador": 15, "tech": 50}  # tokens gifted on role assignment

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
