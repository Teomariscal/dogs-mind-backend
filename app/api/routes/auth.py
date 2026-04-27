import os
import secrets
import string
import httpx
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import jwt
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Config ────────────────────────────────────────────────────────────────────
JWT_SECRET    = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Schemas ───────────────────────────────────────────────────────────────────
AMBASSADOR_CODE    = os.environ.get("AMBASSADOR_CODE", "").strip()
AMBASSADOR_TOKENS  = 15
DEFAULT_TOKENS     = 5

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    invite_code: str = ""   # optional ambassador code

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    token: str
    user_id: str
    email: str
    tokens: float
    role: str = "user"


# ── Helpers ───────────────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS)
    return jwt.encode({"sub": user_id, "exp": expire}, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> str:
    """Returns user_id or raises HTTPException."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload["sub"]
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")


# ── Dependency ────────────────────────────────────────────────────────────────
from fastapi import Header
from typing import Optional

async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")
    token = authorization.split(" ", 1)[1]
    user_id = decode_token(token)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return user


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post("/register", response_model=AuthResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="Email ya registrado")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")

    # Check ambassador code
    is_ambassador = AMBASSADOR_CODE and req.invite_code.strip() == AMBASSADOR_CODE
    role   = "ambassador" if is_ambassador else "user"
    tokens = AMBASSADOR_TOKENS if is_ambassador else DEFAULT_TOKENS

    user = User(email=req.email, password_hash=hash_password(req.password),
                tokens=tokens, role=role)
    db.add(user)
    db.commit()
    db.refresh(user)

    return AuthResponse(
        token=create_token(str(user.id)),
        user_id=str(user.id),
        email=user.email,
        tokens=float(user.tokens),
        role=user.role,
    )


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    return AuthResponse(
        token=create_token(str(user.id)),
        user_id=str(user.id),
        email=user.email,
        tokens=float(user.tokens),
        role=user.role,
    )


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "user_id": str(current_user.id),
        "email":   current_user.email,
        "tokens":  float(current_user.tokens),
        "role":    current_user.role,
    }


# ── Password recovery ─────────────────────────────────────────────────────────
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
RESEND_FROM    = os.environ.get("RESEND_FROM", "Dogs Mind <onboarding@resend.dev>")
APP_URL        = os.environ.get("APP_URL", "https://thedogsmindbeta.netlify.app")


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


def _generate_temp_password(length: int = 10) -> str:
    """Random readable password (no ambiguous chars)."""
    alphabet = (string.ascii_letters + string.digits).translate(
        str.maketrans("", "", "lI1O0o")
    )
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _send_password_email(to_email: str, temp_password: str) -> None:
    """POST email via Resend. Raises HTTPException on failure."""
    if not RESEND_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="RESEND_API_KEY no configurada en el servidor.",
        )

    subject = "Tu nueva contraseña — Dogs Mind"
    html = f"""
    <div style="font-family: -apple-system, system-ui, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px 24px; color: #1a1f17;">
      <div style="font-family: Georgia, serif; font-size: 24px; font-weight: 600; color: #4a6741; margin-bottom: 8px;">The Dogs Mind</div>
      <div style="font-style: italic; color: #6a6a55; margin-bottom: 24px;">by Teo Mariscal</div>
      <p style="font-size: 16px; line-height: 1.6; margin-bottom: 16px;">Has solicitado recuperar tu contraseña. Aquí tienes una nueva, generada al azar:</p>
      <div style="background: #f7f5ee; border: 1.5px solid rgba(184,146,42,0.45); border-radius: 12px; padding: 18px; text-align: center; font-size: 22px; font-weight: 700; letter-spacing: 2px; color: #1a1f17; font-family: 'Courier New', monospace; margin: 16px 0 24px;">{temp_password}</div>
      <p style="font-size: 14px; line-height: 1.6; color: #555; margin-bottom: 8px;">Por seguridad, te recomendamos cambiarla por una nueva contraseña al iniciar sesión.</p>
      <p style="font-size: 14px; line-height: 1.6; margin-top: 24px;"><a href="{APP_URL}" style="color: #4a6741; text-decoration: underline;">Iniciar sesión en Dogs Mind →</a></p>
      <p style="font-size: 12px; color: #999; margin-top: 32px; border-top: 1px solid #eee; padding-top: 16px;">Si no solicitaste este cambio, contacta con nosotros lo antes posible.</p>
    </div>
    """

    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from":    RESEND_FROM,
                    "to":      [to_email],
                    "subject": subject,
                    "html":    html,
                },
            )
            if r.status_code >= 400:
                raise HTTPException(
                    status_code=502,
                    detail=f"Error enviando email: {r.text[:200]}",
                )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Error de red al enviar email: {e}")


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Generate a new password, store its hash, and email it to the user.
    Returns 200 even if email doesn't exist (no enumeration leakage).
    """
    user = db.query(User).filter(User.email == req.email).first()
    if user:
        new_password = _generate_temp_password()
        user.password_hash = hash_password(new_password)
        db.commit()
        _send_password_email(req.email, new_password)
    # Always return same response regardless of email existence
    return {"ok": True, "message": "Si el email existe, recibirás una nueva contraseña en unos segundos."}
