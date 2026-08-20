# ALLTHINGS140 RADIO — Agents Onboarding

**Do not overwrite valuable existing instructions.** This file was created for this onboarding pass.

---

## ALLTHINGS140 RADIO — What Is It?

A 24/7 dubstep/bass internet radio station with four operational planes:
- **Plane 1:** Public listener & community (Cloudflare Pages + Tunnel)
- **Plane 2:** 24/7 broadcast authority (Oracle Cloud VM 1)
- **Plane 3:** Visuals & realtime server (Oracle Cloud VM 2)
- **Plane 4:** Management & workstation (desktop DJ, visuals app, bots)

---

## Project Memory Location

**`/home/ebmarah/Projects/ALLTHINGS140_PROJECT_CONTEXT/`**

Contains: PROJECT_MEMORY.md, ARCHITECTURE.md, APPLICATIONS.md, INFRASTRUCTURE.md,
CURRENT_STATUS.md, PATHS.md, DO_NOT_BREAK.md, OPEN_ISSUES.md, RECENT_CHANGES.md,
OPENCODE_START_HERE.md

Always read these before starting any task.

---

## Critical Directories

| Path | Purpose |
|------|---------|
| `/home/ebmarah/Projects/AllThings140Radio/` | Git repo, source code, version 2.3.2 |
| `/opt/allthings140radio-server/server.py` | Installed broadcast engine |
| `/var/lib/allthings140radio/` | Station SQLite DB, rotation state, catalog integrity |
| `/srv/allthings140radio/` | Emergency mirror (575 files), data |
| `/home/ebmarah/Videos/at140radio/desktop visuals/` | Stage + visual media |
| `/home/ebmarah/Projects/ALLTHINGS140_PROJECT_CONTEXT/` | Project memory documentation |

---

## Key Versions (Check Before Any Change)

| Component | Installed | Source | Status |
|-----------|-----------|--------|--------|
| Station server | 0.8.0 | `tools/server.py`, git main | ACTIVE PRODUCTION |
| Web frontend | 1.6.1 | `radio/`, git main | ACTIVE PRODUCTION |
| Visuals app | 0.1.30 | `visuals-app/`, Tauri v2 | ACTIVE DEV/WORKSTATION |
| Green staging | N/A | `visuals-green/`, Cloudflare Pages | FROZEN (cutover gates open) |
| Visuals realtime | 0.1.0-staging | `visuals-realtime/app.py` | ACTIVE STAGING |
| DJ app | 0.7.0 | `tools/dj_app.py`, git main | ACTIVE TOOL |
| Android app | 1.1.0 | `android/mobile-app/` | ACTIVE ARTIFACT (debug signed) |
| Discord bot | N/A | `discord-bot/` | STANDALONE (token needs rotation) |

---

## How to Determine the Latest App Version

1. **Check git log:** `git -C /home/ebmarah/Projects/AllThings140Radio log --oneline -5`
2. **Check VERSION.txt:** `cat /home/ebmarah/Projects/AllThings140Radio/VERSION.txt` (returns "2.3.2")
3. **Check installed:** Compare against `/opt/allthings140radio-server/`, `/opt/allthings140radio-dj/`, `visuals-app/package.json`
4. **Check Git tags/refs:** `git -C /home/ebmarah/Projects/AllThings140Radio tag`; `git -C /home/ebmarah/Projects/AllThings140Radio branch -a`
5. **Cross-reference** with CURRENT_STATUS.md and APPLICATIONS.md

**Rule of thumb:** Git history > installed binary > VERSION.txt. But always verify from actual runtime, not assumptions.

---

## Production / Staging / Development — How to Tell

| Environment | How to Identify | Key Differences |
|-------------|-----------------|-----------------|
| **Production** | Radio is live on `https://allthings140radio.online`; `stream.ebeinc.online/live.mp3` active; Oracle VM 1 services running; Cloudflare Pages live | Zero downtime; backup-first deployments; all services 100% online; catalog state must be HEALTHY |
| **Staging** | GREEN: `https://allthings140-visuals-green.pages.dev/`; visuals-realtime at `visuals-realtime-staging.allthings140radio.online`; not connected to production radio | Frozen at production baseline; cutover gates still open; media role separation; z-index fixes under test |
| **Development** | Local Tauri app (port 14340); local DJ app; local server.py runs; no Cloudflare deployment | No restrictions; can modify anything; but changes don't affect production until deployed |

**Rule:** When in doubt, assume PRODUCTION and follow the safeguards in DO_NOT_BREAK.md.

---

## What Must Not Be Blindly Overwritten

| Resource | Why | Safeguard |
|----------|-----|-----------|
| `tools/server.py` | AutoDJ engine; 24/7 station authority | Backup before any change; verify health; never deploy without rollback plan |
| `/var/lib/allthings140radio/station.db` | Source of truth for approvals, rotation, metadata | HEALTHY catalog state before changes; never modify without backup |
| Production visuals SHA-256 `4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32` | Locked baseline; changing without authorization corrupts production | Verify GREEN deploy hash; never change without explicit authorization |
| `/etc/allthings140radio/config.json` | Production secrets and config (mode 0600, root-owned) | Never expose or modify without understanding full impact; keep outside Git |
| `/etc/allthings140radio/support.env` | Stripe live keys (mode 0600, root-owned) | Never commit to Git; rotate in secure vault if exposed |
| Cloudflare Worker `ADMIN_ALERT_KEY` | Auth protection for takeover alerts | Set via `wrangler secret put` + redeploy worker; never set secret without deploy |
| Google Drive `at140drive:` | Master music library; 571+ tracks | Emergency mirror (575 files) is local fallback; never assume Drive-only uploads are playable |
| `discord-bot/.env` | Bot token (plaintext) | .gitignored; never commit; rotate in Developer Portal if exposed |

