#!/usr/bin/env bash
# ==============================================================================
# ALLTHINGS140 Hub — Debian (.deb) Package Builder
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

VERSION="1.2.1"
PACKAGE_NAME="allthings140-hub"
ARCH="amd64"
BUILD_DIR="$PROJECT_ROOT/build-deb/${PACKAGE_NAME}_${VERSION}_${ARCH}"

echo "Building Debian package for $PACKAGE_NAME v$VERSION..."

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR/usr/local/bin"
mkdir -p "$BUILD_DIR/usr/share/applications"
mkdir -p "$BUILD_DIR/opt/allthings140-hub"

# Control file
cat << EOF > "$BUILD_DIR/DEBIAN/control"
Package: $PACKAGE_NAME
Version: $VERSION
Section: sound
Priority: optional
Architecture: $ARCH
Maintainer: ALLTHINGS140 Radio <allthings140radio@pm.me>
Depends: python3 (>= 3.10), python3-requests
Recommends: python3-venv, python3-pip, tailscale
Description: Central Operations & Safety Console for ALLTHINGS140 Radio
 Management and observability interface for the ALLTHINGS140 ecosystem.
 Runtime-critical 24/7 radio services remain independent of this desktop app.
EOF

# Copy source tree to /opt/allthings140-hub
cp -r "$SCRIPT_DIR" "$BUILD_DIR/opt/allthings140-hub/hub"

# Multi-resolution icons
for size in 16 24 32 48 64 128 256 512; do
    icon_dir="$BUILD_DIR/usr/share/icons/hicolor/${size}x${size}/apps"
    mkdir -p "$icon_dir"
    src_icon="$SCRIPT_DIR/assets/icons/allthings140-hub-${size}x${size}.png"
    if [[ -f "$src_icon" ]]; then
        cp "$src_icon" "$icon_dir/${PACKAGE_NAME}.png"
    fi
done

# Launcher binary
cat << 'EOF' > "$BUILD_DIR/usr/local/bin/allthings140-hub"
#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="/opt/allthings140-hub"
VENV_PY="$HOME/.local/share/allthings140-hub/.venv/bin/python3"
PY=""
if [[ -x "$VENV_PY" ]] && "$VENV_PY" -c 'import PySide6, requests' >/dev/null 2>&1; then
    PY="$VENV_PY"
elif python3 -c 'import PySide6, requests' >/dev/null 2>&1; then
    PY="python3"
else
    MSG=$'ALLTHINGS140 Hub needs PySide6.\n\nRun this once in Terminal:\n\n  allthings140-hub-bootstrap\n\nThen open ALLTHINGS140 Hub again.'
    if command -v zenity >/dev/null 2>&1; then zenity --error --title="ALLTHINGS140 Hub Dependencies" --text="$MSG" || true; fi
    printf '%s\n' "$MSG" >&2
    exit 70
fi
if [[ $# -eq 0 || "$1" == "--gui" || "$1" == "-g" ]]; then
    exec "$PY" /opt/allthings140-hub/hub/main.py
else
    exec "$PY" /opt/allthings140-hub/hub/cli.py "$@"
fi
EOF
chmod +x "$BUILD_DIR/usr/local/bin/allthings140-hub"

cat << 'EOF' > "$BUILD_DIR/usr/local/bin/allthings140-hub-bootstrap"
#!/usr/bin/env bash
set -euo pipefail
VENV="$HOME/.local/share/allthings140-hub/.venv"
echo "Creating ALLTHINGS140 Hub private Python environment at: $VENV"
python3 -m venv "$VENV"
"$VENV/bin/python3" -m pip install --upgrade pip
"$VENV/bin/python3" -m pip install PySide6 requests
"$VENV/bin/python3" -c 'import PySide6, requests; print("Hub Python dependencies verified.")'
EOF
chmod +x "$BUILD_DIR/usr/local/bin/allthings140-hub-bootstrap"

# Desktop file
cat << EOF > "$BUILD_DIR/usr/share/applications/${PACKAGE_NAME}.desktop"
[Desktop Entry]
Type=Application
Name=ALLTHINGS140 Hub
GenericName=Radio Ecosystem Operations Center
Comment=Central control and show-control operations center for ALLTHINGS140 Radio
Exec=/usr/local/bin/$PACKAGE_NAME %F
Icon=$PACKAGE_NAME
Terminal=false
Categories=AudioVideo;Audio;Development;Utility;
StartupWMClass=$PACKAGE_NAME
StartupNotify=true
X-GNOME-UsesNotifications=true
EOF

# Build package
dpkg-deb --build "$BUILD_DIR" "$PROJECT_ROOT/dist/${PACKAGE_NAME}_${VERSION}_${ARCH}.deb"
echo "Debian package created: dist/${PACKAGE_NAME}_${VERSION}_${ARCH}.deb"
