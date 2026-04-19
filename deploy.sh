#!/bin/bash
# deploy.sh — actualiza Railway + Netlify con un solo comando
set -e

NETLIFY_TOKEN="nfp_r3D2zq9KARSmVAbpEtPJ8nNpfJXfpFC133bf"
NETLIFY_SITE="8e7733f8-12bd-4c23-8cf4-7594b1bab5ff"
FRONTEND_DIR="$(dirname "$0")/frontend"

echo "📦 Sincronizando frontend..."
# Asegura que index.html esté actualizado desde el HTML principal
cp "$FRONTEND_DIR/teo-mariscal-v3.html" "$FRONTEND_DIR/index.html"

echo "🚀 Subiendo a GitHub (Railway auto-despliega)..."
git -C "$(dirname "$0")" add -A
git -C "$(dirname "$0")" commit -m "deploy: update frontend" 2>/dev/null || echo "  (sin cambios en git)"
git -C "$(dirname "$0")" push origin main

echo "🌐 Desplegando en Netlify..."
NETLIFY_AUTH_TOKEN="$NETLIFY_TOKEN" netlify deploy --prod \
  --dir="$FRONTEND_DIR" \
  --site="$NETLIFY_SITE" \
  --message "auto-deploy $(date '+%Y-%m-%d %H:%M')" 2>&1 | tail -5

echo ""
echo "✅ ¡Listo! Ambos servicios actualizados:"
echo "   Railway → https://dogs-mind-backend-production.up.railway.app"
echo "   Netlify → https://thedogsmindbeta.netlify.app"
