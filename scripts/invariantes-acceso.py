#!/usr/bin/env python3
"""
¿SE PUEDE USAR LA APP SIN PAGAR? — comprobado sobre TODOS los usuarios reales.

Founder, 21-oct-2026:

    "impidelo por codigo, al 100% de seguridad de que no puede una persona
     seguir funcionando. Primero sin codigo, sin tokens, tiene que ser algo
     imposible. Y sin suscripcion, pasado el tiempo, tambien."

Esto no prueba una funcion con casos inventados: coge a TODAS las personas que
hay en produccion, le pregunta al muro real que haria con cada una, y lo
compara con la regla. Una sola discrepancia y falla.

LA REGLA, en las palabras del founder:

  · Anterior al 1-sep-2026 .... gasta SU saldo hasta agotarlo, sin suscribirse.
                                Al agotarse: ni consulta ni compra creditos
                                sueltos — primero la suscripcion.
  · Posterior al 1-sep ........ suscripcion mensual, o una invitacion viva.
                                Sin eso, no entra.
  · Sin saldo ................. no consulta, y NO puede comprar creditos.
  · Equipo / admin / exento ... pasan siempre.

Se ejecuta desde `listo-para-enviar.sh`. Falla cerrado: si no puede medirlo,
no pasa.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime

SERVICIO = "575945b9-be54-4712-ae52-1bc26e88327b"
CORTE = datetime(2026, 9, 1)
PRECIO_ANALISIS = 3.0

# Motivos por los que alguien pasa SIN ser ni legado con saldo ni suscrito.
# Son exenciones legitimas y no se juzgan aqui.
EXENTOS = {"privileged", "exempt", "partner", "corporate", "paywall_off"}

# La prueba de 3 dias es una funcion que existe a proposito, no un agujero.
# La primera version de este script la contaba como violacion y saco 57
# "fallos" que eran 48 cuentas de humo estrenando su trial. Un comprobador que
# grita por lo que funciona bien se acaba ignorando, y entonces ya no comprueba
# nada.
TRIAL = "trial"

# Las cuentas de humo no son personas. Se quedan fuera del recuento para que
# el numero que se mira sea el de gente real. El dominio se lee dentro de
# main(), que es donde ya esta armado el sys.path.


def main() -> int:
    try:
        r = subprocess.run(["npx", "-y", "@railway/cli", "variables",
                            "--service", SERVICIO, "--json"],
                           capture_output=True, text=True, timeout=300)
        V = json.loads(r.stdout)
    except Exception as e:
        print(f"   ✗ no he podido leer Railway ({type(e).__name__}). "
              f"Falla cerrado: no afirmo que la app este cerrada.")
        return 1

    for k, v in V.items():
        os.environ[k] = str(v)
    os.environ["DATABASE_URL"] = re.sub(
        r"@postgres\.railway\.internal:\d+",
        "@roundhouse.proxy.rlwy.net:31136", V["DATABASE_URL"])
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from app.core.smoke import SMOKE_DOMAIN as _SMOKE
    from app.core import subscriptions as subs
    from app.database import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    try:
        usuarios = db.query(User).filter(User.deleted_at.is_(None)).all()
    except Exception:
        usuarios = db.query(User).all()

    ahora = datetime.utcnow()
    fallos: list[str] = []
    cuenta = {"legado": 0, "suscrito": 0, "invitado": 0, "fuera": 0, "exento": 0, "trial": 0}

    for u in usuarios:
        tk = float(getattr(u, "tokens", 0) or 0)
        legado = bool(u.created_at and u.created_at < CORTE)
        vence = getattr(u, "subscription_expires_at", None)
        viva = bool(vence and vence > ahora)

        estado = subs.access_state(u, amount=PRECIO_ANALISIS)
        packs = subs.puede_comprar_packs(u)
        pasa, motivo = estado["allowed"], estado["reason"]

        if (u.email or "").lower().endswith(_SMOKE):
            continue                      # cuenta de humo: no es una persona
        if motivo in EXENTOS or packs.get("motivo") in EXENTOS:
            cuenta["exento"] += 1
            continue
        if motivo == TRIAL:
            cuenta["trial"] += 1
            # En prueba SI puede consultar. Lo que no puede, ni en prueba, es
            # comprar creditos sueltos sin suscribirse.
            if packs.get("puede"):
                fallos.append(f"{u.email}: en prueba de 3 dias y PUEDE COMPRAR "
                              f"creditos sueltos ({packs.get('motivo')})")
            continue

        # ── 1. SIN SALDO NO SE CONSULTA, PASE LO QUE PASE ──────────────────
        if tk < PRECIO_ANALISIS and pasa:
            fallos.append(f"{u.email}: tiene {tk:.2f} tk (menos que un analisis) "
                          f"y el muro le DEJA PASAR ({motivo})")

        # ── 2. SIN SALDO TAMPOCO SE COMPRAN CREDITOS SUELTOS ───────────────
        #    "no pueden comprar tokens, tienen que primero pagar suscripcion"
        if tk <= 0 and not viva and packs.get("puede"):
            fallos.append(f"{u.email}: sin saldo y sin suscripcion viva, y "
                          f"PUEDE COMPRAR creditos sueltos ({packs.get('motivo')})")

        # ── 3. EL POSTERIOR AL CORTE NO ENTRA SIN SUSCRIPCION VIVA ─────────
        if not legado and not viva and pasa:
            fallos.append(f"{u.email}: alta {u.created_at:%Y-%m-%d} (posterior al "
                          f"corte), sin suscripcion viva, y PASA ({motivo})")

        # ── 4. AL LEGADO NO SE LE QUITA LO QUE SE LE PROMETIO ──────────────
        if legado and tk >= PRECIO_ANALISIS and not pasa:
            fallos.append(f"{u.email}: anterior al corte con {tk:.2f} tk y el muro "
                          f"lo BLOQUEA ({motivo}) — se le prometio lo contrario")

        if not pasa:
            cuenta["fuera"] += 1
        elif motivo == "legacy_balance":
            cuenta["legado"] += 1
        elif motivo == "subscription":
            cuenta["suscrito"] += 1 if not viva else 0
            cuenta["invitado"] += 1 if viva else 0
        else:
            cuenta["suscrito"] += 1

    db.close()

    print(f"   usuarios revisados: {len(usuarios)}")
    print(f"     dentro por saldo heredado ... {cuenta['legado']}")
    print(f"     dentro por suscripcion ...... {cuenta['suscrito'] + cuenta['invitado']}")
    print(f"     en prueba de 3 dias ......... {cuenta['trial']}")
    print(f"     exentos (equipo/admin) ...... {cuenta['exento']}")
    print(f"     fuera ....................... {cuenta['fuera']}")

    if fallos:
        print(f"\n   ✗ {len(fallos)} PERSONAS PUEDEN LO QUE NO DEBERIAN:")
        for f in fallos[:25]:
            print(f"     · {f}")
        if len(fallos) > 25:
            print(f"     ... y {len(fallos)-25} mas")
        return 1

    print("\n   ✓ Nadie puede usar la app sin tener derecho a usarla.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
