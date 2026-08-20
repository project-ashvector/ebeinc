# ALLTHINGS140 Radio — 24/7 Disaster Recovery & Incident Runbook

**Author:** Antigravity (Google Deepmind)  
**Date:** 2026-08-17  
**Scope:** 24/7 Zero-Downtime Recovery Procedures for Broadcast, Visuals, Cloudflare, and Workstation  

---

## 1. Quick Emergency Triage Matrix

| Incident | Symptom | First Command to Run | Expected Resolution Time |
|---|---|---|---|
| **Audio Silence** | `stream.ebeinc.online` empty bytes | `tailscale ssh ebmarah@allthings140radio-server "sudo systemctl restart allthings140radio-server"` | < 30 seconds |
| **AutoDJ Freeze** | Track progress stuck at 0:00 | `tailscale ssh ebmarah@allthings140radio-server "sudo systemctl restart allthings140radio-cache"` | < 15 seconds |
| **Public Stream Down** | DNS / 502 Bad Gateway | `tailscale ssh ebmarah@allthings140radio-server "sudo systemctl restart cloudflared"` | < 20 seconds |
| **VM 1 Rebooted** | All VM 1 services down | Run automated healthcheck `allthings140-hub health` (systemd restarts automatically) | Automatic |
| **VM 2 Rebooted** | Realtime WebSockets offline | `tailscale ssh ebmarah@allthings140-visuals-realtime "sudo systemctl status allthings140-visuals-realtime"` | Automatic |
| **Bad Site Deploy** | Web app error or broken CSS | Open Hub → Website → Cloudflare Deploy → Click `⏪ Instant Rollback` | < 10 seconds |
| **Hub UI Freeze** | Desktop GUI unresponsive | `pkill -f allthings140-hub && allthings140-hub` (Radio stream is unaffected!) | < 5 seconds |
| **Visuals App Stuck** | Desktop visualizer frozen | Launch Visuals Workstation v0.1.37 (async tasks prevent freezes) | < 10 seconds |

---

## 2. Step-by-Step Incident Recovery Procedures

### Incident 1: Public Audio Stream Goes Silent
1. Check stream response:
   ```bash
   curl -I https://stream.ebeinc.online/live.mp3
   ```
2. Verify Oracle VM 1 loopback API:
   ```bash
   tailscale ssh ebmarah@allthings140radio-server "curl -fsS http://127.0.0.1:14080/api/health"
   ```
3. If Icecast or Server is stopped, execute guarded restart:
   ```bash
   tailscale ssh ebmarah@allthings140radio-server "sudo systemctl restart icecast2 allthings140radio-server"
   ```
4. Verify audio bytes flowing:
   ```bash
   curl -s --range 0-10000 https://stream.ebeinc.online/live.mp3 | wc -c
   # Must return 10001 bytes
   ```

---

### Incident 2: AutoDJ Stops Advancing / Missing Track Error
1. Check Catalog Integrity state:
   ```bash
   tailscale ssh ebmarah@allthings140radio-server "cat /var/lib/allthings140radio/catalog-integrity.json"
   ```
2. If `status != "HEALTHY"`, trigger emergency mirror fallback:
   ```bash
   tailscale ssh ebmarah@allthings140radio-server "sudo python3 /opt/allthings140radio-server/tools/recover_playback_assets.py --apply"
   ```
3. Restart AutoDJ cache daemon:
   ```bash
   tailscale ssh ebmarah@allthings140radio-server "sudo systemctl restart allthings140radio-cache"
   ```

---

### Incident 3: Cloudflare Website Broken / Bad Deployment Rollback
1. Open **ALLTHINGS140 Hub** → **WEBSITE & CMS** → **Cloudflare Deploy**.
2. Select the last known good deployment in the table.
3. Click **`⏪ Instant Rollback`**.
4. The Hub restores the timestamped snapshot tarball from `backups/` and triggers a clean re-deploy to Cloudflare Pages.
5. Verify live site:
   ```bash
   curl -fsS https://allthings140radio.online | grep "ALLTHINGS140"
   ```

---

### Incident 4: Desktop Hub or Workstation Crash
1. **Critical Fact:** The Hub is NOT in the live audio or broadcast chain. If the Hub crashes or is closed, 24/7 radio broadcasting continues uninterrupted on Oracle Cloud VM 1.
2. Restart the Hub from application menu or terminal:
   ```bash
   allthings140-hub
   ```
3. The Hub reconnects non-blockingly to all telemetry streams and recovers full operational observability within 2 seconds.

---

### Incident 5: Tailscale Mesh Network Disconnect
1. If Tailscale drops on the local workstation:
   ```bash
   sudo systemctl restart tailscaled
   tailscale status
   ```
2. Public listeners on `allthings140radio.online` and `stream.ebeinc.online` remain 100% unaffected because Cloudflare Tunnels route directly to Oracle Cloud.
