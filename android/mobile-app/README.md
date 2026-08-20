# ALLTHINGS140 Radio — Android Phone App v1.3.0 RC

Native Android release candidate for the ALLTHINGS140 Radio listener app.

## Identity
- Application ID: `online.ebeinc.allthings140radio`
- Version: `1.3.0` (`versionCode 15`)
- minSdk: 23
- compileSdk / targetSdk: 36
- Java: 17
- Media3: 1.11.0

## Architecture
- `MainActivity` — native listener UI.
- `RadioService` — single Media3 `MediaLibraryService` playback authority for app/system/Android Auto.
- `StationStatusClient` — public station metadata/listener-status fallback.
- `SettingsActivity` — version/build/update/privacy links.
- `PrivacyActivity` — in-app native privacy notice.
- `RadioSiteActivity` — restricted HTTPS first-party WebView used for the station Visuals section only.
- `RadioVisualizerView` — lightweight branded animation; does not record/sample microphone/device audio.

The main app intentionally does **not** embed the whole station website. General Website opens externally. Green Room is intentionally excluded from the initial Google Play UI until its UGC moderation/reporting/blocking/Terms requirements are complete.

## Development build
Prerequisites: Android SDK Platform 36/build tools, JDK 17+, and working Gradle network/cache.

```bash
./gradlew clean testDebugUnitTest lintDebug assembleDebug
```

The debug variant uses application-id suffix `.debug` and version-name suffix `-debug` so it can be kept separate from production.

## Release bundle
Production signing is intentionally not stored in this repository/package. Configure secure Gradle properties or environment variables for the real upload keystore:
- `RELEASE_STORE_FILE` / `KEYSTORE_FILE`
- `RELEASE_STORE_PASSWORD` / `KEYSTORE_PASSWORD`
- `RELEASE_KEY_ALIAS` / `KEY_ALIAS`
- `RELEASE_KEY_PASSWORD` / `KEY_PASSWORD`

Then run:

```bash
./gradlew bundleRelease
```

Do not add debug-signing fallback to the release build.

## Release status
Static source validation passed, but v1.3.0 was not Gradle-built in the ChatGPT sandbox because that environment lacks the Android SDK and cannot download Gradle. Before Play submission, run `FINAL_LAPTOP_VALIDATION_PROMPT.txt` and complete `GOOGLE_PLAY_RELEASE_CHECKLIST.md`.

## Important handoff files
- `APP_AUDIT_REPORT.txt` — current v1.3.0 audit.
- `GOOGLE_PLAY_RELEASE_CHECKLIST.md` — release gate.
- `DEVICE_TEST_PLAN.md` — physical/emulator QA.
- `PRIVACY_POLICY_WEB_DRAFT.md` — draft to verify and host publicly.
- `PLAY_STORE_LISTING_DRAFT.md` — store copy.
- `STORE_ASSET_CHECKLIST.md` — required visuals.
- `FINAL_LAPTOP_VALIDATION_PROMPT.txt` — autonomous final build/device-validation prompt.
- `APP_AUDIT_REPORT_ANTIGRAVITY_ORIGINAL.txt` — preserved pre-v1.3 report.
