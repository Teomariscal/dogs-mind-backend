"""
Delegations — programa de afiliación por país (2026-05-16).

Cada delegación (ej. Bocalán México, Bocalán Argentina, etc.) tiene un
código único que sus equipos comparten con clientes finales. Al registrarse
con ese código, el usuario queda atribuido permanentemente a la delegación
vía `User.delegation_id` (FK inmutable). Esto permite:

  1. Otorgar tokens de bienvenida extras (welcome_bonus_tokens).
  2. Trackear cuántos usuarios captó cada delegación (count).
  3. Calcular % de comisión sobre el revenue de "sus" usuarios.

Modelo agregado, NO expone datos individuales. El reporting solo devuelve
totales por delegación, preservando privacidad de los usuarios.

Decisiones de diseño (Teo 2026-05-16):
  - A1: códigos legibles tipo `BOCALAN-MX`, `BOCALAN-AR`
  - B1: +3 tokens al registrarse (total 8 vs 5 estándar)
  - C1: 10% comisión sobre revenue web por defecto
  - D2: 5% comisión sobre IAP iOS (Apple ya se queda 15-30%, hay que dejar margen)
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Numeric, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Delegation(Base):
    __tablename__ = "delegations"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Código compartido con clientes finales. Se valida case-insensitive en
    # /auth/register para tolerar errores del usuario. Único en BD.
    code            = Column(String(40), unique=True, nullable=False, index=True)
    # Nombre humano para reporting y toasts ("Bienvenido por cortesía de Bocalán México").
    name            = Column(String(120), nullable=False)
    country         = Column(String(80), nullable=False)
    contact_email   = Column(String(255), nullable=True)
    # Tokens extra al saldo de bienvenida (5 base + welcome_bonus_tokens).
    # Configurable por delegación (B3 implícito vía Admin patch).
    welcome_bonus_tokens   = Column(Integer, nullable=False, default=3)
    # % de comisión sobre revenue de los usuarios atribuidos.
    # Por canal de pago: web (Stripe) vs iOS IAP (Apple ya cobra 15-30%).
    commission_pct_web     = Column(Numeric(5, 2), nullable=False, default=10.00)
    commission_pct_ios     = Column(Numeric(5, 2), nullable=False, default=5.00)
    # Toggle para desactivar sin borrar (preserva atribución histórica).
    active          = Column(Boolean, nullable=False, default=True)
    created_at      = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at      = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
