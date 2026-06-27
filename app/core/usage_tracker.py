"""
Helper para registrar uso y coste estimado en usage_log.

Precios Anthropic vigentes 2026-06 (en USD/millón tokens):
- claude-sonnet-4-6 / 4-5: input 3.00 / output 15.00
- claude-haiku-4-5:        input 1.00 / output 5.00
- claude-opus-4-8 / 4-7:   input 5.00 / output 25.00  (modelo de fallback ante 529)

Voyage AI (embeddings):
- voyage-3-large: 0.18 USD / millón tokens

Tipo de cambio aproximado USD→EUR: 0.92 (revisable). Para CFO real,
ajustar via env var EXCHANGE_USD_EUR cuando convenga.
"""

import os
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.database import SessionLocal
from app.models.usage_log import UsageLog

logger = logging.getLogger(__name__)

# Precios USD por 1M tokens (revisar trimestralmente)
_PRICES = {
    "claude-sonnet-4-6":  {"in": 3.00,  "out": 15.00},
    "claude-sonnet-4-5":  {"in": 3.00,  "out": 15.00},   # usado en /analysis/chat
    "claude-haiku-4-5":   {"in": 1.00,  "out": 5.00},    # corregido: era 0.80/4.00 (precio Haiku 3.5, infravaloraba ~25%)
    "claude-opus-4-8":    {"in": 5.00,  "out": 25.00},   # fallback ante 529 de Sonnet
    "claude-opus-4-7":    {"in": 5.00,  "out": 25.00},
    "voyage-3-large":     {"in": 0.18,  "out": 0.0},     # solo input
}

_USD_EUR = float(os.environ.get("EXCHANGE_USD_EUR", "0.92"))


def estimate_cost_eur(model: str, input_tokens: Optional[int], output_tokens: Optional[int]) -> Optional[float]:
    """Coste estimado en EUR. None si modelo no en tabla."""
    if model not in _PRICES:
        return None
    p = _PRICES[model]
    in_t = input_tokens or 0
    out_t = output_tokens or 0
    cost_usd = (in_t / 1_000_000.0) * p["in"] + (out_t / 1_000_000.0) * p["out"]
    return round(cost_usd * _USD_EUR, 6)


def log_usage(
    user_id: Optional[UUID],
    endpoint: str,
    model: str,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    tokens_charged: Optional[float] = None,
    success: str = "ok",
    notes: Optional[str] = None,
):
    """
    Sync log function — abre su propia DB session porque corre fuera del
    request lifecycle (vía BackgroundTasks). NO bloquea la response.
    Fail-open: cualquier error en el log se silencia.
    """
    db = SessionLocal()
    try:
        cost = estimate_cost_eur(model, input_tokens, output_tokens)
        row = UsageLog(
            user_id=user_id,
            endpoint=endpoint,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_eur=cost,
            tokens_charged=tokens_charged,
            success=success,
            notes=(notes or "")[:256] if notes else None,
        )
        db.add(row)
        db.commit()
    except Exception as e:
        logger.warning("usage_log write failed: %s", e, exc_info=False)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        try:
            db.close()
        except Exception:
            pass
