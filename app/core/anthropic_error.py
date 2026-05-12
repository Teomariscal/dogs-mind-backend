"""
Helper para traducir errores transient de Anthropic API (529 overloaded,
rate-limit, network) a códigos HTTP apropiados para el cliente.

Sin esto el backend devuelve HTTP 500 con el detail crudo de Anthropic
("Error code: 529 - {'type': 'overloaded_error', ...}") que confunde al
cliente: parece un bug nuestro cuando es saturación del proveedor IA.

Uso típico en routers:

    from app.core.anthropic_error import raise_http_for_anthropic

    try:
        result = run_intervention_plan(request)
    except Exception as e:
        raise_http_for_anthropic(e)  # devuelve 503 si overloaded, raise HTTPException 500 si otro

`raise_http_for_anthropic` SIEMPRE levanta HTTPException — nunca retorna.
"""

from fastapi import HTTPException


# Mensajes user-facing para cada tipo de error transient.
# Se mantienen en español por defecto; el cliente puede traducirlos si quiere.
_MSG_OVERLOADED = (
    "El servicio de IA está temporalmente sobrecargado. "
    "Reinténtalo en un minuto."
)
_MSG_RATE_LIMIT = (
    "Has alcanzado el límite de peticiones a la IA por ahora. "
    "Espera unos segundos antes de reintentar."
)
_MSG_TIMEOUT = (
    "El servicio de IA tardó demasiado en responder. "
    "Reinténtalo en un momento."
)


def _classify(exc: Exception) -> tuple[int, str] | None:
    """Devuelve (status_code, detail) si el error es un transient de
    Anthropic conocido, o None si es genérico (caller decide el 500)."""
    msg = str(exc)
    msg_lower = msg.lower()

    # 529 overloaded — el más común cuando hay picos de demanda.
    if "overloaded_error" in msg_lower or "529" in msg:
        return 503, _MSG_OVERLOADED

    # 429 rate limit.
    if "rate_limit_error" in msg_lower or "429" in msg:
        return 429, _MSG_RATE_LIMIT

    # Timeouts de red / conexión.
    if any(t in msg_lower for t in ["timeout", "connectionerror", "readtimeout"]):
        return 504, _MSG_TIMEOUT

    return None


def raise_http_for_anthropic(exc: Exception, *, fallback_msg: str | None = None):
    """Mira el error de Anthropic y levanta una HTTPException apropiada.

    - 529 overloaded → 503 con mensaje user-friendly.
    - 429 rate limit → 429 con mensaje user-friendly.
    - timeout/conexión → 504 con mensaje user-friendly.
    - Otro → 500 con el str del exc (o fallback_msg si se pasa).

    Esta función SIEMPRE levanta HTTPException — nunca retorna.
    """
    classification = _classify(exc)
    if classification is not None:
        status, detail = classification
        raise HTTPException(status_code=status, detail=detail)
    # Fallback 500 con el detail crudo o el mensaje del caller.
    raise HTTPException(status_code=500, detail=fallback_msg or str(exc))
