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
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.case import DailyTip
from app.services.daily_tip_ai import generate_daily_tip, get_fallback_tip

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

    # 2) Generar via Haiku
    try:
        tip = generate_daily_tip(lang=lang)
    except Exception as e:
        # Anthropic caido / overload / timeout — devolver fallback estatico
        # sin persistir (para que mañana se reintente).
        logger.error(f"[daily-tip] Haiku failed for {today} {lang}: {e}")
        return DailyTipResponse(
            date=today, lang=lang, tip=get_fallback_tip(lang), cached=False,
        )

    # 3) Persistir y devolver
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
