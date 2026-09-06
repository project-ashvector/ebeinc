#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
APK="${1:-$ROOT/app/build/outputs/apk/release/app-release.apk}"
AAB="${2:-$ROOT/app/build/outputs/bundle/release/app-release.aab}"
APK_ANALYZER="${ANDROID_HOME:-$HOME/android-sdk}/cmdline-tools/latest/bin/apkanalyzer"

if [[ ! -x "$APK_ANALYZER" ]]; then
  APK_ANALYZER="$(command -v apkanalyzer || true)"
fi
if [[ ! -x "$APK_ANALYZER" ]]; then
  echo "apkanalyzer is required to verify the release manifest." >&2
  exit 1
fi
for artifact in "$APK" "$AAB"; do
  if [[ ! -f "$artifact" ]]; then
    echo "Release artifact is missing: $artifact" >&2
    exit 1
  fi
done

manifest="$($APK_ANALYZER manifest print "$APK")"
require_manifest() {
  if [[ "$manifest" != *"$1"* ]]; then
    echo "Release APK Android Auto contract missing: $1" >&2
    exit 1
  fi
}

require_manifest 'package="online.ebeinc.allthings140radio"'
require_manifest 'android:versionCode="26"'
require_manifest 'android:versionName="1.3.10"'
require_manifest 'android:name="com.google.android.gms.car.application"'
if [[ "$manifest" != *'android:resource="@ref/'* && "$manifest" != *'android:resource="@xml/automotive_app_desc"'* ]]; then
  echo "Release APK Android Auto metadata does not reference an automotive descriptor." >&2
  exit 1
fi
require_manifest 'android:name="online.ebeinc.allthings140radio.RadioService"'
require_manifest 'android:exported="true"'
require_manifest 'android:foregroundServiceType="0x2"'
require_manifest 'android:name="androidx.media3.session.MediaLibraryService"'
require_manifest 'android:name="android.media.browse.MediaBrowserService"'

if ! unzip -l "$AAB" | grep 'base/res/xml/automotive_app_desc.xml' >/dev/null; then
  echo "Release AAB is missing base/res/xml/automotive_app_desc.xml." >&2
  exit 1
fi
if ! unzip -p "$AAB" base/res/xml/automotive_app_desc.xml | strings | grep 'media' >/dev/null; then
  echo "Release AAB automotive descriptor does not declare media." >&2
  exit 1
fi
if ! unzip -l "$APK" | grep 'classes.dex' >/dev/null; then
  echo "Release APK is missing executable classes." >&2
  exit 1
fi

echo "Android Auto release contract verified for:"
echo "  APK: $APK"
echo "  AAB: $AAB"
