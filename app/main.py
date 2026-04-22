import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.routes import health, analysis, avatar, documents, intervention
from app.api.routes import auth, payments as payments_router

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
        ]
        for sql in migrations:
            try:
                with engine.connect() as conn:
                    conn.execute(text(sql))
                    conn.commit()
            except Exception:
                pass  # already applied

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
    "https://thedogsmindbeta.netlify.app",  # production frontend
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
app.include_router(intervention.router)
app.include_router(avatar.router)
app.include_router(documents.router)


@app.get("/", include_in_schema=False)
def serve_frontend():
    """Serve the Dogs Mind single-page app or redirect to Netlify."""
    from fastapi.responses import RedirectResponse
    if os.path.isfile(FRONTEND_HTML):
        return FileResponse(FRONTEND_HTML, media_type="text/html")
    # Frontend is hosted on Netlify — redirect there
    return RedirectResponse(url="https://thedogsmindbeta.netlify.app", status_code=302)


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
  #drop-zone { border: 2px dashed #c0b8aa; border-radius: 12px; padding: 40px 20px; text-align: center; cursor: pointer; transition: all .2s; background: #faf8f4; }
  #drop-zone.hover { border-color: #4a6741; background: #edf2eb; }
  #drop-zone input { display: none; }
  #drop-zone .icon { font-size: 40px; margin-bottom: 12px; }
  #drop-zone .label { font-size: 15px; font-weight: 600; margin-bottom: 4px; }
  #drop-zone .sub { font-size: 13px; color: #aaa; }
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
  <h1>🐕 Dogs Mind · Admin</h1>
  <p>Inicia sesión con tu cuenta de administrador</p>
  <input type="email" id="adm-email" placeholder="Email" onkeydown="if(event.key==='Enter')adminLogin()">
  <input type="password" id="adm-pass" placeholder="Contraseña" onkeydown="if(event.key==='Enter')adminLogin()">
  <button id="login-btn" type="button" onclick="adminLogin()">Entrar</button>
  <div id="login-err" style="color:#c00;font-size:13px;margin-top:10px;"></div>
</div>

<div id="admin-content">
<div class="card">
  <h1>🐕 Dogs Mind · Admin RAG</h1>
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

<!-- USERS CARD -->
<div class="card">
  <h2>👥 Gestión de usuarios</h2>
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
async function loadUsers() {
  var res = await fetch('/admin/users', { headers: ah() });
  var data = await res.json();
  var rows = (data.users || []).map(function(u) {
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
  document.getElementById('users-tbody').innerHTML = rows || '<tr><td colspan="4" style="color:#aaa;">Sin usuarios</td></tr>';
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
