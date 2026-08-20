# AllThings140Radio project record

- Canonical project: `/home/ebmarah/Projects/AllThings140Radio`
- Public site: `https://allthings140radio.online/`
- Public status: `https://status.ebeinc.online/api/public/status`
- Public stream: `https://stream.ebeinc.online/live.mp3`
- Oracle service source: `/opt/allthings140radio-server/`
- Oracle data: `/var/lib/allthings140radio/`
- Oracle fallback audio/storage: `/srv/allthings140radio/`
- Drive mount: `/mnt/allthings140radio-drive`
- Protected configuration: `/etc/allthings140radio/`
- DJ source: `tools/dj_app.py`; installed under `/opt/allthings140radio-dj/`
- Main ports: 14000 loopback Icecast; 14080 private control; 14082 loopback public gateway; 14083 restricted live source.
- Deployment: incremental, backup-first, syntax-check, single-service restart, local health, public health, rollback retained.

## Audit 2026-08-12

Production version 0.7.0 was live with 485 playable tracks, two listeners during checks, healthy watchdog/silence state, 80.9% free station storage, active Drive/stream/tunnel services and current backups. Direct public checks of ports 14080 and 14083 were blocked while intended HTTPS endpoints worked. Drive contains 490 root-level MP3/WAV files. No missing playable files or simple duplicates were found. Most track artist metadata is missing. A disconnect-handling patch was backed up, deployed and verified to keep AutoDJ and Icecast healthy.

Final hardening added rotated Icecast credentials, a loopback authentication relay, loopback-only control/live listeners with tailnet-only forwarding, staged/hash-based ingestion, 486 persistent content hashes, conservative metadata repair (385 unknown artists reduced to 51), six-track artist cooldown for new rotation cycles, a stateful bounded supervisor, encrypted/validated off-host backups, expanded CLI health operations, and an implemented EBE Dock Radio panel. Remaining manual work is review of 51 ambiguous metadata rows and interactive testing of disruptive UI controls during a scheduled window.

Never add actual credentials to this record.

## Catalog integrity recovery 2026-08-15

The apparent 88-file loss was an admission failure, not loss from Google
Drive: all 571 catalog filenames existed in the Drive master, while production
cache-only resolution could see only the 487-file emergency mirror and the
50-track hot cache. Later uploads entered Drive/catalog but were never admitted
to local playback, and cache planning could not select tracks AutoDJ already
considered unavailable. All 88 affected approved tracks were conservatively
restored from Drive into the emergency mirror and independently verified by
SHA-256 and duration; 569 eligible tracks are now playback-ready and the two
remaining rows are intentionally unapproved/rights-blocked.

Production server 0.8.0 separates catalog unlinking from asset handling,
disables legacy prune/delete routes, implements durable idempotent operation
manifests and status lookup, protects shared paths, provides audited quarantine
and restore, and classifies metadata matches as review-only unless audio
identity is proven. A read-only integrity monitor drives HEALTHY/DEGRADED/
CRITICAL catalog state, and a low-priority 30-minute playback-admission timer
prevents future Drive-only uploads from becoming stranded. DJ 0.7.0 adds a
Catalog Integrity screen and removes prominent destructive bulk actions.

Incident evidence is under
`recovery/catalog-incident-20260815T111250Z/`; the root-only forensic backup is
`/srv/allthings140radio/backups/catalog-incident-20260815T111250Z/`; the
verified pre-deployment rollback is
`/srv/allthings140radio/backups/predeploy-integrity-20260815T121447Z/`.

## Background playback reliability deployment 2026-08-13

Root cause investigation reproduced a suspended Chromium page whose audio
element reported `paused=false` while `readyState=0` and `currentTime=0`. The
old visible-page handler only recovered when `audio.paused` was true. Frozen
retry/status timers, a single `statusPending` gate, unchanged-URL attachment,
and cache-first service-worker delivery could leave that zombie media
connection and stale metadata in place. The client also lacked a server
generation/sequence for ordering responses. Oracle cloudflared logs showed
client stream cancellations, while playback/encoder state remained independent
of listener GETs. The active public stream was verified as Oracle Icecast via
the production Tunnel; a stale source-only laptop Funnel proxy branch was
removed from `_worker.js` so it cannot be accidentally reintroduced.

Deployed frontend 1.6.1 now performs a deduplicated resume transaction on
visibility, pageshow, focus, online, freeze/resume. It aborts frozen status
requests, fetches no-store authoritative state, discards older sequence data,
and rejoins the live MP3 mount when media is stale. Reconnects use bounded
exponential backoff plus jitter and generation guards. An intentional-pause
race found during the first production freeze test was fixed; the final test
made one attach and resumed ready/playing across a track change. The service
worker is cache v54 and uses network-first delivery for critical JS.

