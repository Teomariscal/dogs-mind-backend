"""
Cuentas corporativas — alta del acuerdo y afiliación de sus miembros.

Endpoints:
- POST /corporate/join            → el usuario se afilia con código (+ dominio)
- GET  /corporate/me              → estado de mi afiliación y cuánto me queda
- POST /admin/corporates          → crear un acuerdo (solo admin)
- GET  /admin/corporates          → listado con consumo real (solo admin)
- POST /admin/corporates/{id}/approve → aceptar/denegar solicitudes pendientes

Reglas del caso (founder 2026-08-04):
  · La institución no paga mensualidad: se pacta una bolsa de créditos.
  · Dos llaves para afiliarse: código + email del dominio pactado.
  · Concesión por año lectivo → el acuerdo caduca.
  · Al agotar cupo o bolsa, el miembro compra o espera. Nunca muro seco.
"""

import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.database import get_db
from app.models.corporate import Corporate
from app.models.user import User

_log = logging.getLogger(__name__)

router = APIRouter(tags=["corporates"])

CREDITOS_POR_TOKEN = 100


def _dominios(corp: Corporate) -> list:
    return [d.strip().lower().lstrip("@") for d in (corp.email_domains or "").split(",") if d.strip()]


def _dominio_ok(corp: Corporate, email: str) -> bool:
    dom = (email or "").split("@")[-1].strip().lower()
    permitidos = _dominios(corp)
    if not permitidos:
        return True                       # acuerdo sin dominio: solo vale el código
    return any(dom == p or dom.endswith("." + p) for p in permitidos)


# ── Afiliación ──────────────────────────────────────────────────────────────
class JoinIn(BaseModel):
    code: str = Field(..., min_length=2, max_length=40)


