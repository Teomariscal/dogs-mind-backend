"""
Dispositivos registrados para notificaciones push.

Una fila por dispositivo, no por usuario: la misma persona puede tener el iPhone
y el iPad, y cada uno trae su token. El token es la direccion a la que se manda
el aviso y lo da el sistema operativo; caduca, cambia al reinstalar y se invalida
si el usuario desinstala, asi que la fila es desechable por naturaleza.

Dos campos que parecen accesorios y son el nucleo de todo:

  `lang` — el idioma NO esta en `users`: viaja en cada peticion y solo se guarda
  en `cases.lang`. Pero una notificacion solo llega a quien tiene token, y el
  token nace de una llamada de la app que trae el idioma de la interfaz. Es
  decir: de todo el que puede recibir push sabemos el idioma, siempre.

  `tz` — zona horaria IANA del dispositivo. Sin ella no se puede cumplir la
  regla de "nada de madrugadas", y deducirla del pais de la delegacion seria
  adivinar. La manda el dispositivo al registrarse.

Ambos se refrescan en cada registro: si alguien cambia la app a italiano o se va
de viaje, el siguiente arranque lo corrige solo.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class PushDevice(Base):
    __tablename__ = "push_devices"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Token FCM. Es unico de verdad: si un movil cambia de cuenta, la fila se
    # reasigna al usuario nuevo en vez de duplicarse, o el aviso de uno le
    # llegaria al otro.
    token      = Column(String(512), nullable=False, unique=True, index=True)

    platform   = Column(String(10), nullable=False)              # ios | android | web
    lang       = Column(String(2), nullable=False, default="es")  # es | en | it
    tz         = Column(String(64), nullable=True)                # IANA: 'Europe/Madrid'

    # Se desactiva, no se borra: cuando FCM contesta que el token ya no vale
    # queremos saber que ese dispositivo existio y dejo de estar.
    active     = Column(Boolean, nullable=False, default=True, index=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_push_at = Column(DateTime, nullable=True)


# "dame los dispositivos vivos de este usuario" es la consulta de cada envio.
Index("ix_push_devices_user_active", PushDevice.user_id, PushDevice.active)


class PushLog(Base):
    """
    Un envio, una fila. De aqui salen los topes de frecuencia —uno cada 3 dias,
    dos por semana— asi que no es un log decorativo: si no se escribe, el tope
    no existe. Por eso se escribe ANTES de mandar nada, no despues.
    """

    __tablename__ = "push_log"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    segmento   = Column(String(32), nullable=False)   # con_casos | nunca_probo | probo_y_no_siguio
    lang       = Column(String(2), nullable=False)
    sent_at    = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    ok         = Column(Boolean, nullable=False, default=True)
    detalle    = Column(String(256), nullable=True)   # error de FCM si lo hubo


Index("ix_push_log_user_sent", PushLog.user_id, PushLog.sent_at)
