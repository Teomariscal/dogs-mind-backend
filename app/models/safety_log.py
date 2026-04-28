"""
Safety classification log (shadow mode).

Records what the input safety classifier detects on each /analysis call,
WITHOUT blocking the response. Once we have enough data to validate
precision/recall, the same classifier output will gate responses.

GDPR scope: input_preview can contain user-supplied text about the dog
(typically not PII). user_id links to the user, so this table is included
in DSAR exports and scrubbed on account deletion (we don't link to email
directly — only via user_id which is anonymized).
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class SafetyLog(Base):
    __tablename__ = "safety_log"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at      = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    endpoint        = Column(String(64), nullable=False)        # /analysis, /analysis/video, /analysis/chat
    input_preview   = Column(Text, nullable=True)                # primeros ~1000 chars del input (truncado)
    classification  = Column(JSONB, nullable=True)               # {agresion_grave: bool, ..., score_global: float, razonamiento: str}
    score_global    = Column(Float, nullable=True, index=True)   # 0-1, copia indexada para queries rápidas
    action_taken    = Column(String(32), nullable=False, default="shadow_log_only")  # shadow_log_only | blocked_in_shadow | blocked
    error           = Column(Text, nullable=True)                # mensaje si el classifier falló
