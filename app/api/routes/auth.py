import os
import secrets
import string
import hashlib
import httpx
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import jwt
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.models.user import User
from app.models.delegation import Delegation

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Config ────────────────────────────────────────────────────────────────────
# JWT_SECRET es OBLIGATORIO en producción. Antes había fallback hardcoded
# "dev-secret-change-in-production" que permitía forjar JWTs si la env var se
# perdía en Railway. Audit 2026-05-17: ahora si la var no está o es el default
# conocido, abortamos el arranque (App Store + security).
_JWT_INSECURE_DEFAULT = "dev-secret-change-in-production"
JWT_SECRET    = os.environ.get("JWT_SECRET", "").strip()
if not JWT_SECRET or JWT_SECRET == _JWT_INSECURE_DEFAULT:
    raise RuntimeError(
        "[FATAL] JWT_SECRET no configurada (o es el default inseguro). "
        "Define una env var JWT_SECRET con un valor aleatorio fuerte antes de arrancar. "
        "Genera uno con: python -c 'import secrets; print(secrets.token_urlsafe(48))'"
    )
JWT_ALGORITHM = "HS256"
# Founder 2026-07-31: la sesión pasa de 30 días a un AÑO. Con 30 días, a todo
# usuario que no volviera a entrar en un mes se le caducaba la sesión en
# silencio: la app seguía mostrándole su cuenta (solo mira si hay token
# guardado) y el fallo aparecía al tocar el servidor — típicamente en mitad de
# un análisis. Caso real jpcarmid@gmail.com y 569 usuarios en la misma
# situación. Ver también la recuperación por enlace más abajo.
JWT_EXPIRE_DAYS = 365

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Schemas ───────────────────────────────────────────────────────────────────
AMBASSADOR_CODE    = os.environ.get("AMBASSADOR_CODE", "").strip()
AMBASSADOR_TOKENS  = 8
DEFAULT_TOKENS     = 5   # NO subir esto para pagar la consulta guiada: el extra se GANA
                         # haciendo la visita guiada, no se regala por registrarse
                         # (founder 2026-08-17). Ver bono guiado en build 28.

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    phone: Optional[str] = None        # PII — opcional, GDPR/CCPA scope
    invite_code: str = ""              # optional ambassador code

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    token: str
    user_id: str
    email: str
    tokens: float
    role: str = "user"
    account_type: str = "particular"
    # Si el registro vino con código de delegación, devolvemos el nombre para
    # que el frontend pueda pintar un toast personalizado ("Bienvenido por
    # cortesía de Bocalán México"). NULL si no hay atribución.
    delegation_name: Optional[str] = None


class ValidateInviteRequest(BaseModel):
    invite_code: str


