"""
QUIEN HA CANJEADO QUE CODIGO. Una fila por persona y codigo, y no mas.

Founder, 25-oct-2026: *"móntalo de tal manera que solamente lo pueden utilizar
con el mismo mail... la persona con el mismo mail no lo puede utilizar dos
veces. Pon una puerta absoluta porque si no nos arruina."*

EL AGUJERO QUE CIERRA, simulado con el codigo real antes de escribir esto:

    1. primer canje de PRO15 ........... 2.160 creditos
    2. lo vuelve a meter el mismo mes ..     0   (lo frena el sello de ciclo)
    3. lo vuelve a meter al mes siguiente . 2.160 OTRA VEZ

O sea: el mismo email, el mismo codigo, 2.160 creditos cada mes, para siempre.
Un codigo repartido a diez personas eran diez suscripciones gratis
indefinidas. Lo unico que lo contenia era un sello por mes natural.

LA CAUSA: `tipo='abierto'` lo copie del PROINV, que era abierto a proposito
para poder repartirlo. Pero *"lo puede canjear cualquiera"* y *"lo puede
canjear la misma persona mil veces"* son dos cosas distintas, y el codigo las
trataba como una sola.

POR QUE UNA TABLA Y NO UN `if`. La restriccion UNIQUE la aplica Postgres en
cada INSERT, pase lo que pase: no depende de que nadie se acuerde de
comprobarlo, ni de que dos peticiones simultaneas no se crucen. Un `if` en
Python se salta con una carrera de dos canjes a la vez; esto no.

Los codigos de EQUIPO tambien quedan registrados. No les estorba —ellos
canjean una vez y luego se renuevan solos, sin volver a tocar el codigo— y
asi el registro dice la verdad sobre quien tiene que.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class InviteRedemption(Base):
    __tablename__ = "invite_redemptions"
    __table_args__ = (
        # LA PUERTA. Un email, un codigo, una vez.
        UniqueConstraint("invite_id", "user_id", name="un_canje_por_persona"),
    )

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invite_id  = Column(UUID(as_uuid=True), ForeignKey("invites.id"), nullable=False, index=True)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    # Se guarda el codigo y el email TAL CUAL estaban al canjear. Si manana se
    # borra el codigo o la persona cambia de correo, la fila sigue diciendo que
    # paso: es un registro, no una referencia.
    code       = Column(String(40), nullable=False, index=True)
    email      = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
