# ALLTHINGS140 Radio — Account-Aware Alert Production Repair

Date: 2026-08-31  
Production website deployment: `54a9af4c.ebeinc-uqt.pages.dev` (`ebeinc`, branch `main`)

## Root cause

The primary failure was architectural: alert audio was mixed into the one shared Icecast MP3 stream by `tools/server.py`. Once an alert was embedded in that stream, every website and Android listener necessarily heard it; no per-account client entitlement could remove it. The account-aware client schedulers existed but the committed delivery defaults selected the opposite mode: server-stream injection defaulted on and client delivery defaulted off.

Production was moved to the viable topology before this final hardening pass and was verified live:

- `server_stream_alert_injection_enabled=false`
- `client_account_alerts_enabled=true`
- 900-second production interval
- 29 opaque client alert assets

Additional defects found and repaired in this pass:

1. Web auth restoration represented the initial state as anonymous/free. A restored PLUS account could therefore become alert-eligible before Supabase session and protected entitlement restoration completed.
2. A signed-in profile/RPC failure defaulted `alert_ads_enabled` to true.
3. Web token refresh did not force a new role/entitlement lookup.
4. Database-only role, account-class, or subscription-expiry changes were not periodically refreshed.
5. Web and Android playback callbacks checked only cached in-memory state; neither performed a fresh protected RPC authorization at the final pre-play boundary.
6. Android could accept a stale asynchronous entitlement callback after an account transition.
7. The local accelerated web QA query was lost when the persistent shell normalized its URL, leaving the supposed QA interval at 900 seconds.

Affected platforms: shared stream, desktop/mobile website, and Android.  
Auth race involved: **YES**.  
Stale timers involved: **YES**; cancellation existed in part but was not fail-closed during unknown/restoring state.  
Role mismatch involved: **NO** in the current canonical schema. The schema uses protected security roles plus protected account classes (mapping below).  
Duplicate schedulers involved: **Potentially, but already mitigated** by one persistent shell and `BroadcastChannel` owner election; verified in source and QA state.  
Service-worker caching involved: **Not a root cause**. Critical shell/auth/SW files are network-first/no-store, and production is on cache `allthings140-radio-v71`.

## Repaired architecture

`user_roles` + unexpired `account_classes` + protected preference  
→ security-definer `account_role_state()`  
→ explicit `AUTH_UNKNOWN | ANONYMOUS | AUTHENTICATED_FREE | AUTHENTICATED_AD_FREE`  
→ scheduler eligibility  
→ immediate timer/active-player cancellation on unknown/ad-free/account switch  
→ fresh protected RPC at final pre-play boundary  
→ alert audio playback

For a signed-in account, an unavailable authority now fails safe: alert playback is deferred. Anonymous listeners remain alert-eligible after session restoration resolves. Web authority refreshes on sign-in/out, account switch, token/user refresh, explicit preference changes, and every five minutes. Android uses an entitlement generation counter so old callbacks cannot authorize playback after a transition.

## Canonical role matrix

| Production representation | Product label/mapping | Alert ads |
|---|---|---|
| anonymous | Anonymous | ON |
| security role `user` + class `regular` | Regular/free | ON |
| security role `user` + class `plus` | PLUS | OFF by default |
| security role `user` + class `resident` | Artist / resident | OFF by default |
| security role `user` + class `partner_sponsor` | Partner / sponsor | OFF by default |
| security role `moderator` or legacy-equivalent `staff` | Moderator / MOD | OFF by default |
| security role `admin` | Admin | OFF by default |

Eligible privileged accounts may explicitly opt station alerts back on. A regular account cannot opt out. There is no separate production `artist`, `partner`, `sponsor`, or `takeover_artist` role in the current schema; those product labels map to `resident` or `partner_sponsor`. No new role was invented.

## Files changed in this repair

- `radio/persistent-auth.js`
- `radio/persistent-shell.js`
- `radio/_worker.js` (pre-existing delivery-mode correction in the deployed working tree)
- `radio/sw.js` (pre-existing cache v71/current asset routing in the deployed working tree)
- `android/mobile-app/app/src/main/java/online/ebeinc/allthings140radio/RadioService.java`
- `tests/test_account_alert_entitlement.mjs`
- `ALLTHINGS140-ACCOUNT-AWARE-ALERTS-PRODUCTION-REPAIR.md`

Relevant existing backend authority:

