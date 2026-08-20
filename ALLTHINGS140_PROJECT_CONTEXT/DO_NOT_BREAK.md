# ALLTHINGS140 RADIO — DO NOT BREAK

## Critical Safeguards — Future AI Agents Must Verify Before Modifying

This file lists the absolute critical safeguards. **Any modification to these systems must be verified before deployment.** When in doubt, stop and verify.

---

### 1. Never Deploy server.py Without a Timestamped Backup

| What | Why | Verification |
|------|-----|-------------|
| **Fact** | `tools/server.py` is the authoritative broadcast engine. It owns the AutoDJ timeline, SQLite catalog, FFmpeg encoding, Icecast integration, and the public status API. A regression could silence the 24/7 station. | **Before any deployment:**<br>1. Create timestamped backup: `cp /opt/allthings140radio-server/server.py /opt/allthings140radio-server/server.py.before-$(date +%Y%m%dT%H%M%SZ)`<br>2. Verify backup exists and is readable<br>3. After deployment: `curl -fsS http://127.0.0.1:14080/api/health` must return OK<br>4. Verify public stream: `curl -fsS https://stream.ebeinc.online/live.mp3` must return audio<br>5. If either check fails: rollback from backup immediately |

**Historical:** August 15, 2026 remediation had 15+ timestamped backups of server.py retained; zero needed because all tests passed, but the pattern was essential.

---

### 2. Never Restart allthings140radio-server Without Verifying Local Health First

| What | Why | Verification |
|------|-----|-------------|
| **Fact** | Restarting the server terminates and restarts the AutoDJ process, FFmpeg encoder, and Icecast connection. If the new binary has a bug, the stream could go silent. | **Before restart:**<br>1. `curl -fsS http://127.0.0.1:14080/api/health` — must return JSON with `ok` or equivalent<br>2. Verify the health endpoint responds before stopping the service<br>3. After restart: repeat local health check + public stream verification |

**Historical:** The August 15, 2026 remediation passed zero service restarts on production VMs; all fixes deployed to Cloudflare edge or staged locally.

---

### 3. Never Verify Public Stream Without Confirming Local Health First

| What | Why | Verification |
|------|-----|-------------|
| **Fact** | The public stream (`stream.ebeinc.online/live.mp3`) goes through Cloudflare Tunnel → Icecast → loopback. A change that fixes local health but breaks the tunnel could leave listeners with a dead stream. | **Sequence matters:**<br>1. Verify local health first (`127.0.0.1:14080/api/health` + `icecast` status)<br>2. Then verify public stream (`stream.ebeinc.online/live.mp3`)\n>3. Both must pass before considering change stable<br>4. If public stream fails after local health passes: investigate Tunnel, not server |

**Historical:** The August 13-15 remediation followed this exact pattern; all changes verified both local and public before marking complete.

---

### 4. Never Ignore the catalog-integrity.json Status

| What | Why | Verification |
|------|-----|-------------|
| **Fact** | `/var/lib/allthings140radio/catalog-integrity.json` drives the catalog state (HEALTHY/DEGRADED/CRITICAL) and the 30-minute playback-admission timer. Ignoring its status could reintroduce the August 15 incident where 88 tracks uploaded to Drive were not visible locally. | **Before making playlist changes:**<br>1. Check `catalog-integrity.json` status field<br>2. If HEALTHY: proceed (but still follow other safeguards)<br>3. If DEGRADED/CRITICAL: resolve underlying issues before playlist changes<br>4. Never add catalog admission without the 30-min timer having fired |

**Historical:** The August 15 incident occurred because cache admission bypassed the integrity system; the recovery deployed the read-only integrity monitor and 30-min timer to prevent recurrence.

---

### 5. Never Change Icecast Credentials Without Reconfiguring the Auth Relay

| What | Why | Verification |
|------|-----|-------------|
| **Fact** | The loopback auth relay on port 14001 (`icecast://source:local-relay@127.0.0.1:14001/live.mp3`) reads real source passwords from protected files and injects them into HTTP Basic auth headers for Icecast. Real passwords never appear in `ps` argv. Changing Icecast credentials without updating the relay breaks the encoder → Icecast connection. | **Before changing Icecast credentials:**<br>1. Update the protected password file(s) the relay reads from<br>2. Verify the relay can still authenticate<br>3. Verify `ps` no longer shows encoder credentials (confirm relay is working)<br>4. After update: test encoder connection and stream continuity |

**Historical:** The relay was specifically designed to prevent passwords appearing in process tables; breaking this pattern exposes secrets.

---

### 6. Never Treat Google Drive as the Only Source of Truth Without Checking the Emergency Mirror

