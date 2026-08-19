"""
Modelo de suscripción (agosto 2026) — catálogo de planes y control de acceso.

Reglas fijadas por el founder (2026-07-30):

  · Cuatro planes mensuales. El descuento va EN CRÉDITOS, no en precio, y se
    mide contra el Básico (no contra el plan anterior):
        Básico 5 € → 800 cr (160 cr/€)   ·  Medio 12 € → 2.160 cr (180)
        Pro   22 € → 4.400 cr (200)      ·  Max   75 € → 17.250 cr (230)
  · Entrada: registro gratis + 3 días de prueba con 500 créditos de bienvenida.
    Al tercer día esos créditos NO se borran: quedan bloqueados y vuelven a
    funcionar en cuanto el usuario se suscribe (se suman a los del plan).
  · Usuarios anteriores al corte: pueden seguir gastando su saldo SIN
    suscribirse hasta bajar de lo que cuesta un análisis (300 cr = 3 tokens).
  · Saldos COMPRADOS: intactos siempre, sin caducidad.

El backend sigue contando en TOKENS (columna NUMERIC, cero migración de datos).
1 token = 100 créditos. La capa visual multiplica ×100.

TODO el muro está gobernado por SUBS_PAYWALL_ENABLED en Railway: apagado, este
módulo no niega nada a nadie (comportamiento idéntico al actual).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

_log = logging.getLogger(__name__)

CREDITS_PER_TOKEN = 100

# Coste del análisis completo — umbral del saldo heredado (300 cr).
ANALYSIS_TOKENS = 3.0

TRIAL_DAYS = 3
WELCOME_CREDITS = 500  # = 5 tokens, que es justo el regalo de registro actual

# Fecha de corte del modelo. Antes de esto = usuario heredado.
DEFAULT_CUTOVER = "2026-08-10"

# Catálogo por defecto. Se puede sobreescribir entero con SUBS_PLANS (JSON) en
# Railway sin tocar código ni publicar build nuevo.
DEFAULT_PLANS = [
    {
        "id": "basico",
        "name": {"es": "Básico", "en": "Basic", "it": "Base"},
        "price": 5.0,
        "price_display": "5 €",
        "credits": 800,
        "product_id_ios": "net.thedogsmind.sub.basico",
        "product_id_android": "net.thedogsmind.sub.basico",
        "stripe_price_env": "STRIPE_PRICE_BASICO",
        "trial_days": TRIAL_DAYS,
        "badge": {"es": "", "en": "", "it": ""},
        "audience": "particular",
        "professional": False,
        "note": {
            "es": "Para propietarios particulares. Si eres profesional de la conducta "
                  "y quieres respuestas muy técnicas y elaboradas, tu plan empieza en Medio.",
            "en": "For private owners. If you are a behaviour professional and want highly "
                  "technical, in-depth answers, your plan starts at Plus.",
            "it": "Per proprietari privati. Se sei un professionista del comportamento e "
                  "vuoi risposte molto tecniche e approfondite, il tuo piano parte da Medio.",
        },
    },
    {
        "id": "medio",
        "name": {"es": "Medio", "en": "Plus", "it": "Medio"},
        "price": 12.0,
        "price_display": "12 €",
        "credits": 2160,
        "product_id_ios": "net.thedogsmind.sub.medio",
        "product_id_android": "net.thedogsmind.sub.medio",
        "stripe_price_env": "STRIPE_PRICE_MEDIO",
        # Los cuatro planes dan los 3 días (founder 2026-08-18); Stripe y las
        # tiendas ya los conceden, esto es lo que hace que la tarjeta lo diga.
        "trial_days": TRIAL_DAYS,
        "badge": {"es": "El más elegido", "en": "Most chosen", "it": "Il più scelto"},
        "audience": "profesional",
        "professional": True,
        "note": {
            "es": "Primer plan profesional: informes técnicos, perros de cliente y perfil de entidad.",
            "en": "First professional plan: technical reports, client dogs and company profile.",
            "it": "Primo piano professionale: referti tecnici, cani di clienti e profilo aziendale.",
        },
    },
    {
        "id": "pro",
        "name": {"es": "Pro", "en": "Pro", "it": "Pro"},
        "price": 22.0,
        "price_display": "22 €",
        "credits": 4400,
        "product_id_ios": "net.thedogsmind.sub.pro",
        "product_id_android": "net.thedogsmind.sub.pro",
        "stripe_price_env": "STRIPE_PRICE_PRO",
        "trial_days": TRIAL_DAYS,
        "badge": {"es": "", "en": "", "it": ""},
        "audience": "profesional",
        "professional": True,
        "note": {
            "es": "Profesional con volumen de casos.",
            "en": "Professional with a steady case load.",
            "it": "Professionista con volume di casi.",
        },
    },
    {
        "id": "max",
        "name": {"es": "Max", "en": "Max", "it": "Max"},
        "price": 75.0,
        "price_display": "75 €",
        "credits": 17250,
        "product_id_ios": "net.thedogsmind.sub.max",
        "product_id_android": "net.thedogsmind.sub.max",
        "stripe_price_env": "STRIPE_PRICE_MAX",
        "trial_days": TRIAL_DAYS,
        "badge": {"es": "Clínicas y centros", "en": "Clinics & centres", "it": "Cliniche e centri"},
        "audience": "profesional",
        "professional": True,
        "note": {
            "es": "Clínicas, centros y equipos.",
            "en": "Clinics, centres and teams.",
            "it": "Cliniche, centri e team.",
        },
    },
]


# ── Profesional por escalón de plan (founder 2026-08-06) ────────────────────
# El Básico es para propietarios particulares. Quien quiere respuestas técnicas
# y elaboradas (profesional de la conducta) arranca en el SEGUNDO escalón.
# Se puede mover con SUBS_PRO_MIN_PLAN sin tocar código.
PLAN_RANK = {"basico": 1, "medio": 2, "pro": 3, "max": 4}


def _env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def paywall_enabled(user=None) -> bool:
    """
    ¿Está el muro activo para este usuario?

    SUBS_PAYWALL_ENABLED lo enciende para todo el mundo (interruptor del 10-ago).
    SUBS_PAYWALL_TEST_EMAILS lo enciende SOLO para las cuentas listadas, que es
    como se prueba el flujo completo en producción sin tocar a ningún cliente.
    """
    if _env_bool("SUBS_PAYWALL_ENABLED", False):
        return True
    if user is not None:
        pruebas = {e.strip().lower() for e in os.environ.get("SUBS_PAYWALL_TEST_EMAILS", "").split(",") if e.strip()}
        if pruebas and (getattr(user, "email", "") or "").lower() in pruebas:
            return True
    return False


def professional_min_plan() -> str:
    """Escalón mínimo que abre lo profesional. Por defecto 'medio'."""
    val = os.environ.get("SUBS_PRO_MIN_PLAN", "medio").strip().lower()
    return val if val in PLAN_RANK else "medio"


def plan_rank(plan_id: Optional[str]) -> int:
    return PLAN_RANK.get((plan_id or "").strip().lower(), 0)


def professional_allowed(user, now: Optional[datetime] = None) -> dict:
    """
    ¿Puede esta cuenta usar las funciones profesionales (perros de cliente,
    perfil de entidad, informe técnico)?

    Nadie pierde lo que ya tenía: quien YA es profesional antes del corte
    (los que pagaron la membresía de 20 €, los invitados, los de cortesía)
    lo conserva. La regla del escalón solo aplica de aquí en adelante.
    """
    now = now or datetime.utcnow()
    minimo = professional_min_plan()

    def out(allowed, reason):
        return {
            "allowed": bool(allowed),
            "reason": reason,
            "min_plan": minimo,
            "min_plan_rank": PLAN_RANK.get(minimo, 2),
            "current_plan": getattr(user, "subscription_plan", None),
            "current_rank": plan_rank(getattr(user, "subscription_plan", None)),
        }

    if not paywall_enabled(user):
        return out(True, "paywall_off")
    if (getattr(user, "role", "user") or "user") in ("admin", "developer", "partner"):
        return out(True, "privileged")
    if is_exempt(user) or (getattr(user, "email", "") or "").lower() in exemption_codes():
        return out(True, "exempt")
    if getattr(user, "corporate_id", None) and \
       (getattr(user, "corporate_status", "") or "") == "active":
        return out(True, "corporate")
    # Derecho adquirido: ya era profesional antes de que existiera esta regla.
    if (getattr(user, "account_type", "") or "") == "professional" and is_legacy(user):
        return out(True, "grandfathered")
    if subscription_active(user, now) and \
       plan_rank(getattr(user, "subscription_plan", None)) >= PLAN_RANK.get(minimo, 2):
        return out(True, "subscription")
    return out(False, "needs_higher_plan")


def cutover_date() -> datetime:
    raw = os.environ.get("SUBS_CUTOVER_DATE", DEFAULT_CUTOVER).strip()
    try:
        return datetime.strptime(raw, "%Y-%m-%d")
    except Exception:
        return datetime.strptime(DEFAULT_CUTOVER, "%Y-%m-%d")


def plans() -> list:
    """Catálogo vigente (env SUBS_PLANS manda; si no, el de código)."""
    raw = os.environ.get("SUBS_PLANS", "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list) and parsed:
                return parsed
        except Exception:
            _log.warning("SUBS_PLANS no es JSON válido — uso el catálogo de código")
    return DEFAULT_PLANS


def plan_by_id(plan_id: str) -> Optional[dict]:
    for p in plans():
        if p.get("id") == plan_id:
            return p
    return None


def plan_by_product_id(product_id: str) -> Optional[dict]:
    if not product_id:
        return None
    pid = product_id.strip()
    for p in plans():
        if pid in (p.get("product_id_ios"), p.get("product_id_android"), p.get("id")):
            return p
    return None


def exemption_codes() -> set:
    """Códigos de cortesía: cuentas que nunca ven el muro (invitados del founder)."""
    raw = os.environ.get("SUBS_EXEMPT_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def is_exempt(user) -> bool:
    """Miembro del equipo con código canjeado: nunca ve el muro, no caduca."""
    return (getattr(user, "subscription_status", None) or "").lower() == "exempt"


def team_code() -> str:
    """Código de equipo (env SUBS_TEAM_CODE en Railway). Vacío = desactivado."""
    return os.environ.get("SUBS_TEAM_CODE", "").strip().upper()


def subscription_active(user, now: Optional[datetime] = None) -> bool:
    now = now or datetime.utcnow()
    status = (getattr(user, "subscription_status", None) or "").lower()
    if status == "exempt":
        return True
    if status not in ("active", "trialing", "in_grace"):
        return False
    expires = getattr(user, "subscription_expires_at", None)
    if expires is None:
        return True  # activa sin fecha conocida (webhook aún no la trajo)
    return expires > now


def trial_state(user, now: Optional[datetime] = None) -> dict:
    """Estado de la prueba de 3 días. `started` = created_at si no hay marca."""
    now = now or datetime.utcnow()
    started = getattr(user, "trial_started_at", None) or getattr(user, "created_at", None)
    if not started:
        return {"active": False, "days_left": 0, "started_at": None, "ends_at": None}
    ends = started + timedelta(days=TRIAL_DAYS)
    left = (ends - now).total_seconds() / 86400.0
    return {
        "active": now < ends,
        "days_left": max(0, int(left) + (1 if left % 1 else 0)),
        "started_at": started,
        "ends_at": ends,
    }


def is_legacy(user) -> bool:
    """Usuario anterior al cambio de modelo."""
    created = getattr(user, "created_at", None)
    return bool(created and created < cutover_date())


def access_state(user, now: Optional[datetime] = None) -> dict:
    """
    Decide si el usuario puede consumir créditos, y por qué.

    reason:
      paywall_off        · el muro está apagado (estado actual hasta el 10-ago)
      privileged         · admin/developer
      exempt             · código de cortesía
      subscription       · suscripción viva
      legacy_balance     · usuario anterior al corte con saldo >= 1 análisis
      trial              · dentro de los 3 días de prueba
      needs_subscription · muro: hay que suscribirse (o el saldo heredado bajó de 300 cr)
    """
    now = now or datetime.utcnow()
    tokens = float(getattr(user, "tokens", 0) or 0)
    trial = trial_state(user, now)

    def out(allowed, reason):
        return {
            "allowed": allowed,
            "reason": reason,
            "tokens": tokens,
            "credits": int(round(tokens * CREDITS_PER_TOKEN)),
            "plan": getattr(user, "subscription_plan", None),
            "subscription_status": getattr(user, "subscription_status", None),
            "subscription_expires_at": getattr(user, "subscription_expires_at", None),
            "trial_active": trial["active"],
            "trial_days_left": trial["days_left"],
            "trial_ends_at": trial["ends_at"],
            "legacy": is_legacy(user),
            "paywall_enabled": paywall_enabled(user),
        }

    if not paywall_enabled(user):
        return out(True, "paywall_off")
    if (getattr(user, "role", "user") or "user") in ("admin", "developer"):
        return out(True, "privileged")
    if (getattr(user, "email", "") or "").lower() in exemption_codes():
        return out(True, "exempt")
    if is_exempt(user):
        return out(True, "exempt")
    if (getattr(user, "role", "user") or "user") == "partner":
        return out(True, "partner")
    if getattr(user, "corporate_id", None) and \
       (getattr(user, "corporate_status", "") or "") == "active":
        return out(True, "corporate")
    if subscription_active(user, now):
        return out(True, "subscription")
    if is_legacy(user) and tokens >= ANALYSIS_TOKENS:
        # Regla del founder: los de antes siguen gastando su saldo sin suscribirse
        # hasta que baje de lo que cuesta un análisis.
        return out(True, "legacy_balance")
    if trial["active"]:
        return out(True, "trial")
    return out(False, "needs_subscription")


def paywall_message(state: dict, lang: str = "es") -> str:
    """Mensaje humano del 402 (el frontend, además, abre la pantalla de planes)."""
    legacy = state.get("legacy")
    textos = {
        "es": (
            "Tu saldo ha bajado de lo que cuesta un análisis. Elige un plan para seguir."
            if legacy else
            "Tu prueba de 3 días ha terminado. Elige un plan para seguir usando la app; "
            "tus créditos de bienvenida vuelven a estar disponibles al suscribirte."
        ),
        "en": (
            "Your balance is below the cost of one analysis. Choose a plan to continue."
            if legacy else
            "Your 3-day trial has ended. Choose a plan to keep using the app; your welcome "
            "credits become available again as soon as you subscribe."
        ),
        "it": (
            "Il tuo saldo è sceso sotto il costo di un'analisi. Scegli un piano per continuare."
            if legacy else
            "La prova di 3 giorni è terminata. Scegli un piano per continuare a usare l'app; "
            "i crediti di benvenuto tornano disponibili appena ti abboni."
        ),
    }
    return textos.get(lang, textos["es"])
