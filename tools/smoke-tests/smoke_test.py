#!/usr/bin/env python3
"""
Dogs Mind — Smoke test pre-App Store
Ejecuta cada 6h via LaunchAgent (~/Library/LaunchAgents/net.thedogsmind.smoke.plist).

Verifica:
  1. Backend Railway health + TTFB
  2. SW versions consistencia prod/staging + detecta rollback
  3. HTML hash change (detect deploys)
  4. Elementos UI críticos presentes
  5. Endpoints HTTP códigos esperados
  6. Delegaciones E2E (3 países random)
  7. Embajador particular E2E
  8. Sites Netlify status
  9. Screenshots (opcional via Playwright)

Output:
  - Log: tools/smoke-tests/logs/YYYY-MM-DD-HHMMSS.log
  - Notification macOS si error o warning

Exit codes:
  0 → todo OK
  1 → errores detectados
  2 → solo warnings
"""

import json
import os
import random
import subprocess
import sys
import time
import urllib.request
import urllib.error
import hashlib
import socket
from datetime import datetime
from pathlib import Path

# ─── Config ──────────────────────────────────────────────────────
HOME = Path.home()
REPO = Path(__file__).resolve().parent.parent.parent
SMOKE_DIR = REPO / "tools" / "smoke-tests"
LOG_DIR = SMOKE_DIR / "logs"
BASE_DIR = SMOKE_DIR / "baselines"
LOG_DIR.mkdir(parents=True, exist_ok=True)
BASE_DIR.mkdir(parents=True, exist_ok=True)

TS = datetime.now().strftime("%Y-%m-%d-%H%M%S")
LOG_FILE = LOG_DIR / f"{TS}.log"

errors = []
warnings = []

# ─── Helpers ─────────────────────────────────────────────────────
def log(msg):
    print(msg)
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")

def ok(msg): log(f"  ✓ {msg}")
def warn(msg):
    warnings.append(msg)
    log(f"  ⚠ WARN: {msg}")
def err(msg):
    errors.append(msg)
    log(f"  ✗ ERROR: {msg}")

def http_get(url, timeout=15):
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DogsMindSmoke/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return r.status, body, time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read() if e.fp else b"", time.time() - t0
    except (urllib.error.URLError, socket.timeout) as e:
        return None, str(e).encode(), time.time() - t0

