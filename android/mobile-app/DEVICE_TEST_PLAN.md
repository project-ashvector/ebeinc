# v1.3.0 Device Test Plan

Record PASS/FAIL, device/OS, and Logcat evidence for failures.

## Install / first launch
- Fresh install opens native Home, not the website.
- No crash, blank screen, or content under status/navigation/cutout areas.
- Settings opens and Version shows 1.3.0 / Build 15 for release candidate (debug build will display the debug suffix in version name).

## Core playback
- Tap Play from stopped state; buffering → playing state is understandable.
- Audio is correct live station stream.
- Pause works and UI changes immediately.
- Resume works without duplicate audio.
- Retry works after forced network failure.
- Rapid play/pause taps do not create multiple players/services.

## Background / lifecycle
- Start playback, press Home; audio continues.
- Turn screen off for 10+ minutes; audio continues without runaway reconnect/log spam.
- Return to app; UI reflects real playback state.
- Open Settings and Visuals while playing; audio continues.
- Swipe app/task away while paused; service can stop.
- Test task removal while playing and document intended/actual behavior.
- Reboot/process-death behavior is acceptable (do not auto-play unexpectedly unless intentionally designed).

## Audio focus / routes
- Plug/unplug wired headset if available; unplug pauses or safely handles becoming-noisy.
- Pair Bluetooth; play/pause from headset controls.
- Take an incoming audio-focus interruption (another media app/call) and confirm sensible behavior.
- Change output device during playback.

## Network reliability
- Wi-Fi off/on while playing.
- Airplane mode on for ~15 sec, then off.
- Wi-Fi ↔ cellular handoff if available.
- Verify no endless frozen "LIVE" state when stream is actually disconnected.
- Run a 30–60 minute soak and review Logcat for repeated player errors, ANRs, or memory issues.

## Metadata / status
- Main screen shows real song title/artist when status endpoint supplies them.
- Long artist/title values do not clip critical controls.
- Listener count is real when available; unavailable state is clear when not.
- Lock screen/media notification shows correct station artwork.
- Verify whether actual changing song title/artist reaches lock screen/Bluetooth/Android Auto. If it stays generic, treat that as a polish issue to solve before advertising dynamic system metadata.

## Visuals WebView
- Visuals opens and renders correctly.
- Back gesture/button works on Android 16.
- Visuals page does not accidentally open Green Room, payment, or arbitrary site pages inside the embedded WebView.
- Third-party/out-of-section links open externally.
- Playback continues while Visuals is open.
- Rotate/resize: WebView remains usable.

## Settings / update
- Version/build/target values are correct.
- Check for Updates never crashes when offline.
- If update fields are absent, UI says feed is not configured rather than "up to date".
- If test feed reports a greater semantic version, Open Google Play becomes available.
- Leave Settings during a slow update check; no crash or dead-Activity update occurs.

## Responsive UI matrix
Test at normal and large fonts on:
- Galaxy S24 Plus / current personal phone.
- Narrow/small phone emulator or device.
- Android 16 gesture-nav phone.
- Landscape.
- >=600dp tablet/foldable profile.
- Font scale ~1.3x and 2.0x.
- Increased display size.

Watch for: clipping, overlap, hidden buttons, fixed-height text truncation, off-screen cards, bad visualizer proportions, excessive blank space, touch targets below 48dp, and content hidden by system bars.

## Android Auto
- Validate app appears as a media source in Android Auto DHU or real vehicle.
- Browse root → live station.
- Start/pause from car controls.
- App icon/attribution icon render acceptably.
- Verify metadata/artwork changes and reconnect behavior.

## Release artifact
- Inspect release AAB/APK for debuggable=false, expected package ID, expected permissions only, no secrets, no giant video, no unexpected native libraries.
- Run 16 KB page-size compatibility test on a supported emulator/device.
