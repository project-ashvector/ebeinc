# Android Auto Audit

## Manifest (verified)

- `com.google.android.gms.car.application` → `@xml/automotive_app_desc`
- `RadioService` exported with `MediaBrowserService` + `MediaLibraryService` intent filters
- Foreground service type `mediaPlayback`

## Regression history

- Branch `fix/android-auto-regression` @ `d5d8318` — trusted Play update for Android Auto
- Guards: `a42de3c` Media discovery release protection

## Verification

`android/mobile-app/verify-android-auto-release.sh` — **PASS** on release APK and AAB

## Device probe

`dumpsys media_session` — no active session during audit (app not playing).

**Status: PASS** (contract verified; in-vehicle test NOT TESTED)
