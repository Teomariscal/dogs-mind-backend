import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id            = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    stripe_session_id  = Column(String(255), unique=True, nullable=False)
    tokens             = Column(Integer, nullable=False)       # 10 / 50 / 200
    amount_cents       = Column(Integer, nullable=False)       # 499 / 1999 / 5999
    status             = Column(String(50), default="pending") # pending / paid
    created_at         = Column(DateTime, default=datetime.utcnow)
