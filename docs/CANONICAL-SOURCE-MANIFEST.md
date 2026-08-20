# ALLTHINGS140 canonical source manifest

Known-good state after Phase 2 on 2026-08-20.

## Canonical source

| Component | Canonical path | Version/state |
|---|---|---|
| Project root | `/home/ebmarah/Projects/AllThings140Radio` | Git `main` |
| Website | `/home/ebmarah/Projects/AllThings140Radio/radio` | Cloudflare Pages project `ebeinc` |
| Android | `/home/ebmarah/Projects/AllThings140Radio/android/mobile-app` | 1.3.1 (16), unchanged in Phase 2 |
| Visuals workstation | `/home/ebmarah/Projects/AllThings140Radio/visuals-app` | 0.1.42, unchanged in Phase 2 |
| Hub | `/home/ebmarah/Projects/AllThings140Radio/hub` | recovered 1.2.1 source |

## Git baseline

- Canonical baseline commit: `fba51bb` (`ALLTHINGS140 canonical pre-launch baseline`)
- Website video implementation commit: `481f9c409477abdcb30457aa7b1748b85b6a319a`
- Commits are local only; nothing was pushed.
- `.gitignore` excludes dependency trees, build products, archives, packages, media derivatives, credentials, environments, tokens, private keys, keystores and private configuration.
- Pre-existing untracked archives/assets remain on disk and were not deleted or moved.

## Hub recovery

- Installed source: `/opt/allthings140-hub/hub`
- Package: `/home/ebmarah/Downloads/allthings140-hub_1.2.1_amd64.deb`
- Package SHA-256: `115844e2f209447a6374e3313eed76caaf7317cfa089c6257c21c92f5c765f2b`
- Extracted package source and installed source matched byte-for-byte.
- Repo-only build, install, uninstall and test material was preserved.
- Recovered changes include atomic state writes/corrupt-state preservation, single-instance locking, background health probes, truthful unknown states, immutable Cloudflare deployment guards, and related UI/safety corrections.
- Version markers and Debian builder now agree on 1.2.1.

## Website production

- Production domain: `https://allthings140radio.online`
- Pages project: `ebeinc`
- Preview: `31f3a97e-31dd-49f1-8f40-1a527e7550eb`
- Production: `4e63a598-1bb0-4d21-b3de-fe714421b123`
- Production source marker: `481f9c4`
- Previous production/rollback deployment: `aa2dc9b7-2559-4331-a736-464924cba52e` (source `c049608`)
- Before modification, local Visuals HTML, `app.js`, `sw.js`, and old video matched production. The homepage differed only through expected Cloudflare email-address obfuscation.

## Desktop Visuals media

- Master: `/home/ebmarah/Videos/at140radio/new vis long.mp4`
- Master SHA-256: `4fadb9e6a5f9803604f8a9f106cba4fbcbe50e45b895b32ece38c8e574078b6c`
- Web intermediate: `/home/ebmarah/Videos/at140radio/visuals-desktop-v8.mp4`
- Intermediate SHA-256: `43e59ba69fa222e1af230e665fb18f55bfbb0640a0e99f1e0b5ae8b7fa9c76c2`
- Intermediate: H.264 High, yuv420p, 1920x1080, 30 fps, 904.000 s, no audio, 6,006,960 bit/s container average, 678,786,553 bytes.
- Encode: `libx264`, preset slow, CRF 20, maxrate 6M, bufsize 12M, High 4.1, GOP 60, fixed two-second keyframes, faststart, audio removed.
- Deployed asset: `/radio/assets/visuals-desktop-v8/index.m3u8` plus 226 four-second transport-stream segments (227 files; about 666 MiB).
- Manifest SHA-256: `8abf8d8b7cbdedcb74d9d57eded40cf7c9c17b760a7ba7c52ae64669c7363db1`
- First segment SHA-256: `1dce589505b2bf596eef2afdd8434ae202c665c23960aeaff782deaa975b313c`
- Poster: `/radio/assets/visuals-desktop-v8-poster.webp`, 368,836 bytes.
- Mobile video remains `/radio/assets/phone-visuals-authoritative-v1.mp4?v=1.0.0`, SHA-256 `190308b28f16465bdac3468c8bfe54450918fe9cb6bc12c63a3c54d67adab32f`.

The HLS directory is a reproducible, ignored deployment derivative because committing 666 MiB of generated segments would undermine repository safety. The authoritative master, encode recipe and hashes above make it reproducible and verifiable.

## Production verification

- Production HTML and vendored hls.js hashes exactly matched local source after deployment.
- Production manifest and first-segment hashes exactly matched local deployment bytes.
- HLS manifest and segments returned HTTP 200 with correct MIME types and immutable cache headers.
- Browser checks passed at 1920x1080, 2560x1440, 1440x900, 1366x768, 2560x1080, and 390x844 with no console or request failures.
- Desktop loaded and played the new 1920x1080 HLS, muted, using `object-fit: cover`.
- A direct end-of-media test crossed from 903.75 s to 4.61 s while remaining unpaused and muted, confirming continuous looping.
- Mobile loaded and played the unchanged 720x1280 MP4, muted, using `object-fit: contain`.
- Homepage retained its existing background. Homepage, room and station-status endpoints returned HTTP 200/online.
- The live stream delivered 187,600 bytes during an eight-second read-only sample; the timeout was intentional because the stream is continuous.
- The master has a visible content cut between its end and beginning, but no black, blank or frozen endpoint frame.

## Rollback

Rollback the Pages project to deployment `aa2dc9b7-2559-4331-a736-464924cba52e`. Source rollback points are Git `fba51bb` for the canonical baseline and pre-task Git `c049608b8da16efebff08de75935492a2cb55aa0`. The old desktop reference was `../assets/visuals-desktop.mp4?v=7.0.0`.
