"""Devuelve el numero de build libre preguntandoselo a Apple.

Contar en local repite numero si alguien subio desde otro sitio, y Apple lo
rechaza con ITMS-90062 sin gastar revision pero perdiendo el viaje
(paso el 1-sep-2026).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from asc import call
    b = call("/v1/builds?filter[app]=6777848632&limit=10&sort=-uploadedDate")
    n = [int(d["attributes"]["version"]) for d in b.get("data", [])
         if str(d["attributes"].get("version", "")).isdigit()]
    print(max(n) + 1 if n else "")
except Exception:
    print("")