@router.post("/corporate/join")
def join_corporate(
    body: JoinIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    corp = db.query(Corporate).filter(
        Corporate.code == body.code.strip().upper()).first()
    if not corp or not corp.vigente():
        raise HTTPException(status_code=404,
                            detail="Ese código no existe o el acuerdo ya no está vigente.")

    if not _dominio_ok(corp, current_user.email):
        doms = ", ".join("@" + d for d in _dominios(corp))
        raise HTTPException(
            status_code=403,
            detail=f"Para unirte a {corp.name} necesitas una cuenta con email {doms}.")

    if corp.max_members:
        n = db.query(User).filter(User.corporate_id == corp.id,
                                  User.corporate_status == "active").count()
        if n >= corp.max_members:
            raise HTTPException(status_code=409,
                                detail=f"{corp.name} ha alcanzado su número máximo de miembros.")

    if current_user.corporate_id == corp.id and current_user.corporate_status == "active":
        return {"ok": True, "ya_afiliado": True, "name": corp.name,
                "message": f"Ya estabas dado de alta en {corp.name}."}

    current_user.corporate_id = corp.id
    current_user.corporate_spent = 0
    if corp.approval_required:
        current_user.corporate_status = "pending"
        mensaje = f"Solicitud enviada a {corp.name}. Te avisamos al aprobarla."
    else:
        current_user.corporate_status = "active"
        if corp.member_account_type == "professional":
            current_user.account_type = "professional"
        mensaje = f"Listo. Tu cuenta está asociada a {corp.name}."
    db.commit()
    _log.info("corporate: %s → %s (%s)", current_user.email, corp.code,
              current_user.corporate_status)
    return {"ok": True, "ya_afiliado": False, "name": corp.name,
            "status": current_user.corporate_status, "message": mensaje}


@router.get("/corporate/me")
def my_corporate(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.corporate_id:
        return {"afiliado": False}
    corp = db.query(Corporate).filter(Corporate.id == current_user.corporate_id).first()
    if not corp:
        return {"afiliado": False}
    cupo = float(corp.member_cap_tokens or 0)
    usado = float(current_user.corporate_spent or 0)
    restante_mio = max(0.0, cupo - usado) if cupo > 0 else corp.bolsa_restante()
    return {
        "afiliado": True,
        "status": current_user.corporate_status,
        "name": corp.name,
        "vigente": corp.vigente(),
        "expires_at": corp.expires_at.isoformat() + "Z" if corp.expires_at else None,
        "credits_cap": int(round(cupo * CREDITOS_POR_TOKEN)) if cupo > 0 else None,
        "credits_used": int(round(usado * CREDITOS_POR_TOKEN)),
        "credits_left": int(round(restante_mio * CREDITOS_POR_TOKEN)),
        "pool_left": int(round(corp.bolsa_restante() * CREDITOS_POR_TOKEN)),
    }


# ── Administración ──────────────────────────────────────────────────────────
class CorporateIn(BaseModel):
    code: str
    name: str
    email_domains: str = ""
    pool_credits: int = 0                 # en CRÉDITOS, como habla el founder
    member_cap_credits: int = 0
    expires_at: Optional[datetime] = None
    starts_at: Optional[datetime] = None
    member_account_type: str = "particular"
    approval_required: bool = False
    max_members: Optional[int] = None
    contact_email: Optional[str] = None
    notes: Optional[str] = None


def _solo_admin(user: User):
    if (user.role or "user") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin.")


@router.post("/admin/corporates", status_code=201)
def crear_corporate(
    body: CorporateIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _solo_admin(current_user)
    if db.query(Corporate).filter(Corporate.code == body.code.strip().upper()).first():
        raise HTTPException(status_code=409, detail="Ese código ya existe.")
    corp = Corporate(
        code=body.code.strip().upper(),
        name=body.name.strip(),
        email_domains=body.email_domains.strip(),
        pool_tokens=body.pool_credits / CREDITOS_POR_TOKEN,
        member_cap_tokens=body.member_cap_credits / CREDITOS_POR_TOKEN,
        starts_at=body.starts_at,
        expires_at=body.expires_at,
        member_account_type=body.member_account_type,
        approval_required=body.approval_required,
        max_members=body.max_members,
        contact_email=body.contact_email,
        notes=body.notes,
    )
    db.add(corp)
    db.commit()
    db.refresh(corp)
    return {"ok": True, "id": str(corp.id), "code": corp.code, "name": corp.name}


@router.get("/admin/corporates")
def listar_corporates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _solo_admin(current_user)
    salida = []
    for c in db.query(Corporate).order_by(Corporate.created_at.desc()).all():
        activos = db.query(User).filter(User.corporate_id == c.id,
                                        User.corporate_status == "active").count()
        pendientes = db.query(User).filter(User.corporate_id == c.id,
                                           User.corporate_status == "pending").count()
        salida.append({
            "id": str(c.id), "code": c.code, "name": c.name,
            "vigente": c.vigente(),
            "expires_at": c.expires_at.isoformat() + "Z" if c.expires_at else None,
            "miembros_activos": activos, "pendientes": pendientes,
            "bolsa_creditos": int(round(float(c.pool_tokens) * CREDITOS_POR_TOKEN)),
            "consumido_creditos": int(round(float(c.pool_spent) * CREDITOS_POR_TOKEN)),
            "coste_eur": round(float(c.pool_spent) * 0.021, 2),
        })
    return {"corporates": salida}


class AprobarIn(BaseModel):
    email: str
    aprobar: bool = True


@router.post("/admin/corporates/{corporate_id}/approve")
def aprobar_miembro(
    corporate_id: str,
    body: AprobarIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _solo_admin(current_user)
    corp = db.query(Corporate).filter(Corporate.id == corporate_id).first()
    if not corp:
        raise HTTPException(status_code=404, detail="Acuerdo no encontrado.")
    u = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if not u or str(u.corporate_id) != str(corp.id):
        raise HTTPException(status_code=404, detail="Esa cuenta no ha solicitado unirse.")
    u.corporate_status = "active" if body.aprobar else "rejected"
    if body.aprobar and corp.member_account_type == "professional":
        u.account_type = "professional"
    db.commit()
    return {"ok": True, "email": u.email, "status": u.corporate_status}
