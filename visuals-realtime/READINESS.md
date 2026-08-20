# Visuals staging readiness — 2026-08-13

```text
PRODUCTION READINESS

Visual Engine: PARTIAL
Stage Overlay: PASS (isolated Cloudflare Pages staging render)
Playlist Engine: PASS (20 consecutive decoded/playing transitions)
Takeover Scheduler: PASS (server-authoritative automatic start/end and normal playlist restoration)
Oracle Realtime Server: PARTIAL (functional/restart tests pass; extended soak remains open)
Chat: PASS (deployed multi-client integration and sanitization)
Audience Presence: PASS (deployed multi-client integration)
Reactions: PASS (deployed integration, rate/replay checks)
Room Energy: PASS (deployed server-authoritative calculation and browser update)
Profiles: PASS (local browser behavior; recovery semantics documented)
Security Checks: PASS (deployed origin rejection plus local payload/rate/replay tests)
Backup: PASS (Oracle timer plus manual run at 20260813T193903Z)
Restore Test: PASS (independent Oracle restore and SQLite quick_check)
Radio Regression Test: PASS
Desktop Performance: NOT YET SOAKED LONG ENOUGH
Mobile Regression: NOT YET TESTED

NEW VISUALS SYSTEM READY: NO
READY FOR CUTOVER: NO
```

Production `/visuals/` and all legacy video assets remain unchanged. No production deployment/cutover is authorized from this result.

## Staging deployment

- Green site: `https://allthings140-visuals-green.pages.dev/` (unlinked, noindex, no-store)
- Realtime health: `https://visuals-realtime-staging.allthings140radio.online/health`
- Dedicated OCI host: `allthings140-visuals-realtime`
- Release: `0.1.0-staging`

## Significant issues found and fixed

1. Oracle Linux reserved 448 MiB of the 1 GiB VM for a failing kdump crash
   kernel. This caused multi-minute boots, SSH/agent stalls, and service
   maintenance hangs. The failed kdump service was disabled and its
   `crashkernel` reservation removed. Verified `MemTotal: 968832 kB` afterward.
2. The deployed server backup initially failed because its hardened systemd
   sandbox did not expose a writable generic temp directory. Backups now create
   temporary restore-test data inside the configured protected backup path.
3. The health helper assumed the old development port. It now derives the URL
   from `REALTIME_HOST` and `REALTIME_PORT`.
4. `/visuals-state` lacked allowlisted CORS, preventing browsers from consuming
   authoritative takeover schedules. Allowlisted CORS was added and verified.
5. Multiple resume/online events could attempt concurrent WebSockets. The green
   client now treats OPEN and CONNECTING sockets as an idempotency guard.
6. Open WebSockets delayed service shutdown. The app now closes clients during
   shutdown and systemd has a bounded 15-second stop timeout.

## Cutover blockers

- Extended desktop soak and memory-growth observation are incomplete.
- A gateway restart originally stopped the tunnel because its systemd unit used
  `Requires=`. The gateway recovered but the tunnel stayed stopped and returned
  HTTP 530. The dependency was changed to `Wants=` so gateway maintenance does
  not tear down the outbound tunnel. Extended soak/restart repetition remains a
  cutover gate.
- Mobile browser regression/profile/reconnect testing is incomplete.
- Missing/corrupt visual and network-interruption matrices need full deployed runs.
- Takeover restart-before-start and management-PC-off scheduling need a longer
  real-time staging test.

Because these gates remain open, the legacy production Visuals implementation
must remain selected and available.

## Workstation and supplied-media update — 2026-08-13

- Built `ALLTHINGS140Radio Visuals` as a Tauri Linux workstation (v0.1.1).
- Added the WYSIWYG Visual Workshop with normalized geometry, draggable layers,
  eight resize handles, center controls, screen-target snapping, editor-only
  zoom, hide-stage mode, undo/redo, versioned presets, and persisted Global
  Visual Frame.
- Imported the user-supplied `stage/alpha.mov` without modifying it. Because it
  is HEVC and its opening is black rather than alpha, staging uses a muted H.264
  derivative with `screen` blend compositing. The source remains untouched.
- Validated all 57 supplied 24/7 MP4 sources and created muted, browser-safe
  1280x720 H.264 staging derivatives. Original videos remain untouched.
