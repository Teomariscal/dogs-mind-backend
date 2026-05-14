"""
Endpoint público para el "Consejo del día" mostrado en s-home.

GET /tip/today?lang=es|en

- Sin auth (público).
- Cachea por (date, lang) en tabla daily_tips. Una sola generacion al dia
  por idioma para TODOS los usuarios.
- Fallback estatico si Anthropic falla.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Literal
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.case import DailyTip
from app.services.daily_tip_ai import generate_daily_tip, get_fallback_tip

# Numero de dias hacia atras de tips que NO se pueden repetir.
# Con minimo 50 tips/año queremos variedad sin repeticion proxima. 14 dias
# da margen amplio: con 14 dias bloqueados Haiku tiene que rotar suficiente.
_NO_REPEAT_WINDOW_DAYS = 14

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tip", tags=["daily-tip"])


class DailyTipResponse(BaseModel):
    date: str
    lang: str
    tip: str
    cached: bool  # True si vino de cache DB, False si recien generado, None si fallback


def _today_utc_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@router.get("/today", response_model=DailyTipResponse)
def get_daily_tip(
    lang: Literal["es", "en"] = Query("es"),
    db: Session = Depends(get_db),
):
    """
    Devuelve el consejo del día para el idioma indicado.
    Cacheado server-side por (date, lang). Una sola generacion Haiku/dia/lang.
    """
    today = _today_utc_str()

    # 1) Ver cache DB
    existing = db.query(DailyTip).filter(
        DailyTip.date == today,
        DailyTip.lang == lang,
    ).first()

    if existing:
        return DailyTipResponse(
            date=today, lang=lang, tip=existing.tip, cached=True,
        )

    # 2) Recuperar tips de los ultimos N dias para que Haiku no los repita.
    #    Garantia: minimo 50 tips/año, sin repeticion en ventana de 14 dias.
    cutoff = (datetime.now(timezone.utc) - timedelta(days=_NO_REPEAT_WINDOW_DAYS)).strftime("%Y-%m-%d")
    recent_rows = db.query(DailyTip).filter(
        DailyTip.lang == lang,
        DailyTip.date >= cutoff,
        DailyTip.date < today,  # excluir hoy (no existe aun, pero por seguridad)
    ).order_by(DailyTip.date.desc()).limit(_NO_REPEAT_WINDOW_DAYS).all()
    recent_tips = [r.tip for r in recent_rows]

    # 3) Generar via Haiku con la lista de tips recientes a evitar
    try:
        tip = generate_daily_tip(lang=lang, recent_tips=recent_tips)
    except Exception as e:
        # Anthropic caido / overload / timeout — devolver fallback estatico
        # sin persistir (para que mañana se reintente).
        logger.error(f"[daily-tip] Haiku failed for {today} {lang}: {e}")
        return DailyTipResponse(
            date=today, lang=lang, tip=get_fallback_tip(lang), cached=False,
        )

    # 4) Persistir y devolver
    try:
        new_tip = DailyTip(date=today, lang=lang, tip=tip)
        db.add(new_tip)
        db.commit()
    except Exception as e:
        # Si dos requests concurrentes generan el mismo dia/lang, el unique
        # index lanza IntegrityError en la 2a. Recuperamos la 1a.
        db.rollback()
        logger.warning(f"[daily-tip] DB write race for {today} {lang}: {e}")
        existing = db.query(DailyTip).filter(
            DailyTip.date == today, DailyTip.lang == lang,
        ).first()
        if existing:
            return DailyTipResponse(
                date=today, lang=lang, tip=existing.tip, cached=True,
            )

    return DailyTipResponse(date=today, lang=lang, tip=tip, cached=False)
