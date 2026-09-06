#!/usr/bin/env python3
"""
DETECTOR DE FUGAS — la vía cognitivista no puede tocar la conductual.

Regla del founder (4-sep-2026): "que salga algo conductual a lo cognitivista es
un resfriado; que salga algo COGNITIVISTA y contamine lo ABA conductual es el
Ebola". Este script es el termómetro del Ebola, y se pasa ANTES y DESPUES de
cada cambio de la vía cognitivista.

Hace tres comprobaciones ESTATICAS. La cuarta —la de verdad, con la app
corriendo en los tres idiomas y las dos vías— es `scripts/sin-fugas-vivo.js`.

  1. FRONTEND: el vocabulario cognitivista solo puede aparecer dentro de la
     region cognitivista marcada. Fuera de ella, ni una palabra.
  2. BACKEND: los prompts cognitivistas solo pueden importarse desde servicios
     que consultan la puerta de cuatro condiciones.
  3. PUERTA: la puerta sigue teniendo sus cuatro condiciones y sigue fallando
     CERRADA (cualquier duda -> conductual).

Uso:
    scripts/sin-fugas.py                 # sobre frontend/
    scripts/sin-fugas.py /ruta/index.html   # sobre el frontend de un binario
"""
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# ── Vocabulario ────────────────────────────────────────────────────────────
# DURO: no existe motivo legitimo para que aparezca fuera de lo cognitivista.
CZ_DURO = [
    "zooantropolog", "marchesini", "tassonomia cz", "appraisal", "arousal",
    "coping", "evocatore", "evocatori", "emendativa", "emendazione",
    "attivita surrogata", "attività surrogata", "rappresentazionale",
    "umwelt", "serendipity", "referenzialit", "detour cognitivo",
    "cooling-down", "prossemica", "iper-polarizzazione",
    "motivazioni neglette", "epimeletic", "et-epimeletic", "sillectic",
    "perlustrativ", "somestesic", "cinestesic",
]
# REVISAR: en italiano corriente tambien significan otra cosa, asi que avisan
# pero no tumban la compilacion. Comprobados el 6-sep-2026:
#   accreditamento -> "accreditamento internazionale" (acreditacion profesional)
#                     y "Accreditamento dei tuoi crediti" (abono de creditos).
CZ_REVISAR = ["accreditamento", "base sicura"]
# ABA: lo que NUNCA puede ver el veterinario que eligio cognitivista.
ABA_DURO = [
    "rinforzo", "rinforzare", "estinzione", "condizionamento operante",
    "stimolo discriminante", "stimolo discriminativo", "analisi funzionale",
    "comportamentismo", "token economy", "shaping", "chaining",
    "refuerzo", "extinción", "estímulo discriminativo",
]

# ── Marcas de region ───────────────────────────────────────────────────────
# Todo lo cognitivista del frontend va entre estas dos marcas. Fuera de ellas,
# el vocabulario de arriba es una FUGA.
ABRE = "== INICIO VIA COGNITIVISTA =="
CIERRA = "== FIN VIA COGNITIVISTA =="

# Servicios que SI pueden hablar cognitivista (porque consultan la puerta).
SERVICIOS_AUTORIZADOS = {
    "app/services/italian_cognitive.py",
    "app/services/clinical_ai.py",
    "app/services/intervention_ai.py",
    "app/services/cognitive_ingestion.py",   # solo ingesta de la RAG B
}

fallos: list[str] = []
avisos: list[str] = []


def rojo(t):  return f"\033[31m{t}\033[0m"
def verde(t): return f"\033[32m{t}\033[0m"
def gris(t):  return f"\033[90m{t}\033[0m"


def regiones_cognitivistas(texto: str) -> list[tuple[int, int]]:
    """Devuelve los tramos [inicio, fin) marcados como cognitivistas."""
    tramos = []
    pos = 0
    while True:
        a = texto.find(ABRE, pos)
        if a == -1:
            break
        c = texto.find(CIERRA, a)
        if c == -1:
            fallos.append(f"marca '{ABRE}' sin su '{CIERRA}' (offset {a})")
            break
        tramos.append((a, c + len(CIERRA)))
        pos = c + len(CIERRA)
    return tramos


