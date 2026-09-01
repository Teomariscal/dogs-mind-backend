#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  UN CAMBIO EN LA RAIZ -> LAS TRES RAMAS
#
#  La raiz es frontend/ (+ app/ si toca backend). Las ramas son App Store,
#  Google Play y la web. Este script las recorre SIEMPRE en el mismo orden y
#  no deja pasar a la siguiente si la anterior no se verifica.
#
#  Nace de un dia (1-sep-2026) en el que se publico en una rama y no en las
#  otras varias veces, y en el que se desplego sin comprobar que arrancaba.
#
#  Uso:  scripts/publicar.sh "mensaje de la version"
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")/.."
MENSAJE="${1:-actualizacion}"
NETLIFY_SITE=152389f9-0282-46b5-a929-db9f9b142912
API=https://dogs-mind-backend-production.up.railway.app

paso() { printf "\n\033[1m── %s\033[0m\n" "$1"; }
ok()   { printf "   ✓ %s\n" "$1"; }
malo() { printf "   ✗ %s\n" "$1"; exit 1; }

# ── 0. RAIZ: nada sale sin pasar esto ───────────────────────────────────────
paso "RAIZ — comprobaciones antes de tocar ninguna rama"

python3 - <<'PY' || malo "JavaScript roto en index.html"
import re, pathlib, subprocess, tempfile, os, sys
s=pathlib.Path('frontend/index.html').read_text(encoding='utf-8')
b=re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', s, re.S)
malos=0
for x in b:
    if not x.strip(): continue
    f=tempfile.NamedTemporaryFile('w',suffix='.js',delete=False); f.write(x); f.close()
    r=subprocess.run(['node','--check',f.name],capture_output=True,text=True)
    if r.returncode: malos+=1; print("     ", r.stderr.strip()[:160])
    os.unlink(f.name)
sys.exit(1 if malos else 0)
PY
ok "los 8 bloques de JavaScript compilan"

python3 - <<'PY' || malo "una funcion interna tiene decorador de ruta (esto tira el backend al arrancar)"
import ast, pathlib, sys
malos=[]
for f in pathlib.Path('app/api/routes').glob('*.py'):
    t=ast.parse(f.read_text(encoding='utf-8'))
    for n in ast.walk(t):
        if not isinstance(n,(ast.FunctionDef, ast.AsyncFunctionDef)): continue
        if not any('router.' in ast.unparse(d) for d in n.decorator_list): continue
        if n.name.startswith('_'): malos.append("%s:%d %s" % (f.name,n.lineno,n.name))
        args, defs = n.args.args, n.args.defaults
        for a in args[:len(args)-len(defs)]:
            an = ast.unparse(a.annotation) if a.annotation else ''
            if an in ('User','Session','Dog','Case'):
                malos.append("%s:%d %s(%s:%s) sin Depends" % (f.name,n.lineno,n.name,a.arg,an))
for m in malos: print("     ", m)
sys.exit(1 if malos else 0)
PY
ok "ninguna ruta mal formada"

python3 - <<'PY' || malo "quedan textos que dicen 'token' al usuario"
import re, pathlib, sys
s=pathlib.Path('frontend/index.html').read_text(encoding='utf-8')
zonas=[(m.start(),m.end()) for m in re.finditer(r'<(script|style)\b[\s\S]*?</\1>', s, re.I)]
prot=lambda i: any(a<=i<b for a,b in zonas)
sucio=[m.group(1).strip() for m in re.finditer(r'>([^<>]*\btokens?\b[^<>]*)<', s, re.I) if not prot(m.start())]
for m in re.finditer(r'^\s{6,12}[a-z0-9_]+:\s*(["\'])((?:(?!\1)[^\\]|\\.)*)\1', s, re.M):
    if re.search(r'token', m.group(2), re.I): sucio.append(m.group(2)[:60])
for x in sucio[:5]: print("     ", x)
sys.exit(1 if sucio else 0)
PY
ok "al usuario solo se le habla de creditos"

SW=$(grep -o "dogs-mind-v[0-9]*" frontend/service-worker.js | head -1)
ok "service worker: $SW"

# ── 1. RAMA BACKEND (si hay cambios en app/) ────────────────────────────────
if ! git diff --quiet app/ 2>/dev/null || ! git diff --cached --quiet app/ 2>/dev/null; then
  paso "RAMA 0 — backend"
  git add -A app/ && git commit -q -m "$MENSAJE" || true
  git push -q origin main
  ok "desplegado a Railway"
  printf "   esperando a que responda"
  for i in $(seq 1 60); do
    C=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "$API/health" || true)
    [ "$C" = "200" ] && { printf "\n"; ok "backend VIVO (HTTP 200)"; break; }
    printf "."; sleep 5
    [ "$i" = "60" ] && { printf "\n"; malo "el backend NO arranca — revertir con: git revert HEAD && git push"; }
  done
fi

# ── 2. RAMA WEB ─────────────────────────────────────────────────────────────
paso "RAMA 1 — web"
( cd frontend && netlify deploy --prod --site=$NETLIFY_SITE --dir=. --message="$MENSAJE" >/dev/null )
printf "   esperando a la CDN"
for i in $(seq 1 40); do
  V=$(curl -s https://thedogsmind.net/service-worker.js | grep -o "dogs-mind-v[0-9]*" | head -1 || true)
  [ "$V" = "$SW" ] && { printf "\n"; ok "web sirviendo $V"; break; }
  printf "."; sleep 4
  [ "$i" = "40" ] && { printf "\n"; malo "la web no sirve $SW todavia"; }
done

# ── 3 y 4. RAMAS DE LAS TIENDAS ─────────────────────────────────────────────
paso "RAMAS 2 y 3 — App Store y Google Play"
echo "   Estas dos NO se automatizan aqui a proposito: cada envio necesita el OK"
echo "   del founder y una revision manual del build. Lo que si se garantiza es"
echo "   que salen del MISMO frontend que acaba de ir a la web."
echo
echo "   Siguiente paso:  scripts/compilar-apps.sh"
