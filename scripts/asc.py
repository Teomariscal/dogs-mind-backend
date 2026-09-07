"""Cliente mínimo de la App Store Connect API.

Vivía en un directorio temporal y se borró solo (7-sep-2026), dejando
`siguiente-build-ios.py` sin poder preguntar el número de build a Apple. Por eso
está aquí: todo lo del proyecto vive en el repositorio.

El SECRETO no está aquí. La clave privada `.p8` sigue fuera del repositorio, en
`~/.appstoreconnect/private_keys/`. Lo que hay abajo son identificadores, no
credenciales: sin el fichero .p8 no sirven de nada.

Uso:
    from asc import call
    call("/v1/apps/6777848632/appStoreVersions?limit=3")
    call("/v1/appStoreVersions", "POST", {...})
"""
import json
import os
import time
import urllib.error
import urllib.request

import jwt  # pyjwt

KEY_ID = "26Q473G2V8"
ISSUER = "4af2188f-87d6-459c-88ea-793b67971435"
RUTA_CLAVE = os.path.expanduser(
    f"~/.appstoreconnect/private_keys/AuthKey_{KEY_ID}.p8")


def _token() -> str:
    with open(RUTA_CLAVE) as f:
        clave = f.read()
    return jwt.encode(
        {"iss": ISSUER, "exp": int(time.time()) + 1200, "aud": "appstoreconnect-v1"},
        clave, algorithm="ES256", headers={"kid": KEY_ID, "typ": "JWT"},
    )


def call(path: str, method: str = "GET", body=None):
    url = path if path.startswith("http") else "https://api.appstoreconnect.apple.com" + path
    datos = json.dumps(body).encode() if body else None
    pet = urllib.request.Request(
        url, data=datos, method=method,
        headers={"Authorization": "Bearer " + _token(),
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pet) as resp:
            crudo = resp.read()
            return json.loads(crudo) if crudo else {"ok": resp.status}
    except urllib.error.HTTPError as e:
        return {"ERROR": e.code, "body": e.read().decode()[:900]}
