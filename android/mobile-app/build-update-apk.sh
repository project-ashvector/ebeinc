#!/usr/bin/env bash
set -euo pipefail

PACKAGE_ID="online.ebeinc.allthings140radio"
OUT_NAME="ALLTHINGS140-RADIO-v1.3.0-UPDATE.apk"
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

fail() { echo; echo "ERROR: $*" >&2; exit 1; }

[ -x ./gradlew ] || chmod +x ./gradlew

if [ -z "${ANDROID_HOME:-}" ] && [ -z "${ANDROID_SDK_ROOT:-}" ]; then
  for candidate in "$HOME/Android/Sdk" "$HOME/Android/sdk" "/opt/android-sdk" "/usr/lib/android-sdk"; do
    if [ -d "$candidate" ]; then
      export ANDROID_HOME="$candidate"
      break
    fi
  done
fi

SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
[ -n "$SDK" ] || fail "Android SDK not found. Open Android Studio once or set ANDROID_HOME."
export ANDROID_HOME="$SDK"
export PATH="$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"

echo "Building ALLTHINGS140 Radio v1.3.0 update APK..."
./gradlew --no-daemon clean assembleUpdate

APK="$(find app/build/outputs/apk/update -maxdepth 1 -type f -name '*.apk' | head -n1 || true)"
[ -n "$APK" ] && [ -f "$APK" ] || fail "Gradle finished but no update APK was found."
cp -f "$APK" "$ROOT/$OUT_NAME"

APKSIGNER=""
if command -v apksigner >/dev/null 2>&1; then
  APKSIGNER="$(command -v apksigner)"
elif [ -d "$ANDROID_HOME/build-tools" ]; then
  APKSIGNER="$(find "$ANDROID_HOME/build-tools" -type f -name apksigner | sort -V | tail -n1 || true)"
fi

if [ -n "$APKSIGNER" ] && [ -x "$APKSIGNER" ]; then
  echo
  echo "New APK signing certificate:"
  "$APKSIGNER" verify --print-certs "$ROOT/$OUT_NAME" | sed -n '1,8p'
else
  echo "WARNING: apksigner not found; APK signature comparison will be skipped."
fi

if command -v adb >/dev/null 2>&1 && adb get-state >/dev/null 2>&1; then
  if adb shell pm path "$PACKAGE_ID" >/dev/null 2>&1; then
    DEVICE_APK_PATH="$(adb shell pm path "$PACKAGE_ID" | head -n1 | tr -d '\r' | sed 's/^package://')"
    if [ -n "$DEVICE_APK_PATH" ]; then
      TMP="$(mktemp -d)"
      trap 'rm -rf "$TMP"' EXIT
      echo
      echo "Existing ALLTHINGS140 Radio detected on connected phone."
      adb pull "$DEVICE_APK_PATH" "$TMP/current.apk" >/dev/null

      if [ -n "$APKSIGNER" ] && [ -x "$APKSIGNER" ]; then
        NEW_CERT="$($APKSIGNER verify --print-certs "$ROOT/$OUT_NAME" 2>/dev/null | grep -m1 'Signer #1 certificate SHA-256 digest:' | sed 's/.*: //')"
        OLD_CERT="$($APKSIGNER verify --print-certs "$TMP/current.apk" 2>/dev/null | grep -m1 'Signer #1 certificate SHA-256 digest:' | sed 's/.*: //')"
        echo "Installed cert: $OLD_CERT"
        echo "New APK cert:  $NEW_CERT"
        if [ -z "$NEW_CERT" ] || [ -z "$OLD_CERT" ] || [ "$NEW_CERT" != "$OLD_CERT" ]; then
          fail "SIGNATURE MISMATCH. This APK will NOT update the installed app. Do not uninstall the current app just to force it. Find the original signing keystore instead."
        fi
        echo "Signature match: PASS"
      fi
    fi
  fi
fi

echo
echo "BUILD COMPLETE"
echo "APK: $ROOT/$OUT_NAME"
echo "Package: $PACKAGE_ID"
echo "Version: 1.3.0 (versionCode 15)"
echo
echo "To install/update manually after signature verification:"
echo "  adb install -r \"$ROOT/$OUT_NAME\""
