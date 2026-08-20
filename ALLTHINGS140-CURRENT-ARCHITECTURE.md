# ALLTHINGS140 Radio — Current System Architecture & Decoupling

**Author:** Antigravity (Google Deepmind)  
**Date:** 2026-08-17  
**Scope:** Decoupled Architecture across Broadcast, Web, Visuals, and Operations Control Planes  

---

## 1. Decoupled Architecture Overview

The system is partitioned into two completely independent dependency paths:
1. **The Live Listener Playback Chain:** High-availability, zero-dependency 24/7 broadcast flow.
2. **The Operations & Management Control Plane:** Workstation-driven observability, CMS, and deployment tooling.

```
========================================================================================
                        PATH 1: LIVE LISTENER PLAYBACK CHAIN
                   (Zero dependencies on workstation or desktop apps)
========================================================================================

                 [ GLOBAL LISTENERS (Web / Android / Car) ]
                                    │
                                    │ HTTPS (Audio Stream / PWA)
                                    ▼
                 [ CLOUDFLARE EDGE (Pages + Anycast CDN) ]
                       allthings140radio.online
                                    │
                                    │ Cloudflare Tunnel (stream.ebeinc.online)
                                    ▼
                 ┌──────────────────────────────────────┐
                 │       ORACLE CLOUD VM 1 (Plane 2)    │
                 │                                      │
                 │   [ Icecast 2 Streaming Server ]     │
                 │                 ▲                    │
                 │                 │ MP3 Stream         │
                 │   [ AutoDJ Engine (server.py) ]      │
                 │                 ▲                    │
                 │    ┌────────────┴─────────────┐      │
                 │    │                          │      │
                 │ [Hot Cache (RAM)]   [575 Audio Files]│
                 │ [SQLite station.db] [Integrity Check]│
                 └──────────────────────────────────────┘


========================================================================================
                   PATH 2: HUB OPERATIONS & MANAGEMENT CONTROL PLANE
                      (Safe to close, restart, crash, or update)
========================================================================================

             [ ALLTHINGS140 HUB (v1.1.0 — Zorin OS Workstation) ]
             ┌──────────────────────────────────────────────────┐
             │ • Telemetry Dashboard (Live Polling)            │
             │ • Site Control CMS (Sponsors, Takeovers, Media) │
             │ • AI Agent Launcher (Antigravity, Codex, etc.)  │
             │ • Cloudflare Deployment Center (Preview/Rollback)│
             │ • Disaster Recovery & Snapshot Backups          │
             └───────┬──────────────────────────┬───────────────┘
                     │                          │
        Tailscale SSH│ (Non-blocking)           │ Wrangler Deploy (Static JSON/HTML)
                     ▼                          ▼
       ┌────────────────────────┐    ┌───────────────────────────┐
       │   ORACLE CLOUD VM 1/2  │    │  CLOUDFLARE PAGES / R2    │
       │   • Healthcheck (:14080│    │  • site-content.json      │
       │   • WebSocket (:14140) │    │  • 1080p60 HLS Segments   │
       │   • System Metrics     │    │  • Static PWA Web Assets  │
       └────────────────────────┘    └───────────────────────────┘
```

---

## 2. Independence Guarantees

| Failure Scenario | Impact on Global Listeners | Impact on Live Audio | Impact on Management Hub |
|---|---|---|---|
| **Hub Closed / Rebooted** | **Zero Impact (0ms)** | **Zero Impact (0ms)** | Reconnects on launch |
| **Visuals App Crashes** | **Zero Impact (0ms)** | **Zero Impact (0ms)** | Can be reopened safely |
| **DJ GUI Closed** | **Zero Impact (0ms)** | **Zero Impact (0ms)** | AutoDJ continues seamlessly |
| **Workstation Offline** | **Zero Impact (0ms)** | **Zero Impact (0ms)** | VM 1 continues 24/7 authority |
| **Cloudflare Deploy Preview** | **Zero Impact (0ms)** | **Zero Impact (0ms)** | Preview tested on isolated URL |

---

## 3. Communication Protocols

1. **Station Health:** HTTP GET `https://status.ebeinc.online/api/public/status` (edge cached 5s, queried every 15s with `?t=...`).
2. **Audio Delivery:** HTTP Shoutcast/Icecast MP3 stream `https://stream.ebeinc.online/live.mp3`.
3. **Visuals Realtime:** WSS `wss://visuals-realtime-staging.allthings140radio.online/ws` (WebSocket frame dispatch).
4. **Site Content Updates:** Static JSON `/data/site-content.json` loaded asynchronously by `radio/app.js` with client-side caching.
5. **Server Management:** Tailscale encrypted WireGuard mesh VPN (`tailscale ssh ebmarah@allthings140radio-server`).
