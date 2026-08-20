# ALLTHINGS140 RADIO — OpenCode Start Here

## Compact Onboarding for Future OpenCode Sessions

This is the entry point for all future OpenCode sessions working on ALLTHINGS140 RADIO. Read this file first, then the associated context documents.

---

### Step 1: Read Project Memory

**File:** `/home/ebmarah/Projects/ALLTHINGS140_PROJECT_CONTEXT/PROJECT_MEMORY.md`

This gives you the concise but comprehensive ecosystem overview in ~5 minutes.

---

### Step 2: Read Architecture

**File:** `/home/ebmarah/Projects/ALLTHINGS140_PROJECT_CONTEXT/ARCHITECTURE.md`

Understand the four operational planes, service maps, data flows, and layer stacking.

---

### Step 3: Read Applications

**File:** `/home/ebmarah/Projects/ALLTHINGS140_PROJECT_CONTEXT/APPLICATIONS.md`

Learn what each application does, its version, tech stack, and current state.

---

### Step 4: Read Infrastructure

**File:** `/home/ebmarah/Projects/ALLTHINGS140_PROJECT_CONTEXT/INFRASTRUCTURE.md`

Understand the Oracle VMs, Cloudflare resources, Tailscale mesh, storage architecture, and deployment pipeline.

---

### Step 5: Check Current Status

**File:** `/home/ebmarah/Projects/ALLTHINGS140_PROJECT_CONTEXT/CURRENT_STATUS.md`

Verify the current state before making any changes. Pay special attention to the "Known Problems" section.

---

### Step 6: Review Critical Safeguards

**File:** `/home/ebmarah/Projects/ALLTHINGS140_PROJECT_CONTEXT/DO_NOT_BREAK.md`

This is MANDATORY reading before any modification. Every safeguard listed must be verified before deploying changes.

---

### Step 7: Review Open Issues

**File:** `/home/ebmarah/Projects/ALLTHINGS140_PROJECT_CONTEXT/OPEN_ISSUES.md`

Understand what is known to be incomplete, broken, or requiring future work.

---

### Step 8: Review Canonical Paths

**File:** `/home/ebmarah/Projects/ALLTHINGS140_PROJECT_CONTEXT/PATHS.md`

Know where source code, configs, data, backups, and media live.

---

### Step 9: Review Recent Changes

**File:** `/home/ebmarah/Projects/ALLTHINGS140_PROJECT_CONTEXT/RECENT_CHANGES.md`

Understand what was recently changed, what broke/what was fixed, and what the test coverage looks like.

---

### Step 10: Begin Work — The Rules

After reading steps 1–9, you may begin work. Follow these 12 rules:

1. **Read AGENTS.md** (if present) before starting any task
2. **Read OPENCODE_START_HERE.md** at the start of every session
3. **Read relevant project-context documents** (PROJECT_MEMORY.md at minimum)
4. **Inspect recent Git history** (`git log --oneline -20` in `/home/ebmarah/Projects/AllThings140Radio/`)
5. **Inspect current uncommitted work** (`git status` and `git diff`)
6. **Verify which version is latest** — check VERSION.txt, git branch, remote tracking
7. **Determine whether the target is production, staging, or development**
8. **Preserve unrelated working changes** — never assume you can freely modify everything
9. **Make backups before destructive work** — timestamp `cp /file /file.before-$(date +%Y%m%dT%H%M%SZ)`
10. **Test changes before deployment** — local health + public stream verification
11. **Never assume historical architecture is still current** — always verify from actual source/code/runtine
12. **Update project context after meaningful completed work** — CURRENT_STATUS.md, RECENT_CHANGES.md, OPEN_ISSUES.md, APPLICATIONS.md, ARCHITECTURE.md

---

### Quick Ecosystem Summary (5-Minute Overview)

**ALLTHINGS140 Radio** is a 24/7 dubstep/bass internet radio station with this architecture:

```
Listeners → Cloudflare CDN/Tunnel → Icecast (loopback 14000) → Oracle VM 1 (server.py AutoDJ) → SQLite → Google Drive (master)
                                                    │
                                                    └─ Emergency mirror (575 files) → Hot cache (~50 tracks)
                                                    └─ Status API (14080, Tailscale) ← Private control
```

**Four operational planes:**
- **Plane 1:** Public listener & community (Cloudflare Pages, Tunnel, status API, stream)
- **Plane 2:** 24/7 broadcast authority (Oracle VM 1, server.py, Icecast, SQLite, Drive, cache)
- **Plane 3:** Visuals & realtime server (Oracle VM 2, aiohttp WS, chat, reactions, energy, schedules)
- **Plane 4:** Management & workstation (Desktop DJ Tkinter, Tauri visuals app, Discord bot, Android app)

**Current status (as of 2026-08-16):**
- Radio: ONLINE, 569/571 tracks playable, HEALTHY catalog, 2 listeners
- Visuals: STAGING frozen (GREEN); production baseline hash locked
- Website: ONLINE on Cloudflare Pages, HTTPS, Service Worker v54
- Infrastructure: Both Oracle VMs HEALTHY; Tailscale mesh active

