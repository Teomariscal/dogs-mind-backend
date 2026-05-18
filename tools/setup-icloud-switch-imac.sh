#!/bin/bash
#
# Dogs Mind — Switch del iMac a usar iCloud para memorias Claude Code
#
# Este script DEBE ejecutarse DESPUÉS de cerrar Claude Code en el iMac.
# Convierte la carpeta local memory/ en un symlink a la copia en iCloud,
# de modo que las ediciones del iMac y del MacBook Air sincronicen.
#
# Solo hay que ejecutarlo UNA VEZ en el iMac.
#

set -e
trap 'echo ""; echo "[FATAL] Error en línea $LINENO. Abortando."; exit 1' ERR

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Dogs Mind — Switch iMac a memorias iCloud (UNA SOLA VEZ)"
echo "════════════════════════════════════════════════════════════════"
echo ""

CLAUDE_PROJ_DIR="$HOME/.claude/projects/-Users-teodoromariscal-Downloads"
ICLOUD_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/dogs-mind-claude"
BACKUP_DIR="$HOME/Desktop/claude-imac-backup-$(date +%Y%m%d-%H%M%S)"

# ── PASO 1: Verificar Claude Code está cerrado ──────────────────────
echo "── [1/5] Verificando que Claude Code esté cerrado..."
if pgrep -x "claude" >/dev/null; then
  echo ""
  echo "    [ERROR] Claude Code está corriendo. Ciérralo primero (Cmd+Q)"
  echo "    y vuelve a ejecutar este script."
  echo ""
  exit 1
fi
echo "    OK, Claude Code cerrado."

# ── PASO 2: Verificar que iCloud tiene las memorias ─────────────────
echo "── [2/5] Verificando iCloud..."
if [ ! -d "$ICLOUD_DIR/memory" ]; then
  echo ""
  echo "    [ERROR] No encuentro las memorias en iCloud:"
  echo "      $ICLOUD_DIR/memory"
  echo ""
  echo "    Esto debería haberse copiado automáticamente por una"
  echo "    sesión previa de Claude. Contacta a Claude para regenerar."
  echo ""
  exit 1
fi
ICLOUD_FILES=$(ls "$ICLOUD_DIR/memory" | wc -l | tr -d ' ')
echo "    OK, $ICLOUD_FILES archivos en iCloud."

# ── PASO 3: Backup de las memorias locales actuales ─────────────────
echo "── [3/5] Backup de memorias locales actuales..."
mkdir -p "$BACKUP_DIR"
if [ -d "$CLAUDE_PROJ_DIR/memory" ] && [ ! -L "$CLAUDE_PROJ_DIR/memory" ]; then
  cp -R "$CLAUDE_PROJ_DIR/memory" "$BACKUP_DIR/memory"
  echo "    Backup creado en: $BACKUP_DIR/memory"
fi
if [ -f "$CLAUDE_PROJ_DIR/CLAUDE.md" ] && [ ! -L "$CLAUDE_PROJ_DIR/CLAUDE.md" ]; then
  cp "$CLAUDE_PROJ_DIR/CLAUDE.md" "$BACKUP_DIR/CLAUDE.md"
fi

# ── PASO 4: Switch a symlinks ───────────────────────────────────────
echo "── [4/5] Switching a symlinks iCloud..."

# memory
if [ -L "$CLAUDE_PROJ_DIR/memory" ]; then
  echo "    memory/ ya era symlink. OK."
else
  rm -rf "$CLAUDE_PROJ_DIR/memory"
  ln -s "$ICLOUD_DIR/memory" "$CLAUDE_PROJ_DIR/memory"
  echo "    memory/ → symlink iCloud."
fi

# CLAUDE.md (si existe)
if [ -f "$ICLOUD_DIR/CLAUDE.md" ]; then
  if [ -L "$CLAUDE_PROJ_DIR/CLAUDE.md" ]; then
    echo "    CLAUDE.md ya era symlink. OK."
  else
    rm -f "$CLAUDE_PROJ_DIR/CLAUDE.md"
    ln -s "$ICLOUD_DIR/CLAUDE.md" "$CLAUDE_PROJ_DIR/CLAUDE.md"
    echo "    CLAUDE.md → symlink iCloud."
  fi
fi

# ── PASO 5: Verificar ───────────────────────────────────────────────
echo "── [5/5] Verificando..."
ls -la "$CLAUDE_PROJ_DIR/memory" "$CLAUDE_PROJ_DIR/CLAUDE.md" 2>/dev/null | head -5

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  SWITCH COMPLETADO. Próximos pasos:"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "  Memorias del iMac y MacBook Air ahora se sincronizan vía iCloud."
echo ""
echo "  Backup de tu estado anterior guardado en:"
echo "    $BACKUP_DIR"
echo "  Puedes eliminarlo después si todo va bien (en ~7 días)."
echo ""
echo "  Ya puedes volver a abrir Claude Code:"
echo "    cd ~/Downloads/dogs-mind-backend && claude"
echo ""
echo "  ⚠ REGLA DE ORO: NUNCA tengas Claude Code abierto en los DOS"
echo "    Macs a la vez. Cierra en uno antes de abrir en el otro."
echo ""
echo "════════════════════════════════════════════════════════════════"
