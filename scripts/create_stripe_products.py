"""
One-off — crea los 2 productos Stripe del flujo Profesional.

Uso (con la STRIPE_SECRET_KEY de Railway en línea):

    cd /Users/teodoromariscal/dogs-mind-backend
    STRIPE_SECRET_KEY=sk_live_XXXXXX .venv/bin/python scripts/create_stripe_products.py

Imprime los 2 price_id que hay que pasar a Claude / añadir al env del backend.
Idempotente por nombre: si ya existen productos con el mismo name, los reusa
en lugar de duplicarlos.
"""

from __future__ import annotations
import getpass
import os
import sys

try:
    import stripe
except ImportError:
    print("ERROR: 'stripe' no está instalado en el venv.", file=sys.stderr)
    print("Ejecuta primero: .venv/bin/pip install stripe==11.4.1", file=sys.stderr)
    sys.exit(2)

# Preferimos variable de entorno si está; si no, pedimos la clave por stdin con
# getpass (entrada oculta — no se ve al pegar, no queda en historial, no se
# expone en el comando). Esto evita el riesgo de exponer la sk_live_… al
# escribir un comando largo en Terminal.
key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
if not key:
    print("Pega tu STRIPE_SECRET_KEY (sk_live_… o sk_test_…) y pulsa Enter.")
    print("La entrada es invisible por seguridad — no verás lo que pegas.\n")
    try:
        key = getpass.getpass("STRIPE_SECRET_KEY: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.", file=sys.stderr)
        sys.exit(1)
    if not key:
        print("ERROR: clave vacía.", file=sys.stderr)
        sys.exit(1)
if not (key.startswith("sk_live_") or key.startswith("sk_test_")):
    print(
        f"ERROR: la clave no parece válida (debería empezar por sk_live_ o sk_test_).",
        file=sys.stderr,
    )
    sys.exit(1)

stripe.api_key = key
mode = "LIVE" if key.startswith("sk_live") else "TEST" if key.startswith("sk_test") else "UNKNOWN"
print(f"\n=== Stripe — modo {mode} ===\n")


def find_or_create_product(*, name: str, description: str, kind_metadata: str):
    """Busca un producto activo por nombre exacto; si no existe lo crea."""
    existing = stripe.Product.search(query=f"name:'{name}' AND active:'true'")
    if existing.data:
        prod = existing.data[0]
        print(f"  Producto ya existía: {prod.id}  (reusando)")
        return prod
    prod = stripe.Product.create(
        name=name,
        description=description,
        metadata={"tdm_kind": kind_metadata},
    )
    print(f"  Producto creado: {prod.id}")
    return prod


def find_or_create_price(*, product_id: str, amount_cents: int, currency: str = "eur"):
    """Busca un price activo del product con ese amount; si no existe lo crea."""
    prices = stripe.Price.list(product=product_id, active=True, limit=10)
    for p in prices.data:
        if p.unit_amount == amount_cents and p.currency == currency:
            print(f"  Price ya existía: {p.id}  (reusando)")
            return p
    p = stripe.Price.create(
        product=product_id,
        unit_amount=amount_cents,
        currency=currency,
    )
    print(f"  Price creado: {p.id}")
    return p


# ── Producto 1: Membresía Profesional anual ─────────────────────────────────
print("→ Producto 1 — Membresía Profesional anual (20,00 €)")
prod1 = find_or_create_product(
    name="Dogs Mind Professional · 1 year",
    description=(
        "Membresía anual Profesional. Incluye 10 tokens de cortesía y "
        "acceso a las funcionalidades Profesional durante 12 meses."
    ),
    kind_metadata="pro_membership_annual",
)
price1 = find_or_create_price(product_id=prod1.id, amount_cents=2000)

# ── Producto 2: Pack Profesional 60 tokens promo ────────────────────────────
print("\n→ Producto 2 — Pack Profesional 60 tokens, promo (37,80 €)")
prod2 = find_or_create_product(
    name="Pack Profesional 60 tokens (promo)",
    description=(
        "60 tokens con 10 % de descuento, disponible solo al activar la "
        "Membresía Profesional (precio normal pack 60: 42 €)."
    ),
    kind_metadata="pro_token_bundle_60",
)
price2 = find_or_create_price(product_id=prod2.id, amount_cents=3780)

# ── Resumen final ───────────────────────────────────────────────────────────
print("\n" + "=" * 64)
print("RESULTADO — Pasa estos 2 PRICE_ID a Claude:")
print("=" * 64)
print(f"\nSTRIPE_PRICE_PRO_MEMBERSHIP    = {price1.id}")
print(f"STRIPE_PRICE_PRO_TOKEN_BUNDLE = {price2.id}")
print()