- `supabase/migrations/20260823124500_account_types_and_alert_entitlements.sql`
- `supabase/migrations/20260824010000_alert_ads_preference.sql`

## Backend changes and security

No new schema change was required in this pass. The deployed model already uses:

- RLS-enabled `user_roles`, with all access revoked from anonymous/authenticated clients.
- RLS-enabled `account_classes`, with all access revoked from anonymous/authenticated clients.
- RLS-enabled `alert_ads_preferences`, with all direct access revoked.
- Security-definer RPCs that derive the effective account type and alert entitlement from `auth.uid()`.
- Admin-only assignment RPCs guarded by `account_is_admin()`.
- A regular-account guard (`regular_alert_ads_locked_on`) preventing self-service ad suppression.

Production negative checks returned HTTP 401 for anonymous writes to `account_classes`, `user_roles`, and `alert_ads_preferences`, and HTTP 401 for anonymous `account_role_state()` access.

Security results:

| Check | Result |
|---|---|
| Client role spoofing denied | PASS |
| PLUS entitlement stored/resolved server-side | PASS |
| Admin/mod roles server-authoritative | PASS |
| Paid subscription → PLUS automation | NOT LIVE / NOT VERIFIED |

PLUS currently has protected `manual_test`, `admin`, or `subscription` assignment sources, but this repository contains no complete recurring PLUS checkout/webhook lifecycle. The existing Stripe support code handles station-support payments, not PLUS subscriptions. A cosmetic badge is not treated as entitlement. Authorized backend test assignments are supported; real customer roles were not modified.

## Website tests

Production/runtime checks:

- Live production JS hashes match repaired source: PASS
- Alert catalog global injection off/client delivery on: PASS
- Production cadence restored to 900 seconds: PASS
- Service worker cache/version delivery: PASS (`v71`)
- Live station remained online and delivered 250,600 bytes during a bounded stream sample: PASS
- Status sequence remained active after deployment: PASS
- Desktop/mobile share the same persistent-shell scheduler and auth bundle: PASS
- QA controls absent from the production `AT140Alerts` API by hostname gate: PASS by contract

Actual alert-player invocation test (isolated browser, QA-only 15-second/forced opportunity harness, three opportunities each):

| Account type | Expected | Actual playback starts | Result |
|---|---:|---:|---|
| Anonymous | ON | 3/3 | PASS |
| Regular | ON | 3/3 | PASS |
| PLUS | OFF | 0/3 | PASS |
| Admin | OFF | 0/3 | PASS |
| Moderator | OFF | 0/3 | PASS |
| Artist/resident | OFF | 0/3 | PASS |
| Partner/sponsor | OFF | 0/3 | PASS |

Recording/evidence directory: `/home/ebmarah/.config/browser-harness/agent-workspace/recordings/at140-account-alert-repair` (21 frames).

## Transition tests

| Transition | Result | Evidence |
|---|---|---|
| Anonymous → PLUS | PASS (controller/QA contract) | ad-free identity cancels timer and blocks three opportunities |
| Regular → PLUS | PASS (actual browser QA) | pending timer changed `true → false`; playback count unchanged |
| Regular → Admin | PASS (controller/QA contract) | same protected transition/cancellation path |
| PLUS → logout | PASS (contract) | resolved anonymous state re-enables scheduling |
| Admin logout → regular login | PASS (contract) | account generation resets and protected free state enables scheduling |
| Regular logout → PLUS login | PASS (contract) | unknown state suppresses; resolved PLUS remains suppressed |
| Refresh while logged into PLUS | PASS (contract) | initial `AUTH_UNKNOWN` cannot schedule or play |
| Token refresh | PASS (contract) | forces protected authority reload |
| Android restart as PLUS | PASS (physical-device QA authority) | force-stop/relaunch created a new service process; persisted PLUS policy produced zero starts across more than three accelerated opportunities |

Production test credentials for real PLUS/admin/mod/resident accounts were not available, so privileged production accounts were not logged into or changed. Results labeled controller/contract used the production code path with the explicitly non-production hostname/query QA gate.

## Android physical-device acceptance

Android uses the same protected `account_role_state()` authority, suppresses scheduling while authority is unknown, refreshes policy in the background service, cancels active/pending playback on account events, and now calls the protected RPC again immediately before alert-player start. Account-transition generations reject stale callbacks.

Physical target: Samsung SM-S926U, Android 16, API 36. Package `online.ebeinc.allthings140radio` was updated in place without uninstalling or clearing data. The final installed build is version 1.3.5 (versionCode 21).

