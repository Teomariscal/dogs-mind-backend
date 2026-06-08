#!/bin/bash
#
# Dogs Mind — Smoke test pre-App Store
# Ejecuta cada 6h via LaunchAgent o manualmente.

# PATH explícito (necesario cuando corre vía LaunchAgent, que tiene PATH limitado)
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
#
# Verifica:
#   1. Backend Railway health + TTFB
#   2. SW versions consistencia prod/staging
#   3. HTML hash change detection (deploy alert)
#   4. Elementos UI críticos presentes
#   5. Endpoints HTTP códigos esperados
#   6. Delegaciones E2E (3 países random)
#   7. Embajador particular E2E
#   8. Sites Netlify status
#   9. Screenshots Playwright + comparación con baseline
#
# Output: tools/smoke-tests/logs/YYYY-MM-DD-HHMMSS.log
# Si hay regresión → osascript notification + exit 1

set +e  # NO abortar en error individual — queremos correr todos los checks

REPO_DIR="$HOME/dogs-mind-backend"
SMOKE_DIR="$REPO_DIR/tools/smoke-tests"
LOG_DIR="$SMOKE_DIR/logs"
BASELINE_DIR="$SMOKE_DIR/baselines"
TS=$(date +%Y-%m-%d-%H%M%S)
LOG_FILE="$LOG_DIR/$TS.log"
ERRORS=0
WARNINGS=0

mkdir -p "$LOG_DIR" "$BASELINE_DIR"

log() { echo "$1" | tee -a "$LOG_FILE"; }
err() { ERRORS=$((ERRORS+1)); log "  ✗ ERROR: $1"; }
warn() { WARNINGS=$((WARNINGS+1)); log "  ⚠ WARN: $1"; }
ok() { log "  ✓ $1"; }

log "════════════════════════════════════════════════════════════════"
log "  Dogs Mind Smoke Test — $TS"
log "════════════════════════════════════════════════════════════════"