def http_post(url, payload=None, headers=None, timeout=15):
    t0 = time.time()
    data = json.dumps(payload or {}).encode()
    h = {"Content-Type": "application/json", "User-Agent": "DogsMindSmoke/1.0"}
    if headers: h.update(headers)
    try:
        req = urllib.request.Request(url, data=data, headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read() if e.fp else b"", time.time() - t0
    except (urllib.error.URLError, socket.timeout) as e:
        return None, str(e).encode(), time.time() - t0

def notify(title, msg, sound=None):
    """macOS notification via osascript."""
    s = f' sound name "{sound}"' if sound else ''
    subprocess.run(
        ["osascript", "-e", f'display notification "{msg}" with title "{title}"{s}'],
        check=False, capture_output=True,
    )

# ─── Header ──────────────────────────────────────────────────────
log("═" * 64)
log(f"  Dogs Mind Smoke Test — {TS}")
log("═" * 64)

# ─── 1. Backend health ───────────────────────────────────────────
log("\n── 1. Backend Railway health")
code, body, ttfb = http_get("https://dogs-mind-backend-production.up.railway.app/health")
if code == 200:
    ok(f"Backend HTTP 200 · TTFB {ttfb:.3f}s")
    if ttfb > 2.0: warn(f"TTFB lento ({ttfb:.2f}s, umbral 2s)")
    try:
        data = json.loads(body)
        if data.get("qdrant") == "connected":
            ok("Qdrant connected")
        else:
            err(f"Qdrant: {data.get('qdrant')}")
    except json.JSONDecodeError:
        warn("Backend OK pero JSON malformado")
else:
    err(f"Backend caído o degradado → HTTP {code}")

# ─── 2. SW versions ──────────────────────────────────────────────
log("\n── 2. SW versions consistencia")
_, sw_prod_body, _ = http_get("https://thedogsmind.net/service-worker.js")
_, sw_stag_body, _ = http_get("https://beta.thedogsmind.net/service-worker.js")
sw_prod_str = sw_prod_body.decode(errors='ignore').split('\n')[0] if sw_prod_body else ""
sw_stag_str = sw_stag_body.decode(errors='ignore').split('\n')[0] if sw_stag_body else ""

import re
m_prod = re.search(r"v(\d+)", sw_prod_str)
m_stag = re.search(r"v(\d+)", sw_stag_str)
sw_prod = f"v{m_prod.group(1)}" if m_prod else "??"
sw_stag = f"v{m_stag.group(1)}" if m_stag else "??"
log(f"  Prod: {sw_prod} · Staging: {sw_stag}")

last_sw_file = BASE_DIR / "last_sw.txt"
if last_sw_file.exists():
    last_sw = last_sw_file.read_text().strip()
    if sw_prod != last_sw and m_prod and re.search(r"v(\d+)", last_sw):
        new_n = int(m_prod.group(1))
        old_n = int(re.search(r"v(\d+)", last_sw).group(1))
        if new_n < old_n:
            err(f"SW ROLLBACK: {last_sw} → {sw_prod}")
        else:
            ok(f"SW updated: {last_sw} → {sw_prod}")
    else:
        ok(f"SW estable en {sw_prod}")
last_sw_file.write_text(sw_prod)

if sw_prod != sw_stag and sw_prod != "??" and sw_stag != "??":
    warn(f"Prod {sw_prod} y Staging {sw_stag} desincronizados")

# ─── 3. HTML hash ────────────────────────────────────────────────
log("\n── 3. HTML hash (deploy detection)")
_, html_body, _ = http_get("https://thedogsmind.net/")
html_hash = hashlib.sha256(html_body).hexdigest()[:16]
html_size = len(html_body)
log(f"  Size: {html_size} · Hash: {html_hash}")

last_hash_file = BASE_DIR / "last_html_hash.txt"
if last_hash_file.exists():
    last_hash = last_hash_file.read_text().strip()
    if html_hash != last_hash:
        ok(f"HTML cambió: {last_hash} → {html_hash}")
    else:
        ok("HTML idéntico al check anterior")
last_hash_file.write_text(html_hash)

# ─── 4. Elementos UI ─────────────────────────────────────────────
log("\n── 4. Elementos UI críticos presentes")
html_str = html_body.decode(errors='ignore')
ui_checks = [
    ('data-i18n="begin_consultation"', "Botón Comenzar consulta"),
    ('id="reg-invite"', "Invite registro particular"),
    ('id="ps-invite"', "Invite Pro signup"),
    ('id="send-btn"', "Botón enviar chat"),
    ('id="video-drop-zone"', "Drop zone vídeo"),
    ("_fmtInsufTokens", "Helper 402 tokens"),
    ("_syncProBtn", "Listener Pro courtesy"),
    ("anam_drop_formats", "i18n drop formats"),
    ("min-width: 0 !important", "Fix chat overflow"),
    ("env(safe-area-inset", "Safe areas iPhone X+"),
]
for pattern, label in ui_checks:
    if pattern in html_str: ok(label)
    else: err(f"FALTA: {label}")

# ─── 5. Endpoints HTTP ───────────────────────────────────────────
log("\n── 5. Endpoints HTTP códigos esperados")
endpoints = [
    ("POST", "/auth/register", 422),
    ("POST", "/auth/login", 422),
    ("POST", "/payments/checkout", 401),
    ("POST", "/payments/pro-activate-courtesy", 401),
    ("POST", "/analysis", 422),
    ("GET", "/admin/delegations/report", 401),
    ("GET", "/cases", 401),
    ("GET", "/tip/today", 200),
]
base = "https://dogs-mind-backend-production.up.railway.app"
for method, path, expected in endpoints:
    if method == "POST":
        code, _, _ = http_post(f"{base}{path}", {})
    else:
        code, _, _ = http_get(f"{base}{path}")
    if code == expected: ok(f"{method} {path} → {code}")
    else: err(f"{method} {path} → {code} (esperado: {expected})")

# ─── 6. Delegaciones E2E ─────────────────────────────────────────
log("\n── 6. Delegaciones E2E (3 países random)")
countries = ["BOCALAN-CL", "BOCALAN-CO", "BOCALAN-ES", "BOCALAN-PE", "BOCALAN-IT", "BOCALAN-EC", "BOCALAN-UY", "BOCALAN-CR", "BOCALAN-IL"]
for code_country in random.sample(countries, 3):
    ns_ms = int(time.time() * 1000_000)
    email = f"smoke-{ns_ms}-{code_country}@dogsmindsmoke.net"
    code, body, _ = http_post(
        f"{base}/auth/register",
        {"email": email, "password": "smoketest1234", "invite_code": code_country},
    )
    try:
        data = json.loads(body)
        deleg = data.get("delegation_name") or ""
        tokens = data.get("tokens")
        if deleg and tokens == 8.0: ok(f"{code_country} → '{deleg}' · {tokens} tokens")
        else: err(f"{code_country} FALLA → deleg='{deleg}' tokens={tokens}")
    except (json.JSONDecodeError, KeyError):
        err(f"{code_country} FALLA → resp malformada: {body[:100]}")

# ─── 7. Embajador E2E ────────────────────────────────────────────
log("\n── 7. Embajador particular E2E")
ns_ms = int(time.time() * 1000_000)
email = f"smoke-amb-{ns_ms}@dogsmindsmoke.net"
code, body, _ = http_post(
    f"{base}/auth/register",
    {"email": email, "password": "smoketest1234", "invite_code": "DogsmindAmb25@"},
)
try:
    data = json.loads(body)
    if data.get("role") == "ambassador" and data.get("tokens") == 8.0:
        ok(f"Embajador → role=ambassador · 8.0 tokens")
    else:
        err(f"Embajador FALLA → role={data.get('role')} tokens={data.get('tokens')}")
except json.JSONDecodeError:
    err(f"Embajador resp malformada: {body[:100]}")

# ─── 8. Netlify sites ────────────────────────────────────────────
log("\n── 8. Netlify sites status")
for url in ["https://thedogsmind.net", "https://beta.thedogsmind.net", "https://dogsmind-hub.netlify.app"]:
    code, _, _ = http_get(url)
    if code == 200: ok(f"{url} → 200")
    else: err(f"{url} → {code}")

# ─── Resumen ─────────────────────────────────────────────────────
log("\n" + "═" * 64)
log(f"  RESUMEN — {len(errors)} errores, {len(warnings)} warnings")
log("═" * 64)
log(f"  Log: {LOG_FILE}")

if errors:
    notify("Dogs Mind FAIL", f"{len(errors)} errores. Ver {LOG_FILE.name}", "Basso")
    sys.exit(1)
elif warnings:
    notify("Dogs Mind OK con warnings", f"{len(warnings)} warnings", None)
    sys.exit(2)
else:
    notify("Dogs Mind OK", f"Todo bien — SW {sw_prod}", None)
    sys.exit(0)
