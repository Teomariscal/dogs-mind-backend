import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Numeric
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email          = Column(String(255), unique=True, nullable=False, index=True)
    password_hash  = Column(String(255), nullable=False)
    tokens         = Column(Numeric(10, 2), default=5, nullable=False)  # 5 tokens de regalo
    role           = Column(String(50), default="user", nullable=False)  # user | collaborator | admin
    created_at     = Column(DateTime, default=datetime.utcnow)
