# ALLTHINGS140 canonical pre-change snapshot

- Captured: 2026-08-20T18:02:21Z
- Purpose: immutable evidence before Phase 2 Hub recovery and desktop `/visuals/` video work
- Repository: `/home/ebmarah/Projects/AllThings140Radio`
- Branch: `main`
- HEAD: `c049608b8da16efebff08de75935492a2cb55aa0`
- Upstream state: 25 commits ahead of `origin/main`
- Working state: 12 modified paths and 123 untracked status entries; this work predates Phase 2 and must be preserved
- Remote: `origin` = `https://github.com/project-ashvector/ebeinc.git`

## Canonical candidates verified

- Website: `/home/ebmarah/Projects/AllThings140Radio/radio`
- Android: `/home/ebmarah/Projects/AllThings140Radio/android/mobile-app` — versionName 1.3.1, versionCode 16
- Visuals workstation: `/home/ebmarah/Projects/AllThings140Radio/visuals-app` — 0.1.42
- Hub repository: `/home/ebmarah/Projects/AllThings140Radio/hub` — package builder 1.2.0, Python package marker 1.1.0, config default 1.0.0 (internally inconsistent)
- Hub installed source: `/opt/allthings140-hub/hub` — 1.2.1
- Hub package: `/home/ebmarah/Downloads/allthings140-hub_1.2.1_amd64.deb` — Debian 1.2.1

## Cloudflare and production evidence

- Account ID: recorded locally by Wrangler but intentionally omitted from this repository document
- Pages project: `ebeinc`
- Domains: `ebeinc-uqt.pages.dev`, `allthings140radio.online`, `ebeinc.online`
- Previous production deployment: `aa2dc9b7-2559-4331-a736-464924cba52e`
- Previous production deployment source marker: `c049608`
- Previous production URL: `https://aa2dc9b7.ebeinc-uqt.pages.dev`
- Production `/visuals/` SHA-256: `017b07f11eb1a3a439f7f60d1f0345fd02d4b6a5a6932017c330f909c757b4c6`
- Local `radio/visuals/index.html` SHA-256: same as production
- Production/local `app.js` SHA-256: `ae23e50c48a7e82ab30b0c57f67732e17acff079f2fbd1ff3819542025d7b419`
- Production/local `sw.js` SHA-256: `b050dfa6d0066f977d5265bacf921441cd9d1e55db89561b6d781a743eb51515`
- Production homepage difference: only Cloudflare Email Address Obfuscation rewrites the mailto link and injects its decoder script; this is expected edge behavior, not source drift
- Existing R2 buckets: `allthings140radio-archives` only; it is not suitable for public media
- Cloudflare Pages single-asset limit verified from current official docs: 25 MiB

## Important file hashes

| File | SHA-256 |
|---|---|
| `.gitignore` | `4933afaca680c18a26a20199ca1294c5463fe8f3c136b098d9a15c518be0cf59` |
| `wrangler.toml` | `42bcd9ca2c4fa11f9118149a92c106af30a60e81cbd292030e433198ac8d1d4e` |
| `radio/_worker.js` | `08fb1f97fa0160368a659e34864aadea3a19bbf9e1539544c44e227fe52582c2` |
| `radio/index.html` | `73d93c45bb72527a10826d77e678f7bbd23ad8317bba2d5b127f018db78aa4e8` |
| `radio/visuals/index.html` | `017b07f11eb1a3a439f7f60d1f0345fd02d4b6a5a6932017c330f909c757b4c6` |
| old desktop video | `64d548c7a37fef86d19e8e11fff846efdb9a58d2ff3439e3461a4710b3c8ca09` |
| mobile video | `190308b28f16465bdac3468c8bfe54450918fe9cb6bc12c63a3c54d67adab32f` |
| supplied master | `4fadb9e6a5f9803604f8a9f106cba4fbcbe50e45b895b32ece38c8e574078b6c` |
| Hub 1.2.1 Debian package | `115844e2f209447a6374e3313eed76caaf7317cfa089c6257c21c92f5c765f2b` |

## Video state

- Old desktop: H.264 High, yuv420p, 1280x720, 24 fps, 904.000 s, 22,184,976 bytes, about 196 kb/s, no audio
- Mobile: `/radio/assets/phone-visuals-authoritative-v1.mp4`; hash above; must remain unchanged
- New master: `/home/ebmarah/Videos/at140radio/new vis long.mp4`; H.264 Main, yuv420p, 1920x1080, 60 fps, 904.022494 s, 1,985,492,985 bytes, 17.57 Mb/s, AAC stereo audio present (audio will be removed from web derivative)

## Secret and generated-file exclusions already observed

The following were verified ignored and their values were not read or printed: `discord-bot/.env`, `android/control-app/daemon.token`, Android build directories, the Play upload keystore, and Node dependency trees. Phase 2 will broaden ignore coverage before staging.

## Rollback point

Before Phase 2 production deployment, rollback is Cloudflare Pages deployment `aa2dc9b7-2559-4331-a736-464924cba52e` plus Git HEAD `c049608b8da16efebff08de75935492a2cb55aa0`. The old desktop asset reference is `../assets/visuals-desktop.mp4?v=7.0.0`.
