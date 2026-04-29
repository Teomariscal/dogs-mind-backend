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

from datetime import datetime
from typing import Optional, List, Literal

from fastapi import APIRouter, Depends, HTTPException, status, Query
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
SEGUIMIENTO_MAX_OBSERVACIONES_CHARS = 1500  # límite anti-abuso, alineado con chat clínico cap
SEGUIMIENTO_MAX_INFO_EXTRA_CHARS = 1000     # ~4 frases típicas
SEGUIMIENTO_MAX_MOTIVO_RESUMIDO_CHARS = 300 # 1 frase


# ── Schemas Pydantic ─────────────────────────────────────────────────────────
class CaseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=150, description="Título del caso (motivo principal)")
    motivo_consulta: Optional[str] = Field(None, max_length=5000, description="Descripción libre del motivo")
    dog_id: Optional[str] = Field(None, description="UUID del perro al que pertenece el caso")

    @field_validator("title", "motivo_consulta")
    @classmethod
    def strip_text(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


class CaseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=150)
    motivo_consulta: Optional[str] = Field(None, max_length=5000)
    status: Optional[Literal["open", "archived"]] = None
    dog_id: Optional[str] = None

    @field_validator("title", "motivo_consulta")
    @classmethod
    def strip_text(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


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

    # Validar dog si se pasa
    valid_dog_id = _validate_dog_ownership(payload.dog_id, user, db)

    case = Case(
        user_id=user.id,
        dog_id=valid_dog_id,
        title=payload.title,
        motivo_consulta=payload.motivo_consulta,
        status="open",
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

    # Validar dog si cambia
    if "dog_id" in data:
        data["dog_id"] = _validate_dog_ownership(data["dog_id"], user, db)

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
