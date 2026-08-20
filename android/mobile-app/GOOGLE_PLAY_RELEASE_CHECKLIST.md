# ALLTHINGS140 Radio v1.3.0 — Google Play Release Checklist

Status legend: **DONE IN SOURCE**, **VERIFY**, **HARD BLOCKER**, **PLAY CONSOLE**, **STORE ASSET**.

## Code and build

- **DONE IN SOURCE** — `compileSdk 36`, `targetSdk 36`, `versionName 1.3.0`, `versionCode 15`.
- **DONE IN SOURCE** — Gradle 8.13 + Android Gradle Plugin 8.13.2 + Java 17 project configuration.
- **DONE IN SOURCE** — Native main radio UI; core app is not just the station website.
- **DONE IN SOURCE** — Media3 foreground media playback service and media-library browsing surface.
- **DONE IN SOURCE** — Responsive insets, portrait-lock removal, landscape/tablet dimension qualifiers.
- **DONE IN SOURCE** — Hardened in-app Visuals WebView; external Website opens device browser.
- **DONE IN SOURCE** — Green Room is not included in initial Play UI.
- **DONE IN SOURCE** — Dangerous/data permissions not present in reviewed manifest.
- **DONE IN SOURCE** — No bundled native `.so`/C/C++ code found in the reviewed source.
- **VERIFY / HARD BLOCKER** — Install Android SDK Platform 36 + matching Build Tools on the development laptop if not already present.
- **VERIFY / HARD BLOCKER** — Run `./gradlew clean testDebugUnitTest lintDebug assembleDebug`.
- **VERIFY / HARD BLOCKER** — Run `./gradlew bundleRelease` with the real release signing configuration.
- **VERIFY** — Inspect release AAB/APK with Android Studio APK Analyzer / bundletool and confirm no unexpected permissions, debug flags, secrets, or huge assets.
- **VERIFY** — Test 16 KB page-size compatibility on an Android 15/16 16-KB environment. This source is Java/Kotlin-resource only with no native library found, which is favorable, but verify the built artifact.

## Signing and package identity

- **HARD BLOCKER** — Choose/confirm the permanent production package ID: `online.ebeinc.allthings140radio`. Once published, changing package identity means a different Play app.
- **HARD BLOCKER** — Configure a production upload key/keystore outside source control.
- **PLAY CONSOLE** — Enroll/use Play App Signing for normal Play distribution.
- **VERIFY** — Keep debug package (`.debug`) separate from production.
- **VERIFY** — Back up the upload key securely; do not place it in this ZIP or a public repo.

## Privacy and Data Safety

- **DONE IN SOURCE** — In-app privacy screen exists.
- **HARD BLOCKER** — Publish a complete privacy policy on a stable public non-PDF URL. The included `PRIVACY_POLICY_WEB_DRAFT.md` is a draft, not the final URL.
- **HARD BLOCKER** — Replace every `[VERIFY BEFORE HOSTING]` statement in the privacy draft with facts verified from your web/server/provider setup.
- **PLAY CONSOLE** — Enter the hosted privacy-policy URL.
- **PLAY CONSOLE** — Complete Data Safety based on actual native app, server logs, embedded Visuals behavior, and service providers. Do not answer only from manifest permissions.
- **PLAY CONSOLE** — Declare ads accurately. This reviewed native source contains no ads SDK.
- **PLAY CONSOLE** — Complete app access declaration (native listener app does not require login in reviewed source).

## Foreground media / Android Auto

- **DONE IN SOURCE** — `FOREGROUND_SERVICE` and `FOREGROUND_SERVICE_MEDIA_PLAYBACK` permissions.
- **DONE IN SOURCE** — `android:foregroundServiceType="mediaPlayback"`.
- **DONE IN SOURCE** — Media-browser service discovery action and automotive media descriptor.
- **PLAY CONSOLE** — Complete foreground-service declaration in App Content for media playback, including any required explanation/demo details.
- **VERIFY** — Test lock-screen notification/media controls.
- **VERIFY** — Test Bluetooth/headset play/pause and unplug/noisy behavior.
- **VERIFY** — Test Android Auto Desktop Head Unit or a real compatible vehicle/head unit.
- **VERIFY** — Confirm now-playing title/artist updates correctly on Android Auto and lock screen, not only in MainActivity.

## User-generated content / Green Room

- **DONE FOR INITIAL RELEASE** — Green Room is excluded from the native release UI.
- **DO NOT RE-ENABLE** until all current Play UGC requirements are implemented and verified, including user acceptance of Terms/community rules, objectionable-content rules, in-app reporting of content/users, blocking where applicable, and actual moderation/enforcement.
- If the app later becomes a social app, re-check current child-safety standards and target-audience obligations before shipping that update.

## Device QA

- **HARD BLOCKER** — Test final debug/release-candidate build on the Galaxy S24 Plus.
- **VERIFY** — Small phone / narrow width.
- **VERIFY** — Android 16 phone with gesture navigation.
- **VERIFY** — Landscape.
- **VERIFY** — Large font (at least 1.3x and 2.0x) and increased display size.
- **VERIFY** — Tablet/foldable or emulator >=600dp width.
- **VERIFY** — Status-bar cutout and 3-button navigation configurations.
- **VERIFY** — Wi-Fi → cellular / cellular → Wi-Fi handoff, airplane-mode interruption, reconnect.
- **VERIFY** — Screen off 10+ minutes while playing.
- **VERIFY** — Incoming audio interruption/audio focus and recovery.
- **VERIFY** — Kill/reopen app while media service is active/inactive.
- **VERIFY** — No crash/ANR/error spam in Logcat during a 30–60 minute playback soak.

## Store listing

- **STORE ASSET — DONE** — 512x512 Play icon included at `play-store-assets/icon_512.png`.
- **STORE ASSET — HARD BLOCKER** — Create 1024x500 feature graphic.
- **STORE ASSET — HARD BLOCKER** — Capture at least two real phone screenshots from the final build. Prefer 4–8 covering Home/Live, playback, Settings, Visuals.
- **STORE ASSET** — Do not use mock screenshots that show features the actual build does not have.
- **PLAY CONSOLE** — Category: Music & Audio is the natural initial category.
- **PLAY CONSOLE** — Complete content rating truthfully for the actual station/site content.
- **PLAY CONSOLE** — Set target audience truthfully. Do not select children unless the product and external content are actually designed/compliant for them.
- **PLAY CONSOLE** — Complete contact details/support email/website.
- **PLAY CONSOLE** — Review country/region availability and pricing (app can be free even if the external site accepts support/donations).

## Submission gate

Do **not** upload to production until all HARD BLOCKER items above are closed. Internal testing can start as soon as a signed/testable AAB is available.
