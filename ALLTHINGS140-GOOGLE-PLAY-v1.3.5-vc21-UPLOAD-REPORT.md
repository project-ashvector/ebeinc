# ALLTHINGS140 Radio — Google Play v1.3.5 (21) Upload Report

Date: 2026-09-01 (America/Los_Angeles)

## Artifact verification

| Field | Result |
|---|---|
| AAB path | `android/mobile-app/app/build/outputs/bundle/release/app-release.aab` |
| AAB SHA-256 | `78f796b9e15e6dd8842ee953253c78b82162a2c81f0fcf5ca2613fe272b09f85` |
| Application ID | `online.ebeinc.allthings140radio` |
| Version name | 1.3.5 |
| Version code | 21 |
| Release build | PASS |
| Non-debuggable | PASS |
| AAB signature | PASS |
| Existing upload certificate | PASS |
| Account-aware alert repair included | YES |
| Production 900-second cadence | YES |
| Accelerated QA harness included | NO |
| New signing key created | NO |

The upload certificate SHA-256 in the artifact exactly matched the certificate registered by Google Play. Google Play App Signing is enabled; the matching local identity is the upload key, not Google's protected app-signing key.

## Google Play inspection

| Field | Result |
|---|---|
| Google Play app | AllThings140 Radio |
| Play package | `online.ebeinc.allthings140radio` |
| Highest previous versionCode | 20 |
| Previous active release | 1.3.4 / 20 — Internal testing |
| Other active workflow | 1.3.1 / 17 — Closed testing Alpha, in review |
| Production status | Inactive |
| Selected track | Internal testing |

VersionCode 21 was unused and higher than every bundle already uploaded (16–20). Internal testing was selected because it was the existing active delivery workflow; no testing track or tester group was created.

## Upload and rollout

| Check | Result |
|---|---|
| Upload | PASS |
| Google processing | PASS |
| VersionCode accepted | PASS |
| Upload signing accepted | PASS |
| Target SDK 36 accepted | PASS |
| Manifest/device validation | PASS |
| Release created | PASS |
| Testing rollout | PASS |
| Production published | NO |

New testing release: **1.3.5 / 21**  
Track: **Internal testing**  
Current release status: **Available to internal testers; full rollout; not reviewed**

Google Play reported 13,336 supported phones, 6,834 tablets, 7 TVs, 25 cars, 72 Chromebooks, and 1 Android XR device, with zero devices removed compared with the previous release.

## Tester access

| Field | Result |
|---|---|
| Existing tester list | `at140radio` |
| Existing users | 8 |
| Join method | Existing web enrollment preserved |
| Tester groups/lists changed | NO |
| Enrollment URL changed | NO |
| Countries/regions changed | NO |

## Play warnings

- Temporary app name remains `online.ebeinc.allthings140radio (unreviewed)` until initial app setup/review completes. Non-blocking and pre-existing.
- Release status is `Not reviewed`. Non-blocking for Internal Testing; the release is already available to internal testers.

## Play errors

None. The final review screen reported **Ready to release** and displayed no blocking errors.

## Final status

The exact repaired AAB was accepted and rolled out to the existing Internal Testing track. Version 1.3.5/versionCode 21 is available to the preserved tester group. Signing configuration, Play app identity, store configuration, and Production were not changed.
