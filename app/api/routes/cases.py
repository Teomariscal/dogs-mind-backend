"""
Cases router — historial clínico persistente.

Endpoints:
- GET    /cases                   → lista casos del usuario (filtrable status/dog_id, paginable)
- GET    /cases/{id}              → detalle del caso con summaries
- GET    /cases/{id}/entries      → lista entries del caso, ordenadas cronológicamente
- POST   /cases                   → crear caso (cuota max 200 activos, valida ownership dog si se pasa dog_id)
- PATCH  /cases/{id}              → editar título / motivo / status / dog_id
- DELETE /cases/{id}              → soft-delete del caso (preserva entries para audit)
- POST   /cases/{id}/entries      → añadir entry tipo 'anamnesis' (input usuario, NO cobra tokens)

Nota: las entries que invocan IA (abc, intervention, seguimiento, chat_aigent) NO se crean
desde aquí. Se crean desde sus endpoints respectivos con su correspondiente cobro de tokens
y deducción de saldo (invariante financiera).

Auth: todos los endpoints requieren JWT.
Ownership: cada endpoint verifica Case.user_id == current_user.id.
GDPR: deleted_at marca borrado lógico; las entries se preservan para audit clínico.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Literal

from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, field_validator

from app.database import get_db
from app.models.user import User
from app.models.dog import Dog
from app.models.case import Case, CaseEntry, ENTRY_TYPES, CASE_STATUSES
from app.api.routes.auth import get_current_user
from app.core.token_utils import deduct_token
from app.services.seguimiento_ai import run_seguimiento, SeguimientoFormData
from app.config import get_settings

router = APIRouter(prefix="/cases", tags=["cases"])


# ── Cuotas (validadas en endpoint) ───────────────────────────────────────────
MAX_CASES_PER_USER = 200
MAX_ENTRIES_PER_CASE = 500

# ── Tarifas tokens (INVARIANTES FINANCIERAS — no tocar sin aprobación CFO) ──
# Ver dogsmind-modelo-negocio-pricing.md y memoria CFO.
SEGUIMIENTO_TOKEN_COST = 1.5  # plantilla + respuesta IA Sonnet 4.6 + RAG

# Plan Sencillo / Pet Owners — INVARIANTE FINANCIERA (CFO 2026-05-04).
# Haiku 4.5 reformula el plan técnico en formato receta. 96 % margen alineado
# con mensaje Aigent. Persistencia obligatoria (solo 1ª generación cobra) +
# rate limit 5/h por caso (anti-abuso). Ver dogs-mind-state.md invariantes 4 y 5.
PLAN_SIMPLE_TOKEN_COST = 0.1
PLAN_SIMPLE_RATE_LIMIT_PER_HOUR = 5
PLAN_SIMPLE_MAX_OUTPUT_TOKENS = 800

# ABC Explained / Cecilia te explica — INVARIANTE FINANCIERA (CFO 2026-05-04).
# Haiku 4.5 traduce análisis ABC técnico a 4 párrafos accesibles. Mismo patrón
# que Plan Sencillo (96 % margen, persistencia, rate limit 5/h por caso).
ABC_EXPLAINED_TOKEN_COST = 0.1
ABC_EXPLAINED_RATE_LIMIT_PER_HOUR = 5
ABC_EXPLAINED_MAX_OUTPUT_TOKENS = 600
SEGUIMIENTO_MAX_OBSERVACIONES_CHARS = 1500  # límite anti-abuso, alineado con chat clínico cap
SEGUIMIENTO_MAX_INFO_EXTRA_CHARS = 1000     # ~4 frases típicas
SEGUIMIENTO_MAX_MOTIVO_RESUMIDO_CHARS = 300 # 1 frase


# ── Schemas Pydantic ─────────────────────────────────────────────────────────
class CaseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=150, description="Título del caso (motivo principal)")
    motivo_consulta: Optional[str] = Field(None, max_length=5000, description="Descripción libre del motivo")
    dog_id: Optional[str] = Field(None, description="UUID del perro propio (Particular: obligatorio. Profesional: opcional)")
    # Campos solo profesionales — perro de cliente que NO está en el perfil del usuario.
    # Validación de tier + exclusividad con dog_id se hace en endpoint.
    client_dog_name: Optional[str] = Field(None, max_length=80)
    client_dog_breed: Optional[str] = Field(None, max_length=120)
    client_dog_age: Optional[str] = Field(None, max_length=80)

    @field_validator("title", "motivo_consulta", "client_dog_name", "client_dog_breed", "client_dog_age")
    @classmethod
    def strip_text(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        s = v.strip()
        return s or None


class CaseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=150)
    motivo_consulta: Optional[str] = Field(None, max_length=5000)
    status: Optional[Literal["open", "archived"]] = None
    dog_id: Optional[str] = None
    client_dog_name: Optional[str] = Field(None, max_length=80)
    client_dog_breed: Optional[str] = Field(None, max_length=120)
    client_dog_age: Optional[str] = Field(None, max_length=80)

    @field_validator("title", "motivo_consulta", "client_dog_name", "client_dog_breed", "client_dog_age")
    @classmethod
    def strip_text(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        s = v.strip()
        return s or None


class CaseResponse(BaseModel):
    id: str
    user_id: str
    dog_id: Optional[str]
    title: str
    motivo_consulta: Optional[str]
    status: str
    summary_abc: Optional[str]
    summary_plan: Optional[str]
    summary_full: Optional[str]
    client_dog_name: Optional[str] = None
    client_dog_breed: Optional[str] = None
    client_dog_age: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CaseEntryCreate(BaseModel):
    """
    Solo para entries de tipo 'anamnesis' (input usuario, sin cobro de tokens).
    Las entries con coste de IA se crean desde sus endpoints específicos.
    """
    type: Literal["anamnesis"] = Field("anamnesis", description="Solo se acepta 'anamnesis' aquí")
    content: str = Field(..., min_length=1, max_length=20000)
    meta: Optional[dict] = Field(None, description="Datos estructurados del formulario de anamnesis")


class SeguimientoCreate(BaseModel):
    """
    Plantilla de seguimiento — 8 campos (definidos por producto).
    Ver dogsmind-modelo-negocio-pricing.md sección 'Plantilla de seguimiento'.
    """
    dias_tratamiento: int = Field(..., ge=0, le=3650, description="Días de tratamiento")
    numero_sesiones: int = Field(..., ge=0, le=10000, description="Número de sesiones realizadas")
    ve_evolucion: bool = Field(..., description="¿Ve evolución? Sí/No")
    criterio_medicion: Optional[str] = Field(
        None, max_length=500,
        description="Criterio usado para medir la evolución (distancia, frecuencia, duración…)",
    )
    descripcion_evolucion: Optional[str] = Field(
        None, max_length=SEGUIMIENTO_MAX_OBSERVACIONES_CHARS,
        description="Descripción libre de la evolución",
    )
    dificultades: Optional[str] = Field(
        None, max_length=SEGUIMIENTO_MAX_OBSERVACIONES_CHARS,
        description="Dificultades en la aplicación de las propuestas",
    )
    motivo_consulta_resumido: Optional[str] = Field(
        None, max_length=SEGUIMIENTO_MAX_MOTIVO_RESUMIDO_CHARS,
        description="Resumen en una frase del motivo de esta consulta",
    )
    informacion_extra: Optional[str] = Field(
        None, max_length=SEGUIMIENTO_MAX_INFO_EXTRA_CHARS,
        description="Información adicional relevante (max ~4 frases)",
    )

    @field_validator(
        "criterio_medicion", "descripcion_evolucion", "dificultades",
        "motivo_consulta_resumido", "informacion_extra",
    )
    @classmethod
    def strip_optional_text(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        s = v.strip()
        return s or None


class SeguimientoResponse(BaseModel):
    entry: "CaseEntryResponse"
    balance_after: float = Field(..., description="Saldo de tokens del usuario tras la operación")
    cache_hit: bool = Field(..., description="True si la llamada IA usó prompt caching (debug/CFO)")


# ── Schemas para migración localStorage → backend ────────────────────────────
class LegacyRecord(BaseModel):
    """
    Record tal y como estaba guardado en localStorage del navegador
    bajo la clave dm_records_<hash_email>.
    """
    id: int = Field(..., description="Timestamp ms de creación (id local)")
    date: Optional[str] = Field(None, description="Fecha en formato dd/mm/yyyy")
    dog_name: Optional[str] = Field(None, max_length=80)
    breed: Optional[str] = Field(None, max_length=120)
    dog_age: Optional[str] = Field(None, max_length=80)
    problem: Optional[str] = Field(None, max_length=20000)
    analysis: Optional[str] = Field(None, max_length=200000)
    plan: Optional[str] = Field(None, max_length=200000)
    status: Optional[str] = Field("active", max_length=40)


class MigrateRequest(BaseModel):
    records: List[LegacyRecord] = Field(..., max_length=500)


class MigrateResponseItem(BaseModel):
    legacy_id: int
    case_id: Optional[str] = None
    status: str  # "created" | "skipped_duplicate" | "skipped_quota" | "skipped_empty"
    detail: Optional[str] = None


class MigrateResponse(BaseModel):
    results: List[MigrateResponseItem]
    created_count: int
    skipped_count: int


class CaseEntryResponse(BaseModel):
    id: str
    case_id: str
    type: str
    content: str
    meta: Optional[dict]
    ai_model: Optional[str]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    tokens_charged: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Helpers ──────────────────────────────────────────────────────────────────
def _get_owned_case(case_id: str, user: User, db: Session) -> Case:
    case = db.query(Case).filter(
        Case.id == case_id,
        Case.user_id == user.id,
        Case.deleted_at.is_(None),
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
    return case


def _validate_dog_ownership(dog_id: Optional[str], user: User, db: Session) -> Optional[str]:
    """Si dog_id se pasa, verifica que pertenece al usuario y está activo. Devuelve UUID válido o None."""
    if not dog_id:
        return None
    dog = db.query(Dog).filter(
        Dog.id == dog_id,
        Dog.user_id == user.id,
        Dog.deleted_at.is_(None),
    ).first()
    if not dog:
        raise HTTPException(status_code=404, detail="Perro no encontrado o no pertenece al usuario")
    return dog_id


def _validate_case_subject(
    user: User,
    dog_id: Optional[str],
    client_dog_name: Optional[str],
    client_dog_breed: Optional[str],
    client_dog_age: Optional[str],
    db: Session,
) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Aplica las reglas de tier sobre el sujeto del caso.

    Particular:
        - dog_id obligatorio y debe ser de uno de sus perros.
        - client_dog_* prohibidos (rechazo 422).
    Professional:
        - Si dog_id se pasa, debe ser de uno de sus perros (mismo check de ownership).
        - Si no hay dog_id, client_dog_name es obligatorio (los demás opcionales).
        - dog_id y client_dog_name son mutuamente excluyentes (no aceptamos los dos
          a la vez para evitar ambigüedad sobre quién es el sujeto del caso).

    Devuelve la tupla (dog_id_valido, client_dog_name, client_dog_breed, client_dog_age).
    """
    has_client = bool(client_dog_name)

    if user.account_type == "particular":
        if any([client_dog_name, client_dog_breed, client_dog_age]):
            raise HTTPException(
                status_code=422,
                detail=(
                    "Las cuentas Particular solo pueden abrir casos con perros propios. "
                    "Para registrar perros de clientes cambia tu cuenta a Profesional."
                ),
            )
        if not dog_id:
            raise HTTPException(
                status_code=422,
                detail="Debes seleccionar uno de tus perros para abrir el caso.",
            )
        valid_dog_id = _validate_dog_ownership(dog_id, user, db)
        return valid_dog_id, None, None, None

    # account_type == 'professional'
    if dog_id and has_client:
        raise HTTPException(
            status_code=422,
            detail=(
                "Indica un perro propio (dog_id) o los datos de un perro de cliente "
                "(client_dog_name), pero no ambos."
            ),
        )
    if not dog_id and not has_client:
        raise HTTPException(
            status_code=422,
            detail="Indica un perro propio (dog_id) o el nombre del perro del cliente.",
        )

    valid_dog_id = _validate_dog_ownership(dog_id, user, db) if dog_id else None
    return valid_dog_id, client_dog_name, client_dog_breed, client_dog_age