# ─── 1. Backend health ───────────────────────────────────────────
log ""
log "── 1. Backend Railway health"
HEALTH=$(curl -s -o /tmp/health.json -w "HTTP %{http_code}|%{time_starttransfer}" https://dogs-mind-backend-production.up.railway.app/health)
CODE="${HEALTH%%|*}"
TTFB="${HEALTH##*|}"
if [[ "$CODE" == "HTTP 200" ]]; then
  ok "Backend $CODE · TTFB ${TTFB}s"
  if (( $(echo "$TTFB > 2.0" | bc -l) )); then warn "TTFB lento: ${TTFB}s (umbral: 2s)"; fi
else
  err "Backend $CODE — caído o degradado"
fi
QDRANT=$(grep -oE '"qdrant":"[^"]*"' /tmp/health.json | cut -d'"' -f4)
if [[ "$QDRANT" == "connected" ]]; then ok "Qdrant connected"; else err "Qdrant: $QDRANT"; fi

# ─── 2. SW versions ──────────────────────────────────────────────
log ""
log "── 2. SW versions consistencia"
SW_PROD=$(curl -s https://thedogsmind.net/service-worker.js | head -1 | grep -oE "v[0-9]+" | head -1)
SW_STAG=$(curl -s https://beta.thedogsmind.net/service-worker.js | head -1 | grep -oE "v[0-9]+" | head -1)
log "  Prod: $SW_PROD · Staging: $SW_STAG"

LAST_SW_FILE="$BASELINE_DIR/last_sw.txt"
if [ -f "$LAST_SW_FILE" ]; then
  LAST_SW=$(cat "$LAST_SW_FILE")
  if [[ "$SW_PROD" != "$LAST_SW" ]]; then
    NEW_NUM=$(echo "$SW_PROD" | sed 's/v//')
    OLD_NUM=$(echo "$LAST_SW" | sed 's/v//')
    if (( NEW_NUM < OLD_NUM )); then
      err "SW ROLLBACK detectado: $LAST_SW → $SW_PROD (regresión)"
    else
      ok "SW updated: $LAST_SW → $SW_PROD (deploy nuevo OK)"
    fi
  else
    ok "SW estable en $SW_PROD"
  fi
fi
echo "$SW_PROD" > "$LAST_SW_FILE"

if [[ "$SW_PROD" != "$SW_STAG" ]]; then warn "Prod ($SW_PROD) y Staging ($SW_STAG) desincronizados"; fi

# ─── 3. HTML hash (detecta deploys silenciosos) ──────────────────
log ""
log "── 3. HTML hash (detecta cambios sin SW bump)"
curl -s https://thedogsmind.net/ -o /tmp/index.html
HTML_SIZE=$(wc -c < /tmp/index.html | tr -d ' ')
HTML_HASH=$(shasum -a 256 /tmp/index.html | cut -d' ' -f1 | cut -c1-16)
log "  Size: $HTML_SIZE · Hash: $HTML_HASH"

LAST_HASH_FILE="$BASELINE_DIR/last_html_hash.txt"
if [ -f "$LAST_HASH_FILE" ]; then
  LAST_HASH=$(cat "$LAST_HASH_FILE")
  if [[ "$HTML_HASH" != "$LAST_HASH" ]]; then
    ok "HTML cambió: $LAST_HASH → $HTML_HASH"
  else
    ok "HTML idéntico"
  fi
fi
echo "$HTML_HASH" > "$LAST_HASH_FILE"

# ─── 4. Elementos UI críticos ────────────────────────────────────
log ""
log "── 4. Elementos UI críticos presentes"
declare -a UI_CHECKS=(
  'data-i18n="begin_consultation"|Botón Comenzar consulta'
  'id="reg-invite"|Invite registro particular'
  'id="ps-invite"|Invite Pro signup'
  'id="send-btn"|Botón enviar chat'
  'id="video-drop-zone"|Drop zone vídeo'
  '_fmtInsufTokens|Helper 402 tokens'
  '_syncProBtn|Listener Pro courtesy'
  'anam_drop_formats|i18n drop formats'
  'min-width: 0 !important|Fix chat overflow'
  'capture="environment"|Vídeo capture mobile'
  '/admin/cfo-report|CFO endpoint'
  'env(safe-area-inset|Safe areas iPhone X+'
)
for ck in "${UI_CHECKS[@]}"; do
  PATTERN="${ck%%|*}"
  LABEL="${ck##*|}"
  # Fix robusto: forzar resultado a int single-line
  COUNT=$(grep -c -- "$PATTERN" /tmp/index.html 2>/dev/null | head -1)
  COUNT=${COUNT:-0}
  if [ "$COUNT" -gt 0 ] 2>/dev/null; then ok "$LABEL"; else err "FALTA: $LABEL"; fi
done

# ─── 5. Endpoints HTTP códigos esperados ─────────────────────────
log ""
log "── 5. Endpoints HTTP códigos esperados"
declare -a ENDPOINTS=(
  "POST|/auth/register|422"
  "POST|/auth/login|422"
  "POST|/payments/checkout|401"
  "POST|/payments/pro-activate-courtesy|401"
  "POST|/analysis|422"
  "GET|/admin/delegations/report|401"
  "GET|/cases|401"
  "GET|/tip/today|200"
)
for ep in "${ENDPOINTS[@]}"; do
  IFS='|' read -r METHOD PATH EXPECTED <<< "$ep"
  ACTUAL=$(curl -s -o /dev/null -w "%{http_code}" -X "$METHOD" "https://dogs-mind-backend-production.up.railway.app$PATH" -H "Content-Type: application/json" -d '{}')
  if [[ "$ACTUAL" == "$EXPECTED" ]]; then ok "$METHOD $PATH → $ACTUAL"; else err "$METHOD $PATH → $ACTUAL (esperado: $EXPECTED)"; fi
done

# ─── 6. Delegaciones E2E ─────────────────────────────────────────
log ""
log "── 6. Delegaciones E2E"
RAND_COUNTRIES=(BOCALAN-CL BOCALAN-CO BOCALAN-ES BOCALAN-PE BOCALAN-IT)
SHUFFLED=($(printf "%s\n" "${RAND_COUNTRIES[@]}" | sort -R | head -3))
for code in "${SHUFFLED[@]}"; do
  EMAIL="smoke-$(date +%s%N)-$code@dogsmindsmoke.net"
  RESP=$(curl -s -X POST https://dogs-mind-backend-production.up.railway.app/auth/register \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL\",\"password\":\"smoketest1234\",\"invite_code\":\"$code\"}")
  DELEG=$(echo "$RESP" | grep -oE '"delegation_name":"[^"]*"' | cut -d'"' -f4)
  TOK=$(echo "$RESP" | grep -oE '"tokens":[0-9.]+' | cut -d':' -f2)
  if [[ -n "$DELEG" && "$TOK" == "8.0" ]]; then ok "$code → '$DELEG' · $TOK tokens"; else err "$code FALLO → resp: $(echo $RESP | head -c 100)"; fi
done

# ─── 7. Embajador E2E ────────────────────────────────────────────
log ""
log "── 7. Embajador E2E"
EMAIL="smoke-amb-$(date +%s%N)@dogsmindsmoke.net"
RESP=$(curl -s -X POST https://dogs-mind-backend-production.up.railway.app/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"smoketest1234\",\"invite_code\":\"DogsmindAmb25@\"}")
ROLE=$(echo "$RESP" | grep -oE '"role":"[^"]*"' | cut -d'"' -f4)
TOK=$(echo "$RESP" | grep -oE '"tokens":[0-9.]+' | cut -d':' -f2)
if [[ "$ROLE" == "ambassador" && "$TOK" == "8.0" ]]; then ok "Embajador → role=$ROLE · $TOK tokens"; else err "Embajador FALLO → role=$ROLE tokens=$TOK"; fi

# ─── 8. Netlify sites ────────────────────────────────────────────
log ""
log "── 8. Netlify sites status"
for url in https://thedogsmind.net https://beta.thedogsmind.net https://dogsmind-hub.netlify.app; do
  C=$(curl -s -o /dev/null -w "%{http_code}" "$url")
  if [[ "$C" == "200" ]]; then ok "$url → 200"; else err "$url → $C"; fi
done

# ─── 9. Screenshots Playwright (opcional, requiere npx) ──────────
log ""
log "── 9. Screenshots visual baseline (Playwright)"
if command -v npx >/dev/null 2>&1; then
  SCREEN_DIR="$SMOKE_DIR/screenshots/$TS"
  mkdir -p "$SCREEN_DIR"
  cat > /tmp/screenshot.mjs <<'JSEOF'
import { chromium } from 'playwright';
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
const page = await ctx.newPage();
const targets = [
  { name: 'home', url: 'https://thedogsmind.net/' },
  { name: 'invite-delegation', url: 'https://thedogsmind.net/?invite=BOCALAN-CL' },
  { name: 'invite-pro', url: 'https://thedogsmind.net/?invite=Pantano26' },
];
for (const t of targets) {
  await page.goto(t.url, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: process.env.SCREEN_DIR + '/' + t.name + '.png', fullPage: false });
  console.log('captured: ' + t.name);
}
await browser.close();
JSEOF
  if SCREEN_DIR="$SCREEN_DIR" timeout 90 npx -y playwright@latest >/dev/null 2>&1 && SCREEN_DIR="$SCREEN_DIR" timeout 90 node /tmp/screenshot.mjs 2>&1 | tee -a "$LOG_FILE"; then
    SHOTS=$(ls "$SCREEN_DIR"/*.png 2>/dev/null | wc -l | tr -d ' ')
    ok "Capturadas $SHOTS pantallas en $SCREEN_DIR"

    # Compare vs baseline (si existe)
    BASE="$BASELINE_DIR/screenshots"
    if [ -d "$BASE" ]; then
      for shot in "$SCREEN_DIR"/*.png; do
        name=$(basename "$shot")
        if [ -f "$BASE/$name" ]; then
          SIZE_NEW=$(stat -f%z "$shot" 2>/dev/null)
          SIZE_OLD=$(stat -f%z "$BASE/$name" 2>/dev/null)
          DIFF_PCT=$(echo "scale=1; ($SIZE_NEW - $SIZE_OLD) / $SIZE_OLD * 100" | bc -l 2>/dev/null | sed 's/-//')
          if (( $(echo "$DIFF_PCT > 10" | bc -l 2>/dev/null) )); then
            warn "$name cambio visual >${DIFF_PCT}% vs baseline (revisar)"
          fi
        fi
      done
    else
      # Primera vez → establecer baseline
      mkdir -p "$BASE"
      cp "$SCREEN_DIR"/*.png "$BASE/" 2>/dev/null
      ok "Baseline visual establecido (primera ejecución)"
    fi
  else
    warn "Playwright no disponible o timeout — skip screenshots"
  fi
else
  warn "npx no instalado — skip screenshots"
fi

# ─── RESUMEN ─────────────────────────────────────────────────────
log ""
log "════════════════════════════════════════════════════════════════"
log "  RESUMEN — $ERRORS errores, $WARNINGS warnings"
log "════════════════════════════════════════════════════════════════"

# Notification macOS
if (( ERRORS > 0 )); then
  osascript -e "display notification \"$ERRORS errores detectados. Ver $LOG_FILE\" with title \"Dogs Mind Smoke FAIL\" sound name \"Basso\"" 2>/dev/null
  exit 1
elif (( WARNINGS > 0 )); then
  osascript -e "display notification \"$WARNINGS warnings. Ver $LOG_FILE\" with title \"Dogs Mind Smoke OK with warnings\"" 2>/dev/null
  exit 0
else
  osascript -e "display notification \"Todo OK — SW $SW_PROD\" with title \"Dogs Mind Smoke OK\"" 2>/dev/null
  exit 0
fi