| What | Why | Verification |
|------|-----|-------------|
| **Fact** | The August 15, 2026 incident proved that 88 tracks uploaded to Google Drive were not visible to local playback due to cache admission decoupling. All 571 catalog filenames existed in Drive, but the emergency mirror and hot cache could only see 487 (emergency) + 50 (hot cache) = 537. | **Before relying solely on Drive:**<br>1. Check emergency mirror file count: `ls /srv/allthings140radio/data/music/ | wc -l` (should be 575)<br>2. Check hot cache count: `ls /srv/allthings140radio/cache/READY/ | wc -l`<br>3. Verify catalog-integrity.json status is HEALTHY<br>4. Acknowledge the 30-min playback-admission timer prevents future stranded tracks<br>5. Never assume Drive-only uploads are immediately playable |

**Historical:** The incident resulted in 88 approved tracks temporarily without resolvable playback audio; all were restored from Drive into the emergency mirror via `tools/recover_playback_assets.py`.

---

### 7. Never Deploy Visuals Changes Without Verifying GREEN layout.json Hash Matches Remote Manifest

| What | Why | Verification |
|------|-----|-------------|
| **Fact** | Production visuals baseline SHA-256: `4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32`. The GREEN staging deployment pipeline verifies that the remote manifest's `layoutRevision` and `layoutHash` match the local published layout before accepting the deployment. A mismatch aborts the deploy. Deploying without verification could push broken visuals to the GREEN staging URL, and if the production baseline is accidentally changed, the entire visual system appearance degrades. | **Before deploying to GREEN staging:**<br>1. After publishing: verify local layout.json hash<br>2. Fetch remote manifest: `curl -fsS https://allthings140-visuals-green.pages.dev/layout.json?verify={revision}`<br>3. Confirm `layoutRevision` and `layoutHash` match local values<br>4. If mismatch: investigate and fix before considering deploy complete<br>5. Production `/visuals/` SHA-256 must not change without explicit authorization |

**Historical:** The deployment pipeline includes this exact verification step (see August 15 remediation: "Remote manifest mismatch (expected revision/hash X/Y, got A/B) — return Err").

---

### 8. Never Modify the ADMIN_ALERT_KEY Without Re-Deploying the Cloudflare Worker

| What | Why | Verification |
|------|-----|-------------|
| **Fact** | The Cloudflare Edge Worker `_worker.js` authenticates `POST /api/public/takeover-alert` via Bearer token check: `token must match env.ADMIN_ALERT_KEY || env.TAKEOVER_ALERT_KEY || env.ADMIN_TOKEN`. Setting the secret in Cloudflare Dashboard/CLI without redeploying the worker leaves the endpoint unauthenticated (anyone can trigger mass email notifications). | **Before changing the secret:**<br>1. Set the new secret via `npx wrangler secret put ADMIN_ALERT_KEY` (or equivalent Cloudflare Dashboard action)<br>2. Redeploy the worker: `npx wrangler pages deploy visuals-green-pages-dist --project-name allthings140-visuals-green --branch staging --commit-dirty=true`<br>3. Test the endpoint: `curl -X POST -H "Authorization: Bearer {new_key}" ...` must return `{ok: true}`<br>4. If the key is set but the worker is not redeployed: the old worker process still uses the old key; the new secret only takes effect after deploy<br>**After deploy:** verify both old and new tokens work (or old tokens are invalidated) |

**Historical:** The August 15 remediation added the auth check but ADMIN_ALERT_KEY was not yet provisioned; the known open issue remains until the secret is set and the worker redeployed.

---

### 9. Never Skip the 30-Minute Playback-Admission Timer

| What | Why | Verification |
|------|-----|-------------|
| **Fact** | A systemd timer (or equivalent) enforces a 30-minute minimum wait after a track is uploaded to Google Drive before it can be admitted to the local cache/playback. Skipping this timer allows tracks to become stranded (uploaded to Drive but never admitted to local playback), recreating the August 15 incident pattern. | **Before admitting newly uploaded tracks:**<br>1. Verify the 30-min timer has fired for the track in question<br>2. Check `catalog-integrity.json` for the track's admission status<br>3. If the track was recently uploaded (within 30 min): wait for the timer<br>4. Never force-admit a track before the timer elapses, even if the file exists in Drive |

**Historical:** The 30-min timer was introduced specifically after the August 15 incident where tracks uploaded to Drive were not admitted to local playback quickly enough; the timer prevents future occurrences.

---

### 10. Never Commit .env Files or Secrets to Git

| What | Why | Verification |
|------|-----|-------------|
| **Fact** | The `.env` file in `discord-bot/` contains the bot token in plaintext. The `visuals-app/` has a `.env.example` that warns "create protected runtime configuration from .env.example; never commit it". The project `.gitignore` should ignore all `.env` files and credential files. Accidental commitment of secrets requires rotation. | **Before any git commit:**<br>1. Run `git status` and verify no `.env` files, key files, or credential files are staged<br>2. Verify `.gitignore` covers all secret locations<br>3. If a secret was accidentally committed: rotate it immediately (Discord token in Developer Portal; Cloudflare secrets via wrangler; Icecast passwords in protected files)<br>4. After rotation: update all references; confirm no secrets in git history |

