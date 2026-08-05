"""
Cuentas corporativas — acuerdos institucionales con bolsa de créditos.

Caso del founder (2026-08-04): la universidad no paga mensualidad; se pacta un
valor y una bolsa de créditos, y sus alumnos se afilian con un código. Ejemplo
real: Universidad Mayor de Chile, alumnos de toda la carrera, un año lectivo.

Cómo se afilia un alumno (dos llaves, no una):
  1. El CÓDIGO de la institución (p. ej. UMAYOR-2026), y
  2. un EMAIL del dominio pactado (p. ej. @umayor.cl).
Con una sola llave no basta: un código suelto circulando por WhatsApp abriría
la puerta a cualquiera.

Reparto de la bolsa:
  · member_cap_tokens > 0 → cada afiliado tiene su cupo; al agotarlo puede
    seguir tirando de la reserva común si queda.
  · member_cap_tokens = 0 → bote común puro, quien llega primero gasta.

Caducidad: `expires_at` es obligatoria en la práctica. Un acuerdo sin fecha
seguiría regalando acceso años después de terminar el curso.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Numeric, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Corporate(Base):
    __tablename__ = "corporates"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Código que se reparte a los afiliados. Se compara en mayúsculas.
    code          = Column(String(40), unique=True, nullable=False, index=True)
    name          = Column(String(160), nullable=False)      # "Universidad Mayor"
    contact_email = Column(String(255), nullable=True)
    # Dominio obligatorio del email del afiliado, sin arroba: "umayor.cl".
    # Varios separados por coma si la institución usa más de uno.
    email_domains = Column(String(400), nullable=False)

    # ── Bolsa pactada ────────────────────────────────────────────────────────
    pool_tokens     = Column(Numeric(12, 2), nullable=False, default=0)  # lo pactado
    pool_spent      = Column(Numeric(12, 2), nullable=False, default=0)  # consumido
    # Cupo por afiliado (0 = bote común sin reparto individual).
    member_cap_tokens = Column(Numeric(10, 2), nullable=False, default=0)

    # ── Vigencia ─────────────────────────────────────────────────────────────
    starts_at  = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    active     = Column(Boolean, nullable=False, default=True)

    # Tipo de cuenta que reciben los afiliados: 'particular' o 'professional'.
    member_account_type = Column(String(20), nullable=False, default="particular")

    # ── Cómo entra un afiliado (founder 2026-08-04) ─────────────────────────
    # False → automático: código + dominio de email correctos y dentro.
    # True  → con aceptación: la solicitud queda PENDIENTE hasta aprobarla.
    # Para una universidad de miles de alumnos, automático; la aceptación
    # manual se reserva a instituciones sin un dominio de correo fiable.
    approval_required = Column(Boolean, nullable=False, default=False)

    max_members = Column(Integer, nullable=True)   # tope de altas, None = sin tope
    notes       = Column(String(500), nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)

    def vigente(self, ahora: datetime = None) -> bool:
        ahora = ahora or datetime.utcnow()
        if not self.active:
            return False
        if self.starts_at and ahora < self.starts_at:
            return False
        if self.expires_at and ahora > self.expires_at:
            return False
        return True

    def bolsa_restante(self) -> float:
        return max(0.0, float(self.pool_tokens or 0) - float(self.pool_spent or 0))