def _count_active_cases(user: User, db: Session) -> int:
    return db.query(Case).filter(
        Case.user_id == user.id,
        Case.deleted_at.is_(None),
    ).count()


def _count_case_entries(case_id: str, db: Session) -> int:
    return db.query(CaseEntry).filter(CaseEntry.case_id == case_id).count()


def _to_case_response(case: Case) -> CaseResponse:
    return CaseResponse(
        id=str(case.id),
        user_id=str(case.user_id),
        dog_id=str(case.dog_id) if case.dog_id else None,
        title=case.title,
        motivo_consulta=case.motivo_consulta,
        status=case.status,
        summary_abc=case.summary_abc,
        summary_plan=case.summary_plan,
        summary_full=case.summary_full,
        client_dog_name=case.client_dog_name,
        client_dog_breed=case.client_dog_breed,
        client_dog_age=case.client_dog_age,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


def _to_entry_response(entry: CaseEntry) -> CaseEntryResponse:
    return CaseEntryResponse(
        id=str(entry.id),
        case_id=str(entry.case_id),
        type=entry.type,
        content=entry.content,
        meta=entry.meta,
        ai_model=entry.ai_model,
        input_tokens=entry.input_tokens,
        output_tokens=entry.output_tokens,
        tokens_charged=float(entry.tokens_charged) if entry.tokens_charged is not None else None,
        created_at=entry.created_at,
    )


# ── INVARIANTE FINANCIERA — NO TOCAR SIN APROBACIÓN CFO ─────────────────────
# Cualquier endpoint que invoque IA debe RESTAR tokens del saldo del usuario
# ANTES de la llamada API. Si saldo insuficiente → 402 Payment Required, sin
# llamada API, sin coste. Esta función es la implementación local que opera
# sobre el objeto User ya cargado por get_current_user.
PRIVILEGED_ROLES = {"admin", "developer", "collaborator"}


def _charge_user_tokens(user: User, amount: float, db: Session) -> float:
    """
    Resta `amount` tokens del usuario. Devuelve el saldo nuevo.

    - Roles privilegiados (admin/developer/collaborator) no consumen.
    - Saldo insuficiente → HTTPException 402.

    No hace commit final: el caller decide cuándo confirmar la transacción
    (típicamente dentro del mismo bloque que persiste la entry de la operación
    para mantener atomicidad: o se cobra Y se guarda la entry, o nada).
    """
    if getattr(user, "role", "user") in PRIVILEGED_ROLES:
        return float(user.tokens)

    current = float(user.tokens)
    if current < amount:
        raise HTTPException(
            status_code=402,
            detail="Saldo insuficiente. Recarga tokens para continuar.",
        )
    user.tokens = current - amount
    db.flush()  # propaga el cambio dentro de la transacción sin commit
    return current - amount


def _regenerate_summary_full(case: Case, db: Session) -> str:
    """
    Regenera el `summary_full` del caso a partir de:
      - Datos del perro (si dog_id está)
      - Título y motivo del caso
      - summary_abc + summary_plan (si existen)
      - Últimas 5 entries de tipo seguimiento (cronológicas)

    El resultado se guarda en case.summary_full y se devuelve. Pensado para
    ~2 KB max — funciona como "contexto cacheable" para futuras llamadas IA.
    """
    parts: List[str] = []

    # 1. Identidad del perro (si está vinculado)
    if case.dog_id:
        dog = db.query(Dog).filter(
            Dog.id == case.dog_id,
            Dog.deleted_at.is_(None),
        ).first()
        if dog:
            edad = datetime.utcnow().year - dog.birth_year
            parts.append(
                f"PERRO: {dog.name}, raza {dog.breed}, "
                f"{edad} años, sexo {dog.sex}, "
                f"{'esterilizado' if dog.neutered else 'sin esterilizar'}"
                + (f", {dog.weight_kg_approx} kg" if dog.weight_kg_approx else "")
            )

    # 2. Caso
    parts.append(f"TÍTULO: {case.title}")
    if case.motivo_consulta:
        # Motivo limitado a 500 chars en el resumen para no inflar
        m = case.motivo_consulta[:500]
        parts.append(f"MOTIVO: {m}")

    # 3. Resúmenes ABC y plan (si existen, ya son compactos por diseño)
    if case.summary_abc:
        parts.append(f"ABC: {case.summary_abc[:600]}")
    if case.summary_plan:
        parts.append(f"PLAN: {case.summary_plan[:600]}")

    # 4. Últimos 5 seguimientos (cronológicos, más antiguo primero)
    recent_seg = (
        db.query(CaseEntry)
        .filter(
            CaseEntry.case_id == case.id,
            CaseEntry.type == "seguimiento",
        )
        .order_by(CaseEntry.created_at.desc())
        .limit(5)
        .all()
    )
    if recent_seg:
        recent_seg = list(reversed(recent_seg))  # cronológicos
        seg_lines = ["SEGUIMIENTOS RECIENTES:"]
        for s in recent_seg:
            meta = s.meta or {}
            fecha = s.created_at.strftime("%Y-%m-%d")
            dias = meta.get("dias_tratamiento", "?")
            sesiones = meta.get("numero_sesiones", "?")
            evol = "Sí" if meta.get("ve_evolucion") else "No"
            criterio = (meta.get("criterio_medicion") or "")[:80]
            descripcion = (meta.get("descripcion_evolucion") or "")[:200]
            seg_lines.append(
                f"- [{fecha}] día {dias}, sesiones {sesiones}, evol={evol}"
                + (f", criterio: {criterio}" if criterio else "")
                + (f", desc: {descripcion}" if descripcion else "")
            )
        parts.append("\n".join(seg_lines))

    summary = "\n\n".join(parts)
    case.summary_full = summary
    return summary


# ── Endpoints ────────────────────────────────────────────────────────────────
@router.get("", response_model=List[CaseResponse])
def list_cases(
    status_filter: Optional[Literal["open", "archived"]] = Query(None, alias="status"),
    dog_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Lista casos del usuario, ordenados por última actualización descendente."""
    q = db.query(Case).filter(
        Case.user_id == user.id,
        Case.deleted_at.is_(None),
    )
    if status_filter:
        q = q.filter(Case.status == status_filter)
    if dog_id:
        q = q.filter(Case.dog_id == dog_id)
    cases = q.order_by(Case.updated_at.desc()).limit(limit).offset(offset).all()
    return [_to_case_response(c) for c in cases]


@router.get("/{case_id}", response_model=CaseResponse)
def get_case(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = _get_owned_case(case_id, user, db)
    return _to_case_response(case)


@router.get("/{case_id}/entries", response_model=List[CaseEntryResponse])
def list_case_entries(
    case_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Lista entries del caso ordenadas cronológicamente (más antiguo primero)."""
    _get_owned_case(case_id, user, db)  # ownership check
    entries = (
        db.query(CaseEntry)
        .filter(CaseEntry.case_id == case_id)
        .order_by(CaseEntry.created_at.asc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [_to_entry_response(e) for e in entries]


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CaseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Cuota
    active_count = _count_active_cases(user, db)
    if active_count >= MAX_CASES_PER_USER:
        raise HTTPException(
            status_code=429,
            detail=f"Has alcanzado el máximo de {MAX_CASES_PER_USER} casos activos.",
        )

    # Gating por tier (Particular: solo perros propios; Profesional: propios o cliente)
    valid_dog_id, client_name, client_breed, client_age = _validate_case_subject(
        user,
        payload.dog_id,
        payload.client_dog_name,
        payload.client_dog_breed,
        payload.client_dog_age,
        db,
    )

    case = Case(
        user_id=user.id,
        dog_id=valid_dog_id,
        title=payload.title,
        motivo_consulta=payload.motivo_consulta,
        status="open",
        client_dog_name=client_name,
        client_dog_breed=client_breed,
        client_dog_age=client_age,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return _to_case_response(case)


@router.patch("/{case_id}", response_model=CaseResponse)
def update_case(
    case_id: str,
    payload: CaseUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = _get_owned_case(case_id, user, db)
    data = payload.model_dump(exclude_unset=True)

    # Si el patch toca cualquier campo del sujeto del caso (perro propio o cliente),
    # revalidamos el conjunto completo aplicando las reglas de tier. Mantiene el
    # invariante de que un caso siempre tiene exactamente un sujeto bien identificado.
    subject_keys = {"dog_id", "client_dog_name", "client_dog_breed", "client_dog_age"}
    if subject_keys & data.keys():
        new_dog_id        = data.get("dog_id",        str(case.dog_id) if case.dog_id else None)
        new_client_name   = data.get("client_dog_name",  case.client_dog_name)
        new_client_breed  = data.get("client_dog_breed", case.client_dog_breed)
        new_client_age    = data.get("client_dog_age",   case.client_dog_age)
        valid_dog_id, c_name, c_breed, c_age = _validate_case_subject(
            user, new_dog_id, new_client_name, new_client_breed, new_client_age, db,
        )
        data["dog_id"]           = valid_dog_id
        data["client_dog_name"]  = c_name
        data["client_dog_breed"] = c_breed
        data["client_dog_age"]   = c_age

    for k, v in data.items():
        setattr(case, k, v)
    case.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(case)
    return _to_case_response(case)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Soft-delete del caso. Las entries asociadas se preservan para audit clínico."""
    case = _get_owned_case(case_id, user, db)
    case.deleted_at = datetime.utcnow()
    db.commit()
    return None


@router.get("/{case_id}/export.pdf")
def export_case_pdf(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Genera un PDF unificado con análisis funcional ABC + plan de intervención.

    Disponible solo cuando el caso ya tiene generadas ambas piezas (lo que
    coincide con el contrato de UI: el botón solo aparece cuando hay las dos).

    Cabecera: logo TDM + nombre del perro + fecha. Si el usuario es profesional
    con logo de empresa subido, se añade en el margen opuesto. Sin datos de
    cliente humano (privacidad).

    Pie: disclaimer clínico + número de página.
    """
    from app.services.pdf_export import (
        build_case_pdf, build_export_filename, has_required_entries_for_export,
    )

    case = _get_owned_case(case_id, user, db)
    if not has_required_entries_for_export(case.id, db):
        raise HTTPException(
            status_code=404,
            detail=(
                "El caso aún no tiene análisis funcional y plan de intervención generados. "
                "Genera ambos antes de descargar el informe."
            ),
        )

    pdf_bytes = build_case_pdf(case, user, db)
    filename = build_export_filename(case, db)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
            # Evita cachés agresivas: el PDF puede regenerarse si cambian datos del caso.
            "Cache-Control": "private, max-age=0, must-revalidate",
        },
    )


@router.post("/{case_id}/entries", response_model=CaseEntryResponse, status_code=status.HTTP_201_CREATED)
def add_anamnesis_entry(
    case_id: str,
    payload: CaseEntryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Añade una entry de tipo 'anamnesis' (input del usuario, sin cobro de tokens).

    Las entries con coste de IA (abc, intervention, seguimiento, chat_aigent)
    NO se crean aquí. Cada una tiene su endpoint dedicado con su cobro de tokens.
    """
    case = _get_owned_case(case_id, user, db)

    # Cuota entries por caso
    entries_count = _count_case_entries(case_id, db)
    if entries_count >= MAX_ENTRIES_PER_CASE:
        raise HTTPException(
            status_code=429,
            detail=f"Has alcanzado el máximo de {MAX_ENTRIES_PER_CASE} entries en este caso.",
        )

    if payload.type != "anamnesis":
        # Defensa en profundidad — el schema ya restringe a Literal["anamnesis"],
        # pero validamos por si el cliente burla la validación de Pydantic.
        raise HTTPException(
            status_code=422,
            detail="Este endpoint solo acepta entries tipo 'anamnesis'.",
        )

    entry = CaseEntry(
        case_id=case.id,
        type="anamnesis",
        content=payload.content,
        meta=payload.meta,
    )
    db.add(entry)
    case.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(entry)
    return _to_entry_response(entry)


# ── Endpoint de consulta de seguimiento ──────────────────────────────────────
@router.post(
    "/{case_id}/seguimiento",
    response_model=SeguimientoResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_seguimiento(
    case_id: str,
    payload: SeguimientoCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Plantilla de seguimiento de un caso clínico abierto.

    Coste: 1,5 tokens (INVARIANTE FINANCIERA — Sonnet 4.6 + RAG, sin re-anamnesis).

    Flujo:
        1. Verifica ownership del caso y cuota de entries
        2. Cobra 1,5 tokens (402 si saldo insuficiente, sin llamada API)
        3. Llama a la IA Teo con summary_full del caso + plantilla + RAG
        4. Persiste entry tipo 'seguimiento' (content = respuesta IA, meta = form data)
        5. Regenera summary_full del caso para futuras consultas
        6. Loggea usage_log para tracking de coste / margen
        7. Devuelve entry + saldo actualizado
    """
    case = _get_owned_case(case_id, user, db)

    # Cuota de entries por caso
    entries_count = _count_case_entries(case_id, db)
    if entries_count >= MAX_ENTRIES_PER_CASE:
        raise HTTPException(
            status_code=429,
            detail=f"Has alcanzado el máximo de {MAX_ENTRIES_PER_CASE} entries en este caso.",
        )

    # ─── Invariante financiera: cobrar ANTES de invocar IA ─────────────────
    new_balance = _charge_user_tokens(user, SEGUIMIENTO_TOKEN_COST, db)

    # ─── Llamada IA Teo (Sonnet 4.6 + RAG) ─────────────────────────────────
    form_data = SeguimientoFormData(**payload.model_dump())
    try:
        ai_result = run_seguimiento(case.summary_full, form_data)
    except Exception as e:
        # IA falló — refund tokens y propagar 500.
        # Esto preserva la invariante "no se cobra al usuario por errores nuestros".
        user.tokens = float(user.tokens) + SEGUIMIENTO_TOKEN_COST
        db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Error generando respuesta de seguimiento: {str(e)[:200]}",
        )

    # ─── Persistir entry + actualizar caso ─────────────────────────────────
    settings = get_settings()
    entry = CaseEntry(
        case_id=case.id,
        type="seguimiento",
        content=ai_result.response_markdown,
        meta=payload.model_dump(),
        ai_model=settings.clinical_model,
        input_tokens=ai_result.input_tokens,
        output_tokens=ai_result.output_tokens,
        tokens_charged=SEGUIMIENTO_TOKEN_COST,
    )
    db.add(entry)
    case.updated_at = datetime.utcnow()

    # Regenerar summary_full incorporando el nuevo seguimiento
    db.flush()  # asegura que la entry esté visible para la query del summary
    _regenerate_summary_full(case, db)

    db.commit()
    db.refresh(entry)

    # ─── Tracking de coste (CFO oversight) ─────────────────────────────────
    try:
        from app.core.usage_tracker import log_usage
        log_usage(
            user_id=str(user.id),
            endpoint="/cases/seguimiento",
            model=settings.clinical_model,
            input_tokens=ai_result.input_tokens,
            output_tokens=ai_result.output_tokens,
            tokens_charged=SEGUIMIENTO_TOKEN_COST,
            success="ok",
        )
    except Exception:
        # Logging no debe romper la respuesta al usuario.
        pass

    return SeguimientoResponse(
        entry=_to_entry_response(entry),
        balance_after=new_balance,
        cache_hit=ai_result.cache_hit,
    )


# ── Plan Sencillo / Pet Owners ───────────────────────────────────────────────
class PlanSimpleResponse(BaseModel):
    text: str
    cached: bool
    balance_after: Optional[float]
    created_at: datetime
    case_id: str


@router.post("/{case_id}/plan-simple", response_model=PlanSimpleResponse)
def generate_plan_simple(
    case_id: str,
    force: bool = Query(False, description="Si true, regenera ignorando cached (cobra otros 0,1)"),
    lang: str = Query("es", description="'es' (default) o 'en'"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Plan Sencillo / Pet Owners — versión accesible del plan de intervención.

    Invariantes financieras (CFO 2026-05-04):
      - 0,1 tokens por generación (margen 96 %, alineado con mensaje Aigent).
      - Persistencia: si existe `CaseEntry.type='plan_simple'`, devuelve cached
        SIN cobro. Solo la primera generación (o force=true explícito) cobra.
      - Rate limit duro: máximo 5 generaciones por caso por hora.
      - Modelo: Haiku 4.5 (sin RAG, sin prompt cache, output ≤800 tok).

    Errores:
      - 404 si el caso aún no tiene plan de intervención generado.
      - 429 si superó rate limit (5/h por caso).
      - 402 si saldo insuficiente para cobrar 0,1 tokens.
    """
    case = _get_owned_case(case_id, user, db)

    # 1. Si existe cached y no force → devolver sin cobro
    if not force:
        cached = (
            db.query(CaseEntry)
            .filter(CaseEntry.case_id == case.id, CaseEntry.type == "plan_simple")
            .order_by(CaseEntry.created_at.desc())
            .first()
        )
        if cached and cached.content:
            return PlanSimpleResponse(
                text=cached.content,
                cached=True,
                balance_after=float(user.tokens),
                created_at=cached.created_at,
                case_id=str(case.id),
            )

    # 2. Verificar que existe un plan de intervención previo (input)
    intervention_entry = (
        db.query(CaseEntry)
        .filter(CaseEntry.case_id == case.id, CaseEntry.type == "intervention")
        .order_by(CaseEntry.created_at.desc())
        .first()
    )
    if not intervention_entry or not intervention_entry.content:
        raise HTTPException(
            status_code=404,
            detail="Necesitas generar el plan de intervención antes de pedir la versión sencilla.",
        )

    # 3. Rate limit (5 generaciones por caso por hora)
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    recent_count = (
        db.query(CaseEntry)
        .filter(
            CaseEntry.case_id == case.id,
            CaseEntry.type == "plan_simple",
            CaseEntry.created_at >= one_hour_ago,
        )
        .count()
    )
    if recent_count >= PLAN_SIMPLE_RATE_LIMIT_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Has alcanzado el máximo de {PLAN_SIMPLE_RATE_LIMIT_PER_HOUR} "
                "generaciones por hora. Espera un momento e inténtalo de nuevo."
            ),
        )

    # 4. Cobrar 0,1 tokens ANTES de invocar IA (invariante financiera)
    new_balance = _charge_user_tokens(user, PLAN_SIMPLE_TOKEN_COST, db)

    # 5. Llamar Haiku 4.5
    try:
        from app.services.plan_simple_ai import run_plan_simple
        ai_result = run_plan_simple(
            original_plan_text=intervention_entry.content,
            lang=lang,
        )
    except Exception as e:
        # Refund si falla la IA
        user.tokens = float(user.tokens) + PLAN_SIMPLE_TOKEN_COST
        db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Error generando plan sencillo: {str(e)[:200]}",
        )

    # 6. Persistir entry tipo 'plan_simple'
    settings = get_settings()
    entry = CaseEntry(
        case_id=case.id,
        type="plan_simple",
        content=ai_result.text,
        ai_model=settings.avatar_model,
        input_tokens=ai_result.input_tokens,
        output_tokens=ai_result.output_tokens,
        tokens_charged=PLAN_SIMPLE_TOKEN_COST,
    )
    db.add(entry)
    case.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(entry)

    # 7. Tracking de coste (CFO oversight, fire-and-forget en log)
    try:
        from app.core.usage_tracker import log_usage
        log_usage(
            user_id=str(user.id),
            endpoint="/cases/plan-simple",
            model=settings.avatar_model,
            input_tokens=ai_result.input_tokens,
            output_tokens=ai_result.output_tokens,
            tokens_charged=PLAN_SIMPLE_TOKEN_COST,
            success="ok",
        )
    except Exception:
        pass

    return PlanSimpleResponse(
        text=ai_result.text,
        cached=False,
        balance_after=new_balance,
        created_at=entry.created_at,
        case_id=str(case.id),
    )


# ── ABC Explained / Cecilia te explica ──────────────────────────────────────
class AbcExplainedResponse(BaseModel):
    text: str
    cached: bool
    balance_after: Optional[float]
    created_at: datetime
    case_id: str


@router.post("/{case_id}/abc-explained", response_model=AbcExplainedResponse)
def generate_abc_explained(
    case_id: str,
    force: bool = Query(False, description="Si true, regenera ignorando cached (cobra otros 0,1)"),
    lang: str = Query("es", description="'es' (default) o 'en'"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Cecilia te explica — versión accesible del análisis funcional ABC.

    Mismas invariantes financieras que Plan Sencillo (CFO 2026-05-04):
      - 0,1 tokens por generación.
      - Persistencia: si existe `CaseEntry.type='abc_explained'`, devuelve
        cached SIN cobro. Solo la primera (o force=true) cobra.
      - Rate limit 5 generaciones por caso por hora.
      - Modelo: Haiku 4.5, output ≤600 tokens (≈4 párrafos 200-350 palabras).

    Errores:
      - 404 si el caso aún no tiene análisis ABC generado.
      - 429 si superó rate limit.
      - 402 si saldo insuficiente.
    """
    case = _get_owned_case(case_id, user, db)

    # 1. Cached → devolver sin cobro
    if not force:
        cached = (
            db.query(CaseEntry)
            .filter(CaseEntry.case_id == case.id, CaseEntry.type == "abc_explained")
            .order_by(CaseEntry.created_at.desc())
            .first()
        )
        if cached and cached.content:
            return AbcExplainedResponse(
                text=cached.content,
                cached=True,
                balance_after=float(user.tokens),
                created_at=cached.created_at,
                case_id=str(case.id),
            )

    # 2. Verificar que existe análisis ABC previo (input)
    abc_entry = (
        db.query(CaseEntry)
        .filter(CaseEntry.case_id == case.id, CaseEntry.type == "abc")
        .order_by(CaseEntry.created_at.desc())
        .first()
    )
    if not abc_entry or not abc_entry.content:
        raise HTTPException(
            status_code=404,
            detail="Necesitas generar primero el análisis funcional ABC.",
        )

    # 3. Rate limit (5 generaciones/h por caso)
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    recent_count = (
        db.query(CaseEntry)
        .filter(
            CaseEntry.case_id == case.id,
            CaseEntry.type == "abc_explained",
            CaseEntry.created_at >= one_hour_ago,
        )
        .count()
    )
    if recent_count >= ABC_EXPLAINED_RATE_LIMIT_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Has alcanzado el máximo de {ABC_EXPLAINED_RATE_LIMIT_PER_HOUR} "
                "generaciones por hora. Espera un momento e inténtalo de nuevo."
            ),
        )

    # 4. Cobrar 0,1 tokens ANTES de invocar IA
    new_balance = _charge_user_tokens(user, ABC_EXPLAINED_TOKEN_COST, db)

    # 5. Llamar Haiku 4.5
    try:
        from app.services.abc_explained_ai import run_abc_explained
        ai_result = run_abc_explained(
            original_abc_text=abc_entry.content,
            lang=lang,
        )
    except Exception as e:
        # Refund si falla la IA
        user.tokens = float(user.tokens) + ABC_EXPLAINED_TOKEN_COST
        db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Error generando explicación: {str(e)[:200]}",
        )

    # 6. Persistir entry tipo 'abc_explained'
    settings = get_settings()
    entry = CaseEntry(
        case_id=case.id,
        type="abc_explained",
        content=ai_result.text,
        ai_model=settings.avatar_model,
        input_tokens=ai_result.input_tokens,
        output_tokens=ai_result.output_tokens,
        tokens_charged=ABC_EXPLAINED_TOKEN_COST,
    )
    db.add(entry)
    case.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(entry)

    # 7. Tracking
    try:
        from app.core.usage_tracker import log_usage
        log_usage(
            user_id=str(user.id),
            endpoint="/cases/abc-explained",
            model=settings.avatar_model,
            input_tokens=ai_result.input_tokens,
            output_tokens=ai_result.output_tokens,
            tokens_charged=ABC_EXPLAINED_TOKEN_COST,
            success="ok",
        )
    except Exception:
        pass

    return AbcExplainedResponse(
        text=ai_result.text,
        cached=False,
        balance_after=new_balance,
        created_at=entry.created_at,
        case_id=str(case.id),
    )


# ── Generación de resúmenes (extracción simple) ─────────────────────────────
# Pensados como punto de partida: comprimir un análisis ABC o un plan completo
# (~5-15 KB) a ~500-800 chars que entran como contexto en futuras consultas.
# Estrategia: limpiar markdown decorativo, tomar las primeras N frases / chars.
# Mejorable a futuro con llamada Haiku para resumir, pero el coste actual de
# extraer es 0 € y el resultado es suficiente para inyectar en summary_full.

import re as _re

_MD_HEADER_RE = _re.compile(r"^[#>]+\s*", _re.MULTILINE)
_MD_BOLD_RE = _re.compile(r"\*\*([^*]+)\*\*")
_MD_ITALIC_RE = _re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_MD_CITATION_RE = _re.compile(r"\[(\d+(?:,\s*\d+)*)\]")
_MD_DECOR_RE = _re.compile(r"^[─═]{3,}$", _re.MULTILINE)
_WS_RE = _re.compile(r"\s+")


def _strip_markdown(text: str) -> str:
    """Limpia markdown inline para extracción de resumen plano."""
    if not text:
        return ""
    t = text
    t = _MD_HEADER_RE.sub("", t)
    t = _MD_BOLD_RE.sub(r"\1", t)
    t = _MD_ITALIC_RE.sub(r"\1", t)
    t = _MD_CITATION_RE.sub("", t)
    t = _MD_DECOR_RE.sub("", t)
    t = _WS_RE.sub(" ", t).strip()
    return t


def _summarize_text(text: str, max_chars: int = 500) -> Optional[str]:
    """Devuelve los primeros max_chars del texto limpiado, cortando en frase."""
    clean = _strip_markdown(text or "")
    if not clean:
        return None
    if len(clean) <= max_chars:
        return clean
    cut = clean[:max_chars]
    last_period = cut.rfind(". ")
    if last_period > max_chars * 0.5:
        return cut[: last_period + 1]
    return cut.rstrip() + "…"


def _build_summary_full(case: Case, dog: Optional[Dog]) -> str:
    """Combina identidad + ABC + plan en un bloque compacto (~2 KB)."""
    parts: List[str] = []
    if dog:
        edad = datetime.utcnow().year - dog.birth_year
        parts.append(
            f"PERRO: {dog.name}, raza {dog.breed}, "
            f"{edad} años, sexo {dog.sex}, "
            f"{'esterilizado' if dog.neutered else 'sin esterilizar'}"
        )
    parts.append(f"TÍTULO: {case.title}")
    if case.motivo_consulta:
        parts.append(f"MOTIVO: {case.motivo_consulta[:500]}")
    if case.summary_abc:
        parts.append(f"ABC: {case.summary_abc[:600]}")
    if case.summary_plan:
        parts.append(f"PLAN: {case.summary_plan[:600]}")
    return "\n\n".join(parts)


# ── Endpoint de migración localStorage → backend ─────────────────────────────
@router.post(
    "/migrate",
    response_model=MigrateResponse,
    status_code=status.HTTP_200_OK,
)
def migrate_legacy_records(
    payload: MigrateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Migra los casos guardados en localStorage del navegador a la base de datos.

    Idempotente: cada record trae un id local (timestamp ms) que se persiste en
    `case.meta.legacy_id`. Si el usuario ya tiene un Case con ese legacy_id,
    se devuelve 'skipped_duplicate' sin volver a crear nada.

    Cuotas:
      - Si el usuario ya está en MAX_CASES_PER_USER, los nuevos se devuelven
        como 'skipped_quota' (sin error 429 — es migración masiva, no fallo).

    Records con análisis o plan vacíos se crean igualmente (el usuario
    pudo tener un caso a medias en localStorage). Sin texto Y sin problem
    Y sin nombre se devuelven como 'skipped_empty' (basura del cliente).
    """
    results: List[MigrateResponseItem] = []
    created = 0
    skipped = 0

    # Pre-cargar legacy_ids ya migrados del usuario para detectar duplicados sin
    # hacer N queries (uno por record).
    existing_cases = db.query(Case).filter(
        Case.user_id == user.id,
        Case.deleted_at.is_(None),
    ).all()
    existing_legacy = set()
    for c in existing_cases:
        if c.summary_abc is None and c.summary_plan is None and c.title is None:
            continue
        meta_legacy_id = None
        # Buscamos legacy_id en cualquier entry tipo anamnesis del caso
        for e in db.query(CaseEntry).filter(
            CaseEntry.case_id == c.id,
            CaseEntry.type == "anamnesis",
        ).all():
            if e.meta and isinstance(e.meta, dict) and "legacy_id" in e.meta:
                meta_legacy_id = e.meta["legacy_id"]
                break
        if meta_legacy_id is not None:
            existing_legacy.add(meta_legacy_id)

    active_count = len([c for c in existing_cases if c.deleted_at is None])

    for rec in payload.records:
        # 1. Saltar duplicados ya migrados
        if rec.id in existing_legacy:
            results.append(MigrateResponseItem(
                legacy_id=rec.id, status="skipped_duplicate",
                detail="Ya migrado en una sincronización anterior."
            ))
            skipped += 1
            continue

        # 2. Saltar records vacíos / basura
        has_content = any([rec.problem, rec.analysis, rec.plan, rec.dog_name])
        if not has_content:
            results.append(MigrateResponseItem(
                legacy_id=rec.id, status="skipped_empty",
                detail="Record sin contenido relevante."
            ))
            skipped += 1
            continue

        # 3. Cuota
        if active_count >= MAX_CASES_PER_USER:
            results.append(MigrateResponseItem(
                legacy_id=rec.id, status="skipped_quota",
                detail=f"Cuota máxima alcanzada ({MAX_CASES_PER_USER}). Casos restantes no migrados."
            ))
            skipped += 1
            continue

        # 4. Crear Case
        title = (rec.problem or rec.dog_name or "Caso clínico").strip()[:150]
        case_status = "archived" if (rec.status or "").lower() in {"archived", "closed", "resolved"} else "open"
        case = Case(
            user_id=user.id,
            dog_id=None,  # Sin vínculo: el usuario lo asocia luego desde la ficha
            title=title,
            motivo_consulta=rec.problem,
            status=case_status,
            summary_abc=_summarize_text(rec.analysis),
            summary_plan=_summarize_text(rec.plan),
        )
        case.summary_full = _build_summary_full(case, dog=None)
        db.add(case)
        db.flush()  # asegurar case.id antes de crear entries

        # 5. Crear entries (anamnesis con legacy_id en meta + abc + intervention)
        anamnesis_meta = {
            "legacy_id": rec.id,
            "legacy_date": rec.date,
            "dog_name": rec.dog_name,
            "breed": rec.breed,
            "dog_age": rec.dog_age,
            "migrated_from_localstorage": True,
        }
        anam = CaseEntry(
            case_id=case.id, type="anamnesis",
            content=(rec.problem or "(Sin texto en el formulario inicial)"),
            meta=anamnesis_meta,
        )
        db.add(anam)

        if rec.analysis:
            db.add(CaseEntry(
                case_id=case.id, type="abc",
                content=rec.analysis,
                meta={"migrated": True},
            ))
        if rec.plan:
            db.add(CaseEntry(
                case_id=case.id, type="intervention",
                content=rec.plan,
                meta={"migrated": True},
            ))

        results.append(MigrateResponseItem(
            legacy_id=rec.id, case_id=str(case.id), status="created"
        ))
        created += 1
        active_count += 1

    db.commit()

    return MigrateResponse(
        results=results,
        created_count=created,
        skipped_count=skipped,
    )