Server 0.7.1 now exposes `station_generation_id`, `station_sequence`,
`server_time`, and `stream_status`. Sequence advances only for authoritative
broadcast transitions (tracks, ads, live handoff), never listener status reads.
Oracle rollback file:
`/opt/allthings140radio-server/server.py.before-background-resume-20260813`.
Production Pages deployment: `827399a7.ebeinc-uqt.pages.dev`. Nineteen tests
passed. Browser recording:
`~/.config/browser-harness/agent-workspace/recordings/at140-background-reliability`.
Full design and diagnostics: `docs/BACKGROUND_PLAYBACK_RELIABILITY.md`.
# Listener support system (2026-08-13)

The website now includes a Stripe-hosted one-time support flow integrated with the existing Python/SQLite/Cloudflare architecture. `tools/support_system.py` owns checkout validation, Stripe API calls, webhook HMAC verification, event replay prevention, paid/refund accounting, safe public data, and authenticated dashboard data. It is intentionally independent from AutoDJ, FFmpeg, Icecast, and the station timeline.

The authoritative support state is the Oracle SQLite database. A Checkout redirect is never proof of payment: only `checkout.session.completed` or `checkout.session.async_payment_succeeded` received at `https://allthings140radio.online/api/public/support/webhook` can mark a matching session paid. The public goal/feed query only paid records and subtracts `charge.refunded` amounts. Public data excludes emails, billing details, IPs, customer IDs, and payment references.

The listener UI lives in `radio/support.js` and `radio/support.css`, with markup in `radio/index.html`. It provides the hero/nav/footer entry points, accessible modal, suggested/custom amounts, optional public identity/message, goal, recent feed, and non-audio live notification. Polling pauses while hidden and refreshes on resume/online. It never creates audio elements or sends playback commands.

The existing DJ desktop app has a Support tab for verified summaries, safe transaction review, goal/feed/notification configuration, and message/entry moderation. Setup, Test Mode, live transition, event list, environment variables, deployment, and troubleshooting are documented in `SUPPORT_SYSTEM_SETUP.md`. Automated coverage is in `tests/test_support_system.py`.

Oracle backend deployed 2026-08-13 with rollback copy `/opt/allthings140radio-server/server.py.before-20260813-support`; Icecast was not restarted. The public support API and SQLite schema are live. Cloudflare Pages deployment is `243e2147.ebeinc-uqt.pages.dev`.

Stripe production payments were activated on 2026-08-13 after account verification. A dedicated live secret key and live webhook endpoint were created for `https://allthings140radio.online/api/public/support/webhook` with the five documented events. Live credentials are stored only in root-owned mode-0600 `/etc/allthings140radio/support.env`; the former sandbox configuration is preserved at `/etc/allthings140radio/support.env.test-mode-backup-20260813`, also mode 0600. A non-charging live Checkout Session was successfully created, forged webhook signatures returned HTTP 400, and API/Icecast/Tunnel services remained active. No real charge was submitted during activation.
# 2026-08-13 production/migration release

The production architecture remains four separated planes: Oracle broadcast authority, public Cloudflare listener plane, private Tailscale control plane, and replaceable workstation development plane. Website public content release adds Roadmap, Sponsor and About sections. Android 1.1.0/versionCode 13 now exposes a Media3 `MediaLibraryService` with a single listener-safe LIVE RADIO item to Android Auto/Automotive; it consumes the same continuous MP3 stream and contains no admin capability. Build validation passed; physical/DHU/Automotive target validation remains explicitly pending.

Operational recovery is documented under `migration/`; the guided entry point is `setup-allthings140radio.sh` and unified public diagnostic is `tools/allthings140-diagnose.py`. Final artifacts and evidence live under `dist/ALLTHINGS140/`. The portable ZIP is `dist/ALLTHINGS140/Migration/allthings140radio-backup-migration.zip`; it excludes env files, private keys, signing stores and large audio/video media. Google Drive remains the master music library.

Baseline commit/tag: `69991d2124bb4c6450e3d4c7f64998aa9b9b50ed` / `allthings140-pre-final-20260813`. Cloudflare Pages deployment: `aac2a08a-9c5a-4184-8470-c9502e38c63b`. Oracle server was not restarted by this release. A 60-second public stream soak crossed an automatic track transition with the same server PID. Python tests passed 25/25 locally and from an isolated extraction of the migration ZIP.

The historic Android artifact and v1.1.0 release APK share certificate SHA-256 `53710e5f9cfff64a64baf9e8a156b917b2a11ab95ed88f7270a96c0996bb3271`, preserving sideload update compatibility. This is a debug certificate; do not claim Google Play production signing readiness until a deliberate upload/app-signing migration is completed.
