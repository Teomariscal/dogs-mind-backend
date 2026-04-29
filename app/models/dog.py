"""
Dog model — perfil de perro persistente del usuario (Pet Owner).

Cada perro pertenece a un único usuario. Almacenamiento de la foto del perfil
inline en la base de datos como base64 (decisión arquitectónica MVP, ver
documento de modelo de negocio para criterio de migración a R2).

GDPR / soft delete: deleted_at marca borrado lógico. La foto se nullifica
explícitamente al hacer soft-delete para liberar storage de PII gráfica.

Cuota Pet Owner (validada en endpoint, NO en modelo):
- Máximo 2 perros activos por usuario
- Foto máximo 200 KB en base64
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, Integer, Boolean, Text, ForeignKey, Index,
)
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Dog(Base):
    __tablename__ = "dogs"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Identidad
    name            = Column(String(50), nullable=False)
    breed           = Column(String(100), nullable=False)
    birth_year      = Column(Integer, nullable=False)        # validar rango en schema Pydantic
    sex             = Column(String(1), nullable=False)      # 'M' | 'F' (validar en schema)
    neutered        = Column(Boolean, nullable=False, default=False)
    weight_kg_approx = Column(Integer, nullable=True)        # peso aproximado en kg, sin decimales

    # Foto de perfil — única, base64. Nullable (foto opcional según producto).
    photo_base64    = Column(Text, nullable=True)

    # Audit / GDPR
    created_at      = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at      = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at      = Column(DateTime, nullable=True, index=True)  # soft-delete


# Índice compuesto para queries frecuentes: "dogs activos del usuario X".
# WHERE user_id = ? AND deleted_at IS NULL
Index("ix_dogs_user_active", Dog.user_id, Dog.deleted_at)
