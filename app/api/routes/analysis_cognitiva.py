"""
POST /analysis/cognitiva — la relación clínica cognitivista de Odette.

Fichero APARTE a propósito. La vía conductual (`analysis.py`) no se toca ni una
línea: son dos caminos que no comparten ni modelo de entrada, ni prompts, ni
ruta. Ése es el aislamiento que pidió el founder el 6-sep-2026 ("extrema
cautela ... que no haya nunca ninguna fuga cognitivista a la parte conductual").

La puerta se comprueba DOS veces a propósito: aquí, para poder devolver un 403
claro y no cobrar; y otra vez dentro del motor, que falla cerrado por su cuenta
aunque alguien lo llamara desde otro sitio en el futuro.
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import text

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.anthropic_error import raise_http_for_anthropic
from app.core.case_persistence import get_user_from_authorization
from app.core.latidos import con_latidos
from app.core.token_utils import deduct_token, refund_token
from app.core.usage_tracker import log_usage
from app.config import get_settings
from app.database import get_db
from app.models.anamnesis_cognitiva import AnamnesiCognitivaInput, AnamnesiCognitivaResponse
from app.services.cognitive_odette import redactar_relazione
from app.services.italian_cognitive import (
    CognitiveReexpressionError,
    cognitive_path_applies,
)

_log = logging.getLogger("analysis_cognitiva")

router = APIRouter(prefix="/analysis", tags=["cognitive-analysis"])

# Mismo coste que el análisis conductual: es el mismo trabajo clínico y el
# founder no quiere dos tarifas para la misma consulta.
COSTE_TOKENS = 3.0


def _sincrono(
    anamnesi: AnamnesiCognitivaInput,
    background_tasks: BackgroundTasks,
    authorization: Optional[str],
    db: Session,
):
    usuario = get_user_from_authorization(authorization, db) if authorization else None
    account_type = getattr(usuario, "account_type", None) if usuario else None
    user_id = str(getattr(usuario, "id", "")) if usuario else None

    # ── LA PUERTA, antes de cobrar ──────────────────────────────────────
    if not cognitive_path_applies(
        lang=anamnesi.lang,
        account_type=account_type,
        stance=anamnesi.stance,
    ):
        raise HTTPException(
            status_code=403,
            detail="Questa via è riservata all'analisi cognitivista italiana per account professionali.",
        )

    deduct_token(authorization, db, amount=COSTE_TOKENS, require_auth=True)

    try:
        relazione, tipo, analisis = redactar_relazione(anamnesi, account_type=account_type)
    except PermissionError:
        refund_token(authorization, db, amount=COSTE_TOKENS)
        raise HTTPException(status_code=403, detail="La via cognitivista non si applica.")
    except CognitiveReexpressionError as e:
        # Nunca se degrada a la salida conductual: antes error y devolución.
        refund_token(authorization, db, amount=COSTE_TOKENS)
        _log.warning("relación cognitivista fallida: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Non è stato possibile redigere la relazione. Riprova tra poco.",
        )
    except Exception as e:
        refund_token(authorization, db, amount=COSTE_TOKENS)
        background_tasks.add_task(
            log_usage, user_id=user_id, endpoint="/analysis/cognitiva",
            model=get_settings().clinical_model, tokens_charged=COSTE_TOKENS,
            success="error", notes=str(e)[:200],
        )
        raise_http_for_anthropic(e)

    background_tasks.add_task(
        log_usage, user_id=user_id, endpoint="/analysis/cognitiva",
        model=get_settings().clinical_model, tokens_charged=COSTE_TOKENS,
        success="ok", notes=tipo,
    )
    # `fatti` es la pasada 1 (el analisis ABA oculto): se devuelve para poder
    # AUDITARLA desde fuera. La app NO la pinta nunca.
    return AnamnesiCognitivaResponse(relazione=relazione, tipo=tipo, fatti=analisis)


# ════════════════════════════════════════════════════════════════════════
#  TRABAJO EN SEGUNDO PLANO — por qué esto NO puede ir colgado de la conexión
#
#  El 13-sep-2026 el founder no conseguía sacar ni una relazione desde el
#  iPhone: la app devolvía "Load failed", que es lo que dice el WebView de iOS
#  cuando la petición se muere a nivel de red. En `usage_log` no había ni una
#  fila de esos intentos, y el motor no registró ningún error: el servidor
#  seguía trabajando y el móvil ya había soltado la conexión.
#
#  La causa de fondo es estructural, no un ajuste: esto son DOS pasadas de
#  generación y tarda minutos, mientras que el análisis conductual tarda ~66 s
#  y por eso sobrevive. Los latidos (`con_latidos`) protegen del SILENCIO, no
#  de que iOS suspenda la red al bloquear la pantalla ni de un tope de duración
#  total en el camino.
#
#  Así que el trabajo se suelta de la conexión: se lanza, se responde al
#  instante con un identificador, y la app pregunta. Bloquear el móvil, salir
#  de la app o perder la cobertura ya no matan el informe.
#
#  El almacén es `analysis_cache`, que ya existía para la idempotencia del
#  análisis conductual: misma tabla, misma huella, sin migraciones —este
#  proyecto no tiene— y con la idempotencia de regalo: reenviar la misma
#  anamnesi devuelve lo ya hecho sin cobrar dos veces.
# ════════════════════════════════════════════════════════════════════════

ENDPOINT = "/analysis/cognitiva"

# Cuánto puede estar un trabajo en "lavorando" antes de darlo por MUERTO.
#
# Sin esto, un trabajo que se corta —un despliegue a mitad, un reinicio del
# contenedor, un proceso que se cae— deja su fila en "lavorando" para siempre.
# Y como la huella de una anamnesi es SIEMPRE la misma, cada intento posterior
# encontraba esa fila y devolvía "en curso" sin relanzar nada: el usuario se
# quedaba sin poder reintentar salvo que cambiara una coma del formulario.
# Lo introduje yo el 13-sep-2026 al pasar esto a segundo plano.
#
# 12 minutos: la generación son dos pasadas y el techo del sondeo del cliente
# son 15, así que da margen de sobra a un trabajo lento sin dejar a nadie
# atrapado. Al relanzar NO se vuelve a cobrar: ese cobro ya se hizo.
LAVORO_MUERTO_MIN = 12


def _huella(anamnesi: AnamnesiCognitivaInput, user_id: Optional[str]) -> Optional[str]:
    if not user_id:
        return None
    try:
        datos = anamnesi.model_dump() if hasattr(anamnesi, "model_dump") else anamnesi.dict()
        crudo = json.dumps(datos, sort_keys=True, default=str, ensure_ascii=False)
        return hashlib.sha256(
            (str(user_id) + "|cognitiva|" + crudo).encode("utf-8")).hexdigest()
    except Exception:
        return None


def _leer(db: Session, huella: str) -> Optional[dict]:
    try:
        fila = db.execute(
            text("select payload from analysis_cache where fingerprint = :f"),
            {"f": huella},
        ).fetchone()
        return json.loads(fila[0]) if fila else None
    except Exception:
        return None


def _escribir(db: Session, huella: str, user_id: str, payload: dict) -> None:
    """Inserta o actualiza. Nunca lanza: perder el rastro no puede tumbar nada."""
    try:
        db.execute(
            text("insert into analysis_cache (fingerprint, user_id, endpoint, payload) "
                 "values (:f, :u, :e, :p) "
                 "on conflict (fingerprint) do update set payload = :p"),
            {"f": huella, "u": str(user_id), "e": ENDPOINT,
             "p": json.dumps(payload, default=str, ensure_ascii=False)},
        )
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def _trabajar(huella: str, anamnesi: AnamnesiCognitivaInput,
              account_type: Optional[str], user_id: str,
              authorization: Optional[str]) -> None:
    """Corre DESPUÉS de haber respondido, con su propia sesión de base de datos.

    La del request ya está cerrada cuando esto arranca, así que abre la suya y
    la cierra. Si falla, devuelve los créditos y deja escrito el motivo: el
    usuario lo lee al preguntar, en vez de quedarse mirando una pantalla.
    """
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        relazione, tipo, analisis = redactar_relazione(anamnesi, account_type=account_type)
        _escribir(db, huella, user_id, {
            "stato": "pronta",
            "relazione": relazione,
            "tipo": tipo,
            "fatti": analisis,
            "finito": datetime.utcnow().isoformat() + "Z",
        })
        try:
            log_usage(user_id=user_id, endpoint=ENDPOINT,
                      model=get_settings().clinical_model,
                      tokens_charged=COSTE_TOKENS, success="ok", notes=tipo)
        except Exception:
            pass
    except Exception as e:
        _log.warning("[cognitiva] trabajo fallido: %s", e)
        try:
            refund_token(authorization, db, amount=COSTE_TOKENS)
        except Exception:
            pass
        detalle = ("Non è stato possibile redigere la relazione. "
                   "I crediti sono stati restituiti. Riprova tra poco.")
        _escribir(db, huella, user_id, {"stato": "errore", "detail": detalle})
        try:
            log_usage(user_id=user_id, endpoint=ENDPOINT,
                      model=get_settings().clinical_model,
                      tokens_charged=0, success="error", notes=str(e)[:200])
        except Exception:
            pass
    finally:
        try:
            db.close()
        except Exception:
            pass


@router.post("/cognitiva", response_model=None)
def crear_relazione_cognitiva(
    anamnesi: AnamnesiCognitivaInput,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Lanza el trabajo y responde AL INSTANTE con su identificador."""
    usuario = get_user_from_authorization(authorization, db) if authorization else None
    account_type = getattr(usuario, "account_type", None) if usuario else None
    user_id = str(getattr(usuario, "id", "")) if usuario else None

    # La puerta, antes de cobrar y antes de mover un dedo.
    if not cognitive_path_applies(
        lang=anamnesi.lang, account_type=account_type, stance=anamnesi.stance,
    ):
        raise HTTPException(
            status_code=403,
            detail="Questa via è riservata all'analisi cognitivista italiana per account professionali.",
        )

    huella = _huella(anamnesi, user_id)
    if not huella:
        raise HTTPException(status_code=401, detail="Sessione non valida.")

    # Ya hecha: se devuelve sin cobrar. Es la idempotencia.
    previo = _leer(db, huella)
    if previo and previo.get("stato") == "pronta":
        return {"stato": "pronta", "id": huella}

    # En marcha: se respeta… salvo que lleve demasiado tiempo, en cuyo caso el
    # trabajo murió y hay que relanzarlo. Sin cobrar: ya se cobró al lanzarlo.
    if previo and previo.get("stato") == "lavorando":
        muerto = True
        try:
            desde = datetime.fromisoformat(
                str(previo.get("iniziato", "")).replace("Z", ""))
            muerto = (datetime.utcnow() - desde) > timedelta(minutes=LAVORO_MUERTO_MIN)
        except Exception:
            # Sin marca de tiempo legible no se puede saber: se da por vivo, que
            # es el lado seguro (no relanzar dos veces el mismo trabajo).
            muerto = False
        if not muerto:
            return {"stato": "lavorando", "id": huella}
        _log.warning("[cognitiva] trabajo colgado mas de %d min: se relanza sin cobrar (%s)",
                     LAVORO_MUERTO_MIN, huella[:12])
        _escribir(db, huella, user_id, {
            "stato": "lavorando",
            "iniziato": datetime.utcnow().isoformat() + "Z",
            "rilanciato": True,
        })
        background_tasks.add_task(_trabajar, huella, anamnesi, account_type,
                                  user_id, authorization)
        return {"stato": "lavorando", "id": huella}

    deduct_token(authorization, db, amount=COSTE_TOKENS, require_auth=True)
    _escribir(db, huella, user_id, {
        "stato": "lavorando",
        "iniziato": datetime.utcnow().isoformat() + "Z",
    })
    background_tasks.add_task(_trabajar, huella, anamnesi, account_type,
                             user_id, authorization)
    return {"stato": "lavorando", "id": huella}


@router.get("/cognitiva/{huella}", response_model=None)
def estado_relazione_cognitiva(
    huella: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """La app pregunta aquí cada pocos segundos. Solo ve lo suyo."""
    usuario = get_user_from_authorization(authorization, db) if authorization else None
    user_id = str(getattr(usuario, "id", "")) if usuario else None
    if not user_id:
        raise HTTPException(status_code=401, detail="Sessione non valida.")

    fila = db.execute(
        text("select payload, user_id from analysis_cache where fingerprint = :f"),
        {"f": huella},
    ).fetchone()
    if not fila or str(fila[1]) != user_id:
        raise HTTPException(status_code=404, detail="Relazione non trovata.")

    payload = json.loads(fila[0])
    estado = payload.get("stato")
    if estado == "pronta":
        return AnamnesiCognitivaResponse(
            relazione=payload.get("relazione", ""),
            tipo=payload.get("tipo", ""),
            fatti=payload.get("fatti", ""),
        )
    if estado == "errore":
        raise HTTPException(status_code=503, detail=payload.get("detail", "Errore."))
    return {"stato": "lavorando"}
