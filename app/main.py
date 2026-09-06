import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.routes import health, analysis, avatar, documents, intervention
# Via cognitivista italiana: router APARTE, para no tocar analysis.py.
from app.api.routes import analysis_cognitiva as analysis_cognitiva_router
from app.api.routes import auth, payments as payments_router
from app.api.routes import dogs as dogs_router
from app.api.routes import cases as cases_router
from app.api.routes import account as account_router
from app.api.routes import daily_followup as daily_followup_router
from app.api.routes import daily_tip as daily_tip_router
from app.api.routes import delegations as delegations_router
from app.api.routes import subscriptions as subscriptions_router
from app.api.routes import puppy_school as puppy_school_router
from app.api.routes import walks as walks_router
from app.api.routes import corporates as corporates_router
from app.api.routes import invites as invites_router
from app.api.routes import training as training_router
from app.api.routes import training_consult as training_consult_router
from app.api.routes import app_config as app_config_router

# Path to the frontend HTML — override via FRONTEND_HTML env var
FRONTEND_HTML = os.environ.get(
    "FRONTEND_HTML",
    os.path.join(os.path.dirname(__file__), "..", "frontend", "teo-mariscal-v3.html"),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: crear tablas en PostgreSQL
    import app.models  # registra User y Payment en Base.metadata
    from app.database import init_db, engine
    init_db()
    # ── DB migrations ─────────────────────────────────────────────────────────
    if engine:
        from sqlalchemy import text
        migrations = [
            # tokens → NUMERIC
            "ALTER TABLE users ALTER COLUMN tokens TYPE NUMERIC(10,2) USING tokens::NUMERIC(10,2)",
            # role column
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50) NOT NULL DEFAULT 'user'",
            # GDPR/CCPA: phone (PII opcional) + soft-delete con PII scrub
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(32)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP",
            "CREATE INDEX IF NOT EXISTS ix_users_deleted_at ON users(deleted_at)",
            # ── Suscripción mensual (modelo agosto 2026) ─────────────────────
            # Columnas nullable: no tocan a ningún usuario existente. El saldo
            # sigue en `tokens`. Reglas: app/core/subscriptions.py
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_plan VARCHAR(20)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(20)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_store VARCHAR(20)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_expires_at TIMESTAMP",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_started_at TIMESTAMP",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_last_grant VARCHAR(64)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS trial_started_at TIMESTAMP",
            "CREATE INDEX IF NOT EXISTS ix_users_subscription_status ON users(subscription_status)",
            # Partner con tope mensual de coste (2026-08-04)
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS partner_month VARCHAR(7)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS partner_spent NUMERIC(10,2) DEFAULT 0",
            # Afiliación corporativa (2026-08-04): universidades y empresas
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS corporate_id UUID",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS corporate_status VARCHAR(12)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS corporate_spent NUMERIC(10,2) DEFAULT 0",
            "CREATE INDEX IF NOT EXISTS ix_users_corporate ON users(corporate_id, corporate_status)",
            # Permitir user_id NULL en payments para conservar historial fiscal tras delete del user
            "ALTER TABLE payments ALTER COLUMN user_id DROP NOT NULL",
            # Safety classifier shadow log (Apple Guideline 1.1.6 + IA risk mitigation)
            # Apoya a init_db() que crea la tabla; aquí garantizamos índice en score
            "CREATE INDEX IF NOT EXISTS ix_safety_log_score ON safety_log(score_global)",
            "CREATE INDEX IF NOT EXISTS ix_safety_log_created ON safety_log(created_at DESC)",
            # Cost tracking — usage_log índices para queries CFO
            "CREATE INDEX IF NOT EXISTS ix_usage_log_endpoint ON usage_log(endpoint)",
            "CREATE INDEX IF NOT EXISTS ix_usage_log_created ON usage_log(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS ix_usage_log_cost ON usage_log(cost_eur)",
            # Dogs — perfil de perro persistente del usuario (Pet Owner: max 2 dogs)
            # init_db() crea la tabla via Base.metadata.create_all(); aquí garantizamos
            # los índices que SQLAlchemy puede no haber creado en upgrades (si la tabla
            # existía antes con otro esquema).
            "CREATE INDEX IF NOT EXISTS ix_dogs_user_id ON dogs(user_id)",
            "CREATE INDEX IF NOT EXISTS ix_dogs_deleted_at ON dogs(deleted_at)",
            "CREATE INDEX IF NOT EXISTS ix_dogs_user_active ON dogs(user_id, deleted_at)",
            # Cases + CaseEntries — historial clínico persistente del caso
            "CREATE INDEX IF NOT EXISTS ix_cases_user_id ON cases(user_id)",
            "CREATE INDEX IF NOT EXISTS ix_cases_dog_id ON cases(dog_id)",
            "CREATE INDEX IF NOT EXISTS ix_cases_status ON cases(status)",
            "CREATE INDEX IF NOT EXISTS ix_cases_deleted_at ON cases(deleted_at)",
            "CREATE INDEX IF NOT EXISTS ix_cases_user_active ON cases(user_id, deleted_at, updated_at DESC)",
            "CREATE INDEX IF NOT EXISTS ix_case_entries_case_id ON case_entries(case_id)",
            "CREATE INDEX IF NOT EXISTS ix_case_entries_type ON case_entries(type)",
            "CREATE INDEX IF NOT EXISTS ix_case_entries_created_at ON case_entries(created_at)",
            "CREATE INDEX IF NOT EXISTS ix_case_entries_case_chrono ON case_entries(case_id, created_at)",
            # Account type (particular | professional) + perfil empresa para profesionales.
            # account_type por defecto 'particular' para preservar comportamiento de usuarios existentes.
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS account_type VARCHAR(20) NOT NULL DEFAULT 'particular'",
            "CREATE INDEX IF NOT EXISTS ix_users_account_type ON users(account_type)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS company_name VARCHAR(120)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS company_legal_rep VARCHAR(120)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS company_web VARCHAR(255)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS company_cif VARCHAR(40)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS company_clients_per_year INTEGER",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS company_city VARCHAR(80)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS company_country VARCHAR(80)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS company_billing_email VARCHAR(255)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS company_collaborate_interest BOOLEAN",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS company_logo_base64 TEXT",
            # Cases — datos libres del perro de cliente (solo profesionales). dog_id sigue
            # siendo el camino canónico para perros propios; estos campos se rellenan solo
            # cuando el caso es sobre un perro que NO está en el perfil del usuario.
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS client_dog_name VARCHAR(80)",
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS client_dog_breed VARCHAR(120)",
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS client_dog_age VARCHAR(80)",

            # case_type: flujo Entrenamiento Específico (2026-05-29). Default
            # "behavior" para casos pre-existentes (cero regresión). Indexado
            # porque se filtra en s-records (badge "Entrenamiento") y porque
            # el coach del daily-followup lo lee para elegir prompt.
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS case_type VARCHAR(20) NOT NULL DEFAULT 'behavior'",
            "CREATE INDEX IF NOT EXISTS ix_cases_case_type ON cases(case_type)",

            # Daily Follow-up — feature seguimiento diario tipo Duolingo.
            # Spec en memoria: project_dogs_mind_daily_followup.md (9-may-2026).
            # init_db() crea las tablas vía Base.metadata.create_all(); estos
            # ALTER son los que SQLAlchemy NO añadirá si la tabla ya existe.
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS daily_followup_enabled BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS current_streak INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS longest_streak INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS last_filled_at TIMESTAMP",
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS current_badge VARCHAR(10)",
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS gold_token_reward_granted BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS in_recovery BOOLEAN NOT NULL DEFAULT FALSE",
            "CREATE INDEX IF NOT EXISTS ix_daily_followup_case_chrono ON daily_followup_entries(case_id, day_local_date DESC)",
            "CREATE INDEX IF NOT EXISTS ix_case_daily_tasks_case_round ON case_daily_tasks(case_id, generation_round, day_index)",

            # ── Daily Follow-up — wizard ampliado 2026-05-09 ─────────────────
            # Cambio de mecánica: 30 tasks batch → check-in on-demand con 2-5
            # ejercicios (último wellness) + 1 pregunta educativa. Schema:
            # spec en project_dogs_mind_daily_followup.md.
            #
            # Cols nuevas en daily_followup_entries:
            "ALTER TABLE daily_followup_entries ADD COLUMN IF NOT EXISTS exercises_generated JSONB",
            "ALTER TABLE daily_followup_entries ADD COLUMN IF NOT EXISTS exercises_results JSONB",
            "ALTER TABLE daily_followup_entries ADD COLUMN IF NOT EXISTS theory_question_id UUID",
            "ALTER TABLE daily_followup_entries ADD COLUMN IF NOT EXISTS theory_answer_index SMALLINT",
            "ALTER TABLE daily_followup_entries ADD COLUMN IF NOT EXISTS is_complete BOOLEAN NOT NULL DEFAULT FALSE",
            # Cols viejas pasan a nullable (entries pre-existentes los conservan;
            # el flujo nuevo los deja en NULL).
            "ALTER TABLE daily_followup_entries ALTER COLUMN task_completed DROP NOT NULL",
            "ALTER TABLE daily_followup_entries ALTER COLUMN dog_state DROP NOT NULL",
            # CheckConstraint dog_state se vuelve incompatible con NULL — drop si existe.
            "ALTER TABLE daily_followup_entries DROP CONSTRAINT IF EXISTS ck_daily_followup_dog_state",
            # Diagnóstico clínico del caso (clave de caché de preguntas).
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS diagnosis_type VARCHAR(40)",
            "CREATE INDEX IF NOT EXISTS ix_cases_diagnosis_type ON cases(diagnosis_type)",
            # ── Idioma fijo por caso (Opción C, 2026-05-16) ──
            # NULLABLE: casos existentes quedan en NULL → endpoints caen al
            # fallback de query-param `?lang=` (cero regresión). Casos creados
            # tras esta migración llevan el lang de UI al crear el caso.
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS lang VARCHAR(2)",
            # ── Programa de delegaciones (afiliación por país, 2026-05-16) ──
            # init_db() crea la tabla `delegations` via Base.metadata.create_all().
            # Aquí garantizamos índices y FK desde users si la tabla ya existía.
            # User.delegation_id es FK nullable: usuarios pre-feature quedan NULL,
            # solo los nuevos que se registren con código válido reciben FK.
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS delegation_id UUID",
            "CREATE INDEX IF NOT EXISTS ix_users_delegation_id ON users(delegation_id)",
            "CREATE INDEX IF NOT EXISTS ix_delegations_code ON delegations(code)",
            "CREATE INDEX IF NOT EXISTS ix_delegations_active ON delegations(active)",
            # grants_professional (2026-05-21): códigos de socios que dan
            # account_type='professional' gratis al registrarse (ej. TDM-SOCIOS).
            "ALTER TABLE delegations ADD COLUMN IF NOT EXISTS grants_professional BOOLEAN NOT NULL DEFAULT FALSE",
            # Tabla theory_questions — caché por diagnosis_type + question_type + lang.
            # init_db() crea la tabla via Base.metadata.create_all(); aquí garantizamos
            # los índices y constraints adicionales.
            "CREATE INDEX IF NOT EXISTS ix_theory_questions_lookup ON theory_questions(diagnosis_type, question_type, lang)",
            # FK opcional de daily_followup_entries.theory_question_id → theory_questions(id).
            # No lo añadimos como FK constraint hard porque queremos preservar entries
            # incluso si se purga la caché (improbable pero defensivo).
        ]
        for sql in migrations:
            try:
                with engine.connect() as conn:
                    conn.execute(text(sql))
                    conn.commit()
            except Exception:
                pass  # already applied

        # ── Bootstrap delegaciones iniciales (idempotente) ────────────────────
        # Lista de delegaciones aprobadas por Teo 2026-05-16. Se crean en el
        # primer arranque tras desplegar la feature; si ya existen no se tocan
        # (INSERT ... WHERE NOT EXISTS). Para añadir nuevas: editar esta lista
        # y push (próximo arranque crea las nuevas). Para modificar tokens/%
        # de una existente: PATCH /admin/delegations/{id} (NO editar aquí).
        BOOTSTRAP_DELEGATIONS = [
            ("BOCALAN-CO", "Bocalán Colombia",   "Colombia"),
            ("BOCALAN-PE", "Bocalán Perú",       "Perú"),
            ("BOCALAN-EC", "Bocalán Ecuador",    "Ecuador"),
            ("BOCALAN-CL", "Bocalán Chile",      "Chile"),
            ("BOCALAN-UY", "Bocalán Uruguay",    "Uruguay"),
            ("BOCALAN-CR", "Bocalán Costa Rica", "Costa Rica"),
            ("BOCALAN-IT", "Bocalán Italia",     "Italia"),
            ("BOCALAN-IL", "Bocalán Israel",     "Israel"),
            ("BOCALAN-ES", "Bocalán España",     "España"),
        ]
        try:
            import uuid as _uuid_mod
            with engine.connect() as conn:
                for code, name, country in BOOTSTRAP_DELEGATIONS:
                    # Defaults coinciden con DelegationCreate Pydantic:
                    # welcome_bonus_tokens=3, commission_pct_web=10, commission_pct_ios=5, active=true
                    # UUID generado en Python para evitar dependencia de pgcrypto.
                    conn.execute(
                        text("""
                            INSERT INTO delegations (id, code, name, country, welcome_bonus_tokens,
                                                     commission_pct_web, commission_pct_ios, active,
                                                     created_at, updated_at)
                            SELECT :id, :code, :name, :country, 3, 10.00, 5.00, true,
                                   NOW(), NOW()
                            WHERE NOT EXISTS (SELECT 1 FROM delegations WHERE code = :code)
                        """),
                        {"id": str(_uuid_mod.uuid4()), "code": code, "name": name, "country": country},
                    )
                conn.commit()
                print(f"[startup] Bootstrap delegations checked ({len(BOOTSTRAP_DELEGATIONS)} entries, idempotent)")
        except Exception as e:
            print(f"[startup] Bootstrap delegations failed (non-fatal): {e}")

        # ── Promote first admin (set via ADMIN_EMAIL env var) ─────────────────
        admin_email = os.environ.get("ADMIN_EMAIL", "").strip()
        if admin_email:
            try:
                from app.models.user import User
                with engine.connect() as conn:
                    conn.execute(text(
                        "UPDATE users SET role='admin' WHERE email=:email AND role='user'"
                    ), {"email": admin_email})
                    conn.commit()
            except Exception:
                pass

        # ── One-time password reset (RESET_PASSWORD env var) ──────────────────
        reset_pw = os.environ.get("RESET_PASSWORD", "").strip()
        if reset_pw and admin_email:
            try:
                from passlib.context import CryptContext
                pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
                hashed = pwd_ctx.hash(reset_pw)
                with engine.connect() as conn:
                    conn.execute(text(
                        "UPDATE users SET password_hash=:pw WHERE email=:email"
                    ), {"pw": hashed, "email": admin_email})
                    conn.commit()
                print(f"[startup] Password reset for {admin_email}")
            except Exception as e:
                print(f"[startup] Password reset failed: {e}")
    # Startup: ensure Qdrant collection exists (only when keys are available)
    from app.config import get_settings
    from app.core.qdrant_client import ensure_collection
    try:
        ensure_collection()
    except Exception as e:
        print(f"[startup] Could not initialise Qdrant collection: {e}")
    yield