**Historical:** The Discord bot `.env` is properly gitignored, but the token should still be rotated if ever shared or exposed in chat logs.

---

## Violation Response Pattern

If any of the above safeguards are inadvertently violated:

1. **Stop** — Immediately cease the operation that violated the safeguard
2. **Assess** — Determine the scope and impact of the violation
3. **Rollback** — If applicable, restore from the timestamped backup (for #1, #2, #4)
4. **Report** — Document the violation in `OPEN_ISSUES.md` and notify the team
5. **Rotate** — If secrets were exposed, rotate them (Discord token, Cloudflare secrets, Icecast passwords)
6. **Fix** — Apply the root cause fix and verify
7. **Recover** — Re-test the full playback path: local health → public stream → all listener endpoints

---

## Verification Commands Cheat Sheet

| Safeguard | Verification Command |
|-----------|---------------------|
| Backup before server deploy | `ls /opt/allthings140radio-server/server.py.before-*` |
| Local health check | `curl -fsS http://127.0.0.1:14080/api/health` |
| Public stream verification | `curl -fsS https://stream.ebeinc.online/live.mp3` (should return audio, HTTP 200/206) |
| Catalog integrity status | `cat /var/lib/allthings140radio/catalog-integrity.json` |
| Emergency mirror file count | `ls /srv/allthings140radio/data/music/ | wc -l` (should be 575) |
| Hot cache file count | `ls /srv/allthings140radio/cache/READY/ | wc -l` |
| Google Drive mount | `df -h /mnt/allthings140radio-dride` (on Oracle VM 1) |
| Icecast relay auth test | `curl -fsS http://127.0.0.1:14001/` (behavior depends on config) |
| Visuals production hash | `sha256sum /path/to/production/visuals/asset` (should match `4ca1a32e...`) |
| GREEN deploy hash verification | `curl -fsS https://allthings140-visuals-green.pages.dev/layout.json?verify={rev}` |
| ADMIN_ALERT_KEY provisioning | `npx wrangler secret list` (should list ADMIN_ALERT_KEY) |
| 30-min timer check | Check systemd timer status: `systemctl status allthings140radio-playback-admission.timer` |
| .env git status | `git status` + `git diff --cached` (no .env files staged) |
| Tailscale status | `tailscale status` |

---

## Emergency Rollback Sequence

```
1. Identify which safeguard was violated
2. If server.py deployed: 
   cp /opt/allthings140radio-server/server.py.before-TIMESTAMP /opt/allthings140radio-server/server.py
   systemctl restart allthings140radio-server
   curl -fsS http://127.0.0.1:14080/api/health && curl -fsS https://stream.ebeinc.online/live.mp3
3. If Cloudflare worker auth broken:
   npx wrangler secret put ADMIN_ALERT_KEY  (set the correct key)
   npx wrangler pages deploy visuals-green-pages-dist --project-name allthings140-visuals-green --branch staging --commit-dirty=true
4. If catalog integrity issue:
   tools/recover_playback_assets.py --interactive (or per the documented procedure)
5. If Discord token exposed:
   Regenerate in Discord Developer Portal; update discord-bot/.env (gitignored, don't commit!)
6. Verify all checks pass from the verification cheat sheet above
```

---

## Things That Must NEVER Happen (Summary)

| # | Violation | Consequence |
|---|-----------|-------------|
| 1 | Deploy server.py without backup | No rollback possible; station could go silent indefinitely |
| 2 | Restart server without local health check | Stream could go silent; no safety net |
| 3 | Skip catalog integrity check | Reintroduce the 88-track incident (approved tracks not playable) |
| 4 | Change Icecast credentials without relay update | Encoder loses auth → stream silence; real passwords potentially exposed in process table |
| 5 | Rely on Drive without emergency mirror | Stranded tracks (88-track incident repeat) |
| 6 | Deploy visuals without hash verification | Broken GREEN staging; production baseline corruption |
| 7 | Set ADMIN_ALERT_KEY without worker redeploy | Takeover alerts unauthenticated; mass email trigger |
| 8 | Skip 30-min admission timer | Tracks become stranded in Drive (incident repeat) |
| 9 | Commit .env / secrets to git | Credential exposure; rotation required; potential production impact |
| 10 | Ignore ADMIN_ALERT_KEY not provisioned | `/api/public/takeover-alert` unauthenticated; anyone can trigger subscriber emails |

---

## This File Must Not Be Deleted or Overwritten

This file is part of the project memory at `/home/ebmarah/Projects/ALLTHINGS140_PROJECT_CONTEXT/DO_NOT_BREAK.md`. Future OpenCode sessions must read this file before making any significant changes to the ALLTHINGS140 Radio ecosystem. Do not delete, rename, or overwrite this file.

If the content needs updating after verified changes, create a new version with a timestamp and retain the previous version for audit trails.