"""
Notificaciones push de reactivacion.

Encargo del founder (10-oct-2026): que quien lleva tres dias sin usar la app
reciba un aviso que le recuerde volver.

Aqui vive todo lo que decide A QUIEN se avisa, CUANDO y CON QUE TEXTO. El
envio en si son veinte lineas al final; lo largo son las guardas, que es lo que
separa un recordatorio de un incordio.

LOS TEXTOS SON DEL FOUNDER. Estan aprobados y transcritos literalmente desde
SPEC_PUSH_REACTIVACION.md. No se tocan, no se "mejoran" y no se añaden variantes
sin que las escriba el.
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

# ── Reglas de producto (del encargo) ─────────────────────────────────────────
DIAS_SIN_ACTIVIDAD   = 3    # a partir de cuanto silencio se avisa
MIN_DIAS_ENTRE_AVISOS = 3   # un envio cada 3 dias como maximo por usuario
MAX_POR_SEMANA        = 2   # tope en 7 dias naturales
HORA_LOCAL_DESDE      = 10  # ventana de envio, hora LOCAL del usuario
HORA_LOCAL_HASTA      = 20  # nada de madrugadas

# Freno de escritura de last_seen_at. Sin esto, cada peticion autenticada seria
# un UPDATE: con el movil abierto son decenas por minuto y por usuario, y lo que
# necesitamos saber es el dia, no el segundo.
LAST_SEEN_FRESCURA_MIN = 15


# ── Los textos del founder ───────────────────────────────────────────────────
# Clave de primer nivel: segmento. Segundo: idioma. (titulo, cuerpo).
#
# Van partidos en titulo + cuerpo porque en la pantalla bloqueada el cuerpo se
# corta sobre los 110 caracteres, y el texto de `con_casos` entero son 148: sin
# partir, la frase que remata ("Tienes seguimientos esperandote") quedaba
# escondida justo en el corte.
#
# Las versiones EN e IT usan los terminos que ya usa la app: seguimiento ->
# follow-up / monitoraggio, adiestramiento -> training / addestramento.
TEXTOS: dict = {
    "con_casos": {
        "es": ("No me creo que vayas a aflojar el ritmo",
               "Un problema de conducta exige constancia. Tú eres una persona constante. "
               "Tienes seguimientos esperándote."),
        "en": ("I don't buy that you'll ease off now",
               "A behaviour problem demands consistency. And you are a consistent person. "
               "You have follow-ups waiting."),
        "it": ("Non ci credo che adesso molli",
               "Un problema di comportamento richiede costanza. E tu sei una persona costante. "
               "Hai dei monitoraggi che ti aspettano."),
    },
    "nunca_probo": {
        "es": ("¿Has probado la app?",
               "Échale un vistazo, porque te vas a sorprender."),
        "en": ("Have you tried the app?",
               "Take a look — it is going to surprise you."),
        "it": ("Hai provato l'app?",
               "Dacci un'occhiata: ti sorprenderà."),
    },
    "probo_y_no_siguio": {
        "es": ("Hace días que no te vemos",
               "Asómate de nuevo a The Dogs' Mind: soluciona cualquier problema de conducta "
               "canina o diseña el mejor plan de adiestramiento."),
        "en": ("We haven't seen you in days",
               "Come back to The Dogs' Mind: solve any dog behaviour problem or design the "
               "best training plan."),
        "it": ("Non ti vediamo da giorni",
               "Rifatti vivo su The Dogs' Mind: risolvi qualsiasi problema di comportamento "
               "del cane o progetta il miglior piano di addestramento."),
    },
}


def texto_de(segmento: str, lang: str) -> tuple:
    """El par (titulo, cuerpo). Cae a español si llega un idioma que no tenemos."""
    porSegmento = TEXTOS.get(segmento) or TEXTOS["probo_y_no_siguio"]
    return porSegmento.get((lang or "es").lower()[:2], porSegmento["es"])


# ── last_seen_at ─────────────────────────────────────────────────────────────
def marcar_visto(db: Session, user) -> None:
    """
    Sella la ultima vez que el usuario tocó la app. Se llama desde
    get_current_user, que es por donde pasa TODA peticion autenticada.

    Escribe como mucho una vez cada LAST_SEEN_FRESCURA_MIN minutos: lo que nos
    importa es el dia, no el segundo, y un UPDATE por peticion castigaria la
    base por nada.

    Nunca lanza. Si esto falla, la peticion del usuario tiene que seguir: es un
    sello de telemetria, no parte de lo que vino a hacer.
    """
    try:
        ahora = datetime.utcnow()
        previo = getattr(user, "last_seen_at", None)
        if previo and (ahora - previo) < timedelta(minutes=LAST_SEEN_FRESCURA_MIN):
            return
        user.last_seen_at = ahora
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


# ── A quien se avisa ─────────────────────────────────────────────────────────
def _segmento_de(db: Session, user_id) -> str:
    """
    Los tres grupos del founder, decididos con lo que hay en la base:

      con_casos          — tiene al menos un caso guardado
      probo_y_no_siguio  — genero algo (hay huella en usage_log) y no guardo caso
      nunca_probo        — se registro y no llego a generar nada

    El orden importa: un usuario con casos tambien tiene usage_log, asi que se
    pregunta primero por lo mas especifico.
    """
    from app.models.case import Case
    from app.models.usage_log import UsageLog

    if db.query(Case.id).filter(Case.user_id == user_id).first():
        return "con_casos"
    if db.query(UsageLog.id).filter(UsageLog.user_id == user_id).first():
        return "probo_y_no_siguio"
    return "nunca_probo"


def _hora_local(tz_nombre: Optional[str]) -> Optional[int]:
    """
    Hora local del dispositivo, 0-23. None si no sabemos la zona.

    Sin zona NO se envia: la regla del founder es que no haya madrugadas, y
    deducir la zona del pais de la delegacion seria adivinar. El dispositivo la
    manda al registrarse, asi que solo le falta a quien tenga una fila vieja.
    """
    if not tz_nombre:
        return None
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(tz_nombre)).hour
    except Exception:
        return None


def _puede_recibir(db: Session, user_id) -> tuple:
    """
    Los topes de frecuencia, contra push_log. Devuelve (puede, motivo).

    Se consulta el log, no una marca en el usuario, porque el log es lo que
    sobrevive a cualquier cambio de criterio: si mañana el tope pasa a uno por
    semana, no hay que migrar nada.
    """
    from app.models.push_device import PushLog

    ahora = datetime.utcnow()

    ultimo = (
        db.query(PushLog.sent_at)
        .filter(PushLog.user_id == user_id, PushLog.ok == True)  # noqa: E712
        .order_by(PushLog.sent_at.desc())
        .first()
    )
    if ultimo and (ahora - ultimo[0]) < timedelta(days=MIN_DIAS_ENTRE_AVISOS):
        return False, f"hace menos de {MIN_DIAS_ENTRE_AVISOS} dias del ultimo"

    en_semana = (
        db.query(func.count(PushLog.id))
        .filter(
            PushLog.user_id == user_id,
            PushLog.ok == True,  # noqa: E712
            PushLog.sent_at > ahora - timedelta(days=7),
        )
        .scalar()
    ) or 0
    if en_semana >= MAX_POR_SEMANA:
        return False, f"ya lleva {en_semana} esta semana"

    return True, ""


def candidatos(db: Session, limite: int = 500) -> list:
    """
    Quien merece un aviso ahora mismo. Devuelve [(user, device, segmento)].

    Las cuatro condiciones, por orden de cuanto recortan:
      1. tiene dispositivo vivo        — sin token no hay a quien mandar nada
      2. no lo ha apagado en ajustes
      3. lleva DIAS_SIN_ACTIVIDAD sin aparecer
      4. su hora local cae en la ventana, y respeta los topes
    """
    from app.models.user import User
    from app.models.push_device import PushDevice
    from app.core.smoke import SMOKE_EMAIL_LIKE, DELETED_EMAIL_LIKE

    corte = datetime.utcnow() - timedelta(days=DIAS_SIN_ACTIVIDAD)

    filas = (
        db.query(User, PushDevice)
        .join(PushDevice, PushDevice.user_id == User.id)
        .filter(
            PushDevice.active == True,          # noqa: E712
            User.deleted_at.is_(None),
            User.push_enabled == True,          # noqa: E712
            ~User.email.like(SMOKE_EMAIL_LIKE),
            ~User.email.like(DELETED_EMAIL_LIKE),
            # NULL = nunca lo hemos sellado. Cuenta como silencio: su fila de
            # dispositivo existe, asi que la app se abrio en algun momento.
            or_(User.last_seen_at.is_(None), User.last_seen_at < corte),
        )
        .limit(limite * 4)   # holgura: muchos caeran por hora local o por tope
        .all()
    )

    salida = []
    vistos = set()
    for user, device in filas:
        if user.id in vistos:
            continue                      # un aviso por persona, no por aparato

        h = _hora_local(device.tz)
        if h is None or not (HORA_LOCAL_DESDE <= h < HORA_LOCAL_HASTA):
            continue

        puede, _motivo = _puede_recibir(db, user.id)
        if not puede:
            continue

        vistos.add(user.id)
        salida.append((user, device, _segmento_de(db, user.id)))
        if len(salida) >= limite:
            break

    return salida


# ── Envio ────────────────────────────────────────────────────────────────────
# FCM sirve para Android Y para iOS: Google habla con APNs por nosotros, asi que
# con una sola credencial y un solo camino se cubren las dos tiendas.
FCM_PROJECT_ID   = os.environ.get("FCM_PROJECT_ID", "").strip()
FCM_CREDENTIALS  = os.environ.get("FCM_CREDENTIALS_JSON", "").strip()   # service account, JSON entero

_token_cache: dict = {"valor": None, "caduca": 0.0}


def _token_google() -> Optional[str]:
    """
    Token OAuth de la cuenta de servicio, cacheado hasta que caduca.

    Devuelve None si no hay credencial configurada: eso NO es un error, es el
    estado normal hasta que el founder cree el proyecto de Firebase. Mientras,
    todo lo demas —seleccion, topes, hora local— funciona y se puede probar en
    seco.
    """
    if not FCM_CREDENTIALS:
        return None
    if _token_cache["valor"] and time.time() < _token_cache["caduca"]:
        return _token_cache["valor"]
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request as GRequest

        info = json.loads(FCM_CREDENTIALS)
        cred = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/firebase.messaging"]
        )
        cred.refresh(GRequest())
        _token_cache["valor"] = cred.token
        _token_cache["caduca"] = time.time() + 3000      # ~50 min, caducan a 60
        return cred.token
    except Exception as e:
        print(f"[push] no se pudo firmar contra Google: {e}")
        return None


def enviar(db: Session, user, device, segmento: str, seco: bool = False) -> tuple:
    """
    Manda UN aviso. Devuelve (ok, detalle).

    `seco=True` recorre todo el camino —elige texto, escribe el log— sin llamar
    a Google. Es como se prueba la seleccion y los topes sin despertar a nadie.

    El log se escribe SIEMPRE, tambien cuando falla: los topes se calculan sobre
    el, asi que un envio que no deje rastro es un envio que se puede repetir.
    """
    from app.models.push_device import PushLog

    titulo, cuerpo = texto_de(segmento, device.lang)

    ok, detalle = True, "seco" if seco else ""
    if not seco:
        token_g = _token_google()
        if not token_g:
            ok, detalle = False, "sin credencial FCM"
        else:
            try:
                r = httpx.post(
                    f"https://fcm.googleapis.com/v1/projects/{FCM_PROJECT_ID}/messages:send",
                    headers={"Authorization": f"Bearer {token_g}"},
                    json={"message": {
                        "token": device.token,
                        "notification": {"title": titulo, "body": cuerpo},
                        # `segmento` viaja para que la app sepa a donde llevar al
                        # usuario cuando toque el aviso.
                        "data": {"segmento": segmento},
                        "apns": {"payload": {"aps": {"sound": "default"}}},
                        "android": {"notification": {"default_sound": True}},
                    }},
                    timeout=20,
                )
                ok = r.status_code == 200
                if not ok:
                    detalle = f"FCM {r.status_code}: {r.text[:180]}"
                    # 404 UNREGISTERED / 400 con token invalido = el aparato ya no
                    # esta. Se apaga la fila para no volver a intentarlo cada dia.
                    if r.status_code in (400, 404) and "UNREGISTERED" in r.text.upper():
                        device.active = False
            except Exception as e:
                ok, detalle = False, f"excepcion: {e}"[:180]

    try:
        db.add(PushLog(user_id=user.id, segmento=segmento, lang=device.lang,
                       ok=ok, detalle=detalle or None))
        if ok and not seco:
            device.last_push_at = datetime.utcnow()
        db.commit()
    except Exception:
        db.rollback()

    return ok, detalle


def pasada(db: Session, seco: bool = False, limite: int = 500) -> dict:
    """
    La pasada completa. Se llama una vez por hora: la ventana es de hora LOCAL,
    asi que a cada hora le toca un trozo distinto del mundo, y los topes impiden
    que nadie reciba dos.
    """
    elegidos = candidatos(db, limite=limite)
    enviados, fallos = 0, 0
    por_segmento: dict = {}
    for user, device, segmento in elegidos:
        ok, _ = enviar(db, user, device, segmento, seco=seco)
        por_segmento[segmento] = por_segmento.get(segmento, 0) + 1
        if ok:
            enviados += 1
        else:
            fallos += 1
    return {"candidatos": len(elegidos), "enviados": enviados, "fallos": fallos,
            "por_segmento": por_segmento, "seco": seco}
