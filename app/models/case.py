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
    Column, String, DateTime, Integer, SmallInteger, Text, ForeignKey, Index,
    Numeric, Boolean, Date, UniqueConstraint, CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


# Tipos válidos de entry. Mantener en sync con el schema Pydantic del router.
ENTRY_TYPES = ("anamnesis", "abc", "intervention", "seguimiento", "chat_aigent", "daily_followup")

# Estados válidos del caso.
CASE_STATUSES = ("open", "archived")

# Estados de badge en seguimiento diario.
BADGE_TIERS = (None, "silver", "gold")

# Estado conductual reportado en el wizard diario (5 opciones).
DOG_STATES = ("calm", "active", "nervous", "reactive", "other")

# Calificación de ejecución de la tarea diaria.
EXECUTION_QUALITIES = (None, "better", "expected", "hard")

# Motivos de no-ejecución de la tarea diaria.
SKIP_REASONS = (None, "no_time", "not_dog_moment", "forgot", "other")


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

    # Identidad del perro cuando NO está en el perfil del usuario (solo profesionales).
    # Si el caso está sobre un perro propio del usuario, dog_id apunta al Dog y estos
    # tres campos se quedan NULL. Si el caso es de un perro de cliente del profesional,
    # dog_id es NULL y estos campos guardan los datos libres introducidos por el usuario.
    # Validación de exclusividad (dog_id XOR client_dog_*) se hace en endpoint.
    client_dog_name  = Column(String(80), nullable=True)
    client_dog_breed = Column(String(120), nullable=True)
    client_dog_age   = Column(String(80), nullable=True)   # texto libre (ej. "3 años", "5m")

    # Resúmenes para contexto IA (ver docstring del módulo)
    summary_abc     = Column(Text, nullable=True)
    summary_plan    = Column(Text, nullable=True)
    summary_full    = Column(Text, nullable=True)

    # ── Daily Follow-up (feature seguimiento diario tipo Duolingo) ─────────────
    # Activado por defecto al aceptar un plan de intervención sobre el caso.
    # Toggle desactivable desde s-records. Spec completa en
    # ~/.claude/projects/.../memory/project_dogs_mind_daily_followup.md.
    daily_followup_enabled  = Column(Boolean, nullable=False, default=False)
    current_streak          = Column(Integer, nullable=False, default=0)
    longest_streak          = Column(Integer, nullable=False, default=0)
    last_filled_at          = Column(DateTime, nullable=True)
    current_badge           = Column(String(10), nullable=True)  # None | 'silver' | 'gold'
    gold_token_reward_granted = Column(Boolean, nullable=False, default=False)
    in_recovery             = Column(Boolean, nullable=False, default=False)

    # Tipo de diagnóstico clínico — clave de caché de preguntas de teoría
    # (p.ej. "leash_reactivity", "separation_anxiety", "recall", "resource_guarding").
    # Lo clasifica Haiku al activar el seguimiento diario a partir del plan de
    # intervención. Permite reutilizar preguntas educativas entre perros con el
    # mismo problema sin perder relevancia. Nullable: casos abiertos antes de
    # esta feature no la tienen rellenada.
    diagnosis_type          = Column(String(40), nullable=True, index=True)

    # ── Idioma fijo del caso (Opción C, decidida 2026-05-16) ──────────────────
    # 'es' | 'en'. Se fija al crear el caso con el idioma de UI del usuario en
    # ese momento. Todos los contenidos clínicos generados (plan, plan-simple,
    # ABC, daily-followup ejercicios) se generan y permanecen en este idioma,
    # independientemente del idioma de UI actual. Coherencia documental clínica.
    # NULLABLE: casos creados antes de esta feature tienen NULL → los endpoints
    # caen al fallback de query-param `?lang=` (comportamiento previo intacto,
    # cero regresión). Backfill manual posterior si se desea.
    lang                    = Column(String(2), nullable=True)

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


class DailyFollowupEntry(Base):
    """
    Una entrada del seguimiento diario por caso, una por día local.
    El UNIQUE constraint (case_id, day_local_date) impide rellenar el mismo
    día dos veces. La lógica de streak / badge / recovery vive en el endpoint
    de inserción.

    Cambio 2026-05-09 (wizard ampliado): el check-in pasa de wizard 4 pasos
    (task_completed/dog_state/observation) a un set de 2-5 ejercicios + pregunta
    educativa generados on-demand por la IA. Los campos viejos quedan nullable
    para soportar entries pre-existentes; las nuevas se rellenan con
    exercises_generated/exercises_results/theory_*.
    """
    __tablename__ = "daily_followup_entries"

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id            = Column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True)
    user_id            = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    day_local_date     = Column(Date, nullable=False)  # día local del usuario (YYYY-MM-DD)

    # Campos legacy (wizard 4 pasos) — quedan nullable para no romper entries
    # ya persistidas. El nuevo flujo los deja en NULL.
    task_completed     = Column(Boolean, nullable=True)
    execution_quality  = Column(String(16), nullable=True)
    skip_reason        = Column(String(20), nullable=True)
    dog_state          = Column(String(16), nullable=True)
    observation        = Column(Text, nullable=True)

    # Wizard ampliado 2026-05-09: ejercicios + pregunta del día
    # exercises_generated: snapshot de los N ejercicios que la IA propuso ese
    # día. Schema: [{title, instruction, result_type, result_chips?, is_wellness}, ...].
    # exercises_results: respuestas del usuario por ejercicio. Schema:
    # [{result_chip_index?, result_text?}, ...] mismo orden que generated.
    exercises_generated   = Column(JSONB, nullable=True)
    exercises_results     = Column(JSONB, nullable=True)

    # Pregunta educativa del día (mix theory/compliance, decidido por IA).
    # theory_question_id apunta a TheoryQuestion (caché por diagnosis_type).
    # theory_answer_index es la opción que pulsó el usuario; al ser educativa
    # (la app le muestra la correcta), siempre coincide con la correcta. No se
    # persiste "answer_correct" porque no aplica a una experiencia formativa.
    theory_question_id    = Column(UUID(as_uuid=True), ForeignKey("theory_questions.id"), nullable=True)
    theory_answer_index   = Column(SmallInteger, nullable=True)

    # is_complete = True solo si TODOS los ejercicios tienen respuesta + la
    # pregunta del día tiene answer_index. La regla de "rellenar el día" para
    # streak depende de este flag.
    is_complete           = Column(Boolean, nullable=False, default=False)

    created_at         = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("case_id", "day_local_date", name="uq_daily_followup_case_day"),
        # CheckConstraint dog_state se elimina porque la columna pasa a nullable
        # y al ser NULL en el flujo nuevo no aplicaría. La validación enum del
        # flujo legacy se hace en Pydantic en el endpoint.
    )