app = FastAPI(
    title="Dogs Mind — Backend API",
    description=(
        "Clinical canine behavioral analysis powered by Claude Sonnet 4.6 "
        "(RAG + prompt caching) and a conversational avatar powered by Claude Haiku 4.5."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
_ALLOWED_ORIGINS = [
    "https://thedogsmind.net",               # production (custom domain)
    "https://www.thedogsmind.net",           # production (www variant)
    "https://beta.thedogsmind.net",          # staging (custom domain)
    "https://thedogsmindbeta.netlify.app",   # staging (Netlify URL, legacy)
    "capacitor://localhost",                 # iOS app (Capacitor WebView)
    "ionic://localhost",                     # iOS app (alt scheme legacy)
    "http://localhost",                      # Android app (Capacitor WebView, androidScheme http)
    "https://localhost",                     # Android app (Capacitor WebView, androidScheme https — default Capacitor 6+)
    "http://localhost:3000",                 # local dev
    "http://localhost:8000",                 # local FastAPI
]
# Allow extra origins via env var (comma-separated) — useful for staging or custom domains
_extra = os.environ.get("EXTRA_ORIGINS", "").strip()
if _extra:
    _ALLOWED_ORIGINS += [o.strip() for o in _extra.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(payments_router.router)
app.include_router(analysis.router)
app.include_router(analysis_cognitiva_router.router)
app.include_router(intervention.router)
app.include_router(avatar.router)
app.include_router(documents.router)
app.include_router(dogs_router.router)
app.include_router(cases_router.router)
app.include_router(account_router.router)
app.include_router(daily_followup_router.router)
app.include_router(daily_tip_router.router)
app.include_router(delegations_router.router)
app.include_router(training_router.router)
app.include_router(training_consult_router.router)
app.include_router(app_config_router.router)
app.include_router(subscriptions_router.router)
app.include_router(puppy_school_router.router)
app.include_router(walks_router.router)
app.include_router(corporates_router.router)
app.include_router(invites_router.router)


@app.get("/", include_in_schema=False)
def serve_frontend():
    """Serve the Dogs Mind single-page app or redirect to Netlify."""
    from fastapi.responses import RedirectResponse
    if os.path.isfile(FRONTEND_HTML):
        return FileResponse(FRONTEND_HTML, media_type="text/html")
    # Frontend is hosted on Netlify — redirect there
    return RedirectResponse(url="https://thedogsmind.net", status_code=302)


@app.get("/admin", include_in_schema=False)
def serve_admin():
    """Admin panel: RAG documents + user management."""
    from fastapi.responses import HTMLResponse
    html = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dogs Mind · Admin</title>
<style>
  body { font-family: system-ui, sans-serif; background: #f5f5f0; margin: 0; padding: 40px 20px; color: #2c2a24; }
  .card { background: #fff; border-radius: 16px; padding: 32px; max-width: 700px; margin: 0 auto 24px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); }
  h1 { font-size: 22px; margin: 0 0 6px; }
  h2 { font-size: 16px; margin: 0 0 16px; border-bottom: 1px solid #eee; padding-bottom: 8px; }
  p { color: #888; font-size: 14px; margin: 0 0 24px; }
  #drop-zone, #drop-zone-b { border: 2px dashed #c0b8aa; border-radius: 12px; padding: 40px 20px; text-align: center; cursor: pointer; transition: all .2s; background: #faf8f4; }
  #drop-zone.hover, #drop-zone-b.hover { border-color: #4a6741; background: #edf2eb; }
  #drop-zone input, #drop-zone-b input { display: none; }
  #drop-zone .icon, #drop-zone-b .icon { font-size: 40px; margin-bottom: 12px; }
  #drop-zone .label, #drop-zone-b .label { font-size: 15px; font-weight: 600; margin-bottom: 4px; }
  #drop-zone .sub, #drop-zone-b .sub { font-size: 13px; color: #aaa; }
  #file-info { margin-top: 16px; font-size: 14px; color: #4a6741; font-weight: 600; min-height: 20px; }
  button { margin-top: 20px; width: 100%; padding: 14px; background: #4a6741; color: #fff; border: none; border-radius: 100px; font-size: 15px; font-weight: 600; cursor: pointer; }
  button:disabled { background: #ccc; cursor: not-allowed; }
  #status { margin-top: 20px; font-size: 14px; min-height: 20px; }
  #docs-section { margin-top: 32px; }
  #docs-section h2 { font-size: 16px; margin-bottom: 12px; }
  .doc-item { background: #f5f5f0; border-radius: 8px; padding: 10px 14px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; font-size: 13px; }
  .doc-item .name { font-weight: 600; }
  .doc-item .chunks { color: #888; }
  .doc-item button { width: auto; padding: 4px 12px; margin: 0; font-size: 12px; background: #c96e3a; border-radius: 100px; }
  /* Users table */
  .u-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .u-table th { text-align: left; padding: 8px 10px; border-bottom: 2px solid #eee; color: #666; font-weight: 600; }
  .u-table td { padding: 8px 10px; border-bottom: 1px solid #f0f0f0; vertical-align: middle; }
  .role-badge { display:inline-block; padding: 2px 8px; border-radius: 100px; font-size: 11px; font-weight: 700; }
  .role-user { background:#f0f0f0; color:#666; }
  .role-ambassador { background:#fff3cd; color:#856404; }
  .role-tech { background:#cff4fc; color:#0c5460; }
  .role-developer { background:#d1ecf1; color:#0c5460; }
  .role-admin { background:#f8d7da; color:#721c24; }
  .btn-sm { width:auto; padding:4px 10px; margin:0; font-size:11px; border-radius:100px; }
  .btn-blue { background:#2a4a8a; }
  .btn-red { background:#c96e3a; }
  .row-input { border:1px solid #ddd; border-radius:6px; padding:4px 8px; font-size:12px; width:60px; }
  #login-section input { width:100%; padding:10px 14px; border:1.5px solid #ddd; border-radius:10px; font-size:14px; margin-bottom:10px; box-sizing:border-box; }
  #admin-content { display:none; }
</style>
</head>
<body>

<!-- LOGIN -->
<div class="card" id="login-section">
  <h1>Dogs Mind · Admin</h1>
  <p>Inicia sesión con tu cuenta de administrador</p>
  <input type="email" id="adm-email" placeholder="Email" onkeydown="if(event.key==='Enter')adminLogin()">
  <input type="password" id="adm-pass" placeholder="Contraseña" onkeydown="if(event.key==='Enter')adminLogin()">
  <button id="login-btn" type="button" onclick="adminLogin()">Entrar</button>
  <div id="login-err" style="color:#c00;font-size:13px;margin-top:10px;"></div>
</div>

<div id="admin-content">
<div class="card">
  <h1>Dogs Mind · Admin RAG</h1>
  <p>Sube PDFs para alimentar la base de conocimiento conductual</p>

  <div id="drop-zone" onclick="document.getElementById('file-input').click()"
       ondragover="event.preventDefault();this.classList.add('hover')"
       ondragleave="this.classList.remove('hover')"
       ondrop="handleDrop(event)">
    <input id="file-input" type="file" accept=".pdf" onchange="handleSelect(this)">
    <div class="icon">📄</div>
    <div class="label">Pulsa o arrastra un PDF aquí</div>
    <div class="sub">Máximo 100 MB</div>
  </div>
  <div id="file-info"></div>
  <button id="upload-btn" onclick="uploadFile()" disabled>Subir a la RAG</button>
  <div id="status"></div>

  <div id="docs-section">
    <h2>📚 Documentos indexados</h2>
    <div id="docs-list"><em style="color:#aaa;font-size:13px;">Cargando...</em></div>
  </div>
</div>

<!-- COGNITIVE CORPUS CARD (RAG B) -->
<div class="card" style="border: 2px solid #5ec8e6;">
  <h1>Corpus Cognitivo IT · RAG B</h1>
  <p>Casos cognitivistas + bibliografía cognitiva (solo vía italiana). Collection separada: <strong>dogs_mind_cognitive_it</strong>. La ingesta anonimiza datos de propietarios (GDPR) antes de indexar.</p>

  <div id="drop-zone-b" onclick="document.getElementById('file-input-b').click()"
       ondragover="event.preventDefault();this.classList.add('hover')"
       ondragleave="this.classList.remove('hover')"
       ondrop="handleDropB(event)"
       style="border-color:#8fd4ec;">
    <input id="file-input-b" type="file" accept=".pdf" onchange="handleSelectB(this)" style="display:none;">
    <div class="icon">📄</div>
    <div class="label">Pulsa o arrastra un PDF aquí (corpus cognitivo)</div>
    <div class="sub">Máximo 100 MB · se anonimiza antes de indexar</div>
  </div>
  <div id="file-info-b" style="margin-top:16px;font-size:14px;color:#2a7a9a;font-weight:600;min-height:20px;"></div>
  <div style="margin-top:12px;font-size:14px;">
    <label style="margin-right:18px;"><input type="radio" name="doctype-b" value="book" checked> Libro / bibliografía <span style="color:#888;">(sin anonimizar)</span></label>
    <label><input type="radio" name="doctype-b" value="case"> Caso real <span style="color:#888;">(anonimiza datos de cliente)</span></label>
  </div>
  <button id="upload-btn-b" onclick="uploadFileB()" disabled style="background:#2a7a9a;margin-top:12px;">Subir a la RAG B (cognitiva)</button>
  <div id="status-b" style="margin-top:20px;font-size:14px;min-height:20px;"></div>

  <div id="docs-section-b" style="margin-top:32px;">
    <h2>📚 Documentos indexados (RAG B)</h2>
    <div id="docs-list-b"><em style="color:#aaa;font-size:13px;">Cargando...</em></div>
  </div>
</div>

<!-- USERS CARD -->
<div class="card">
  <h2>👥 Gestión de usuarios</h2>
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap;">
    <input id="user-search" type="search" oninput="renderUsers()" placeholder="🔎 Buscar por email o rol…"
      style="flex:1;min-width:220px;padding:8px 12px;border:1px solid #ddd;border-radius:8px;font-size:14px;">
    <span id="user-count" style="color:#888;font-size:12px;white-space:nowrap;"></span>
  </div>
  <div style="overflow-x:auto;">
    <table class="u-table">
      <thead><tr><th>Email</th><th>Rol</th><th>Tokens</th><th>Acciones</th></tr></thead>
      <tbody id="users-tbody"><tr><td colspan="4" style="color:#aaa;font-size:13px;">Cargando...</td></tr></tbody>
    </table>
  </div>
  <button onclick="loadUsers()" style="width:auto;padding:8px 20px;margin-top:16px;font-size:13px;">🔄 Actualizar lista</button>
</div>

<script>
var selectedFile = null;

function handleDrop(e) {
  e.preventDefault();
  document.getElementById('drop-zone').classList.remove('hover');
  var f = e.dataTransfer.files[0];
  if (f && f.type === 'application/pdf') setFile(f);
  else alert('Solo se aceptan archivos PDF');
}
function handleSelect(input) {
  if (input.files[0]) setFile(input.files[0]);
}
function setFile(f) {
  selectedFile = f;
  document.getElementById('file-info').textContent = '📄 ' + f.name + ' (' + (f.size/1024/1024).toFixed(1) + ' MB)';
  document.getElementById('upload-btn').disabled = false;
}

async function uploadFile() {
  if (!selectedFile) return;
  var btn = document.getElementById('upload-btn');
  var status = document.getElementById('status');
  btn.disabled = true;
  btn.textContent = 'Subiendo...';
  status.textContent = '';
  var fd = new FormData();
  fd.append('file', selectedFile);
  try {
    var res = await fetch('/documents/upload', { method: 'POST', body: fd });
    var data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al subir');
    status.innerHTML = '⏳ Indexando <strong>' + data.filename + '</strong>...';
    btn.textContent = 'Subir a la RAG';
    selectedFile = null;
    document.getElementById('file-info').textContent = '';
    pollJob(data.job_id);
  } catch(e) {
    status.textContent = '❌ Error: ' + e.message;
    btn.disabled = false;
    btn.textContent = 'Subir a la RAG';
  }
}

async function pollJob(jobId) {
  var status = document.getElementById('status');
  var interval = setInterval(async function() {
    try {
      var res = await fetch('/documents/jobs/' + jobId);
      var data = await res.json();
      if (data.status === 'done') {
        clearInterval(interval);
        status.innerHTML = '✅ <strong>' + data.filename + '</strong> indexado correctamente — ' + data.chunks_indexed + ' chunks';
        loadDocs();
      } else if (data.status === 'error') {
        clearInterval(interval);
        status.textContent = '❌ Error: ' + data.error;
      }
    } catch(e) { clearInterval(interval); }
  }, 2000);
}

async function loadDocs() {
  var list = document.getElementById('docs-list');
  try {
    var res = await fetch('/documents');
    var data = await res.json();
    if (!data.documents || data.documents.length === 0) {
      list.innerHTML = '<em style="color:#aaa;font-size:13px;">No hay documentos indexados aún</em>';
      return;
    }
    list.innerHTML = data.documents.map(function(d) {
      return '<div class="doc-item"><div><div class="name">📄 ' + d.filename + '</div><div class="chunks">' + d.chunk_count + ' chunks</div></div><button onclick="deleteDoc(\\'' + d.filename + '\\')">🗑 Eliminar</button></div>';
    }).join('');
  } catch(e) {
    list.innerHTML = '<em style="color:#aaa;font-size:13px;">Error al cargar documentos</em>';
  }
}

async function deleteDoc(filename) {
  if (!confirm('¿Eliminar ' + filename + ' de la RAG?')) return;
  await fetch('/documents/' + encodeURIComponent(filename), { method: 'DELETE' });
  loadDocs();
}

// ── RAG B: corpus cognitivo IT (slot separado, destino fijo dogs_mind_cognitive_it) ──
var selectedFileB = null;

function handleDropB(e) {
  e.preventDefault();
  document.getElementById('drop-zone-b').classList.remove('hover');
  var f = e.dataTransfer.files[0];
  if (f && f.type === 'application/pdf') setFileB(f);
  else alert('Solo se aceptan archivos PDF');
}
function handleSelectB(input) {
  if (input.files[0]) setFileB(input.files[0]);
}
function setFileB(f) {
  selectedFileB = f;
  document.getElementById('file-info-b').textContent = '📄 ' + f.name + ' (' + (f.size/1024/1024).toFixed(1) + ' MB)';
  document.getElementById('upload-btn-b').disabled = false;
}

async function uploadFileB() {
  if (!selectedFileB) return;
  var btn = document.getElementById('upload-btn-b');
  var status = document.getElementById('status-b');
  btn.disabled = true;
  btn.textContent = 'Subiendo...';
  status.textContent = '';
  var fd = new FormData();
  fd.append('file', selectedFileB);
  var dt = document.querySelector('input[name="doctype-b"]:checked');
  fd.append('doc_type', dt ? dt.value : 'book');
  try {
    var res = await fetch('/documents/cognitive/upload', { method: 'POST', body: fd });
    var data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al subir');
    status.innerHTML = '⏳ Anonimizando e indexando <strong>' + data.filename + '</strong>... (la anonimización tarda ~1 min por caso)';
    btn.textContent = 'Subir a la RAG B (cognitiva)';
    selectedFileB = null;
    document.getElementById('file-info-b').textContent = '';
    pollJobB(data.job_id);
  } catch(e) {
    status.textContent = '❌ Error: ' + e.message;
    btn.disabled = false;
    btn.textContent = 'Subir a la RAG B (cognitiva)';
  }
}

async function pollJobB(jobId) {
  var status = document.getElementById('status-b');
  var interval = setInterval(async function() {
    try {
      var res = await fetch('/documents/jobs/' + jobId);
      var data = await res.json();
      if (data.status === 'done') {
        clearInterval(interval);
        status.innerHTML = '✅ <strong>' + data.filename + '</strong> anonimizado e indexado — ' + data.chunks_indexed + ' chunks';
        loadDocsB();
      } else if (data.status === 'error') {
        clearInterval(interval);
        status.textContent = '❌ Error (nada indexado): ' + data.error;
      }
    } catch(e) { clearInterval(interval); }
  }, 2000);
}

async function loadDocsB() {
  var list = document.getElementById('docs-list-b');
  try {
    var res = await fetch('/documents/cognitive');
    var data = await res.json();
    if (!data.documents || data.documents.length === 0) {
      list.innerHTML = '<em style="color:#aaa;font-size:13px;">RAG B vacía — aún no hay corpus cognitivo</em>';
      return;
    }
    list.innerHTML = data.documents.map(function(d) {
      return '<div class="doc-item"><div><div class="name">📄 ' + d.filename + '</div><div class="chunks">' + d.chunk_count + ' chunks</div></div><button onclick="deleteDocB(\\'' + d.filename + '\\')">🗑 Eliminar</button></div>';
    }).join('');
  } catch(e) {
    list.innerHTML = '<em style="color:#aaa;font-size:13px;">Error al cargar documentos</em>';
  }
}

async function deleteDocB(filename) {
  if (!confirm('¿Eliminar ' + filename + ' de la RAG B (cognitiva)?')) return;
  await fetch('/documents/cognitive/' + encodeURIComponent(filename), { method: 'DELETE' });
  loadDocsB();
}

// ── ADMIN AUTH ───────────────────────────────────────────────────────────────
var _jwt = '';
async function adminLogin() {
  var email = document.getElementById('adm-email').value.trim();
  var pass  = document.getElementById('adm-pass').value;
  var err   = document.getElementById('login-err');
  var btn   = document.getElementById('login-btn');
  err.textContent = '';
  err.style.color = '#c00';
  if (!email || !pass) { err.textContent = 'Rellena email y contraseña.'; return; }
  btn.disabled = true;
  btn.textContent = 'Verificando…';
  try {
    var res = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email, password: pass })
    });
    var data = await res.json();
    if (!res.ok) { err.textContent = data.detail || 'Error ' + res.status; return; }
    if (data.role !== 'admin') { err.textContent = 'Sin permisos de administrador (rol: ' + data.role + ')'; return; }
    _jwt = data.token;
    document.getElementById('login-section').style.display = 'none';
    document.getElementById('admin-content').style.display = 'block';
    loadDocs();
    loadDocsB();
    loadUsers();
  } catch(e) {
    err.textContent = 'Error de red: ' + e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Entrar';
  }
}

function ah() { return { 'Content-Type':'application/json', 'Authorization':'Bearer ' + _jwt }; }

// ── USERS ────────────────────────────────────────────────────────────────────
var _allUsers = [];
async function loadUsers() {
  var res = await fetch('/admin/users', { headers: ah() });
  var data = await res.json();
  _allUsers = data.users || [];
  renderUsers();
}

function renderUsers() {
  var box = document.getElementById('user-search');
  var q = (box && box.value ? box.value : '').trim().toLowerCase();
  var list = q
    ? _allUsers.filter(function(u) {
        return (u.email || '').toLowerCase().indexOf(q) >= 0 ||
               (u.role || '').toLowerCase().indexOf(q) >= 0;
      })
    : _allUsers;
  var rows = list.map(function(u) {
    return '<tr>' +
      '<td>' + u.email + '</td>' +
      '<td><span class="role-badge role-' + u.role + '">' + u.role + '</span></td>' +
      '<td>' + parseFloat(u.tokens).toFixed(2) + '</td>' +
      '<td style="white-space:nowrap;">' +
        '<select id="sel-' + btoa(u.email) + '" style="border:1px solid #ddd;border-radius:6px;padding:3px 6px;font-size:12px;margin-right:4px;">' +
          ['user','ambassador','tech','developer','admin'].map(function(r){ return '<option value="'+r+'"'+(r===u.role?' selected':'')+'>'+r+'</option>'; }).join('') +
        '</select>' +
        '<button class="btn-sm btn-blue" onclick="setRole(&#39;'+u.email+'&#39;)">Rol</button>' +
        '&nbsp;<input class="row-input" id="tok-'+btoa(u.email)+'" type="number" placeholder="tok" min="0.25" step="0.25">' +
        '<button class="btn-sm btn-blue" onclick="addTok(&#39;'+u.email+'&#39;)" style="margin-left:4px;">+Tok</button>' +
      '</td>' +
    '</tr>';
  }).join('');
  var empty = q ? 'Sin resultados para “' + q + '”' : 'Sin usuarios';
  document.getElementById('users-tbody').innerHTML = rows || '<tr><td colspan="4" style="color:#aaa;">' + empty + '</td></tr>';
  var cnt = document.getElementById('user-count');
  if (cnt) cnt.textContent = q ? (list.length + ' de ' + _allUsers.length) : (_allUsers.length + ' usuarios');
}

async function setRole(email) {
  var key = btoa(email);
  var role = document.getElementById('sel-' + key).value;
  var res = await fetch('/admin/set-role', { method:'POST', headers:ah(), body: JSON.stringify({email, role}) });
  var data = await res.json();
  if (!res.ok) { alert(data.detail); return; }
  alert('✅ ' + email + ' → ' + role + ' (' + parseFloat(data.tokens).toFixed(2) + ' tok)');
  loadUsers();
}

async function addTok(email) {
  var key = btoa(email);
  var amount = parseFloat(document.getElementById('tok-' + key).value);
  if (!amount || amount <= 0) { alert('Introduce una cantidad válida'); return; }
  var res = await fetch('/admin/add-tokens', { method:'POST', headers:ah(), body: JSON.stringify({email, amount}) });
  var data = await res.json();
  if (!res.ok) { alert(data.detail); return; }
  alert('✅ +' + amount + ' tok → ' + email + ' (total: ' + parseFloat(data.tokens).toFixed(2) + ')');
  loadUsers();
}

// Auto-load docs only after login — removed from here to avoid unauthenticated calls
</script>
</div><!-- /admin-content -->
</body>
</html>"""
    return HTMLResponse(html)