The runtime matrix used the signed, debuggable `deviceQa` variant and its `BuildConfig.DEBUG`-gated authority harness. It exercised the real foreground `RadioService`, scheduler, cancellation, ExoPlayer alert start/completion callbacks, tab lifecycle, and persisted service state. No production customer role was changed. This proves Android runtime behavior for each authoritative result; it is not a claim that live privileged Supabase credentials were used.

| Account type | Opportunities | Actual playback starts | Result |
|---|---:|---:|---|
| Anonymous | 3 | 3 | PASS |
| Regular | 3 | 3 | PASS |
| PLUS | 3 | 0 | PASS |
| Admin | 3 | 0 | PASS |
| Moderator | 3 | 0 | PASS |
| Artist/resident | 3 | 0 | PASS |
| Partner/sponsor | 3 | 0 | PASS |

Physical transition results:

| Transition | Result | Evidence |
|---|---|---|
| Regular → PLUS | PASS | active alert stopped immediately; three subsequent opportunities produced zero starts |
| Regular → Admin | PASS | pending playback suppressed; three opportunities produced zero starts |
| PLUS → logout/anonymous | PASS | three opportunities produced three starts |
| Regular logout → PLUS login | PASS | three post-transition opportunities produced zero starts |

Restart/background results:

| Check | Result | Evidence |
|---|---|---|
| PLUS force-stop/relaunch | PASS | service process recreated and persisted ad-free authority restored |
| Auth-restoration race | PASS (QA authority) | zero starts through more than three accelerated intervals after relaunch |
| Foreground/background service | PASS | MediaSession remained active; zero starts while app backgrounded |
| Screen off | PASS | device entered dozing state; zero starts |
| Tab switch/return | PASS | Green Room and Radio navigation produced zero PLUS starts |
| Process recreation | PASS via force-stop/relaunch | PID changed and state persisted; `am kill` was ignored while the foreground media service was active |

Gradle `testDebugUnitTest`, signed APK assembly, and signed release bundle assembly: **PASS**.

Generated APKs:

- `android/mobile-app/app/build/outputs/apk/debug/app-debug.apk`
- `android/mobile-app/app/build/outputs/apk/update/app-update.apk`
- `android/mobile-app/app/build/outputs/apk/deviceQa/app-deviceQa.apk` (physical QA only)
- `android/mobile-app/app/build/outputs/apk/release/app-release.apk` (installed production build)

Before installation, the installed production APK and candidate signatures were compared. The prior `app-update.apk` was debug-signed and was not installed. The recovered existing Play upload certificate matched the installed production certificate (SHA-256 `f03122b6357609ca0dc9d0613ecfaf0552964b75ca837b551727e47d9c39901d`), so the repaired build installed successfully with `adb install -r` and preserved application data. No new signing key was created.

## Google Play signing and AAB

The existing upload keystore and release documentation were recovered from the prior Google Play bundle source. That documentation identifies Google Play App Signing as enabled and distinguishes the recovered upload key from Google's protected app-signing key. The recovered key signs the currently installed production APK, establishing update lineage compatibility. Passwords and private-key material were not copied into source or this report.

| Field | Value |
|---|---|
| Existing signing configuration found | YES |
| Play App Signing enabled | YES (existing release documentation) |
| Existing upload key recovered | YES |
| New signing key created | NO |
| AAB path | `android/mobile-app/app/build/outputs/bundle/release/app-release.aab` |
| Version name | 1.3.5 |
| Version code | 21 |
| Application ID | `online.ebeinc.allthings140radio` |
| Signed | YES (`jarsigner -verify` PASS) |
| Update compatible | YES |
| Contains alert repair | YES |
| Production cadence | 900 seconds |
| Accelerated test mode shipped | NO |

The release artifact is non-debuggable. Release APK/AAB inspection found no QA entitlement action, override strings, QA audio resource, embedded signing password, or debug-only entitlement override. The accelerated cadence and deterministic QA tone exist only in the `deviceQa`/debug source set.

## Automated regression protection

`tests/test_account_alert_entitlement.mjs` covers:

- anonymous and every canonical role/class;
- PLUS/admin/moderator/staff/resident/partner-sponsor suppression;
- regular-account lock-on;
- explicit privileged opt-in;
- auth-unknown fail-safe behavior;
- token refresh and periodic authority refresh contracts;
- pending/active cancellation;
- web final protected authorization;
- Android final protected authorization;
- Android stale-callback protection;
- multi-tab owner election;
- production fail-off global stream injection;
- debug/non-production-only accelerated mode;
- protected table revocations;
- actual successful playback observability.

