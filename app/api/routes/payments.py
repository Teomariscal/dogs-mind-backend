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

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

APP_URL = os.environ.get("APP_URL", "https://thedogsmindbeta.netlify.app")

# Packs disponibles
PACKS = {
    10:  {"tokens": 10,  "amount_cents": 499,  "label": "10 Tokens Dogs Mind"},
    50:  {"tokens": 50,  "amount_cents": 1999, "label": "50 Tokens Dogs Mind"},
    200: {"tokens": 200, "amount_cents": 5999, "label": "200 Tokens Dogs Mind"},
}


class CheckoutRequest(BaseModel):
    pack: int  # 10, 50 o 200


# ── Crear sesión de pago ───────────────────────────────────────────────────────
@router.post("/payments/checkout")
def create_checkout(
    req: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pack = PACKS.get(req.pack)
    if not pack:
        raise HTTPException(status_code=400, detail="Pack inválido. Elige 10, 50 o 200.")

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
