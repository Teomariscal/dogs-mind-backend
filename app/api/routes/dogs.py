"""
Dogs router — perfil de perro persistente del usuario (Pet Owner).

Endpoints:
- GET    /dogs              → lista mis perros activos (con foto)
- GET    /dogs/{id}         → detalle de un perro (ownership check)
- POST   /dogs              → crear perro (cuota: 2 max para Pet Owner)
- PATCH  /dogs/{id}         → editar parcial
- DELETE /dogs/{id}         → soft delete (libera cuota)
- PUT    /dogs/{id}/photo   → actualizar foto del perfil (≤200 KB en base64)
- DELETE /dogs/{id}/photo   → quitar foto del perfil

Auth: todos los endpoints requieren JWT vía get_current_user.
Ownership: cada endpoint verifica que el dog pertenece al usuario autenticado.
GDPR: borrado lógico con scrub de la foto (PII gráfica) en el soft-delete.
"""

import base64
import re
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, field_validator

from app.database import get_db
from app.models.user import User
from app.models.dog import Dog
from app.api.routes.auth import get_current_user
from app.core import subscriptions as _subs

router = APIRouter(prefix="/dogs", tags=["dogs"])


# ── Cuotas (validadas en endpoint, NO en modelo) ─────────────────────────────
MAX_DOGS_PET_OWNER = 2
MAX_PHOTO_BYTES_RAW = 200 * 1024  # 200 KB después de decodificar base64
ALLOWED_PHOTO_MIME = {"image/jpeg", "image/png", "image/webp"}

# Año mínimo aceptado para nacimiento (1900 = 124 años, suficientemente generoso)
MIN_BIRTH_YEAR = 1900


# ── Schemas Pydantic (validación entrada/salida) ─────────────────────────────
class DogBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="Nombre del perro")
    breed: str = Field(..., min_length=1, max_length=100, description="Raza")
    birth_year: int = Field(..., description="Año de nacimiento")
    sex: str = Field(..., min_length=1, max_length=1, description="'M' (macho) o 'F' (hembra)")
    neutered: bool = Field(False, description="Esterilizado")
    weight_kg_approx: Optional[int] = Field(None, ge=0, le=120, description="Peso aproximado en kg")

    @field_validator("sex")
    @classmethod
    def sex_must_be_M_or_F(cls, v: str) -> str:
        v_up = v.upper()
        if v_up not in {"M", "F"}:
            raise ValueError("sex debe ser 'M' o 'F'")
        return v_up

    @field_validator("birth_year")
    @classmethod
    def birth_year_in_range(cls, v: int) -> int:
        current_year = datetime.utcnow().year
        if v < MIN_BIRTH_YEAR or v > current_year:
            raise ValueError(f"birth_year fuera de rango ({MIN_BIRTH_YEAR}–{current_year})")
        return v

    @field_validator("name", "breed")
    @classmethod
    def strip_text(cls, v: str) -> str:
        return v.strip()


class DogCreate(DogBase):
    photo_base64: Optional[str] = Field(None, description="Foto inicial opcional, data URL base64")


class DogUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    breed: Optional[str] = Field(None, min_length=1, max_length=100)
    birth_year: Optional[int] = None
    sex: Optional[str] = Field(None, min_length=1, max_length=1)
    neutered: Optional[bool] = None
    weight_kg_approx: Optional[int] = Field(None, ge=0, le=120)

    @field_validator("sex")
    @classmethod
    def sex_must_be_M_or_F(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v_up = v.upper()
        if v_up not in {"M", "F"}:
            raise ValueError("sex debe ser 'M' o 'F'")
        return v_up

    @field_validator("birth_year")
    @classmethod
    def birth_year_in_range(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        current_year = datetime.utcnow().year
        if v < MIN_BIRTH_YEAR or v > current_year:
            raise ValueError(f"birth_year fuera de rango ({MIN_BIRTH_YEAR}–{current_year})")
        return v

    @field_validator("name", "breed")
    @classmethod
    def strip_text(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


class DogPhotoUpload(BaseModel):
    photo_base64: str = Field(..., description="Data URL base64 de la foto (image/jpeg|png|webp, ≤200 KB)")


class DogResponse(BaseModel):
    id: str
    user_id: str
    name: str
    breed: str
    birth_year: int
    sex: str
    neutered: bool
    weight_kg_approx: Optional[int]
    photo_base64: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Helpers de validación de foto ────────────────────────────────────────────
_DATA_URL_RE = re.compile(r"^data:(image/(jpeg|png|webp));base64,(.+)$")


def validate_photo_base64(photo: str) -> str:
    """
    Valida un data URL base64 de imagen.
    - Formato: data:image/(jpeg|png|webp);base64,<contenido>
    - Tamaño raw decodificado ≤ 200 KB
    Devuelve el data URL original si pasa todas las comprobaciones.
    Lanza HTTPException 422 si falla.
    """
    if not photo or not isinstance(photo, str):
        raise HTTPException(status_code=422, detail="photo_base64 vacío o inválido")

    match = _DATA_URL_RE.match(photo)
    if not match:
        raise HTTPException(
            status_code=422,
            detail="photo_base64 debe tener formato 'data:image/jpeg|png|webp;base64,...'"
        )

    mime = match.group(1)
    if mime not in ALLOWED_PHOTO_MIME:
        raise HTTPException(status_code=422, detail=f"Formato de imagen no permitido: {mime}")

    b64_content = match.group(3)
    try:
        raw_bytes = base64.b64decode(b64_content, validate=True)
    except Exception:
        raise HTTPException(status_code=422, detail="photo_base64 no es base64 válido")

    if len(raw_bytes) > MAX_PHOTO_BYTES_RAW:
        raise HTTPException(
            status_code=422,
            detail=f"Foto demasiado grande ({len(raw_bytes)} bytes). Máximo {MAX_PHOTO_BYTES_RAW} bytes (200 KB)."
        )

    return photo


def _get_owned_dog(dog_id: str, user: User, db: Session) -> Dog:
    """Carga un dog por id verificando ownership. Lanza 404 si no existe o no es del usuario."""
    dog = db.query(Dog).filter(
        Dog.id == dog_id,
        Dog.user_id == user.id,
        Dog.deleted_at.is_(None),
    ).first()
    if not dog:
        # Por seguridad GDPR, no revelar si el id existe pero pertenece a otro: 404 plano.
        raise HTTPException(status_code=404, detail="Perro no encontrado")
    return dog


def _count_active_dogs(user: User, db: Session) -> int:
    return db.query(Dog).filter(
        Dog.user_id == user.id,
        Dog.deleted_at.is_(None),
    ).count()


# ── Endpoints ────────────────────────────────────────────────────────────────
@router.get("", response_model=List[DogResponse])
def list_dogs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Lista todos los perros activos del usuario autenticado, ordenados por fecha de creación."""
    dogs = (
        db.query(Dog)
        .filter(Dog.user_id == user.id, Dog.deleted_at.is_(None))
        .order_by(Dog.created_at.asc())
        .all()
    )
    return [
        DogResponse(
            id=str(d.id),
            user_id=str(d.user_id),
            name=d.name,
            breed=d.breed,
            birth_year=d.birth_year,
            sex=d.sex,
            neutered=d.neutered,
            weight_kg_approx=d.weight_kg_approx,
            photo_base64=d.photo_base64,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in dogs
    ]


@router.get("/{dog_id}", response_model=DogResponse)
def get_dog(
    dog_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dog = _get_owned_dog(dog_id, user, db)
    return DogResponse(
        id=str(dog.id),
        user_id=str(dog.user_id),
        name=dog.name,
        breed=dog.breed,
        birth_year=dog.birth_year,
        sex=dog.sex,
        neutered=dog.neutered,
        weight_kg_approx=dog.weight_kg_approx,
        photo_base64=dog.photo_base64,
        created_at=dog.created_at,
        updated_at=dog.updated_at,
    )


@router.post("", response_model=DogResponse, status_code=status.HTTP_201_CREATED)
def create_dog(
    payload: DogCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Cuota de perros activos. El tutor lleva los suyos (2); el profesional
    # lleva los de sus clientes y la cuota escala con el plan que paga.
    tope = _subs.max_dogs_for(user)
    active_count = _count_active_dogs(user, db)
    if active_count >= tope:
        detalle = (
            f"Has alcanzado el máximo de {tope} perros activos. "
            "Elimina uno antes de crear otro."
        )
        if tope <= MAX_DOGS_PET_OWNER:
            detalle += (
                " Si llevas perros de clientes, el plan profesional amplía este límite."
            )
        raise HTTPException(status_code=429, detail=detalle)

    # Validar foto si viene
    photo = payload.photo_base64
    if photo:
        photo = validate_photo_base64(photo)

    dog = Dog(
        user_id=user.id,
        name=payload.name,
        breed=payload.breed,
        birth_year=payload.birth_year,
        sex=payload.sex,
        neutered=payload.neutered,
        weight_kg_approx=payload.weight_kg_approx,
        photo_base64=photo,
    )
    db.add(dog)
    db.commit()
    db.refresh(dog)

    return DogResponse(
        id=str(dog.id),
        user_id=str(dog.user_id),
        name=dog.name,
        breed=dog.breed,
        birth_year=dog.birth_year,
        sex=dog.sex,
        neutered=dog.neutered,
        weight_kg_approx=dog.weight_kg_approx,
        photo_base64=dog.photo_base64,
        created_at=dog.created_at,
        updated_at=dog.updated_at,
    )


@router.patch("/{dog_id}", response_model=DogResponse)
def update_dog(
    dog_id: str,
    payload: DogUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dog = _get_owned_dog(dog_id, user, db)

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(dog, k, v)
    dog.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(dog)

    return DogResponse(
        id=str(dog.id),
        user_id=str(dog.user_id),
        name=dog.name,
        breed=dog.breed,
        birth_year=dog.birth_year,
        sex=dog.sex,
        neutered=dog.neutered,
        weight_kg_approx=dog.weight_kg_approx,
        photo_base64=dog.photo_base64,
        created_at=dog.created_at,
        updated_at=dog.updated_at,
    )


@router.delete("/{dog_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dog(
    dog_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Soft-delete del perro. Libera cuota. PII gráfica (foto) se nullifica para liberar storage."""
    dog = _get_owned_dog(dog_id, user, db)
    dog.deleted_at = datetime.utcnow()
    dog.photo_base64 = None  # GDPR scrub de PII gráfica
    db.commit()
    return None


@router.put("/{dog_id}/photo", response_model=DogResponse)
def update_dog_photo(
    dog_id: str,
    payload: DogPhotoUpload,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dog = _get_owned_dog(dog_id, user, db)
    dog.photo_base64 = validate_photo_base64(payload.photo_base64)
    dog.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(dog)

    return DogResponse(
        id=str(dog.id),
        user_id=str(dog.user_id),
        name=dog.name,
        breed=dog.breed,
        birth_year=dog.birth_year,
        sex=dog.sex,
        neutered=dog.neutered,
        weight_kg_approx=dog.weight_kg_approx,
        photo_base64=dog.photo_base64,
        created_at=dog.created_at,
        updated_at=dog.updated_at,
    )


@router.delete("/{dog_id}/photo", response_model=DogResponse)
def delete_dog_photo(
    dog_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dog = _get_owned_dog(dog_id, user, db)
    dog.photo_base64 = None
    dog.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(dog)

    return DogResponse(
        id=str(dog.id),
        user_id=str(dog.user_id),
        name=dog.name,
        breed=dog.breed,
        birth_year=dog.birth_year,
        sex=dog.sex,
        neutered=dog.neutered,
        weight_kg_approx=dog.weight_kg_approx,
        photo_base64=dog.photo_base64,
        created_at=dog.created_at,
        updated_at=dog.updated_at,
    )
