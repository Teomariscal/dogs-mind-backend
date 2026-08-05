import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Numeric, Integer, Boolean, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


# Tipos válidos de account_type — fuente de verdad para la app + validación Pydantic.
ACCOUNT_TYPES = ("particular", "professional")


class User(Base):
    __tablename__ = "users"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email          = Column(String(255), unique=True, nullable=False, index=True)
    password_hash  = Column(String(255), nullable=False)
    phone          = Column(String(32), nullable=True)        # PII — opcional, GDPR/CCPA scope
    tokens         = Column(Numeric(10, 2), default=5, nullable=False)  # 5 tokens de regalo
    role           = Column(String(50), default="user", nullable=False)  # user | collaborator | admin
    # Tipo de cuenta (independiente de role). Particular = solo análisis de sus perros propios.
    # Professional = puede abrir casos con perros de cliente (nombre libre) + perfil empresa.
    account_type   = Column(String(20), default="particular", nullable=False, index=True)
    created_at     = Column(DateTime, default=datetime.utcnow)
    # GDPR/CCPA: soft-delete con PII scrub. NULL = activo. Timestamp = cuenta eliminada.
    deleted_at     = Column(DateTime, nullable=True, index=True)

    # ── Perfil de empresa/entidad (solo se rellena si account_type = 'professional') ──
    # Validados en endpoint, NO en modelo. Nullable porque un profesional puede no haber
    # configurado todavía su empresa (slot Entidad vacío en home → primer tap abre form).
    company_name                 = Column(String(120), nullable=True)
    company_legal_rep            = Column(String(120), nullable=True)  # representante legal (form Profesional)
    company_web                  = Column(String(255), nullable=True)
    company_cif                  = Column(String(40), nullable=True)   # opcional, solo si quiere factura
    company_clients_per_year     = Column(Integer, nullable=True)
    company_city                 = Column(String(80), nullable=True)
    company_country              = Column(String(80), nullable=True)   # ISO-3166 alpha-2 o nombre libre
    company_billing_email        = Column(String(255), nullable=True)
    company_collaborate_interest = Column(Boolean, nullable=True)      # ¿quiere colaborar con TDM?
    # Logo de empresa inline base64 (mismo enfoque que Dog.photo_base64). Nullable.
    company_logo_base64          = Column(Text, nullable=True)

    # ── Programa de delegaciones (afiliación por país, 2026-05-16) ──────────
    # FK opcional a Delegation. Se fija al registrarse cuando el invite_code
    # coincide con el code de una delegación activa. Una vez fijada NO debe
    # cambiar (atribución inmutable para coherencia de reporting de comisiones).
    # NULL = usuario no atribuido a ninguna delegación.
    delegation_id                = Column(UUID(as_uuid=True), ForeignKey("delegations.id"), nullable=True, index=True)

    # ── Suscripción mensual (modelo agosto 2026) ────────────────────────────
    # Todo nullable: sin suscripción = NULL, que es el estado de todos hoy.
    # El saldo sigue viviendo en `tokens` (1 token = 100 créditos); estas
    # columnas solo dicen QUIÉN puede gastarlo y cuándo se recarga.
    # Reglas y catálogo: app/core/subscriptions.py
    subscription_plan        = Column(String(20), nullable=True)   # basico|medio|pro|max
    subscription_status      = Column(String(20), nullable=True)   # active|trialing|in_grace|canceled|expired
    subscription_store       = Column(String(20), nullable=True)   # apple|google|stripe
    subscription_expires_at  = Column(DateTime, nullable=True)     # fin del ciclo pagado
    subscription_started_at  = Column(DateTime, nullable=True)
    # Clave del último ciclo al que ya se le abonaron créditos — evita doble
    # abono si la tienda reenvía el mismo webhook.
    subscription_last_grant  = Column(String(64), nullable=True)
    # Arranque de la prueba de 3 días. NULL → se usa created_at.
    trial_started_at         = Column(DateTime, nullable=True)
    # ── Partner (founder 2026-08-04) ────────────────────────────────────────
    # Acceso libre con TOPE de coste para nosotros: 8 €/mes. No ve el muro y no
    # gasta su saldo hasta agotar el cupo; pasado el cupo vuelve a la norma
    # (gasta sus créditos o espera al mes siguiente).
    partner_month            = Column(String(7), nullable=True)   # 'YYYY-MM'
    partner_spent            = Column(Numeric(10, 2), nullable=True, default=0)

    # ── Afiliación corporativa (founder 2026-08-04) ─────────────────────────
    # El alumno/empleado bebe de la bolsa de su institución. Estado:
    #   'active'   → afiliado y consumiendo
    #   'pending'  → esperando aceptación (solo si el acuerdo la exige)
    #   'rejected' → solicitud denegada
    #   NULL       → no afiliado
    corporate_id     = Column(UUID(as_uuid=True), ForeignKey("corporates.id"),
                              nullable=True, index=True)
    corporate_status = Column(String(12), nullable=True)
    corporate_spent  = Column(Numeric(10, 2), nullable=True, default=0)
