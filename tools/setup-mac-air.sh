#!/bin/bash
#
# Dogs Mind — Setup MacBook Air (uno-shot)
#
# Instala todo lo necesario para trabajar Dogs Mind en este Mac y conecta
# las memorias de Claude Code con las del iMac de mesa vía iCloud Drive.
#
# Uso: descarga el repo y ejecuta este script directamente.
#   curl -fsSL https://raw.githubusercontent.com/Teomariscal/dogs-mind-backend/main/tools/setup-mac-air.sh | bash
#

set -e  # abortar si cualquier comando falla
trap 'echo ""; echo "[FATAL] Error en línea $LINENO. Abortando."; exit 1' ERR

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Dogs Mind — Setup MacBook Air (Claude Code + repo + iCloud)"
echo "════════════════════════════════════════════════════════════════"
echo ""

# ── PASO 1: Homebrew ────────────────────────────────────────────────
echo "── [1/7] Verificando Homebrew..."
if ! command -v brew >/dev/null 2>&1; then
  echo ""
  echo "    [ATENCION] Homebrew no esta instalado."
  echo "    No puedo instalarlo desde aquí porque este script se ejecuta via pipe"
  echo "    (curl | bash) sin acceso a TTY, y Homebrew necesita pedirte el password."
  echo ""
  echo "    Ejecuta MANUALMENTE en tu Terminal:"
  echo ""
  echo "      /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
  echo ""
  echo "    Cuando termine la instalacion (incluyendo los 2 comandos del PATH que"
  echo "    Homebrew te diga al final), VUELVE A EJECUTAR este script."
  echo ""
  exit 1
else
  echo "    Homebrew ya instalado."
fi

# ── PASO 2: Git, Python, Node ───────────────────────────────────────
echo "── [2/7] Instalando git, python3, node..."
for pkg in git python3 node; do
  if ! command -v $pkg >/dev/null 2>&1; then
    echo "    Instalando $pkg..."
    brew install $pkg
  else
    echo "    $pkg ya instalado."
  fi
done

# ── PASO 3: Netlify CLI ─────────────────────────────────────────────
echo "── [3/7] Instalando Netlify CLI..."
if ! command -v netlify >/dev/null 2>&1; then
  npm install -g netlify-cli
else
  echo "    Netlify CLI ya instalado."
fi

# ── PASO 4: Claude Code ─────────────────────────────────────────────
echo "── [4/7] Instalando Claude Code..."
if ! command -v claude >/dev/null 2>&1; then
  curl -fsSL https://claude.ai/install.sh | bash
  # Añadir a PATH si no está
  if ! command -v claude >/dev/null 2>&1; then
    export PATH="$HOME/.local/bin:$PATH"
  fi
else
  echo "    Claude Code ya instalado."
fi

# ── PASO 5: Clonar repo Dogs Mind ───────────────────────────────────
echo "── [5/7] Clonando repo Dogs Mind..."
mkdir -p ~/Downloads
cd ~/Downloads
if [ -d "dogs-mind-backend" ]; then
  echo "    Repo ya existe. Actualizando con git pull..."
  cd dogs-mind-backend && git pull origin main && cd ..
else
  git clone https://github.com/Teomariscal/dogs-mind-backend.git
fi

# ── PASO 6: Verificar carpeta iCloud + symlinks de memoria ─────────
echo "── [6/7] Configurando memorias de Claude Code vía iCloud..."
ICLOUD_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/dogs-mind-claude"
CLAUDE_PROJ_DIR="$HOME/.claude/projects/-Users-teodoromariscal-Downloads"

if [ ! -d "$ICLOUD_DIR/memory" ]; then
  echo ""
  echo "    [ATENCION] La carpeta iCloud aún no se ha sincronizado:"
  echo "      $ICLOUD_DIR/memory"
  echo ""
  echo "    Abre Finder → iCloud Drive → busca 'dogs-mind-claude'."
  echo "    Si NO aparece, espera 5-10 min y vuelve a ejecutar este script."
  echo "    Si SÍ aparece pero con icono de descarga (nube↓), pulsa sobre"
  echo "    los archivos para forzar descarga, espera y reintenta."
  echo ""
  exit 1
fi

mkdir -p "$CLAUDE_PROJ_DIR"

# Eliminar memory/ existente si hay (vacío o no)
if [ -e "$CLAUDE_PROJ_DIR/memory" ] || [ -L "$CLAUDE_PROJ_DIR/memory" ]; then
  rm -rf "$CLAUDE_PROJ_DIR/memory"
fi
ln -s "$ICLOUD_DIR/memory" "$CLAUDE_PROJ_DIR/memory"
echo "    Symlink memoria creado:"
echo "      $CLAUDE_PROJ_DIR/memory → iCloud"

# CLAUDE.md si existe
if [ -f "$ICLOUD_DIR/CLAUDE.md" ]; then
  if [ -e "$CLAUDE_PROJ_DIR/CLAUDE.md" ] || [ -L "$CLAUDE_PROJ_DIR/CLAUDE.md" ]; then
    rm -f "$CLAUDE_PROJ_DIR/CLAUDE.md"
  fi
  ln -s "$ICLOUD_DIR/CLAUDE.md" "$CLAUDE_PROJ_DIR/CLAUDE.md"
  echo "    Symlink CLAUDE.md creado."
fi

# Sesiones JSONL recientes: COPIA (NO symlink) — cada Mac mantiene sus
# propias sesiones después de la copia inicial. Symlink causaría conflicts
# si ambos Macs escribieran a la vez en la misma sesión activa.
if [ -d "$ICLOUD_DIR/sessions" ]; then
  echo "    Copiando sesiones recientes desde iCloud al Air..."
  local_count=0
  for f in "$ICLOUD_DIR/sessions"/*.jsonl; do
    if [ -f "$f" ]; then
      base=$(basename "$f")
      # Solo copiar si NO existe ya en el Air (no sobreescribir sesiones del Air)
      if [ ! -f "$CLAUDE_PROJ_DIR/$base" ]; then
        cp "$f" "$CLAUDE_PROJ_DIR/$base"
        local_count=$((local_count + 1))
      fi
    fi
  done
  echo "    $local_count sesiones nuevas copiadas (las que ya existían se preservaron)."
fi

# ── PASO 7: Resumen ─────────────────────────────────────────────────
echo "── [7/7] Setup completado."
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  TODO LISTO. Próximos pasos:"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "  1. Login en Claude Code:"
echo "       claude login"
echo ""
echo "  2. Login en Netlify (si vas a hacer deploys):"
echo "       netlify login"
echo ""
echo "  3. Abrir Claude Code en el proyecto:"
echo "       cd ~/Downloads/dogs-mind-backend && claude"
echo ""
echo "  4. Yo (Claude) tendré acceso a todas las memorias del iMac"
echo "     gracias a los symlinks iCloud. Cuando edite memorias, se"
echo "     sincronizan automáticamente al iMac también."
echo ""
echo "  ⚠ REGLA DE ORO: NUNCA tengas Claude Code abierto en los DOS"
echo "    Macs a la vez. Cierra en uno antes de abrir en el otro."
echo ""
echo "════════════════════════════════════════════════════════════════"
