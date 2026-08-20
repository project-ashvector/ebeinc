# ALLTHINGS140 Hub — Operator Guide & Safety Manual

**Audience:** Station Operators, DJs, Curators, Community Managers, and Engineers  
**Application Version:** 1.2.0  
**Station Authority:** 24/7 dubstep/bass internet radio

---

## 1. Start Here — 24/7 Radio Independence

> ### ⚠️ THE GOLDEN OPERATOR RULE
> **Closing this Hub application does NOT stop the radio station.**
> The live stream runs 24/7 on dedicated cloud infrastructure (**Oracle VM 1**). You can open and close the Hub at any time with **zero risk** to the broadcast.

* **What the Hub Controls:** Telemetry monitoring, local app launching, AI coding prompts, website CMS management, and guarded Cloudflare deployments.
* **What the Hub Does NOT Control Directly:** Audio playback streams continuously from Oracle VM 1 to Cloudflare and listener devices.
* **Workstation Role:** This workstation provides operations management. Live listeners continue hearing audio even if this computer is powered off.

---

## 2. The Four Operational Planes

```
┌─────────────────────────────────────────────────────────────┐
│ PLANE 1: PUBLIC LISTENER & COMMUNITY                       │
│ • Website (allthings140radio.online) on Cloudflare Pages   │
│ • Stream Relay (stream.ebeinc.online/live.mp3)             │
│ • Android Mobile App (Media3 ExoPlayer background audio)   │
│ • Discord Community Bot (/nowplaying, live takeover alerts)│
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ Cloudflare Tunnel & CDN
┌─────────────────────────────────────────────────────────────┐
│ PLANE 2: 24/7 BROADCAST AUTHORITY (Oracle VM 1)             │
│ • Station Engine: tools/server.py (AutoDJ rotation)         │
│ • Icecast 2 Streaming Audio Server (Port 14080)             │
│ • Hot Cache & SQLite Database (/var/lib/allthings140radio/) │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ Tailscale Encrypted Mesh
┌─────────────────────────────────────────────────────────────┐
│ PLANE 3: VISUALS & REALTIME SERVER (Oracle VM 2)            │
│ • Visuals Realtime Server (visuals-realtime/app.py)         │
│ • WebSockets: Audience presence, room energy, reactions     │
│ • Cloudflare Tunnel to visuals-realtime-staging             │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ Tailscale MagicDNS
┌─────────────────────────────────────────────────────────────┐
│ PLANE 4: WORKSTATION & MANAGEMENT (This Computer)           │
│ • ALLTHINGS140 Hub (Desktop Operations Console)             │
│ • Desktop DJ App (tools/dj_app.py)                          │
│ • Visuals Show-Control Workstation (Tauri v2 / Rust)        │
│ • AI Coding Agents & Emergency Music Mirror (575 files)     │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. The 4-Tier Safety Level System

Every interactive operation is color-coded so operators know the exact scope of risk:

### 🟢 Tier 1: GREEN (Safe / Read-Only)
* **What it does:** Telemetry reads, health diagnostic scans, log viewing, opening local folders, copying prompts.
* **Impact:** 100% read-only. Zero modifications to local data or production streams.

### 🟡 Tier 2: YELLOW (Local Workspace Change)
* **What it does:** Saving local Hub preferences, creating local backup archives, editing website CMS drafts (`sponsors.json`, `partners.json`).
* **Impact:** Modifies local workspace files on this computer only. Live website and production stream are NOT touched until a deployment is manually promoted.

### 🟠 Tier 3: ORANGE (Remote Service Change)
* **What it does:** Restarting systemd services on Oracle VM 1 or VM 2, executing the 10-step safe update wizard.
* **Impact:** May cause a brief 1–2 second audio reconnect. Icecast relay buffers will keep listeners connected.
* **Guard:** Always prompts with a structured pre-flight impact verification dialog.

### 🔴 Tier 4: RED (Production / Destructive)
* **What it does:** Promoting a Cloudflare preview to live `allthings140radio.online`, deleting media files from disk, or restoring a backup snapshot.
* **Impact:** Direct changes to public live site or local file removal.
* **Guard:** Enforces multi-point impact confirmation detailing "What it touches", "Expected impact", and "Rollback plan".

---

## 4. Operational Procedures & Recovery

### Procedure A: Safely Updating an Application (10-Step Protocol)
1. Navigate to **Apps & Projects → Update Center**.
2. Select target component in the **Select Target Application** dropdown.
3. Click **🚀 Run Safe Update Wizard**.
4. The wizard automatically:
   - Verifies unit and integration test suite.
   - Creates an immutable `.tar.gz` snapshot in `backups/` BEFORE modifying files.
   - Compiles release artifacts.
   - Deploys first to Staging (e.g. Green Web Stage).
   - Signals background service reload.
   - Verifies live endpoint health.
   - Saves an engineering audit record in `handoffs/`.

### Procedure B: Managing Website Content (Zero-Code CMS)
1. Open **Website & CMS → Sponsors / Partners / Takeovers / Announcements / Roadmap**.
2. Click **➕ Add** or double-click any row to edit.
3. Save changes. Local JSON is updated immediately.
4. Navigate to **Website & CMS → Cloudflare Deployment**.
5. Click **🚀 Create Preview Deployment**.
6. Review preview link with **🌐 Open Selected Preview**.
7. Once verified, click **⭐ Promote to Production**.

### Procedure C: Emergency Audio Mirror Recovery
* **Master Mirror Location:** `/srv/allthings140radio/data/music/` (575 verified playable MP3 tracks).
* **When to use:** If Google Drive connection degrades or remote storage is unavailable.
* **Action:** The station server on Oracle VM 1 automatically falls back to local hot cache and emergency mirror tracks.

---

## 5. Troubleshooting Matrix

| Symptom | Probable Cause | Action |
|---------|----------------|--------|
| Public Stream shows OFFLINE | Oracle VM 1 service stopped or tunnel severed | Check **Operations → Servers**; verify `allthings140radio-server.service` |
| Catalog status is DEGRADED | Some approved tracks missing from local hot cache | AutoDJ continues playing available tracks; run track verifier in background |
| Website preview not loading | Cloudflare Pages build in progress | Check deployment table status in **Cloudflare Deployment** view |
| App Card "Launch" disabled | Component is a server service or background daemon | Click **💻 Terminal** or **🤖 Work On App** to inspect |
