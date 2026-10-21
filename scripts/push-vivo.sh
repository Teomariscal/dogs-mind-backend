#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  ¿LAS NOTIFICACIONES PUSH SALEN DE VERDAD?
#
#  Founder, 21-oct-2026: *"es alucinante que fallemos en esto que es la clave
#  del proyecto"* y *"ponte un sistema que te obligue a enviarlos"*.
#
#  Esto es ese sistema. No comprueba que el CODIGO de push exista —existe desde
#  el 10-oct y no ha enviado una sola notificacion—. Comprueba los CUATRO
#  eslabones de la cadena real, y basta que falle uno para que no llegue nada:
#
#    1. La app pide permiso y REGISTRA el token    -> @capacitor/push-notifications
#    2. Los tokens llegan al servidor              -> filas en push_devices
#    3. El servidor sabe hablar con Apple/Google   -> FCM_PROJECT_ID + credenciales
#    4. Alguien ejecuta la pasada cada hora        -> disparador + filas en push_logs
#
#  Se llama solo desde `listo-para-enviar.sh`: mientras esto este rojo, no sale
#  un build prometiendo avisos que no llegan.
#
#  Uso:  scripts/push-vivo.sh            (informe; devuelve 1 si la cadena esta rota)
#        scripts/push-vivo.sh --silencio (solo el codigo de salida)
# ─────────────────────────────────────────────────────────────────────────────
set -uo pipefail
cd "$(dirname "$0")/.."

SILENCIO=0
[ "${1:-}" = "--silencio" ] && SILENCIO=1
di() { [ "$SILENCIO" = "1" ] || printf "%b\n" "$1"; }

SERVICIO=575945b9-be54-4712-ae52-1bc26e88327b

di "\n\033[1m── ¿SALEN LAS PUSH? ──\033[0m"

python3 - "$SERVICIO" <<'PY'
import json, os, re, subprocess, sys

servicio = sys.argv[1]
silencio = os.environ.get("PUSH_VIVO_SILENCIO") == "1"
def di(s=""):
    if not silencio: print(s)

roto = []

# ── 1. ¿La app registra el token? ───────────────────────────────────────────
try:
    pkg = json.load(open("mobile/package.json"))
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
except Exception:
    deps = {}
tiene_plugin = any("push" in k for k in deps)

try:
    html = open("frontend/index.html", encoding="utf-8").read()
except Exception:
    html = ""
registra = "/push/devices" in html

if tiene_plugin and registra:
    di("   ✓ 1. la app registra el token de push")
else:
    falta = []
    if not tiene_plugin: falta.append("@capacitor/push-notifications no esta instalado")
    if not registra:     falta.append("el frontend no llama a /push/devices")
    di("   ✗ 1. LA APP NO REGISTRA NINGUN TOKEN -> " + "; ".join(falta))
    roto.append("la app no registra tokens")

# ── 2, 3 y 4 necesitan produccion ───────────────────────────────────────────
try:
    r = subprocess.run(["npx", "-y", "@railway/cli", "variables",
                        "--service", servicio, "--json"],
                       capture_output=True, text=True, timeout=240)
    V = json.loads(r.stdout)
except Exception as e:
    # FALLA CERRADO. No poder comprobarlo NO es haberlo comprobado: si saliera 0
    # aqui, un Railway caido o un token caducado dejarian pasar un build que
    # promete avisos que no llegan. Que es exactamente como llegamos hasta hoy.
    di(f"   \u2717 NO HE PODIDO COMPROBARLO ({type(e).__name__}). No afirmo que funcione.")
    sys.exit(1)

# ── 3. Credenciales ─────────────────────────────────────────────────────────
tiene_fcm = bool(V.get("FCM_PROJECT_ID")) and bool(V.get("FCM_CREDENTIALS_JSON"))
if tiene_fcm:
    di("   ✓ 3. el servidor tiene credenciales de FCM")
else:
    di("   ✗ 3. NO HAY CREDENCIALES FCM en Railway (FCM_PROJECT_ID / FCM_CREDENTIALS_JSON)")
    roto.append("faltan las credenciales FCM")

# ── 2 y 4. Dispositivos y envios ────────────────────────────────────────────
try:
    import psycopg2
    url = re.sub(r"@postgres\.railway\.internal:\d+",
                 "@roundhouse.proxy.rlwy.net:31136", V["DATABASE_URL"])
    con = psycopg2.connect(url); cur = con.cursor()

    cur.execute("select to_regclass('push_devices')")
    hay_tabla = cur.fetchone()[0] is not None
    n_disp = 0
    if hay_tabla:
        cur.execute("select count(*) from push_devices where active is true")
        n_disp = cur.fetchone()[0]
    if n_disp > 0:
        di(f"   ✓ 2. {n_disp} dispositivos registrados")
    else:
        di("   ✗ 2. CERO DISPOSITIVOS REGISTRADOS: no hay a quien enviar")
        roto.append("cero dispositivos")

    cur.execute("select to_regclass('push_logs')")
    if cur.fetchone()[0] is None:
        di("   ✗ 4. la tabla push_logs NO EXISTE: no se ha enviado nunca nada")
        roto.append("nunca se ha enviado una push")
    else:
        cur.execute("select count(*) from push_logs where sent_at > now() - interval '48 hours'")
        rec = cur.fetchone()[0]
        cur.execute("select count(*) from push_logs")
        tot = cur.fetchone()[0]
        if rec > 0:
            di(f"   ✓ 4. {rec} push enviadas en las ultimas 48 h ({tot} en total)")
        else:
            di(f"   ✗ 4. NINGUNA PUSH EN 48 h (total historico: {tot}): el disparador no corre")
            roto.append("el disparador no corre")
except Exception as e:
    di(f"   \u2717 NO HE PODIDO MIRAR LA BASE ({type(e).__name__}). Falla cerrado: no afirmo nada.")
    sys.exit(1)

di()
if roto:
    di("   \033[1mLA CADENA ESTA ROTA.\033[0m No llega ni una notificacion a nadie.")
    for x in roto:
        di(f"     · {x}")
    di("\n   Mientras esto siga asi, la app NO puede prometer avisos: ni el de")
    di("   reactivacion a los 3 dias, ni el de 'se te acabo la invitacion'.")
    sys.exit(1)

di("   \033[1mLa cadena entera funciona.\033[0m")
sys.exit(0)
PY
