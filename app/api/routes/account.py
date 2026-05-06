"""
Account router — tipo de cuenta + perfil empresa para profesionales.

Endpoints:
- GET    /me/account              → estado de la cuenta (tipo + datos empresa, sin logo)
- PUT    /me/account-type         → cambia entre 'particular' y 'professional'
- PUT    /me/company              → guarda/actualiza datos empresa (solo si professional)
- GET    /me/company/logo         → devuelve el logo de la empresa (data URL base64)
- POST   /me/company/logo         → sube/sustituye el logo (≤200 KB, data URL)
- DELETE /me/company/logo         → quita el logo

Auth: todos los endpoints requieren JWT vía get_current_user.

Política producto:
- account_type por defecto = 'particular' (usuarios existentes y nuevos signups).
- Vuelta atrás profesional → particular conserva los datos de empresa (no se borran).
- Para llamar a /me/company el usuario debe ser professional. Si pasa a particular,
  los datos quedan latentes pero ya no son editables.
"""

from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, EmailStr, HttpUrl, field_validator

from app.database import get_db
from app.models.user import User, ACCOUNT_TYPES
from app.api.routes.auth import get_current_user
from app.api.routes.dogs import validate_photo_base64  # reuse: data URL ≤200 KB

router = APIRouter(prefix="/me", tags=["account"])


# ── Schemas Pydantic ─────────────────────────────────────────────────────────
class AccountTypeUpdate(BaseModel):
    account_type: str = Field(..., description="'particular' | 'professional'")

    @field_validator("account_type")
    @classmethod
    def must_be_valid(cls, v: str) -> str:
        if v not in ACCOUNT_TYPES:
            raise ValueError(f"account_type inválido. Valores permitidos: {', '.join(ACCOUNT_TYPES)}")
        return v


class CompanyUpdate(BaseModel):
    """
    Datos del perfil empresa/entidad. Nombre y web son obligatorios; el resto opcional.
    Se guarda completo en cada PUT (no PATCH parcial) para mantener el form-save simple.
    """
    name: str = Field(..., min_length=1, max_length=120, description="Nombre empresa o autónomo")
    web: HttpUrl = Field(..., description="Web de la empresa (URL completa con http(s)://)")
    cif: Optional[str] = Field(None, max_length=40, description="CIF/Tax ID — opcional, solo si quiere factura mensual")
    clients_per_year: Optional[int] = Field(
        None, ge=0, le=1_000_000,
        description="Número medio de clientes al año (informativo)",
    )
    city: Optional[str] = Field(None, max_length=80)
    country: Optional[str] = Field(None, max_length=80)
    billing_email: Optional[EmailStr] = Field(None, description="Email para facturación (si quiere factura mensual)")
    collaborate_interest: Optional[bool] = Field(None, description="¿Te gustaría colaborar con The Dogs Mind?")

    @field_validator("cif", "city", "country")
    @classmethod
    def strip_optional(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        s = v.strip()
        return s or None  # cadena vacía → NULL

    @field_validator("name")
    @classmethod
    def strip_required(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("El nombre no puede estar vacío")
        return s


class LogoUpload(BaseModel):
    logo_base64: str = Field(
        ...,
        description="Data URL base64 del logo (image/jpeg|png|webp, ≤200 KB)",
    )


class AccountResponse(BaseModel):
    account_type: str
    has_company_logo: bool
    company: Optional[dict] = None  # None si no hay company_name todavía


class LogoResponse(BaseModel):
    logo_base64: Optional[str] = None


# ── Helpers ──────────────────────────────────────────────────────────────────
def _company_to_dict(user: User) -> Optional[dict]:
    """Devuelve el bloque company solo si hay nombre seteado; si no, None."""
    if not user.company_name:
        return None
    return {
        "name":                  user.company_name,
        "web":                   user.company_web,
        "cif":                   user.company_cif,
        "clients_per_year":      user.company_clients_per_year,
        "city":                  user.company_city,
        "country":               user.company_country,
        "billing_email":         user.company_billing_email,
        "collaborate_interest":  user.company_collaborate_interest,
    }


def _require_professional(user: User) -> None:
    if user.account_type != "professional":
        raise HTTPException(
            status_code=403,
            detail="Solo los usuarios profesionales pueden gestionar el perfil empresa.",
        )


# ── Endpoints ────────────────────────────────────────────────────────────────
@router.get("/account", response_model=AccountResponse)
def get_account(user: User = Depends(get_current_user)):
    """Estado de la cuenta: tipo + datos empresa (sin logo, para mantener respuesta ligera)."""
    return AccountResponse(
        account_type=user.account_type,
        has_company_logo=bool(user.company_logo_base64),
        company=_company_to_dict(user),
    )


@router.put("/account-type", response_model=AccountResponse)
def update_account_type(
    payload: AccountTypeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Cambia el tipo de cuenta. Vuelta atrás profesional → particular preserva los datos
    de empresa (no se borran), pero deja de ser editable hasta volver a profesional.
    """
    if user.account_type != payload.account_type:
        user.account_type = payload.account_type
        db.commit()
        db.refresh(user)
    return AccountResponse(
        account_type=user.account_type,
        has_company_logo=bool(user.company_logo_base64),
        company=_company_to_dict(user),
    )


@router.put("/company", response_model=AccountResponse)
def update_company(
    payload: CompanyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Guarda/actualiza el perfil empresa.

    Permitido también para usuarios particulares: el flujo de activación
    Profesional pide al usuario rellenar nombre + web ANTES del pago, para
    que la cuenta ya esté identificada como profesional cuando vuelva del
    checkout. Si nunca paga, los datos quedan latentes (no se promueve la
    cuenta a profesional). El upload del logo sí mantiene gating
    professional (los particulares no necesitan logo en informes).
    """
    user.company_name                 = payload.name
    user.company_web                  = str(payload.web)
    user.company_cif                  = payload.cif
    user.company_clients_per_year     = payload.clients_per_year
    user.company_city                 = payload.city
    user.company_country              = payload.country
    user.company_billing_email        = str(payload.billing_email) if payload.billing_email else None
    user.company_collaborate_interest = payload.collaborate_interest
    db.commit()
    db.refresh(user)

    return AccountResponse(
        account_type=user.account_type,
        has_company_logo=bool(user.company_logo_base64),
        company=_company_to_dict(user),
    )


@router.get("/company/logo", response_model=LogoResponse)
def get_company_logo(user: User = Depends(get_current_user)):
    """Devuelve el logo (data URL base64) o None si no hay logo. No requiere ser professional
    para leerlo (vuelta atrás conserva el dato; lectura segura)."""
    return LogoResponse(logo_base64=user.company_logo_base64)


@router.post("/company/logo", response_model=LogoResponse)
def upload_company_logo(
    payload: LogoUpload,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Sube/sustituye el logo de empresa. Requiere account_type = 'professional'.
    Reutiliza el validador de fotos (mismo cap de 200 KB que photo perro)."""
    _require_professional(user)
    valid = validate_photo_base64(payload.logo_base64)
    user.company_logo_base64 = valid
    db.commit()
    db.refresh(user)
    return LogoResponse(logo_base64=user.company_logo_base64)


@router.delete("/company/logo", response_model=LogoResponse)
def delete_company_logo(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Quita el logo. No requiere ser professional (permite limpieza tras downgrade)."""
    user.company_logo_base64 = None
    db.commit()
    db.refresh(user)
    return LogoResponse(logo_base64=None)