def comprobar_frontend(ruta: Path):
    print(f"\n1. FRONTEND — {ruta}")
    texto = ruta.read_text(encoding="utf-8", errors="replace")
    bajo = texto.lower()
    tramos = regiones_cognitivistas(texto)
    print(gris(f"   regiones cognitivistas marcadas: {len(tramos)}"))

    def dentro(i):
        return any(a <= i < b for a, b in tramos)

    fugas = {}
    for palabra in CZ_DURO:
        for m in re.finditer(re.escape(palabra), bajo):
            if not dentro(m.start()):
                linea = texto.count("\n", 0, m.start()) + 1
                fugas.setdefault(palabra, []).append(linea)

    if fugas:
        for p, lineas in sorted(fugas.items()):
            fallos.append(f"FUGA en frontend: '{p}' fuera de la región cognitivista, líneas {lineas[:6]}")
            print(rojo(f"   ✗ '{p}' → líneas {lineas[:6]}"))
    else:
        print(verde("   ✓ cero vocabulario cognitivista fuera de su región"))

    for palabra in CZ_REVISAR:
        sitios = [texto.count("\n", 0, m.start()) + 1
                  for m in re.finditer(re.escape(palabra), bajo) if not dentro(m.start())]
        if sitios:
            avisos.append(f"'{palabra}' aparece fuera de la región en {sitios[:6]} "
                          f"— repasar que sigue siendo uso corriente y no el término CZ")
            print(gris(f"   · revisar '{palabra}' → líneas {sitios[:6]}"))


def comprobar_backend():
    print("\n2. BACKEND — quién puede importar los prompts cognitivistas")
    r = subprocess.run(
        ["grep", "-rln", "italian_cognitive", "app/"],
        cwd=RAIZ, capture_output=True, text=True)
    ficheros = [f for f in r.stdout.strip().split("\n") if f]
    intrusos = [f for f in ficheros
                if f not in SERVICIOS_AUTORIZADOS
                and not f.startswith("app/core/prompts/")]
    for f in ficheros:
        marca = verde("✓") if f not in intrusos else rojo("✗")
        print(f"   {marca} {f}")
    for f in intrusos:
        fallos.append(f"FUGA en backend: {f} usa el motor cognitivista sin estar autorizado")
    if not intrusos:
        print(verde("   ✓ solo servicios autorizados"))


def comprobar_puerta():
    print("\n3. PUERTA — cuatro condiciones y falla cerrada")
    p = RAIZ / "app/services/italian_cognitive.py"
    if not p.exists():
        fallos.append("no existe app/services/italian_cognitive.py")
        return
    t = p.read_text(encoding="utf-8")
    cuerpo = t[t.find("def cognitive_path_applies"):]
    cuerpo = cuerpo[:cuerpo.find("\ndef ", 10)] if "\ndef " in cuerpo[10:] else cuerpo
    exigencias = {
        "flag encendida": "enabled" in cuerpo or "IT_COGNITIVE" in cuerpo,
        "lang == it": '"it"' in cuerpo or "'it'" in cuerpo,
        "cuenta profesional": "professional" in cuerpo,
        "stance == cognitive": "cognitive" in cuerpo,
    }
    for nombre, ok in exigencias.items():
        print(f"   {verde('✓') if ok else rojo('✗')} {nombre}")
        if not ok:
            fallos.append(f"la puerta ya no exige: {nombre}")
    negativos = cuerpo.count("return False")
    print(f"   {verde('✓') if negativos >= 4 else rojo('✗')} falla cerrada "
          f"({negativos} salidas en False; hacen falta 4)")
    if negativos < 4:
        fallos.append(f"la puerta solo tiene {negativos} salidas en False")


def main():
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "frontend/index.html"
    print("═" * 66)
    print("  DETECTOR DE FUGAS COGNITIVISTAS")
    print("═" * 66)
    comprobar_frontend(destino)
    comprobar_backend()
    comprobar_puerta()
    print("\n" + "═" * 66)
    if fallos:
        print(rojo(f"  {len(fallos)} FALLO(S) — no se compila ni se envía:"))
        for f in fallos:
            print(rojo(f"   · {f}"))
        sys.exit(1)
    print(verde("  ✓ SIN FUGAS"))
    for a in avisos:
        print(gris(f"   · {a}"))


if __name__ == "__main__":
    main()