class ValidateInviteResponse(BaseModel):
    """
    Respuesta de pre-validación de invite_code (sin crear cuenta).
    Si `valid` es False, los demás campos son None y el cliente debe mostrar
    un mensaje neutro (no enumeramos qué tipo de código sería).
    """
    valid: bool
    type: Optional[str] = None       # 'delegation' | 'ambassador' | None
    label: Optional[str] = None      # nombre legible ("Bocalán Chile", "Embajador")
    tokens: Optional[int] = None     # total welcome tokens si valid


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
    if user.deleted_at is not None:
        raise HTTPException(status_code=401, detail="Cuenta eliminada")
    return user


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post("/register", response_model=AuthResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    # Normalizar email para evitar bugs case-sensitive (autocomplete navegador
    # puede mandar emails con mayúsculas que rompen logins posteriores).
    from sqlalchemy import func
    email_norm = str(req.email).strip().lower()
    if db.query(User).filter(func.lower(User.email) == email_norm).first():
        raise HTTPException(status_code=400, detail="Email ya registrado")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")

    # ── Resolución de invite_code ────────────────────────────────────────────
    # Orden de prioridad (más específico primero):
    #   1. ¿Coincide con una Delegation activa? → role=user, tokens=5+bonus, atribuido
    #   2. ¿Coincide con AMBASSADOR_CODE env? → role=ambassador, tokens=AMBASSADOR_TOKENS
    #   3. Sin match → role=user, tokens=DEFAULT_TOKENS
    #
    # case-sensitive a propósito para evitar colisiones accidentales.
    # Trim de espacios por defensa contra paste con whitespace.
    invite_clean = (req.invite_code or "").strip()
    delegation_obj: Optional[Delegation] = None
    role = "user"
    tokens = DEFAULT_TOKENS
    account_type = "particular"

    if invite_clean:
        # Resolución 1: delegation
        delegation_obj = db.query(Delegation).filter(
            Delegation.code == invite_clean,
            Delegation.active == True,
        ).first()
        if delegation_obj:
            tokens = DEFAULT_TOKENS + int(delegation_obj.welcome_bonus_tokens or 0)
            # role queda 'user' — la delegación NO confiere role especial.
            # Pero si el código es de socios (grants_professional), se otorga
            # account_type='professional' GRATIS (sin pago de membresía Pro).
            if getattr(delegation_obj, "grants_professional", False):
                account_type = "professional"
        # Resolución 2: ambassador (solo si no fue delegation)
        elif AMBASSADOR_CODE and invite_clean == AMBASSADOR_CODE:
            role = "ambassador"
            tokens = AMBASSADOR_TOKENS

    # Sanitize phone: trim + None si vacío
    phone_clean = (req.phone or "").strip() or None

    user = User(
        email=email_norm,
        password_hash=hash_password(req.password),
        phone=phone_clean,
        tokens=tokens,
        role=role,
        account_type=account_type,
        delegation_id=(delegation_obj.id if delegation_obj else None),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return AuthResponse(
        token=create_token(str(user.id)),
        user_id=str(user.id),
        email=user.email,
        tokens=float(user.tokens),
        role=user.role,
        account_type=user.account_type,
        delegation_name=(delegation_obj.name if delegation_obj else None),
    )


# ── Rate limit pre-validación de invite_code ─────────────────────────────────
# Sliding window in-memory por IP (mismo patrón que payments.pro-activate-cortesia
# pero con tope más alto porque la UI llama on-blur del input — usuarios pueden
# corregir varias veces). Se limpia al reiniciar Railway (aceptable para 1 worker).
from collections import defaultdict as _defaultdict_inv
from datetime import datetime as _dt_inv, timedelta as _td_inv
from fastapi import Request as _Request_inv

_INVITE_VALIDATE_FAILS: dict = _defaultdict_inv(list)
INVITE_VALIDATE_MAX_FAILS_PER_HOUR = 30


def _invite_client_ip(request: _Request_inv) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _invite_is_blocked(ip: str) -> tuple[bool, int]:
    now = _dt_inv.utcnow()
    cutoff = now - _td_inv(hours=1)
    fails = [t for t in _INVITE_VALIDATE_FAILS.get(ip, []) if t > cutoff]
    _INVITE_VALIDATE_FAILS[ip] = fails
    if len(fails) >= INVITE_VALIDATE_MAX_FAILS_PER_HOUR:
        oldest = fails[0]
        retry = int((oldest + _td_inv(hours=1) - now).total_seconds())
        return True, max(retry, 60)
    return False, 0


@router.post("/validate-invite", response_model=ValidateInviteResponse)
def validate_invite(
    req: ValidateInviteRequest,
    request: _Request_inv,
    db: Session = Depends(get_db),
):
    """
    Pre-validación de invite_code SIN crear cuenta.

    Diseñado para feedback inline en el formulario de registro (on-blur del
    input). Espeja exactamente la lógica de resolución que aplica `/register`:
      1. Delegation activa → type='delegation', tokens=5+bonus
      2. AMBASSADOR_CODE  → type='ambassador', tokens=8
      3. Sin match        → valid=False (sin enumerar nada)

    El endpoint NO escribe en DB. Rate-limit por IP anti brute-force.
    """
    ip = _invite_client_ip(request)
    blocked, retry_after = _invite_is_blocked(ip)
    if blocked:
        raise HTTPException(
            status_code=429,
            detail="Demasiados intentos. Espera unos minutos.",
            headers={"Retry-After": str(retry_after)},
        )

    code = (req.invite_code or "").strip()
    if not code:
        return ValidateInviteResponse(valid=False)

    # Delegation primero (más específico)
    delegation = db.query(Delegation).filter(
        Delegation.code == code,
        Delegation.active == True,
    ).first()
    if delegation:
        return ValidateInviteResponse(
            valid=True,
            type="delegation",
            label=delegation.name or delegation.code,
            tokens=DEFAULT_TOKENS + int(delegation.welcome_bonus_tokens or 0),
        )

    # Ambassador después
    if AMBASSADOR_CODE and code == AMBASSADOR_CODE:
        return ValidateInviteResponse(
            valid=True,
            type="ambassador",
            label="Embajador",
            tokens=AMBASSADOR_TOKENS,
        )

    # Fallo: registramos para rate-limit (no devolvemos 4xx — el cliente
    # necesita la respuesta 200 con valid=False para pintar el mensaje).
    _INVITE_VALIDATE_FAILS[ip].append(_dt_inv.utcnow())
    return ValidateInviteResponse(valid=False)


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    # Email normalizado lowercase + búsqueda case-insensitive — fix para usuarios
    # que se registraron con email en mayúscula vía autocomplete del navegador.
    from sqlalchemy import func
    email_norm = (req.email or "").strip().lower()
    user = db.query(User).filter(func.lower(User.email) == email_norm).first()
    if not user or user.deleted_at is not None or not verify_password(req.password, user.password_hash):
        # Mensaje uniforme aunque la cuenta esté eliminada (no leak de existencia/estado)
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    return AuthResponse(
        token=create_token(str(user.id)),
        user_id=str(user.id),
        email=user.email,
        tokens=float(user.tokens),
        role=user.role,
        account_type=user.account_type,
    )


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "user_id":      str(current_user.id),
        "email":        current_user.email,
        "phone":        current_user.phone,
        "tokens":       float(current_user.tokens),
        "role":         current_user.role,
        "account_type": current_user.account_type,
    }


# ── GDPR/CCPA: Data export (DSAR) ─────────────────────────────────────────────
@router.get("/me/data-export")
def data_export(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Devuelve TODOS los datos personales del usuario en JSON portable.
    Cumple con: GDPR Art. 15 (right of access) + Art. 20 (data portability),
    CCPA "right to know".
    Nota: los datos del PERRO no son PII y no entran aquí.
    """
    from app.models.payment import Payment
    payments = db.query(Payment).filter(Payment.user_id == current_user.id).all()
    return {
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "format_version": "1.0",
        "data_controller": "The Dogs Mind — Teodoro Mariscal Diaz",
        "user": {
            "id":           str(current_user.id),
            "email":        current_user.email,
            "phone":        current_user.phone,
            "tokens":       float(current_user.tokens),
            "role":         current_user.role,
            "account_type": current_user.account_type,
            "created_at":   current_user.created_at.isoformat() + "Z" if current_user.created_at else None,
            "deleted_at":   current_user.deleted_at.isoformat() + "Z" if current_user.deleted_at else None,
        },
        "company": {
            "name":                  current_user.company_name,
            "web":                   current_user.company_web,
            "cif":                   current_user.company_cif,
            "clients_per_year":      current_user.company_clients_per_year,
            "city":                  current_user.company_city,
            "country":               current_user.company_country,
            "billing_email":         current_user.company_billing_email,
            "collaborate_interest":  current_user.company_collaborate_interest,
            "has_logo":              bool(current_user.company_logo_base64),
        } if current_user.company_name else None,
        "payments": [
            {
                "id":                str(p.id),
                "stripe_session_id": p.stripe_session_id,
                "tokens":            p.tokens,
                "amount_eur":        p.amount_cents / 100.0,
                "status":            p.status,
                "created_at":        p.created_at.isoformat() + "Z" if p.created_at else None,
            }
            for p in payments
        ],
        "subprocessors": [
            {"name": "Anthropic",   "purpose": "AI inference (clinical analysis + avatars)", "region": "USA"},
            {"name": "Voyage AI",   "purpose": "Embeddings for RAG",                          "region": "USA"},
            {"name": "Qdrant Cloud","purpose": "Vector storage (knowledge base, no PII)",    "region": "EU"},
            {"name": "Railway",     "purpose": "Backend hosting",                             "region": "EU"},
            {"name": "Netlify",     "purpose": "Frontend hosting",                            "region": "USA/global CDN"},
            {"name": "Resend",      "purpose": "Transactional email (password recovery)",     "region": "USA"},
            {"name": "Plausible",   "purpose": "Analytics (privacy-friendly, no cookies)",    "region": "EU"},
            {"name": "Stripe",      "purpose": "Web payments processing",                     "region": "USA/EU"},
            {"name": "Apple",       "purpose": "App Store In-App Purchases (when applicable)","region": "USA/EU"},
        ],
        "notes": (
            "Este export incluye toda la información personal (PII) del usuario "
            "almacenada en nuestros sistemas. Datos del perro (raza, edad, conducta, "
            "análisis funcional, plan de intervención) no se consideran datos personales "
            "y por tanto quedan fuera del alcance de GDPR/CCPA respecto al usuario."
        ),
    }


# ── GDPR/CCPA: Account deletion ──────────────────────────────────────────────
class DeleteAccountRequest(BaseModel):
    password: str
    confirm:  str  # debe ser exactamente "DELETE" o "ELIMINAR"


@router.delete("/me")
def delete_account(
    req: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Elimina la cuenta del usuario con scrub PII (soft-delete).
    Cumple con: GDPR Art. 17 (right to erasure) + CCPA "right to delete".
    Requiere Apple App Store Guideline 5.1.1(v) (account deletion in-app).

    Mantiene la fila User para preservar integridad referencial con payments
    (necesario para registros fiscales). PII (email, password_hash, phone) se
    anonimiza. user_id de payments se mantiene asociado a la fila scrubeada.
    """
    # Re-verificar password (defensa contra session hijack)
    if not verify_password(req.password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    # Confirmación textual obligatoria
    if req.confirm.strip().upper() not in ("DELETE", "ELIMINAR"):
        raise HTTPException(
            status_code=400,
            detail="Confirmación inválida. Escribe 'DELETE' o 'ELIMINAR' para continuar.",
        )

    if current_user.deleted_at is not None:
        # Idempotente: si ya está borrada, no hacemos nada
        return {"status": "already_deleted", "deleted_at": current_user.deleted_at.isoformat() + "Z"}

    # Scrub PII manteniendo fila para integridad fiscal
    deletion_ts = datetime.utcnow()
    current_user.email         = f"deleted-{current_user.id}@thedogsmind.deleted"
    current_user.password_hash = "deleted"
    current_user.phone         = None
    current_user.tokens        = 0
    current_user.role          = "deleted"
    current_user.deleted_at    = deletion_ts
    # Scrub PII de empresa (también es PII profesional bajo GDPR)
    current_user.company_name                 = None
    current_user.company_web                  = None
    current_user.company_cif                  = None
    current_user.company_clients_per_year     = None
    current_user.company_city                 = None
    current_user.company_country              = None
    current_user.company_billing_email        = None
    current_user.company_collaborate_interest = None
    current_user.company_logo_base64          = None
    db.commit()

    return {
        "status":     "deleted",
        "deleted_at": deletion_ts.isoformat() + "Z",
        "message":    (
            "Tu cuenta y todos tus datos personales han sido eliminados. "
            "Los registros de pago se conservan anonimizados durante 4 años "
            "por requisito legal fiscal (España). Puedes solicitar el borrado "
            "completo de los pagos contactando con privacy@thedogsmind.net."
        ),
    }


# ── Password recovery ─────────────────────────────────────────────────────────
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
RESEND_FROM    = os.environ.get("RESEND_FROM", "Dogs Mind <onboarding@resend.dev>")
APP_URL        = os.environ.get("APP_URL", "https://thedogsmindbeta.netlify.app")


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


def _generate_temp_password(length: int = 10) -> str:
    """Random readable password (no ambiguous chars). Legacy — ya no se usa
    en /forgot-password (ahora se manda un enlace), se conserva por si algún
    flujo interno lo necesita."""
    alphabet = (string.ascii_letters + string.digits).translate(
        str.maketrans("", "", "lI1O0o")
    )
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ── Recuperación por ENLACE (founder 2026-07-31) ─────────────────────────────
# Antes se enviaba una contraseña generada que el usuario tenía que teclear a
# mano, y CADA nueva solicitud invalidaba la anterior. Como los correos son
# idénticos y sin hora, el usuario que reintentaba se dejaba fuera él solo
# (caso real jpcarmid@gmail.com). Ahora se envía un enlace firmado:
#   · No hay nada que teclear ni que copiar mal.
#   · Pedir varios enlaces NO rompe nada: todos siguen siendo válidos hasta
#     que se use uno; al cambiar la contraseña, la huella deja de coincidir y
#     todos los enlaces mueren a la vez (un solo uso efectivo).
#   · Sin tabla nueva ni migración: el estado va firmado dentro del token.
RESET_TOKEN_HOURS = 2


def _reset_fingerprint(password_hash: str) -> str:
    """Huella del hash actual: si la contraseña cambia, los enlaces caducan."""
    return hashlib.sha256((password_hash or "").encode()).hexdigest()[:16]


def create_reset_token(user) -> str:
    payload = {
        "sub": str(user.id),
        "typ": "pwreset",
        "pw":  _reset_fingerprint(user.password_hash),
        "exp": datetime.utcnow() + timedelta(hours=RESET_TOKEN_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _send_reset_link_email(to_email: str, link: str) -> None:
    """Envía el enlace de restablecimiento vía Resend."""
    if not RESEND_API_KEY:
        raise HTTPException(status_code=500, detail="RESEND_API_KEY no configurada en el servidor.")

    subject = "Restablece tu contraseña — The Dogs' Mind"
    html = f"""
    <div style="font-family: -apple-system, system-ui, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px 24px; color: #1a1f17;">
      <div style="font-family: Georgia, serif; font-size: 24px; font-weight: 600; color: #4a6741; margin-bottom: 8px;">The Dogs' Mind</div>
      <div style="font-style: italic; color: #6a6a55; margin-bottom: 24px;">by Teo Mariscal</div>
      <p style="font-size: 16px; line-height: 1.6; margin-bottom: 24px;">Has pedido restablecer tu contraseña. Pulsa el botón y elige una nueva:</p>
      <p style="text-align:center; margin: 0 0 24px;">
        <a href="{link}" style="display:inline-block; background:#4a6741; color:#fff; text-decoration:none; font-size:16px; font-weight:700; padding:14px 28px; border-radius:100px;">Elegir mi contraseña</a>
      </p>
      <p style="font-size: 14px; line-height: 1.6; color:#555; margin-bottom: 16px;">El enlace caduca en {RESET_TOKEN_HOURS} horas. Si has pedido varios correos, <strong>cualquiera de ellos sirve</strong>: en cuanto uses uno, los demás dejan de funcionar.</p>
      <p style="font-size: 12px; line-height:1.5; color:#999; margin-top: 28px; border-top: 1px solid #eee; padding-top: 16px;">Si el botón no funciona, copia esta dirección en tu navegador:<br><span style="word-break:break-all;">{link}</span></p>
      <p style="font-size: 12px; color: #999; margin-top: 16px;">Si no has pedido este cambio, ignora este correo: tu contraseña actual sigue siendo válida. Ante cualquier duda escríbenos a <a href="mailto:privacy@thedogsmind.net" style="color:#999;">privacy@thedogsmind.net</a>.</p>
    </div>
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
                json={"from": RESEND_FROM, "to": [to_email], "subject": subject, "html": html},
            )
            if r.status_code >= 400:
                raise HTTPException(status_code=502, detail=f"Error enviando email: {r.text[:200]}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Error de red enviando email: {e}")


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
      <div style="background: #fff8e6; border: 1.5px solid #e8c46c; border-radius: 10px; padding: 14px 16px; margin: 0 0 20px; font-size: 14px; line-height: 1.6; color: #6a4f10;">
        <strong>Importante:</strong> escribe esta contraseña <strong>a mano</strong> al iniciar sesión.<br>
        Si la copias y pegas, algunos clientes de email añaden caracteres invisibles (espacios o saltos de línea) que impiden el inicio de sesión y dan el mensaje &quot;Email o contraseña incorrectos&quot;.
      </div>
      <p style="font-size: 14px; line-height: 1.6; color: #555; margin-bottom: 8px;">Una vez dentro, te recomendamos cambiarla por una contraseña tuya en <em>Mis Tokens → Cambiar contraseña</em>.</p>
      <p style="font-size: 14px; line-height: 1.6; margin-top: 24px;"><a href="{APP_URL}" style="color: #4a6741; text-decoration: underline;">Iniciar sesión en Dogs Mind →</a></p>
      <p style="font-size: 12px; color: #999; margin-top: 32px; border-top: 1px solid #eee; padding-top: 16px;">Si no solicitaste este cambio, contacta con nosotros lo antes posible en <a href="mailto:privacy@thedogsmind.net" style="color: #999;">privacy@thedogsmind.net</a>.</p>
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
    Email is normalized to lowercase to avoid case-mismatch bugs.
    """
    # Fix audit 2026-05-17: usar case-insensitive match (func.lower) igual que
    # register/login. Antes el filter exacto fallaba en silencio para usuarios
    # cuyo email se persistió con mayúsculas pre-normalización → nunca recibían
    # email de recuperación pero la respuesta era "ok" (zero feedback).
    from sqlalchemy import func
    email_norm = (req.email or "").strip().lower()
    user = db.query(User).filter(func.lower(User.email) == email_norm).first()
    if user and user.deleted_at is None:
        # NO se toca la contraseña actual: sigue siendo válida hasta que el
        # usuario elija una nueva desde el enlace. Así, pedir el correo varias
        # veces (o pedirlo por error) nunca deja a nadie fuera.
        token = create_reset_token(user)
        link = f"{APP_URL.rstrip('/')}/reset.html?t={token}"
        _send_reset_link_email(user.email, link)
    # Always return same response regardless of email existence
    return {"ok": True, "message": "Si el email existe, recibirás un enlace en unos segundos."}


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Fija la contraseña elegida por el usuario desde el enlace del correo.

    El enlace lleva firmada la huella del hash actual: al cambiar la
    contraseña, esa huella deja de coincidir y TODOS los enlaces emitidos
    quedan invalidados de golpe (un solo uso efectivo, sin tabla extra).
    """
    if len(req.new_password or "") < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")
    try:
        payload = jwt.decode(req.token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception:
        raise HTTPException(status_code=400, detail="El enlace ha caducado o no es válido. Pide uno nuevo.")
    if payload.get("typ") != "pwreset":
        raise HTTPException(status_code=400, detail="Enlace no válido.")
    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user or user.deleted_at is not None:
        raise HTTPException(status_code=400, detail="Enlace no válido.")
    if payload.get("pw") != _reset_fingerprint(user.password_hash):
        raise HTTPException(status_code=400, detail="Este enlace ya se ha usado. Pide uno nuevo si lo necesitas.")

    user.password_hash = hash_password(req.new_password)
    db.commit()
    # Sesión lista: el usuario entra directo, sin volver a escribir nada.
    return {
        "ok": True,
        "token": create_token(str(user.id)),
        "email": user.email,
        "account_type": user.account_type,
    }


# ── Change password (logged in) ──────────────────────────────────────────────
class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cambia la contraseña del usuario autenticado.
    Requiere reautenticación con la contraseña actual (defensa session hijack).
    """
    if not verify_password(req.current_password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Contraseña actual incorrecta")
    new_pw = (req.new_password or "")
    if len(new_pw) < 6:
        raise HTTPException(status_code=400, detail="La contraseña nueva debe tener al menos 6 caracteres")
    if new_pw == req.current_password:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe ser distinta de la actual")
    current_user.password_hash = hash_password(new_pw)
    db.commit()
    return {"ok": True, "message": "Contraseña actualizada correctamente"}