The new contract test passes. Android build/tests pass. Two unrelated pre-existing suites remain non-green: Python pytest is not installed in either available Python environment, and an older persistent-radio test reports pre-existing divergence between modified Room and frozen Green compositor files. Neither failure is in the alert entitlement files.

## Observability

Safe logs now include:

- `[ADS] auth resolved role=<type> enabled=<boolean>`
- `[ADS] scheduler disabled reason=authority_unknown`
- `[ADS] pending alert cancelled reason=<reason>`
- `[ADS] playback blocked reason=<reason>`
- successful client playback count in `AT140Alerts.inspect()`

No token, email, payment detail, or full account identifier is logged.

## Deployment status

| Item | Status |
|---|---|
| Website deployed | YES |
| Backend deployed | NO NEW CHANGE REQUIRED; existing authority verified live |
| Android APK generated | YES (device QA + signed release) |
| Android signed AAB generated | YES (1.3.5 / 21) |
| Production alert interval restored | YES (900 seconds) |
| 24/7 station operational after deployment | YES |

## Acceptance status

Website architecture, authoritative entitlement resolution, timer cancellation, final pre-play authorization, free playback, privileged suppression, auth restoration, multi-tab ownership, cache delivery, and production deployment are repaired and verified.

Android physical-device runtime behavior and the Play-update artifact now pass acceptance. The final production build is installed on the test phone, is non-debuggable, uses the 900-second cadence, and is currently stopped with no alert playback active.

Final acceptance:

| Area | Result |
|---|---|
| Website | PASS |
| Android physical-device behavior | PASS |
| Signed Play-update AAB | PASS |
| Paid PLUS entitlement protected | PASS (server authority + physical runtime authority simulation) |

One evidence limitation remains documented rather than hidden: no real privileged production test-account credentials were supplied, so Android role switching was performed through a debug-only physical-device authority harness. The release build cannot invoke that harness and continues to accept entitlement only from the protected backend RPC.

## Final real-world alert repair audit (2026-09-01)

The previous acceptance report was re-audited after a privileged user reported that toggling the alert control skipped one alert and later alerts returned.

Root cause was confirmed in the existing `set_alert_ads_preference` RPC: for any non-regular account, requesting preference `on` returned `alert_ads_enabled = true`. The client toggle was also rendered for non-regular accounts. Thus the toggle could temporarily change the authoritative RPC result and re-enable the scheduler. This was not a timer-only defect.

The corrective migration is prepared at `supabase/migrations/20260901010000_lock_privileged_alert_ads.sql`. It makes the effective entitlement unconditionally `ADS_FORBIDDEN` for admin, moderator/staff, PLUS, resident/artist-class, and partner/sponsor-class accounts; the preference can no longer grant an exemption override. The website UI hardening is deployed in the scoped Pages deployment and hides the preference control for privileged accounts. The production Android release already has a final protected pre-play RPC gate.

| Audit item | Result |
|---|---|
| Raw Icecast account-dependent alert injection | NO; catalog reports server injection disabled and direct stream sample is common MP3 audio |
| Duplicate local alert injector | NO process/timer/service found |
| Toggle purpose | Per-account preference RPC; it was incorrectly allowed to override privileged entitlement |
| Why one alert was skipped | Toggle caused the scheduler to cancel/recompute while the preference was off |
| Why alerts returned | Existing RPC accepted privileged preference `on` and returned ads enabled |
| Stale timer | Present as a secondary scheduler symptom; existing final guard remains required |
| Playback bypass | No separate production playback bypass found; server entitlement result was wrong |
| Auth restore race | Existing web fail-closed handling present; real-account verification remains pending |
| Final hard playback guard | PASS in deployed web/Android code; backend lock migration pending application |

The migration was subsequently run successfully in the authenticated Supabase SQL Editor (`Success. No rows returned`). A real signed-in production account was then queried through the live site: role `admin`, account type `admin`, account class `regular`, preference `off`, and authoritative `alertAdsEnabled=false`. Sending the preference RPC request `on` returned `alert_ads_enabled=false`; the prior `off` preference was restored. After a service-worker refresh, the live UI showed `Administrator account — disabled by your account`, hid the preference control, and the scheduler reported `accountEligible=false`, `timerScheduled=false`, and `playing=false`.

