"""
Invitaciones a un plan por tiempo limitado (embajadores e invitados).

Un código = un uso. Al canjearlo concede los créditos del plan y una vigencia;
cuando vence, la cuenta vuelve sola a la norma general. La renovación es
DELIBERADAMENTE manual: se emite un código nuevo a quien lo merece.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Invite(Base):
    __tablename__ = "invites"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code         = Column(String(40), unique=True, nullable=False, index=True)
    tipo         = Column(String(20), nullable=False, default="invitado")   # embajador | invitado | abierto
    plan_id      = Column(String(20), nullable=False)                       # basico | medio | pro | max
    days         = Column(Integer, nullable=False, default=30)
    account_type = Column(String(20), nullable=False, default="particular")
    note         = Column(String(300), nullable=True)
    # Cuantos abonos mensuales da la invitacion. None = sin tope (miembros del
    # equipo). 1 = un mes (invitados). 3 = Embajador. Si esta columna no esta
    # declarada aqui, el codigo lee el valor por defecto y todos duran 1 mes:
    # me paso el 1-sep-2026.
    meses        = Column(Integer, nullable=True, default=1)

    # Codigos ABIERTOS (tipo="abierto"): los usa cualquiera que los tenga, no se
    # gastan y no caducan. Para esos, used_by_id se queda a NULL y el control es
    # 'activo': ponerlo a False deja de admitir canjes NUEVOS sin quitarle nada
    # a quien ya lo canjeo. Es el freno de mano del codigo TDM-TEAM.
    activo     = Column(Boolean, nullable=False, default=True)

    used_by_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    used_at    = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)                            # plazo para canjearlo
    created_at = Column(DateTime, default=datetime.utcnow)
