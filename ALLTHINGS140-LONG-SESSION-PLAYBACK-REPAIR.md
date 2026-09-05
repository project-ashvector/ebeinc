# ALLTHINGS140 Long-Session Playback Repair

Date: 2026-09-02  
Status: DEPLOYED — awaiting extended listener confirmation

## Root cause

The production broadcast did not stop. Oracle VM runtime evidence showed the station server, encoder, and Icecast source continuously active since 2026-09-01 22:17 UTC, with `NRestarts=0`, no encoder errors, no source disconnect, zero watchdog recoveries, and healthy raw audio.

The failure was in listener recovery:

- The persistent website shell forwarded `waiting`, `stalled`, `error`, and `ended` media events but did not recover its owning `<audio>` element.
- Route-level reconnect code could not force a fresh request through the shell proxy when the URL was unchanged.
- Android recovered buffering and explicit player errors, but not clean Icecast EOF (`STATE_ENDED`) or an unexpected idle/non-playing state.

A brief edge/network interruption could therefore leave a long-running listener stopped while the shared station continued normally.

## Repair

### Website

- Centralized recovery in the persistent shell that owns the only radio audio element.
- Bounded reconnect delays: 1, 2, 5, 10, 20, then 30 seconds.
- Twelve-second stall guard for `waiting`/`stalled`.
- Immediate handling for `error`, `ended`, network restoration, and unexpected pause.
- Ten-second continuity watchdog catches silent stuck states.
- Every recovery forces a new HTTP request with a cache-busting query value.
- Recovery is disabled immediately after an intentional user pause.
- Added observable recovery attempt/pending state.
- Updated shell asset reference to `3.0.1` and service-worker cache to `allthings140-radio-v72`.

Production Cloudflare Pages deployment: `68a789d0.ebeinc-uqt.pages.dev`  
Rollback deployment: `449cd628.ebeinc-uqt.pages.dev`

### Android

- Added recovery for `Player.STATE_ENDED` and unexpected `Player.STATE_IDLE`.
- Added a ten-second continuous-stream watchdog.
- Watchdog acts only while `playWhenReady` is true, so an intentional pause remains authoritative.
- Existing fresh-request recovery, buffering guard, wake lock, and account-aware alert guard remain intact.

Version: `1.3.7`  
Version code: `23`  
APK SHA-256: `a37d8489aea34f3ac34c32e3893c2024cccfb9f9a7041ce893561f9d6863dc43`  
AAB SHA-256: `859041712be89118739d05cf43ef0980ebf80c0d2e82f6daff5c67b1325196bd`  
Upload certificate SHA-256: `f03122b6357609ca0dc9d0613ecfaf0552964b75ca837b551727e47d9c39901d`

Google Play: Internal testing ACTIVE, latest release `23 (1.3.7)`  
Tester list: `at140radio`, 8 users, preserved  
Production track: NOT PUBLISHED

Physical phone install: PASS — Samsung SM-S926U (`R5CXB09PTTT`), upgraded in place from 1.3.6/22 to 1.3.7/23 with data preserved. Real account restored as `allthings140@gmail.com`, canonical account type ADMIN, alert ads disabled. Media3 session verified active in `PLAYING` state after installation.

## Verification

- Focused stream-continuity contract: PASS
- Web JavaScript syntax: PASS
- Android debug unit suite: PASS
- Signed release APK/AAB build: PASS
- Physical production-package install over prior version: PASS
- Real ADMIN session/entitlement restoration: PASS
- Physical-phone live Media3 playback: PASS
- Preview runtime EOF fault injection: PASS
  - desired playback remained true
  - recovery became pending
  - audio generation advanced from 1 to 2
  - a fresh `at140_reconnect` request played
- Intentional-pause fault injection: PASS
  - desired playback remained false
  - no recovery was scheduled
- Production `persistent-shell.js` hash matches source: PASS
- Production HTML references shell `3.0.1`: PASS
- Production service worker contains cache `v72`: PASS
- Station server: ACTIVE, `NRestarts=0`
- AutoDJ: ACTIVE
- Icecast source: ACTIVE
- Raw stream: ACTIVE
- Catalog: HEALTHY, 2,462 playback-ready tracks, 0 missing approved audio
- Account-sensitive global alert injection remains disabled.

No station server, Icecast, encoder, catalog, or VM restart was performed for this client-continuity repair.

## Known unrelated test state

Two pre-existing broad frontend assertions remain red and were not changed: Room/Green byte identity and a SoundCloud foundation-only string expectation. Neither touches the listener audio recovery path. All focused continuity and account-entitlement tests pass.

## Payments

Stripe subscription work: NOT STARTED  
Google Play subscription work: NOT STARTED  
$5 PLUS work: NOT STARTED
