# EBE Talkie Talkie v0.1.2 — Install Fix

Android family push-to-talk app for Cody, Mom, and Girlfriend.

## Install repair

v0.1.0 and v0.1.1 were GitHub Actions debug builds. Separate CI runners generated separate temporary Android debug signing keys, so Android could reject a later APK with **App not installed** because the package name matched but the signing certificate did not.

v0.1.2 fixes that by:

- using the proper release application ID `online.ebeinc.talkietalkie` instead of the old `.debug` test package;
- signing family builds with one stable family-test certificate so future builds from this family branch can update in place;
- building a signed release APK and verifying its certificate and package identity in CI;
- embedding the new detailed purple EBE Talkie Talkie walkie-talkie icon.

Because the old test app used `online.ebeinc.talkietalkie.debug`, v0.1.2 can install beside it. After v0.1.2 is verified working, the old debug app can be removed.

## v0.1.1 functionality retained

- WebRTC push-to-talk and encrypted signaling.
- Background listening foreground service and ongoing Android notification.
- Saved call sign and room code with automatic rejoin.
- Explicit disconnect and room-code sharing.
- Clear current-speaker UI, transmission meter, beeps and vibration feedback.
- Network reconnect handling.

## Security note

The family-test signing key is intended only for this sideloaded family build. Before a public or Play Store release, migrate to a private production signing key and EBE-controlled signaling/TURN infrastructure.
