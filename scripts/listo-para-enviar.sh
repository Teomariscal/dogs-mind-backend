#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  PUERTA DE ENVÍO — nada sale sin pasar por aquí
#
#  Nace de un fallo concreto (4-sep-2026): verifiqué el binario 2728e243, luego
#  toqué código, recompilé a 2938b371 y le pedí al founder permiso para enviar
#  ESE, que no había probado. Sus palabras: "¿Para qué me preguntas si lo envías
#  cuando sabes que no debes?".
#
#  La regla "compruebo el binario final, no mi copia de trabajo" no se puede
#  dejar a mi memoria. Aquí se ata a la HUELLA del frontend que va dentro del
#  binario: si el md5 que voy a enviar no es exactamente el que registré como
#  verificado, esto se niega.
#
#  Uso:
#    scripts/listo-para-enviar.sh registrar "prueba 1" "prueba 2" …
#        Toma el md5 del IPA recién compilado y lo apunta con sus pruebas.
#    scripts/listo-para-enviar.sh comprobar
#        Devuelve 0 solo si el binario actual coincide con lo registrado.
#
#  Saltárselo exige que el founder lo pida explícitamente. No hay atajo.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")/.."
REGISTRO="scripts/verificado.json"
IPA="${IPA:-/tmp/DMexport/App.ipa}"
AAB="${AAB:-mobile/android/app/build/outputs/bundle/release/app-release.aab}"

huella_ios() {
  [ -f "$IPA" ] || { echo "SIN_IPA"; return; }
  local d; d=$(mktemp -d)
  ( cd "$d" && unzip -q "$IPA" ) 2>/dev/null || { echo "IPA_ROTA"; return; }
  md5 -q "$d"/Payload/App.app/public/index.html 2>/dev/null || echo "SIN_INDEX"
}
huella_android() {
  [ -f "$AAB" ] || { echo "SIN_AAB"; return; }
  unzip -p "$AAB" base/assets/public/index.html 2>/dev/null | md5 -q || echo "SIN_INDEX"
}

case "${1:-comprobar}" in

registrar)
  shift
  [ $# -gt 0 ] || { echo "✗ Hay que nombrar las pruebas que se han pasado."; exit 1; }
  HI=$(huella_ios); HA=$(huella_android)
  case "$HI" in SIN_*|IPA_ROTA) echo "✗ No hay IPA que registrar ($HI)"; exit 1;; esac
  [ "$HI" = "$HA" ] || { echo "✗ iOS y Android llevan frontends DISTINTOS:"; echo "   iOS=$HI  Android=$HA"; exit 1; }
  python3 - "$REGISTRO" "$HI" "$@" <<'PY'
import json, sys, datetime, pathlib
reg, huella = sys.argv[1], sys.argv[2]
pruebas = sys.argv[3:]
pathlib.Path(reg).write_text(json.dumps({
    "md5_frontend": huella,
    "verificado_el": datetime.datetime.now().isoformat(timespec="seconds"),
    "pruebas": pruebas,
}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("   ✓ registrado %s con %d pruebas" % (huella, len(pruebas)))
PY
  ;;

comprobar)
  HI=$(huella_ios); HA=$(huella_android)
  echo "── PUERTA DE ENVÍO ──"
  echo "   frontend dentro del IPA : $HI"
  echo "   frontend dentro del AAB : $HA"
  [ "$HI" = "$HA" ] || { echo "   ✗ LAS DOS TIENDAS LLEVAN COSAS DISTINTAS. No se envía."; exit 1; }
  [ -f "$REGISTRO" ] || { echo "   ✗ No hay ninguna verificación registrada. No se envía."; exit 1; }
  python3 - "$REGISTRO" "$HI" <<'PY'
import json, sys
reg, huella = sys.argv[1], sys.argv[2]
d = json.load(open(reg, encoding="utf-8"))
if d.get("md5_frontend") != huella:
    print("   ✗ Lo verificado NO es lo que se va a enviar.")
    print("     verificado: %s (%s)" % (d.get("md5_frontend"), d.get("verificado_el")))
    print("     a enviar  : %s" % huella)
    print("     -> hay que volver a verificar ESTE binario y registrarlo.")
    sys.exit(1)
print("   ✓ el binario a enviar es exactamente el verificado el %s" % d.get("verificado_el"))
for p in d.get("pruebas", []):
    print("     · %s" % p)
PY
  echo "   ✓ puerta abierta"
  ;;

*)
  echo "uso: $0 [registrar \"prueba\"… | comprobar]"; exit 1;;
esac