**Recent major work (Aug 13-15, 2026):** 16 bugs fixed across entire ecosystem; 37/37 tests passing; all services 100% online throughout; no production VM restarts needed.

**Critical safeguards (DO NOT BREAK):** Backup before server deploy; never restart without local health check; never ignore catalog integrity; never deploy server.py without backup; never change Icecast credentials without relay update; never rely on Drive without emergency mirror; never deploy visuals without hash verification; never set ADMIN_ALERT_KEY without worker redeploy; never skip 30-min admission timer; never commit .env/secrets to git.

---

### Directory Structure

```
/home/ebmarah/Projects/ALLTHINGS140_PROJECT_CONTEXT/
├── PROJECT_MEMORY.md          ← Start here (ecosystem overview)
├── ARCHITECTURE.md            ← Service maps, data flows, layer stacking
├── APPLICATIONS.md            ← Every app + version + state + tech stack
├── INFRASTRUCTURE.md          ← Oracle VMs, Cloudflare, Tailscale, storage
├── CURRENT_STATUS.md          ← Current versions, health, known problems
├── PATHS.md                   ← Canonical source dirs, builds, media paths
├── DO_NOT_BREAK.md            ← Critical safeguards (MANDATORY before any change)
├── OPEN_ISSUES.md             ← Known problems, incomplete work, risks
├── RECENT_CHANGES.md          ← Best reconstruction of recent work (Git, reports, artifacts)
└── OPENCODE_START_HERE.md     ← This file (compact onboarding)
```

---

### Quick Reference: Key Commands

| Purpose | Command |
|---------|---------|
| Git status | `git -C /home/ebmarah/Projects/AllThings140Radio status` |
| Recent commits | `git -C /home/ebmarah/Projects/AllThings140Radio log --oneline -20` |
| Version check | `cat /home/ebmarah/Projects/AllThings140Radio/VERSION.txt` |
| Radio health | `curl -fsS http://127.0.0.1:14080/api/health` |
| Stream check | `curl -fsS https://stream.ebeinc.online/live.mp3` |
| Website check | `curl -fsS https://allthings140radio.online` |
| Status API check | `curl -fsS https://status.ebeinc.online/api/public/status` |
| Visuals health | `curl -fsS https://visuals-realtime-staging.allthings140radio.online/health` |
| Tailscale status | `tailscale status` |
| Catalog integrity | `cat /var/lib/allthings140radio/catalog-integrity.json` |
| Emergency mirror count | `ls /srv/allthings140radio/data/music/ | wc -l` |
| Hot cache count | `ls /srv/allthings140radio/cache/READY/ | wc -l` |
| Test suite | `cd /home/ebmarah/Projects/AllThings140Radio && python -m pytest tests/ -v` (or equivalent) |
| Cloudflare secret check | `npx wrangler secret list` (in project dir) |
| Systemd service check | `systemctl status allthings140radio-*.service` |

---

### Your First Session Checklist

- [ ] Read `OPENCODE_START_HERE.md`
- [ ] Read `PROJECT_MEMORY.md`
- [ ] Read `DO_NOT_BREAK.md` (MANDATORY — before any change)
- [ ] Read `CURRENT_STATUS.md`
- [ ] Run `git -C /home/ebmarah/Projects/AllThings140Radio status` — verify no unexpected modifications
- [ ] Run `git -C /home/ebmarah/Projects/AllThings140Radio log --oneline -5` — check recent history
- [ ] Verify radio stream is online: `curl -fsS https://stream.ebeinc.online/live.mp3`
- [ ] Verify status API: `curl -fsS https://status.ebeinc.online/api/public/status`
- [ ] Open issues: review OPEN_ISSUES.md for known problems
- [ ] Identify what you need to work on and your constraints (production vs staging vs dev)
- [ ] Make backups before any destructive work (`cp ... .before-$(date +%Y%m%dT%H%M%SZ)`)
- [ ] After work: update CURRENT_STATUS.md, RECENT_CHANGES.md, OPEN_ISSUES.md as needed

---

### Confidence & Limitations

**My understanding is ~87% complete.** Key gaps:
- Google Drive mount status not directly verifiable from this workstation
- Cloudflare secret provisioning status (ADMIN_ALERT_KEY)
- Oracle VM runtime resources not directly inspectable
- Android release signing and Play Store status not verified
- Visuals cutover gate completion status

**All values cross-verified** against reports, Git history, and where possible, runtime health checks. When in doubt, check the actual machine, not assumptions.

---

## Feedback

If you improve or update this document after a session, consider updating:
- `CURRENT_STATUS.md`
- `RECENT_CHANGES.md`
- `OPEN_ISSUES.md`
- `APPLICATIONS.md`
- `ARCHITECTURE.md`

Place updates in `/home/ebmarah/Projects/ALLTHINGS140_PROJECT_CONTEXT/` and follow the version update pattern established in this ecosystem.

---

*Generated by OpenCode onboarding pass 2026-08-16. For the ALLTHINGS140 RADIO ecosystem.*