# Índice para "últimas N entries de un caso ordenadas".
Index("ix_daily_followup_case_chrono", DailyFollowupEntry.case_id, DailyFollowupEntry.day_local_date.desc())


class CaseDailyTask(Base):
    """
    Tareas diarias pre-generadas por Sonnet 4.6 cuando se acepta el plan de
    intervención. 30 tasks por caso (day_index 1..30), cada una de 1-2 frases.
    Si el usuario llega al día 31 sin cerrar el caso, se regenera una nueva
    serie con leve variación (~$0.003 por regeneración).
    """
    __tablename__ = "case_daily_tasks"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id     = Column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True)
    day_index   = Column(SmallInteger, nullable=False)  # 1..30
    task_text   = Column(Text, nullable=False)
    generation_round = Column(SmallInteger, nullable=False, default=1)  # 1, 2, ... si se regeneran ciclos

    created_at  = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("case_id", "day_index", "generation_round",
                         name="uq_case_daily_tasks_case_day_round"),
        CheckConstraint("day_index BETWEEN 1 AND 30", name="ck_case_daily_tasks_day_range"),
    )


Index("ix_case_daily_tasks_case_round", CaseDailyTask.case_id, CaseDailyTask.generation_round, CaseDailyTask.day_index)


class TheoryQuestion(Base):
    """
    Caché de preguntas educativas del seguimiento diario, indexada por
    `diagnosis_type` (la clave de cacheo) + `question_type` + `lang`.

    La IA (Sonnet) genera preguntas tipo test (3 opciones, 1 correcta + explicación).
    En lugar de regenerarlas para cada perro, se guardan aquí: cuando llega un
    nuevo caso del mismo diagnóstico, hay una probabilidad alta (≥70%) de servir
    una pregunta de la caché que el usuario aún no haya visto, abaratando coste
    sin perder relevancia.

    La experiencia es educativa, no evaluativa: el frontend muestra la respuesta
    correcta (oculta tras desplegable o invertida) antes de que el usuario marque.
    Por eso se persiste `correct_index` a nivel de pregunta, pero a nivel de
    entry del usuario solo se guarda qué opción pulsó (que coincide).
    """
    __tablename__ = "theory_questions"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    diagnosis_type  = Column(String(40), nullable=False, index=True)  # clave de caché
    question_type   = Column(String(20), nullable=False)              # 'theory' | 'compliance'
    lang            = Column(String(2), nullable=False)               # 'es' | 'en'

    question_text   = Column(Text, nullable=False)
    options         = Column(JSONB, nullable=False)                   # array de 3 strings
    correct_index   = Column(SmallInteger, nullable=False)            # 0/1/2
    explanation     = Column(Text, nullable=False)

    usage_count     = Column(Integer, nullable=False, default=0)
    created_at      = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "question_type IN ('theory','compliance')",
            name="ck_theory_questions_type",
        ),
        CheckConstraint(
            "correct_index BETWEEN 0 AND 2",
            name="ck_theory_questions_correct_idx",
        ),
        CheckConstraint(
            "lang IN ('es','en')",
            name="ck_theory_questions_lang",
        ),
    )


Index(
    "ix_theory_questions_lookup",
    TheoryQuestion.diagnosis_type, TheoryQuestion.question_type, TheoryQuestion.lang,
)


class DailyTip(Base):
    """
    Caché del "Consejo del día" mostrado en s-home. Indexado por (date, lang).

    Generado por Claude Haiku 4.5 con prompt experto en psicologia del
    aprendizaje canino. Una sola entrada por (fecha UTC, idioma): todos los
    usuarios ven el MISMO consejo el mismo dia para esa lang. Coste minimo:
    2 generaciones/dia (es + en) ≈ $0.0001/dia.

    El usuario NO ve atribucion a "Cecilia"; el frontend solo muestra:
    "Consejo del día: <tip>"
    """
    __tablename__ = "daily_tips"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date        = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD UTC
    lang        = Column(String(2), nullable=False)               # 'es' | 'en'
    tip         = Column(Text, nullable=False)
    created_at  = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "lang IN ('es','en')",
            name="ck_daily_tips_lang",
        ),
    )


Index(
    "ix_daily_tips_lookup",
    DailyTip.date, DailyTip.lang,
    unique=True,
)
