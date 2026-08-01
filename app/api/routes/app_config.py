"""Configuración remota de la app (bandera de avisos + paywall de suscripción).

Diseñado para el cambio de modelo económico de agosto 2026:
  · 1-ago  → banner de aviso en la app (APP_BANNER_ENABLED=true en Railway).
  · 10-ago → paywall de suscripción + puerta de recarga (SUBS_* en Railway).

TODO se gobierna con variables de entorno en Railway: encender/apagar avisos,
cambiar textos y definir planes NO requiere nuevo build de iOS/Android ni
deploy del frontend. El binario solo lleva el código de render (dormido).

Endpoint público sin auth: el frontend lo consulta al arrancar. Fail-safe:
si algo falla, el frontend asume "todo apagado" (comportamiento actual).
"""

import json
import os

from fastapi import APIRouter

router = APIRouter()


def _env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


@router.get("/app-config")
def get_app_config():
    # ── Banner de aviso (1-ago) ──────────────────────────────────────────────
    # El TEXTO lo aporta el founder vía env vars (regla: copy público suyo).
    # Si un idioma falta, el frontend cae al texto ES; si ES falta, no pinta nada.
    banner = {
        "enabled": _env_bool("APP_BANNER_ENABLED", False),
        "id": os.environ.get("APP_BANNER_ID", "aviso-2026-08"),
        "level": os.environ.get("APP_BANNER_LEVEL", "info"),  # info | warning
        "text": {
            "es": os.environ.get("APP_BANNER_TEXT_ES", ""),
            "en": os.environ.get("APP_BANNER_TEXT_EN", ""),
            "it": os.environ.get("APP_BANNER_TEXT_IT", ""),
        },
    }

    # ── Suscripciones (10-ago) ───────────────────────────────────────────────
    # SUBS_PLANS: JSON con la lista de planes (ids de producto de tienda,
    # créditos, precios de display). Los números los decide el founder; hasta
    # entonces queda vacío y el paywall no se muestra aunque el flag esté on.
    # Si SUBS_PLANS no está puesta, manda el catálogo de código (planes fijados
    # por el founder el 30-jul: 5/12/22/75 € → 800/2.160/4.400/17.250 créditos).
    from app.core import subscriptions as _subs

    subscriptions = {
        "enabled": _env_bool("SUBS_PAYWALL_ENABLED", False),
        # Puerta del 10-ago: si true, la recarga de tokens exige suscripción
        # activa o código de exención (la aplican los endpoints de compra).
        "recharge_gate": _env_bool("SUBS_RECHARGE_GATE", False),
        "plans": _subs.plans(),
        "credits_per_token": _subs.CREDITS_PER_TOKEN,
        "trial_days": _subs.TRIAL_DAYS,
        "welcome_credits": _subs.WELCOME_CREDITS,
    }

    return {"banner": banner, "subscriptions": subscriptions}