---

## before You Code — Checklist

- [ ] Read `AGENTS.md` (this file)
- [ ] Read `OPENCODE_START_HERE.md`
- [ ] Read relevant project-context documents (at minimum PROJECT_MEMORY.md)
- [ ] Inspect recent Git history (`git log --oneline -20`)
- [ ] Inspect current uncommitted work (`git status`, `git diff`)
- [ ] Verify which version is latest (VERSION.txt, git branch, remote tracking)
- [ ] Determine whether target is production, staging, or development
- [ ] Preserve unrelated working changes
- [ ] Make backups before destructive work (`cp ... .before-$(date +%Y%m%dT%H%M%SZ)`)
- [ ] Test changes before deployment (local health + public stream verification)
- [ ] Never assume historical architecture is still current
- [ ] Update project context after meaningful completed work

---

## Quick Health Checks (Before Any Modification)

| Check | Command | Must Pass |
|-------|---------|-----------|
| Radio local health | `curl -fsS http://127.0.0.1:14080/api/health` | HTTP 200, OK |
| Radio public stream | `curl -fsS https://stream.ebeinc.online/live.mp3` | HTTP 200/206, audio bytes > 0 |
| Status API | `curl -fsS https://status.ebeinc.online/api/public/status` | HTTP 200, online=True |
| Website | `curl -fsS https://allthings140radio.online` | HTTP 200, contains "AllThings140" |
| Catalog integrity | `cat /var/lib/allthings140radio/catalog-integrity.json` | status = HEALTHY |
| Emergency mirror | `ls /srv/allthings140radio/data/music/ | wc -l` | 575 files |
| Tailscale | `tailscale status` | Key hosts connected (allthings140radio-server active, allthings140-visuals-realtime connected) |
| Visuals production hash | Verify `4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32` | Matches (never change production without preservation) |

---

## Common Pitfalls (Learn from Past)

| Pitfall | Lesson | Prevention |
|---------|--------|------------|
| Deploying server.py without backup | No rollback possible; station could go silent | Always timestamp `cp ... .before-$(date +%Y%m%dT%H%M%SZ)` first |
| Ignoring catalog-integrity.json status | Reintroduce 88-track incident (approved tracks not playable) | Check HEALTHY/DEGRADED/CRITICAL before playlist changes |
| Changing Icecast credentials without relay update | Encoder loses auth → stream silence; passwords in process table | Update protected password files; verify relay auth; confirm `ps` no longer shows credentials |
| Deploying visuals without hash verification | Broken GREEN staging; production baseline corruption | Verify layout.json hash + remote manifest revision/hash match |
| Setting ADMIN_ALERT_KEY without worker redeploy | Endpoint unauthenticated; mass email trigger | `wrangler secret put` + `wrangler pages deploy`; test endpoint after |
| Skipping 30-min admission timer | Tracks become stranded in Drive (incident repeat) | Wait for timer; check catalog-integrity.json admission status |
| Committing .env / secrets to git | Credential exposure; rotation required | .gitignore covers .env; never commit secrets; rotate if exposed |
| Assuming Drive mount works from this workstation | Paths referenced but not directly verifiable | Check Oracle VM 1; use emergency mirror as verified fallback |
| Restarting server without local health check | Stream could go silent; no safety net | `curl -fsS http://127.0.0.1:14080/api/health` must pass first |

---

## Need to Know: Immediate Risks (Ranked)

| Rank | Risk | Location | Urgency |
|------|------|----------|---------|
| 1 | Discord bot token in plaintext `.env` | `discord-bot/.env` | HIGH — Regenerate in Developer Portal |
| 2 | Cloudflare Worker `ADMIN_ALERT_KEY` not provisioned | `radio/_worker.js` | MEDIUM — Set via `wrangler secret put` + redeploy |
| 3 | Android release signed with debug keystore | `android/mobile-app/app/build.gradle` | MEDIUM — Provide KEYSTORE_FILE etc. for GP |
| 4 | Extended visuals desktop soak incomplete | visuals workstation | LOW — Needs overnight+ soak |
| 5 | Google Drive mount status unverified | config references only | MEDIUM — Verify via Oracle VM 1 |
| 6 | Takeover restart-before-start scheduling needs longer soak | visuals-realtime staging | LOW — Needs longer real-time test |

---

## Key Contacts (read-only, no secrets)

- **Primary email:** allthings140radio@pm.me (Proton Mail; do not send emails during discovery)
- **Oracle VM 1:** `allthings140radio-server` (Tailscale MagicDNS; SSH via `tailscale ssh`)
- **Oracle VM 2:** `allthings140-visuals-realtime` (Tailscale; SSH with dedicated key)
- **Cloudflare:** `_worker.js` auth; `wrangler secret put` for secrets; Pages for deployment
- **Tailscale mesh:** `at140tail` firewalld zone; both `sshd` and `tailscaled` must remain enabled

---

*This file: `/home/ebmarah/Projects/AllThings140Radio/AGENTS.md`  
Created: 2026-08-16 (onboarding pass)  
Purpose: Compact onboarding for future coding agents*

*Always read PROJECT_MEMORY.md, DO_NOT_BREAK.md, and CURRENT_STATUS.md before starting any task.*