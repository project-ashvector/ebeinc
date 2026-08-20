# ALLTHINGS140 Hub — Strategic Roadmap & Evolution Plan

**Date:** 2026-08-17  
**Project:** ALLTHINGS140 Radio Ecosystem  
**Target:** ALLTHINGS140 Hub (`allthings140-hub`)  

---

## 1. Vision & Strategic Direction

The **ALLTHINGS140 Hub** is designed as the permanent mission control center for ALLTHINGS140 Radio. Its evolution follows four sequential milestones:
1. **Foundation & Orchestration (Completed v1.0.0):** Unified application discovery, live telemetry, AI agent control center, engineering handoffs, and desktop integration.
2. **Telemetry & Live Show Control (Phase 2):** Realtime WebSocket monitoring, 1-click visual staging cutover, audio loudness analytics.
3. **Automated Maintenance & CI/CD (Phase 3):** Automatic pre-deployment test gates, encrypted off-site replication, release packaging pipelines.
4. **Autonomous AI Broadcasting (Phase 4):** Real-time AI DJ voice synthesis, interstitial generation, and machine-learning track classification.

---

## 2. Phase Breakdown & Milestones

### Phase 1: Core Foundation & Desktop Integration (COMPLETED — v1.0.0)
- [x] Comprehensive ecosystem discovery indexing 16 components across 4 operational planes.
- [x] Custom dark cyberpunk theme with Cyan/Purple neon accents tailored for live operations.
- [x] Multi-resolution icon set (16x16 through 512x512) and Zorin OS dock `StartupWMClass` matching.
- [x] Realtime health polling service (Stream status, listener count, catalog health, hot cache).
- [x] AI Coding Agent Control Center supporting Antigravity (`agy`), Codex (`codex`), OpenCode (`opencode`), and Local Ollama (`ollama`).
- [x] Reusable Prompt Library with 8 operational presets and full CRUD persistence.
- [x] Engineering Handoff System with 1-click **ChatGPT Export**.
- [x] Report Library indexing all documents, audits, and architectural specifications.
- [x] 10-Step Safe Update Workflow Wizard with rollback backups.
- [x] Debian package builder (`hub/build_deb.sh`) generating `allthings140-hub_1.0.0_amd64.deb`.
- [x] Automated test suite with 13 unit/integration tests passing 100%.

---

### Phase 2: Show Control & Realtime Staging (Near-Term)
- [ ] **Realtime Visuals Streamer:** Direct WebSocket feed from Oracle VM 2 (`visuals-realtime`) into Hub UI to visualize room energy and active visualizer presets live.
- [ ] **Visuals Staging Cutover Gate:** Safe 1-click promotion of Green staging (`visuals-green`) to production once geometry parity and soak tests pass.
- [ ] **Live Audio Spectrum Analyzer:** Web Audio / PCM visualizer inside the Hub header bar for instant audio confidence monitoring.
- [ ] **DJ Takeover Scheduler:** Live calendar and automated countdown for scheduled guest DJ takeovers and remote live streams.

---

### Phase 3: Automated Maintenance & Release Pipelines (Mid-Term)
- [ ] **Automated Nightly DB Backups:** Scheduled cron integration creating encrypted daily snapshots of `/var/lib/allthings140radio/station.db` and mirroring to cold storage.
- [ ] **Android Play Store Release Pipeline:** Provisioning release keystore for `android/mobile-app` and automated APK/AAB bundle builds.
- [ ] **Discord Bot Token Rotation & Slash Commands:** Secure vault token migration and expansion of `/trackrequest`, `/schedule`, and `/visuals` commands.
- [ ] **Tailscale Service Health Auto-Recovery:** Automatic service restart triggers with progressive backoff if Icecast or AutoDJ fails health checks.

---

### Phase 4: Autonomous AI Broadcasting (Long-Term)
- [ ] **AI Host Voice Synthesizer:** Local GPU-accelerated speech synthesis generating dynamic show intros, track trivia, and station IDs between dubstep sets.
- [ ] **Audio Feature Classifier:** Machine learning classification of BPM (140±2), key, and sub-bass energy to refine AutoDJ rotation algorithms.
- [ ] **Multi-Station WebRTC Federation:** Peer-to-peer stage visualization sync across multiple synchronized listener rooms.

---

## 3. Maintenance & Safe Operation Guidelines

1. **Zero Downtime Rule:** Always verify local health (`curl -fsS http://127.0.0.1:14080/api/health`) and public stream (`https://stream.ebeinc.online/live.mp3`) before modifying server configurations.
2. **Visuals Baseline Hash:** Never alter production visuals without preserving baseline SHA-256 hash `4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32`.
3. **Mobile Video Preservation:** Never replace or modify `radio/assets/visuals-phone.mp4` when updating desktop visual assets.
4. **Secret Protection:** Never commit `.env`, Stripe keys, Discord tokens, or SSH keys to Git repositories.
