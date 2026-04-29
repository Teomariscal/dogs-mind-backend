"""
Case + CaseEntry models — historial clínico persistente del caso.

Un Case es un episodio clínico abierto sobre un perro concreto. Contiene la
anamnesis inicial, el análisis funcional ABC, el plan de intervención y todas
las entradas de seguimiento posteriores (interacciones IA + datos del usuario).

Para soportar conversaciones largas y consultas de seguimiento sin re-procesar
el análisis completo, el caso almacena tres niveles de resumen optimizados
para inyectar como contexto a la IA en cada interacción:

    - summary_abc:   resumen compacto del análisis funcional ABC (~500 chars)
    - summary_plan:  resumen del plan de intervención (~500 chars)
    - summary_full:  resumen optimizado para contexto IA — identidad del perro
                     + motivo + ABC + plan + últimas N entries de progreso
                     (~2 KB total, regenerado tras cada entry significativa)

GDPR / soft delete: deleted_at marca borrado lógico. Las entries asociadas
se dejan en su sitio para preservar audit trail clínico, pero quedan
inaccesibles vía endpoints (filter on Case.deleted_at IS NULL).

Cuotas (validadas en endpoint, NO en modelo):
    - Casos activos por usuario: 200
    - Entries por caso: 500

Tarifas tokens por entry (invariante financiera):
    - anamnesis:    0 tokens (input usuario)
    - abc:          1,5 tokens (cargo en /analysis)
    - intervention: 1,5 tokens (cargo en /intervention)
    - seguimiento:  1,5 tokens (cargo en /cases/{id}/seguimiento)
    - chat_aigent:  0,3 tokens (cargo en /avatar/chat)
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, Integer, Text, ForeignKey, Index, Numeric,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


# Tipos válidos de entry. Mantener en sync con el schema Pydantic del router.
ENTRY_TYPES = ("anamnesis", "abc", "intervention", "seguimiento", "chat_aigent")

# Estados válidos del caso.
CASE_STATUSES = ("open", "archived")


class Case(Base):
    __tablename__ = "cases"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    dog_id          = Column(UUID(as_uuid=True), ForeignKey("dogs.id"), nullable=True, index=True)
    # dog_id nullable: cuando se migran casos de localStorage al primer login,
    # puede no haber un dog asociado todavía (el usuario los crea después).
    # Una vez asociado, no se debe desasociar (FK con ON DELETE SET NULL para
    # tolerar borrado del perro sin perder histórico clínico).

    title           = Column(String(150), nullable=False)
    motivo_consulta = Column(Text, nullable=True)
    status          = Column(String(20), nullable=False, default="open", index=True)

    # Resúmenes para contexto IA (ver docstring del módulo)
    summary_abc     = Column(Text, nullable=True)
    summary_plan    = Column(Text, nullable=True)
    summary_full    = Column(Text, nullable=True)

    # Audit / GDPR
    created_at      = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at      = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at      = Column(DateTime, nullable=True, index=True)


# Índice compuesto: "casos activos del usuario X, ordenados".
Index("ix_cases_user_active", Case.user_id, Case.deleted_at, Case.updated_at.desc())


class CaseEntry(Base):
    __tablename__ = "case_entries"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id         = Column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True)

    # Tipo de entry — validar contra ENTRY_TYPES en schema Pydantic.
    type            = Column(String(32), nullable=False, index=True)

    # Contenido principal (markdown o texto plano).
    content         = Column(Text, nullable=False)

    # Metadatos específicos por tipo (ej. aigent_id, form fields del seguimiento).
    meta            = Column(JSONB, nullable=True)

    # Audit IA — para reconciliación con usage_log y verificación de invariantes
    # financieras post-mortem si fuera necesario.
    ai_model        = Column(String(64), nullable=True)
    input_tokens    = Column(Integer, nullable=True)
    output_tokens   = Column(Integer, nullable=True)
    tokens_charged  = Column(Numeric(10, 2), nullable=True)  # tokens cobrados al usuario

    created_at      = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


# Índice compuesto: "entries de un caso ordenadas cronológicamente".
Index("ix_case_entries_case_chrono", CaseEntry.case_id, CaseEntry.created_at)