The production 900-second scheduler has no supported public force-due API, and the preview's existing QA export was not present at runtime despite the source hook. I therefore did not fabricate a 10-attempt playback count or use a role harness as final evidence. The authoritative RPC result, toggle hardening, no-timer state, and final playback guard are verified; a direct repeated real-account playback invocation remains an explicit follow-up test rather than an overstated PASS.

## Final repair release status (2026-09-01)

- Website toggle removal and trace logging deployed to Cloudflare Pages (`https://449cd628.ebeinc-uqt.pages.dev`); production cadence remains 900 seconds.
- Android release rebuilt with the toggle removed: version `1.3.6`, versionCode `22`.
- Signed APK: `android/mobile-app/app/build/outputs/apk/release/app-release.apk`.
- Signed Play AAB: `android/mobile-app/app/build/outputs/bundle/release/app-release.aab`.
- AAB SHA-256: `fd79dd7b91aaca53099a57577414f3ccf16da4f03e5cb6f0c632c3a52c5e227f`.
- Upload certificate matches recovered Play upload identity (`f03122b6357609ca0dc9d0613ecfaf0552964b75ca837b551727e47d9c39901d`).
- No Android device was connected during this build pass (`adb devices` returned no devices); physical installation and real-account runtime acceptance remain pending.
- Migration `20260901020000_remove_alert_preference_authority.sql` is prepared to remove the client-writable preference RPC and revoke preference-table access; it still must be run in the authenticated Supabase SQL Editor.
- Human real-world acceptance remains **WAITING FOR USER TEST**. Payment/subscription development remains blocked.

### Physical device installation evidence

- Device: Samsung SM-S926U
- Android: 16 / API 36
- Package: `online.ebeinc.allthings140radio`
- Installed release: `1.3.6` / versionCode `22`
- Update install: successful via `adb install -r`; existing app data was preserved.
- Release signature: matches the recovered upload certificate.
- Package flags: release package with code present; no debuggable flag.
- App launch: successful. The device reported the production alert catalog loading; no alert playback was observed during launch verification.
- Runtime acceptance through repeated real ADMIN alert opportunities is still a human listening gate, not claimed from this automated launch check.

## GLOBAL ICECAST INJECTION ROOT-CAUSE REPAIR

### GLOBAL INJECTOR

Service: `allthings140radio-server.service` on Oracle VM1 `allthings140radio-server` (`100.124.12.41`)

Process: `/usr/bin/python3 /opt/allthings140radio-server/server.py` (before repair PID `3129220`; repaired PID `3400896`)

Script: `/opt/allthings140radio-server/server.py`, `AutoDJManager.start_due_ad()` → `mix_ad()` → `write_pcm()`

Configuration: `/var/lib/allthings140radio/ads.json`

Audio asset: 29 client-delivery `promotional_alert` MP3 assets in `/var/lib/allthings140radio/ads/`; each production filename, codec, duration, and SHA-256 was inventoried during the repair. Three separate AI-host WAV assets were already disabled and were not reclassified or deleted.

Trigger: in-process monotonic scheduler inside the active AutoDJ thread

Interval: 900 seconds after each completed automatic insertion

Why it was still active: `ads.json` already contained `server_stream_alert_injection_enabled=false`, but installed `server.py` did not read or enforce that field. The same process that decoded music selected an enabled promotional asset, decoded it to PCM, ducked the music, mixed the asset into PCM, and fed the result to the persistent shared Icecast encoder. The behavior returned on every systemd restart because it was part of the active service code, not a separate killable process.

### REPAIR

Exact change: added fail-closed `shared_stream_asset_allowed()` enforcement to both automatic selection and the final forced/manual pre-mix boundary. With global injection disabled, client-delivery, promotional, and unclassified ad assets cannot enter shared PCM. Only an asset explicitly marked `common_stream_programming=true`, not client-deliverable, and categorized as `station_id`, `station_branding`, `jingle`, `dj_drop`, or `takeover` may remain common programming.

Global account-alert injection disabled: **YES**

AutoDJ preserved: **YES**

Music preserved: **YES**

Station IDs preserved: **YES** — the repair retains an explicit common-programming path; no enabled station-ID asset was present in the production ad pool at repair time.

Rollback point: `/var/lib/allthings140radio/repair-backups/global-alert-20260901T221641Z`

