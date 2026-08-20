# AllThings140Radio project manifest

- Canonical location: `/home/ebmarah/Projects/AllThings140Radio/`
- Purpose: Local development and management workspace for the radio platform, website, chat worker, Discord bot, Android clients, deployment tooling, assets, builds, and preserved backups.
- Project type: web-radio platform and operations workspace
- Primary technology: HTML/CSS/JavaScript, Node.js/Cloudflare Workers, Python, Android/Gradle
- Git: Yes; existing `.git` preserved.

## Layout and operation

- Important directories: Repository root web files; `chat-worker/`; `discord-bot/`; `tools/`; `android/`; `operations/`; `assets/`.
- Main entry points: Static site at repository root; Python tools under `tools/`; package scripts in component folders.
- Build/run: Component-specific; inspect each package or Python tool before running.
- Test: `python3 -m pytest tests` (lightweight local test suite).
- Operations command: `allthings140 status` or `allthings140 diagnose`.
- Deployment/external services: See existing README/handoff files where present; deployment is never automatic from this workstation manifest.

## Multi-PC policy

Synchronize authored source, documentation, safe configuration templates, and intentional assets. Do not synchronize secret environment files, credentials, private/signing keys, dependency directories, caches, logs, generated builds, IDE state, or machine-local runtime databases. Configure all secrets separately on every PC.

Warning: Production radio is remote. Never deploy, restart, or reconfigure it as part of workstation maintenance.

Architecture and operations are documented in `ARCHITECTURE.md`, `SERVER.md`, `GOOGLE_DRIVE.md`, `DJ_APP.md`, `CONTROL_APP.md`, `EBE_DOCK.md`, `TROUBLESHOOTING.md`, `BACKUP_RECOVERY.md`, and `ALLTHINGS140RADIO-PROJECT-RECORD.md`.
