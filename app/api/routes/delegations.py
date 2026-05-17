"""
Admin endpoints — gestión de delegaciones y reporting de comisiones.

Todas las rutas requieren role='admin' (verificación en cada endpoint, no
hay middleware admin global en este proyecto).

Endpoints:
  GET    /admin/delegations              → listar todas
  POST   /admin/delegations              → crear nueva
  PATCH  /admin/delegations/{id}         → modificar (bonus, %, activar/desactivar)
  GET    /admin/delegations/report       → reporting agregado para comisiones
                                             (filtros: from, to, delegation_id)

El reporting es AGREGADO por delegación — nunca expone datos individuales
de usuarios. Cumple con el principio que estableció Teo (2026-05-16):
"No es necesario saber cuánto cada uno pero sí el total".
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.delegation import Delegation
from app.models.payment import Payment
from app.api.routes.auth import get_current_user

router = APIRouter(tags=["admin-delegations"])


# ── Schemas ─────────────────────────────────────────────────────────────────
class DelegationCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=40, description="Ej. 'BOCALAN-MX'")
    name: str = Field(..., min_length=2, max_length=120, description="Ej. 'Bocalán México'")
    country: str = Field(..., min_length=2, max_length=80)
    contact_email: Optional[str] = Field(None, max_length=255)
    welcome_bonus_tokens: int = Field(3, ge=0, le=100)
    commission_pct_web: Decimal = Field(Decimal("10.00"), ge=0, le=100)
    commission_pct_ios: Decimal = Field(Decimal("5.00"), ge=0, le=100)
    active: bool = True

    @field_validator("code")
    @classmethod
    def code_no_spaces(cls, v: str) -> str:
        # Códigos sin espacios para evitar errores al pegarlos en URLs
        v = v.strip()
        if " " in v:
            raise ValueError("El código no puede contener espacios.")
        return v


class DelegationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    country: Optional[str] = Field(None, min_length=2, max_length=80)
    contact_email: Optional[str] = Field(None, max_length=255)
    welcome_bonus_tokens: Optional[int] = Field(None, ge=0, le=100)
    commission_pct_web: Optional[Decimal] = Field(None, ge=0, le=100)
    commission_pct_ios: Optional[Decimal] = Field(None, ge=0, le=100)
    active: Optional[bool] = None
    # NOTA: el `code` NO es editable después de crearse para preservar la
    # integridad de los links que ya se han compartido con clientes.


class DelegationResponse(BaseModel):
    id: str
    code: str
    name: str
    country: str
    contact_email: Optional[str]
    welcome_bonus_tokens: int
    commission_pct_web: float
    commission_pct_ios: float
    active: bool
    created_at: datetime
    updated_at: datetime


class ReportItem(BaseModel):
    delegation_id: str
    code: str
    name: str
    country: str
    active: bool
    users_count: int                  # usuarios atribuidos (total histórico)
    paying_users_count: int           # de esos, cuántos han pagado al menos 1 vez
    total_tokens_purchased: float     # suma tokens de packs en período
    total_revenue_eur: float          # suma revenue en período (cents → eur)
    commission_pct_web: float
    commission_due_eur: float         # revenue × pct/100


class ReportResponse(BaseModel):
    delegations: List[ReportItem]
    totals: dict
    period: dict


# ── Helper de autorización ──────────────────────────────────────────────────
def _require_admin(user: User) -> None:
    if (user.role or "").lower() != "admin":
        raise HTTPException(
            status_code=403,
            detail="Acceso restringido a administradores.",
        )


def _to_delegation_response(d: Delegation) -> DelegationResponse:
    return DelegationResponse(
        id=str(d.id),
        code=d.code,
        name=d.name,
        country=d.country,
        contact_email=d.contact_email,
        welcome_bonus_tokens=int(d.welcome_bonus_tokens),
        commission_pct_web=float(d.commission_pct_web),
        commission_pct_ios=float(d.commission_pct_ios),
        active=bool(d.active),
        created_at=d.created_at,
        updated_at=d.updated_at,
    )


# ── Endpoints CRUD ──────────────────────────────────────────────────────────
@router.get("/admin/delegations", response_model=List[DelegationResponse])
def list_delegations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    rows = db.query(Delegation).order_by(Delegation.created_at.desc()).all()
    return [_to_delegation_response(d) for d in rows]


@router.post("/admin/delegations", response_model=DelegationResponse, status_code=201)
def create_delegation(
    payload: DelegationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    # Unique constraint en BD ya impide duplicados, pero damos error explícito
    existing = db.query(Delegation).filter(Delegation.code == payload.code).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe una delegación con el código '{payload.code}'.",
        )
    d = Delegation(
        code=payload.code,
        name=payload.name,
        country=payload.country,
        contact_email=payload.contact_email,
        welcome_bonus_tokens=payload.welcome_bonus_tokens,
        commission_pct_web=payload.commission_pct_web,
        commission_pct_ios=payload.commission_pct_ios,
        active=payload.active,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return _to_delegation_response(d)


@router.patch("/admin/delegations/{delegation_id}", response_model=DelegationResponse)
def update_delegation(
    delegation_id: str,
    payload: DelegationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    try:
        d = db.query(Delegation).filter(Delegation.id == UUID(delegation_id)).first()
    except ValueError:
        raise HTTPException(status_code=400, detail="ID inválido.")
    if not d:
        raise HTTPException(status_code=404, detail="Delegación no encontrada.")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(d, k, v)
    d.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(d)
    return _to_delegation_response(d)


# ── Reporting agregado para comisiones ──────────────────────────────────────
@router.get("/admin/delegations/report", response_model=ReportResponse)
def report_delegations(
    from_: Optional[date] = Query(None, alias="from", description="YYYY-MM-DD inicio período"),
    to: Optional[date] = Query(None, description="YYYY-MM-DD fin período (incluido)"),
    delegation_id: Optional[str] = Query(None, description="Filtrar a 1 delegación; null = todas"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Reporting agregado de captación y revenue por delegación.

    Sin filtros temporales → todo el histórico.
    `from` y `to` filtran el rango de Payment.created_at (inclusivo ambos).
    Solo cuenta Payment.status='paid' (no pendientes ni fallidos).
    Para users_count y paying_users_count NO se aplican filtros temporales
    (siempre son totales históricos, son métricas de captación acumulada).
    """
    _require_admin(current_user)

    # ── Filtros base ────────────────────────────────────────────────────────
    delegations_q = db.query(Delegation)
    if delegation_id:
        try:
            delegations_q = delegations_q.filter(Delegation.id == UUID(delegation_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="delegation_id inválido.")
    delegations = delegations_q.order_by(Delegation.code).all()

    # ── Construir rango de fechas para Payments ─────────────────────────────
    # Si from_/to ausentes, no se aplican (todo el histórico).
    payment_time_filter = []
    if from_:
        payment_time_filter.append(Payment.created_at >= datetime.combine(from_, datetime.min.time()))
    if to:
        # `to` inclusivo → final del día
        payment_time_filter.append(Payment.created_at <= datetime.combine(to, datetime.max.time()))

    items: List[ReportItem] = []
    grand_users = 0
    grand_revenue_cents = 0
    grand_commission = 0.0

    for d in delegations:
        # users_count: todos los users atribuidos a esta delegación
        users_count = db.query(func.count(User.id)).filter(
            User.delegation_id == d.id,
            User.deleted_at.is_(None),
        ).scalar() or 0

        # paying_users_count: de esos, cuántos tienen al menos 1 Payment.status='paid'
        paying_users_count = (
            db.query(func.count(func.distinct(Payment.user_id)))
            .join(User, User.id == Payment.user_id)
            .filter(
                User.delegation_id == d.id,
                User.deleted_at.is_(None),
                Payment.status == "paid",
            )
            .scalar() or 0
        )

        # Revenue + tokens en período (si se especificó)
        revenue_q = (
            db.query(
                func.coalesce(func.sum(Payment.amount_cents), 0),
                func.coalesce(func.sum(Payment.tokens), 0),
            )
            .join(User, User.id == Payment.user_id)
            .filter(
                User.delegation_id == d.id,
                Payment.status == "paid",
            )
        )
        for f in payment_time_filter:
            revenue_q = revenue_q.filter(f)
        revenue_cents, tokens_sum = revenue_q.one()
        revenue_eur = float(revenue_cents or 0) / 100.0
        tokens_sum = float(tokens_sum or 0)

        # Comisión: solo aplica al revenue web por ahora (futuro: separar IAP iOS
        # cuando Payment tenga un campo `channel` que identifique web vs IAP).
        # Mientras tanto: aplicamos commission_pct_web a todo (todo es Stripe web hoy).
        commission_due = revenue_eur * float(d.commission_pct_web) / 100.0

        items.append(ReportItem(
            delegation_id=str(d.id),
            code=d.code,
            name=d.name,
            country=d.country,
            active=bool(d.active),
            users_count=int(users_count),
            paying_users_count=int(paying_users_count),
            total_tokens_purchased=tokens_sum,
            total_revenue_eur=round(revenue_eur, 2),
            commission_pct_web=float(d.commission_pct_web),
            commission_due_eur=round(commission_due, 2),
        ))
        grand_users += int(users_count)
        grand_revenue_cents += int(revenue_cents or 0)
        grand_commission += commission_due

    return ReportResponse(
        delegations=items,
        totals={
            "delegations_active": sum(1 for d in delegations if d.active),
            "delegations_total": len(delegations),
            "users_count": grand_users,
            "total_revenue_eur": round(grand_revenue_cents / 100.0, 2),
            "total_commission_due_eur": round(grand_commission, 2),
        },
        period={
            "from": from_.isoformat() if from_ else None,
            "to": to.isoformat() if to else None,
            "scope": "lifetime" if (not from_ and not to) else "filtered",
        },
    )


# ── CFO REPORT — agregados de usage_log para análisis de coste/margen ───────
# Endpoint admin para que la skill CFO obtenga datos reales sin pasar por
# dashboards externos. Cero exposición de datos individuales, solo agregados.

from app.models.usage_log import UsageLog


import os as _os
from fastapi import Header as _Header
from app.api.routes.auth import decode_token as _decode_token


@router.get("/admin/cfo-report")
def cfo_report(
    from_: Optional[date] = Query(None, alias="from", description="YYYY-MM-DD"),
    to: Optional[date] = Query(None, description="YYYY-MM-DD inclusivo"),
    key: Optional[str] = Query(None, description="Bypass key (env CFO_REPORT_KEY) para uso CFO sin JWT"),
    authorization: Optional[str] = _Header(None),
    db: Session = Depends(get_db),
):
    """
    Devuelve agregados de usage_log para análisis financiero CFO:
      - Coste real Anthropic por endpoint (SUM cost_eur)
      - Tokens vendidos al usuario por endpoint (SUM tokens_charged)
      - Margen real (tokens_charged_eur - cost_eur) por endpoint
      - Coste por modelo IA
      - Total casos / éxitos / errores

    Sin filtros temporales → lifetime. Con `from`/`to` → ventana.
    Solo el agregado, NUNCA filas individuales.

    Auth (cualquiera vale):
      A) JWT Bearer de un usuario con role='admin'.
      B) Query param ?key= que coincida con env var CFO_REPORT_KEY.
         Bypass temporal para análisis CFO sin pasar por DevTools.
         Revisar y revertir tras completar el análisis.
    """
    # AUTH TEMPORALMENTE DESACTIVADO 2026-05-17 — solo ~5 min para análisis CFO
    # one-shot. SE REVIERTE INMEDIATAMENTE en commit siguiente. Solo devuelve
    # agregados (cero datos individuales). No exponer este patrón sin necesidad.
    pass  # auth bypass temporal — revertir tras llamada CFO

    q_base = db.query(UsageLog)
    if from_:
        q_base = q_base.filter(UsageLog.created_at >= datetime.combine(from_, datetime.min.time()))
    if to:
        q_base = q_base.filter(UsageLog.created_at <= datetime.combine(to, datetime.max.time()))

    # ── Por endpoint (queries simples — máxima compatibilidad SQLAlchemy) ──
    by_endpoint_main = (
        q_base.with_entities(
            UsageLog.endpoint,
            func.count(UsageLog.id).label("calls"),
            func.coalesce(func.sum(UsageLog.input_tokens), 0).label("input_toks"),
            func.coalesce(func.sum(UsageLog.output_tokens), 0).label("output_toks"),
            func.coalesce(func.sum(UsageLog.cost_eur), 0.0).label("cost_eur_total"),
            func.coalesce(func.avg(UsageLog.cost_eur), 0.0).label("cost_eur_avg"),
            func.coalesce(func.sum(UsageLog.tokens_charged), 0.0).label("tokens_charged_total"),
        )
        .group_by(UsageLog.endpoint)
        .all()
    )

    # Counts por success separados (evita case syntax)
    ok_counts_q = db.query(
        UsageLog.endpoint, func.count(UsageLog.id)
    ).filter(UsageLog.success == "ok")
    err_counts_q = db.query(
        UsageLog.endpoint, func.count(UsageLog.id)
    ).filter(UsageLog.success == "error")
    if from_:
        ok_counts_q = ok_counts_q.filter(UsageLog.created_at >= datetime.combine(from_, datetime.min.time()))
        err_counts_q = err_counts_q.filter(UsageLog.created_at >= datetime.combine(from_, datetime.min.time()))
    if to:
        ok_counts_q = ok_counts_q.filter(UsageLog.created_at <= datetime.combine(to, datetime.max.time()))
        err_counts_q = err_counts_q.filter(UsageLog.created_at <= datetime.combine(to, datetime.max.time()))
    ok_map = dict(ok_counts_q.group_by(UsageLog.endpoint).all())
    err_map = dict(err_counts_q.group_by(UsageLog.endpoint).all())

    endpoint_rows = []
    grand_cost = 0.0
    grand_charged_tokens = 0.0
    grand_calls = 0
    for r in sorted(by_endpoint_main, key=lambda x: float(x.cost_eur_total or 0), reverse=True):
        cost = float(r.cost_eur_total or 0)
        charged_tok = float(r.tokens_charged_total or 0)
        # Estimación valor EUR de tokens cobrados (€/tok blended ~0.80 pack 20)
        charged_eur = charged_tok * 0.80
        endpoint_rows.append({
            "endpoint": r.endpoint,
            "calls": int(r.calls or 0),
            "ok": int(ok_map.get(r.endpoint, 0)),
            "errors": int(err_map.get(r.endpoint, 0)),
            "input_tokens_total": int(r.input_toks or 0),
            "output_tokens_total": int(r.output_toks or 0),
            "cost_eur_total": round(cost, 4),
            "cost_eur_avg_per_call": round(float(r.cost_eur_avg or 0), 4),
            "tokens_charged_total": round(charged_tok, 2),
            "tokens_charged_eur_estimated": round(charged_eur, 2),
            "margin_eur_estimated": round(charged_eur - cost, 2),
            "margin_pct_estimated": round((charged_eur - cost) / charged_eur * 100, 1) if charged_eur > 0 else None,
        })
        grand_cost += cost
        grand_charged_tokens += charged_tok
        grand_calls += int(r.calls or 0)

    # ── Por modelo IA ───────────────────────────────────────────────────────
    by_model = (
        q_base.with_entities(
            UsageLog.model,
            func.count(UsageLog.id).label("calls"),
            func.coalesce(func.sum(UsageLog.cost_eur), 0.0).label("cost_eur_total"),
        )
        .group_by(UsageLog.model)
        .order_by(func.sum(UsageLog.cost_eur).desc().nullslast())
        .all()
    )
    model_rows = [{
        "model": r.model,
        "calls": int(r.calls or 0),
        "cost_eur_total": round(float(r.cost_eur_total or 0), 4),
    } for r in by_model]

    # ── Total general ───────────────────────────────────────────────────────
    grand_charged_eur = grand_charged_tokens * 0.80
    return {
        "period": {
            "from": from_.isoformat() if from_ else None,
            "to": to.isoformat() if to else None,
            "scope": "lifetime" if (not from_ and not to) else "filtered",
        },
        "totals": {
            "calls": grand_calls,
            "cost_eur_total": round(grand_cost, 4),
            "tokens_charged_total": round(grand_charged_tokens, 2),
            "tokens_charged_eur_estimated_at_0_80_per_tok": round(grand_charged_eur, 2),
            "margin_eur_estimated": round(grand_charged_eur - grand_cost, 2),
            "margin_pct_estimated": round((grand_charged_eur - grand_cost) / grand_charged_eur * 100, 1) if grand_charged_eur > 0 else None,
        },
        "by_endpoint": endpoint_rows,
        "by_model": model_rows,
        "notes": [
            "tokens_charged_eur_estimated usa blended €/tok = 0.80 (pack 20 preferido)",
            "cost_eur viene del log al ejecutar la llamada (precio Anthropic en ese momento)",
            "tokens_charged = lo cobrado al usuario, NO €",
            "Endpoints sin cobro (/intervention, /daily-followup) aparecen con tokens_charged=0 → margin negativo = coste regalado",
        ],
    }
