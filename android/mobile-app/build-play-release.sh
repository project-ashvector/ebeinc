#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
KEY_ROOT="$ROOT/../google play/ALLTHINGS140-RADIO-v1.3.1-PLAY-BUNDLE-BUILD"
KEYINFO="$KEY_ROOT/PLAY_UPLOAD_KEY_INFO.txt"
KEYSTORE="$KEY_ROOT/play-upload-keystore.jks"

if [[ ! -f "$KEYINFO" || ! -f "$KEYSTORE" ]]; then
  echo "Existing ALLTHINGS140 Play upload material is unavailable." >&2
  exit 1
fi

getv() { sed -n "s/^$1: //p" "$KEYINFO" | head -n1; }
export KEYSTORE_FILE="$KEYSTORE"
export KEY_ALIAS="$(getv 'Key alias')"
export KEYSTORE_PASSWORD="$(getv 'Keystore password')"
export KEY_PASSWORD="$(getv 'Key password')"

cd "$ROOT"
./gradlew --no-daemon :app:assembleDeviceQa :app:assembleDeviceQaAndroidTest \
  :app:assembleRelease :app:bundleRelease --console=plain
"$ROOT/verify-android-auto-release.sh"

echo "Signed device-QA APK, release APK, and release AAB built with the existing upload key."
echo "Android Auto discovery contract verified in release artifacts."
