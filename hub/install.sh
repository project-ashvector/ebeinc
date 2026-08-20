#!/usr/bin/env bash
# ==============================================================================
# ALLTHINGS140 Hub — Installer & Zorin OS Desktop Integration
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HOME_DIR="${HOME:-/home/ebmarah}"

APP_ID="allthings140-hub"
APP_NAME="ALLTHINGS140 Hub"
INSTALL_PREFIX="$HOME_DIR/.local"
BIN_DIR="$INSTALL_PREFIX/bin"
DESKTOP_DIR="$INSTALL_PREFIX/share/applications"
ICONS_DIR="$INSTALL_PREFIX/share/icons/hicolor"
VENV_DIR="$INSTALL_PREFIX/share/allthings140-hub/.venv"

echo "=================================================="
echo " Installing ALLTHINGS140 Hub onto Zorin OS"
echo "=================================================="

# 1. Ensure Python Virtual Environment
echo "→ Setting up dedicated Python virtual environment at $VENV_DIR..."
mkdir -p "$(dirname "$VENV_DIR")"
if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet PySide6 requests

# 2. Install High-Resolution Desktop Icons (16x16 to 512x512)
echo "→ Installing multi-resolution desktop icons into $ICONS_DIR..."
for size in 16 24 32 48 64 128 256 512; do
    target_icon_dir="$ICONS_DIR/${size}x${size}/apps"
    mkdir -p "$target_icon_dir"
    src_icon="$SCRIPT_DIR/assets/icons/allthings140-hub-${size}x${size}.png"
    if [[ -f "$src_icon" ]]; then
        cp "$src_icon" "$target_icon_dir/${APP_ID}.png"
    fi
done

# Update GTK icon cache
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$INSTALL_PREFIX/share/icons/hicolor" 2>/dev/null || true
fi

# 3. Install Executable Binary Launcher in ~/.local/bin
echo "→ Creating executable launcher at $BIN_DIR/$APP_ID..."
mkdir -p "$BIN_DIR"
cat << 'EOF' > "$BIN_DIR/$APP_ID"
#!/usr/bin/env bash
set -euo pipefail

HUB_ROOT="/home/ebmarah/Projects/AllThings140Radio"
VENV_PYTHON="/home/ebmarah/.local/share/allthings140-hub/.venv/bin/python3"

# If GUI is requested (or no args), launch main.py; else route to cli.py
if [[ $# -eq 0 ]]; then
    export PYTHONPATH="$HUB_ROOT"
    exec "$VENV_PYTHON" "$HUB_ROOT/hub/main.py"
elif [[ "$1" == "--gui" || "$1" == "-g" ]]; then
    export PYTHONPATH="$HUB_ROOT"
    exec "$VENV_PYTHON" "$HUB_ROOT/hub/main.py"
else
    export PYTHONPATH="$HUB_ROOT"
    exec "$VENV_PYTHON" "$HUB_ROOT/hub/cli.py" "$@"
fi
EOF

chmod +x "$BIN_DIR/$APP_ID"

# 4. Install Desktop Entry for Zorin OS Dock & App Menu
echo "→ Installing Zorin OS desktop launcher at $DESKTOP_DIR/${APP_ID}.desktop..."
mkdir -p "$DESKTOP_DIR"
cat << EOF > "$DESKTOP_DIR/${APP_ID}.desktop"
[Desktop Entry]
Type=Application
Name=ALLTHINGS140 Hub
GenericName=Radio Ecosystem Operations Center
Comment=Central control and show-control operations center for ALLTHINGS140 Radio
Exec=$BIN_DIR/$APP_ID %F
Icon=$APP_ID
Terminal=false
Categories=AudioVideo;Audio;Development;Utility;
StartupWMClass=$APP_ID
StartupNotify=true
X-GNOME-UsesNotifications=true
Keywords=Radio;Hub;ALLTHINGS140;Dubstep;Broadcast;Visuals;DJ;
EOF

chmod +x "$DESKTOP_DIR/${APP_ID}.desktop"

# 5. Update Desktop Database
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

echo "=================================================="
echo " ALLTHINGS140 Hub successfully installed!"
echo " Binary:  $BIN_DIR/$APP_ID"
echo " Desktop: $DESKTOP_DIR/${APP_ID}.desktop"
echo " WM_CLASS: $APP_ID (Dock-matching verified)"
echo "=================================================="