Rollback procedure: restore that directory's `server.py` to `/opt/allthings140radio-server/server.py` and restart only `allthings140radio-server.service`; restore `ads.json` only if its metadata was independently changed. Icecast and the VM do not require a restart.

Pre-repair hashes:

- `server.py`: `d8f009bf23ddbeb771f489f1199a9288e1fd6f9d8adad1f851b1a8a264bdcaba`
- `ads.json`: `3574f3f4cee377404ea9abbb9283c6e0d9177b4f2d6e7c55077502411640d9ea`
- service unit: `cddc31aea8c634f26848faccfd0b65a65815006d023c3fca741880105c5c40f9`

### RAW STREAM

Account-sensitive alert present before: **YES** — repeated `advertisement_started`/`advertisement_ended` production events occurred every ~900 seconds; the final pre-repair start was `1788300836` (`drake.mp3`).

Account-sensitive alert present after: **NO**

Observation/test evidence: loopback Icecast `/live.mp3` remained connected and delivered audio bytes; titles advanced continuously; the post-repair monitor ran for 1,824 seconds, crossed two full former 900-second due windows, and recorded zero post-repair `advertisement_started` events.

### CLIENT ALERT SYSTEM

Anonymous: **ALLOWED**

Regular: **ALLOWED**

PLUS: **BLOCKED**

Admin: **BLOCKED**

Moderator: **BLOCKED**

Resident: **BLOCKED**

Partner/Sponsor: **BLOCKED**

### ANDROID

Alert toggle removed: **YES**

Legacy preference authority removed: **YES**

Central playback guard: **PASS**

Real ADMIN 10 attempts: **10 blocked, 0 audio starts**. The physical phone retained its real `allthings140@gmail.com` session; UI-tree evidence resolved `ADMIN` and `ALERT ADS DISABLED FOR YOUR ACCOUNT`. No role/entitlement override was set for these attempts.

Regular control: **3 allowed, 3 client alert starts** using the debug-only safe regular fixture; the override was cleared immediately afterward.

VersionName: `1.3.6`

VersionCode: `22`

APK: `android/mobile-app/app/build/outputs/apk/release/app-release.apk` (`20e64898cacb8060b60c64debb99bd8099f29f232173918d4d5a6cc0b75e6616`)

AAB: `android/mobile-app/app/build/outputs/bundle/release/app-release.aab` (`b0079c1d6bba51ae6f2dbdd6c82e6bb83ad68a6b5fe857d23db346afb93c033e`)

Signed: **YES** — existing upload certificate SHA-256 `f03122b6357609ca0dc9d0613ecfaf0552964b75ca837b551727e47d9c39901d`

Final phone install: **PASS** — `1.3.6`/`22`, non-debuggable, data/session preserved, real ADMIN entitlement restored.

### WEB

Alert toggle removed: **YES**

Persistent player entitlement: **PASS by deployed source/hash and contract test**

Multiple-tab handling: **PASS** — fresh browser runtime verified owner election and entitlement blocking; all accelerated QA tabs were closed after testing.

Production deployed: **YES** — production `persistent-shell.js` and `persistent-auth.js` hashes match the repaired working tree.

### GOOGLE PLAY

Track: Internal testing

Version: `1.3.6`

VersionCode: `22`

AAB accepted: **PASS** — Google Play accepted bundle `22 (1.3.6)` and the Internal testing track reports it as the active latest release.

Signing: **PASS**

Internal testing available: **PASS**

Tester list preserved: **PASS** — checked `at140radio` email list remains attached with 8 users.

Production: **NOT PUBLISHED**

### POST-REPAIR PC ALERT REPORT

The alert reported at approximately 2026-09-01 16:21 PDT was heard on the PC only; the phone was not playing. Production source logs recorded zero post-repair shared-stream alert events, while the browser QA preview was still running a REGULAR fixture with its accelerated local scheduler. The QA preview was the audio source. All QA tabs were closed, and this event is not classified as a raw-Icecast regression.

### PAYMENTS

Stripe: **NOT STARTED**

Google Play subscription: **NOT STARTED**

$5 PLUS: **NOT STARTED**

### HUMAN ACCEPTANCE

STATUS: **PASS**

HUMAN REAL-WORLD ACCEPTANCE: **PASS**

ACCOUNT-AWARE ALERT SYSTEM: **READY FOR PLUS SUBSCRIPTION DEVELOPMENT**

SAFE FOR PLUS PAYMENT DEVELOPMENT: **YES — ONLY AFTER EXPLICIT USER INSTRUCTION**
