"""Devuelve el numero de build libre preguntandoselo a Apple.

Contar en local repite numero si alguien subio desde otro sitio, y Apple lo
rechaza con ITMS-90062 sin gastar revision pero perdiendo el viaje
(paso el 1-sep-2026).
"""
import sys
sys.path.insert(0, "/private/tmp/claude-501/-Users-teomariscal/0e1cfb7e-2c92-4e57-a1c6-08e8bf5c9726/scratchpad")
try:
    from asc import call
    b = call("/v1/builds?filter[app]=6777848632&limit=10&sort=-uploadedDate")
    n = [int(d["attributes"]["version"]) for d in b.get("data", [])
         if str(d["attributes"].get("version", "")).isdigit()]
    print(max(n) + 1 if n else "")
except Exception:
    print("")
