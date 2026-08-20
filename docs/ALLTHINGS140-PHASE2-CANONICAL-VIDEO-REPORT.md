# ALLTHINGS140 Phase 2 completion report

## A. Canonical source

The canonical root is `/home/ebmarah/Projects/AllThings140Radio`. Canonical website, Android, Visuals workstation and Hub paths are recorded in `CANONICAL-SOURCE-MANIFEST.md`.

## B. Git

The current meaningful project state was captured locally in baseline commit `fba51bb`. Secret/build/archive exclusions were broadened before staging. A staged-content/path scan found no actual secret material. No history was rewritten, no untracked material was cleaned, and no commit was pushed. The video implementation is commit `481f9c4`.

## C. Hub

The repository was behind the installed/package implementation. The Debian package and `/opt` source were equivalent, so their genuine 1.2.1 changes were merged file-by-file while repo-only build/install/uninstall/tests were retained. The changes add atomic/corruption-safe state persistence, an instance lock, asynchronous health workers, truthful unknown-state handling, guarded immutable deployment behavior, and matching UI corrections. All version markers now say 1.2.1. Compilation passed. Existing tests mostly passed; two old assertions still expect fabricated success/health behavior deliberately removed by 1.2.1 and must be updated in a later Hub test task.

## D. Website and Cloudflare

The local website matched the deployed Visuals page, app/service-worker scripts and old media bytes before changes. The only homepage drift was Cloudflare's expected email-obfuscation transformation. Pages project `ebeinc` remains the production host; DNS and unrelated Cloudflare settings were untouched.

## E. Old desktop Visuals video

`radio/assets/visuals-desktop.mp4`: H.264 High/yuv420p, 1280x720, 24 fps, 904 s, no audio, 22,184,976 bytes, about 196 kb/s. It remains available as a compatibility/error fallback and was not deleted.

## F. New source video

The exact user-specified `/home/ebmarah/Videos/at140radio/new vis long.mp4` was used. It is the genuine 1920x1080, 60 fps, 904.022 s master at 1,985,492,985 bytes and about 17.57 Mb/s, with AAC stereo. No similarly named candidate was substituted.

## G. Compression

CRF 18, 20 and 22 samples were compared. The selected encode uses H.264 High/yuv420p, slow preset, CRF 20 constrained to 6 Mb/s with a 12 Mb buffer, 30 fps, two-second GOP, faststart and no audio. Pages has a 25 MiB per-file limit, so the resulting quality-first MP4 was losslessly segmented into four-second HLS pieces for deployment rather than degraded to an unsuitable bitrate.

## H. New web video

The encoded MP4 is 1920x1080 at 30 fps, 904.000 s, 678,786,553 bytes and approximately 6.007 Mb/s. Production serves `assets/visuals-desktop-v8/index.m3u8` and 226 segments. hls.js 1.7.1 is vendored locally; Safari can use native HLS. A representative 368,836-byte WebP poster is used.

## I. Quality comparison

The new stream carries roughly thirty times the old video's average bitrate and genuine 1080p detail. Representative dark, bright, particle-heavy and fast-motion samples retained substantially better gradients, particles and motion clarity. The source itself has a perceptible creative cut at the loop boundary; it has no black/blank/frozen endpoint frame.

## J. Responsive tests

Local, preview and production browser tests covered 1920x1080, 2560x1440, 1440x900, 1366x768, 2560x1080 and 390x844. Desktop preserves aspect ratio with centered cover behavior. Mobile independently selects the unchanged portrait video with contain behavior. Production's final repeated pass had no console errors or failed requests.

A direct production loop test sought to 903.75 seconds and observed playback continue at 4.61 seconds, still playing and muted.

## K. Cloudflare preview

Preview `31f3a97e-31dd-49f1-8f40-1a527e7550eb` passed HTTP, MIME, immutable-cache, byte-hash, desktop/mobile playback and audio-isolation checks before production deployment.

## L. Cloudflare production

Production deployment `4e63a598-1bb0-4d21-b3de-fe714421b123` is live. Homepage, Visuals and room returned HTTP 200. Production HTML, hls.js, playlist and a representative segment matched local hashes. The network-loaded desktop source is the new immutable HLS path, not the old MP4 fallback.

## M. Radio safety

The Visuals media contains no audio and remains muted. Browser checks confirmed the station audio element stayed independent and paused until user action; station status reported online. A read-only eight-second request received 187,600 live-stream bytes (the expected continuous response was deliberately timed out). No radio player or server source was changed.

## N. Rollback

The immediate Pages rollback is deployment `aa2dc9b7-2559-4331-a736-464924cba52e` (source `c049608`). The canonical pre-video Git point is `fba51bb`. The old file/reference remains available.

## O. Files intentionally changed

- `.gitignore`
- Hub 1.2.1 source/version/build files under `hub/`, including new `hub/util/atomic_io.py` and `hub/ui/worker.py`
- `radio/visuals/index.html`
- `radio/_headers`
- `radio/assets/visuals-desktop-v8-poster.webp`
- `radio/vendor-hls-1.7.1.min.js` and license
- Generated ignored deployment derivative `radio/assets/visuals-desktop-v8/`
- Phase 2 snapshot, manifest and report under `docs/`

The baseline commit also versioned meaningful pre-existing canonical source without changing its behavior.

## P. Files not changed

Phase 2 made no application changes to Android, the Visuals workstation, Green Room frontend/backend, chat, radio server, privacy/terms, Wear OS or Google Play configuration. Homepage code and the mobile Visuals asset were not changed. Historical source/media were not deleted or moved.

## Operational note

A temporary public R2 bucket was explored after Wrangler rejected the 647 MiB single MP4, but the CLI cannot upload objects over 300 MiB. No object was created; the newly created empty bucket was removed. The existing archive bucket was untouched. Final delivery uses Cloudflare Pages HLS.
