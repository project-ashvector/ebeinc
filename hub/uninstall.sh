#!/usr/bin/env bash
# ==============================================================================
# ALLTHINGS140 Hub — Uninstaller
# ==============================================================================
set -euo pipefail

HOME_DIR="${HOME:-/home/ebmarah}"
APP_ID="allthings140-hub"

echo "Uninstalling ALLTHINGS140 Hub from $HOME_DIR..."

rm -f "$HOME_DIR/.local/bin/$APP_ID"
rm -f "$HOME_DIR/.local/share/applications/${APP_ID}.desktop"
rm -rf "$HOME_DIR/.local/share/allthings140-hub"

for size in 16 24 32 48 64 128 256 512; do
    rm -f "$HOME_DIR/.local/share/icons/hicolor/${size}x${size}/apps/${APP_ID}.png"
done

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$HOME_DIR/.local/share/icons/hicolor" 2>/dev/null || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME_DIR/.local/share/applications" 2>/dev/null || true
fi

echo "ALLTHINGS140 Hub has been removed."
