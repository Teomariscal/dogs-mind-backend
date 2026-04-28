"""
Per-call usage and cost tracking.

Records every billable AI call (analysis, video, chat, avatar) with the
real input/output tokens, model used, and an estimated EUR cost. Used for:

- CFO oversight: real cost per user / per month / per endpoint
- Margin calculation (compare token sales vs API spend)
- Detection of abusive usage patterns
- Future: dynamic pricing if cost outpaces revenue per user

Designed as INSERT-only audit log. No updates, no deletions on user's
account deletion (rows are anonymized: user_id may go null but the row
stays for financial reconciliation).
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class UsageLog(Base):
    __tablename__ = "usage_log"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at      = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    endpoint        = Column(String(64), nullable=False, index=True)        # /analysis, /analysis/video, /analysis/chat, /avatar/chat
    model           = Column(String(64), nullable=False)                    # claude-sonnet-4-6, claude-haiku-4-5, voyage-3-large
    input_tokens    = Column(Integer, nullable=True)
    output_tokens   = Column(Integer, nullable=True)
    cost_eur        = Column(Float, nullable=True, index=True)              # EUR estimado (precio Anthropic listado a fecha de log)
    tokens_charged  = Column(Float, nullable=True)                          # tokens internos cobrados al usuario (para margen)
    success         = Column(String(8), nullable=False, default="ok")       # ok | error | partial
    notes           = Column(String(256), nullable=True)                    # contexto/error si aplica
