from functools import lru_cache
import anthropic
from app.config import get_settings


@lru_cache
def get_anthropic_client() -> anthropic.Anthropic:
    settings = get_settings()
    # max_retries=5 (default del SDK = 2): el SDK reintenta con backoff exponencial
    # ante 429/5xx/529 (sobrecarga de Anthropic). Aguanta sobrecargas transitorias
    # de Sonnet sin que el usuario llegue a ver el error.
    return anthropic.Anthropic(api_key=settings.anthropic_api_key, max_retries=5)


def create_message_resilient(*, model, fallback_model=None, **kwargs):
    """
    Envoltura de client.messages.create con FALLBACK DE MODELO ante sobrecarga.

    Tras agotar los reintentos del SDK sobre el modelo primario, si Anthropic
    sigue devolviendo 529 (Overloaded), reintenta UNA vez con `fallback_model`
    (que tiene un pool de capacidad distinto — p.ej. Opus cuando Sonnet está
    saturado). Cualquier otro error (auth, bad request, rate limit, etc.) se
    propaga sin tocar. Aditivo: sin `fallback_model` se comporta exactamente
    igual que client.messages.create.
    """
    client = get_anthropic_client()
    try:
        return client.messages.create(model=model, **kwargs)
    except anthropic.APIStatusError as e:
        if fallback_model and getattr(e, "status_code", None) == 529:
            # Opus 4.7/4.8 NO aceptan temperature/top_p/top_k (devuelven 400). Como el
            # fallback puede ser un Opus, los quitamos al subir de modelo para que el
            # reintento no falle por eso.
            fb_kwargs = {k: v for k, v in kwargs.items()
                         if k not in ("temperature", "top_p", "top_k")}
            return client.messages.create(model=fallback_model, **fb_kwargs)
        raise