- Deployed the proper stage and 57-video playlist to GREEN staging only.
- Added WYSIWYG layers for the production Visuals overlays found during the
  source audit: station/takeover logo and the 24/7 Playlist / Now Live metadata
  card. Presence, reactions, Room Energy and stage screen target are represented
  in the same Workshop composition. Logo/alert frames persist with layouts.
- Added normal/takeover test-state switching and difficult long-string previews.
- GREEN staging uses live radio metadata and server-authoritative takeover state;
  the desktop simulation never changes a schedule.
- Network interruption tests passed for 5s, 30s, 2m and 5m; visual playback
  continued and realtime recovered. A persisted takeover began after the
  workstation was closed and gateway restarted, then the normal playlist
  returned. A full Oracle reboot subsequently restored gateway and tunnel.
- Responsive automated Chromium tests passed at 390x844, 844x390, 768x1024 and
  1024x768 with no horizontal overflow. This was emulation, not a physical phone.
- The production `/visuals/` SHA-256 remained
  `4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32`.

Remaining cutover gates include a multi-hour/overnight browser+server soak,
physical-phone regression, final user-chosen screen alignment, and full manual
takeover asset-package validation. Therefore:

```text
NEW VISUALS SYSTEM READY: NO
READY FOR CUTOVER: NO
```
## Media-selector workstation update (2026-08-13)

- Desktop package bumped to `0.1.2` and installed as `allthings140-radio-visuals`.
- The Visual Workspace now uses the imported media inventory: 1 supplied browser-compatible stage derivative and 57 canonical 24/7 Visual entries.
- Stage and Visual inspectors are layer-specific; selecting Stage shows the Stage Video selector and selecting Visual Content shows the searchable/countable Visual selector.
- GREEN staging renderer accepts the published layout schema and continues to fall back to the canonical 57-item playlist when no temporary preview is published.
- Production remains locked and the frozen `/visuals/` baseline remains `4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32`.
- The Tauri GUI could not be screenshot-captured from the restricted shell because GTK has no attached display session; package installation and launcher/package verification passed. Human visual approval is still required.

NEW VISUALS SYSTEM READY: NO
READY FOR CUTOVER: NO
## Workstation media playback fix (2026-08-13)

- Root cause identified: Tauri 2 resolves local media through `https://asset.localhost`, but the workstation CSP omitted that origin from `media-src`; both H.264 Visuals and the Stage therefore emitted media errors despite valid files.
- Fixed in workstation `0.1.3` by allowing the Tauri asset origin and preserving the existing layered Stage/Visual composition.
- Supplied Stage source: `/home/ebmarah/Videos/at140radio/desktop visuals/stage/alpha.mov` (HEVC, 1920x1080, 60fps, 48.019s, YUV420, no embedded alpha stream, AAC audio). Runtime derivative remains muted H.264 `visuals-green/media/stage/stage-overlay.mp4`; original source is preserved.
- Installed package: `0.1.3`. Package SHA-256: `72d7881ebbb8ddd5ed87c363f4a28bebbef9baf21682a23a9ca0c44aa8b03eb8`.
- GREEN playlist inventory remains 57 entries and realtime health is online.
- Production remains frozen at `4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32`.
- GUI playback could not be interactively observed from the restricted shell because no GTK display session is attached; human verification of the installed window remains required.

NEW VISUALS SYSTEM READY: NO
READY FOR CUTOVER: NO
## Media-role separation update (2026-08-13)

- Workstation `0.1.4` scans Stage assets only from `/home/ebmarah/Videos/at140radio/desktop visuals/stage/` and normal Visuals only from `/home/ebmarah/Videos/at140radio/desktop visuals/visuals/`.
- Current verified inventory: Stage assets `1` (`alpha.mov`), normal Visuals `57` (`87.mp4` included).
- Imported entries now carry explicit `mediaType` values (`stage` or `visual`); derivatives inherit the logical source role.
- Production remains frozen at `4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32`.
- Installed package SHA-256: `b7fe1cbf65994b260ab0b58af823f5db69a76adacd53c0601d2f8840e52d8b0c`.
- No production cutover performed. GUI visual confirmation still requires the logged-in desktop display session.

NEW VISUALS SYSTEM READY: NO
READY FOR CUTOVER: NO
