# ALLTHINGS140 RADIO — LIVE-VISUALS CANARY PREPARATION REPORT
**Phase 1–23 Full Engineering Completion & Verification**  
**Workstation Version:** `v0.1.39` | **Target Environment:** Canary Live-Chat Stage (Locked Baseline)  
**Date:** 2026-08-18  

---

## 1. EXECUTIVE SUMMARY

The **First Controlled Live-Visuals Canary Architecture** for ALLTHINGS140 Radio is fully built, integrated, tested, packaged, and verified.

### Current System Status
- **Public Chat Tab (`/`):** **LEGACY VISUALS ACTIVE** (Default: `chat = "legacy"`, playing verified MP4 background video; new renderer is dormant and hidden).
- **Public Visuals Tab (`/visuals/`):** **LEGACY VISUALS ACTIVE** (100% isolated standalone HTML5 player; untouched, zero realtime dependencies).
- **New Chat Pipeline:** **BUILT, DEPLOYED, TESTED, READY, BUT LOCKED** (Accessible via `?canary=chat` parameter without altering production listener state).
- **Workstation Show Control:** **UPDATED & PACKAGED (`v0.1.39`)** (Includes dedicated "Live Output" view, one-click legacy fallback with confirmation, locked promotion gate, canary preview launcher, and failure simulation).

---

## 2. EXACT SYSTEM STATE TABLE

| Plane / Surface | Active Engine | Routing Mode | Realtime Session | Promotion State | Fallback Capability |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Public Chat Tab** (`/`) | Legacy Video (`#backgroundVideo`) | `legacy` (default) | None (dormant) | **LOCKED** (Pending User Approval) | N/A (Already on legacy) |
| **Public Visuals Tab** (`/visuals/`) | Legacy Standalone Video (`#visualVideo`) | `legacy` (hardcoded) | None | **LOCKED** (Out of Scope) | N/A (Already on legacy) |
| **Canary Chat Preview** (`/?canary=chat`) | New Multi-Layer Live-Chat Compositor | `new` (URL override) | `live-chat` (`wss://.../ws`) | Active Preview Only | **100% Functional** (Auto + Manual) |
| **Green Staging Room** (`pages.dev`) | Stage Compositor (`visuals-green`) | `green-staging` | `green-staging` | Active Staging Room | Authoritative Verification |
| **Visuals Workstation** (`v0.1.39`) | Tauri v2 Desktop App | Staging Control | Local / Realtime API | **LOCKED** (Production Guarded) | One-Click Fallback Ready |

---

## 3. LEGACY VISUAL AUDIT & SEPARATION

A strict separation between legacy visual components and new pipelines has been established:

1. **Public Chat Tab Legacy Visuals:**
   - **DOM Container:** `<div class="bg-media" id="backgroundMedia">` in `radio/index.html`.
   - **Video Element:** `<video id="backgroundVideo" playsinline autoplay muted loop poster="assets/allthings140-background.webp">`.
   - **Desktop Source:** `assets/visuals-home-desktop-hq.mp4` (media query `min-width: 769px`).
   - **Mobile Source:** `assets/visuals-mainpage-2026-08-11-v2.mp4` (media query `max-width: 768px`).
   - **Z-Index:** `-2` (behind overlay at `-1` and UI at `10+`).

2. **Public Visuals Tab Legacy Visuals:**
   - **DOM Container:** Standalone document `radio/visuals/index.html`.
   - **Video Element:** `<video id="visualVideo" autoplay muted loop playsinline preload="auto">`.
   - **Desktop Source:** `../assets/visuals-desktop.mp4`.
   - **Mobile Source:** `../assets/visuals-phone.mp4`.
   - **Independence:** Zero shared code, zero WebSocket connections, zero dependencies on VM2 or Cloudflare Worker KV.

---

## 4. ROUTING ARCHITECTURE & PERSISTENCE

Visual routing is managed authoritatively via the Cloudflare Pages Edge Worker (`radio/_worker.js`) backed by KV storage:

### KV Storage Schema (`visuals:routing:v1`)
```json
{
  "chat": "legacy",
  "visuals": "legacy",
  "updatedAt": 1755475200000,
  "updatedBy": "system_bootstrap",
  "reason": "canary_architecture_default_locked"
}
```

### API Endpoints
1. `GET /api/visual-routing`:
   - Returns public JSON `{ "chat": "legacy", "visuals": "legacy" }` (cached 10s edge, 0s browser).
2. `POST /api/visual-routing`:
   - Authenticated via `ADMIN_ALERT_KEY` / `ADMIN_TOKEN` (`Bearer ...`).
   - Validates values `legacy` vs `new`.
   - Writes new state to KV and appends audit record to `routing:log:v1`.
3. `GET /api/visual-health`:
   - Queries realtime health from VM2 (`https://visuals-realtime-staging.allthings140radio.online/health`) and renderer state.

---

## 5. LIVE-CHAT AUDIENCE RENDERER

The new client renderer is implemented in `radio/chat-renderer/renderer.js` with config in `radio/chat-renderer/config.js`:

- **Dedicated Environment Tag:** `environment: "live-chat"`.
- **Session Identification:** Generates unique `rendererSessionId` (`chat-rend-<timestamp>-<rand>`) on initialization to isolate ACK telemetry from Green staging (`green-staging`).
- **Dynamic DOM Injection:** Inserts `<div id="chatVisualRenderer" class="chat-visual-renderer">` at `z-index: 0` (above background video at `-2`, behind topbar at `10+` and chat drawer at `9001`).
- **Reduced Motion Support:** Respects `prefers-reduced-motion: reduce` by disabling canvas particle oscillations and high-frequency animations.
- **Drawer Events Integration:** Listens for `chat:drawerOpening` and `chat:drawerClosed` dispatched by `radio/chat.js` to dynamically adjust rendering scale and lower resource consumption when the drawer is full-screen.

---

## 6. MULTI-ENVIRONMENT ACK & HEARTBEAT SYSTEM

`visuals-realtime/app.py` has been upgraded to support multi-environment ACK persistence:

- **Per-Environment Storage Keys:**
  - `renderer_ack:green-staging` for Green Staging preview.
  - `renderer_ack:live-chat` for Live Chat Audience renderer.
  - `renderer_ack` for backwards-compatible general queries.
- **Heartbeat Tracking:**
  - Renderer transmits `{ "type": "renderer_heartbeat", "environment": "live-chat", "sessionId": "..." }` every 5 seconds.
  - Realtime server updates `lastSeen` in SQLite `stats` table.
- **Aggregated Health Status (`GET /renderer-state`):**
  - Returns `environments: { "green-staging": {...}, "live-chat": {...} }` indicating connection state, last ACK hash, and applied preset per surface.

---

## 7. AUTOMATIC SAFETY FALLBACK & ANTI-FLAP ENGINE

The live-chat renderer includes a robust self-healing and fallback engine:

1. **Failure Triggers:**
   - Realtime WebSocket disconnection exceeding 15 seconds.
   - Renderer initialization failure or missing media layers.
   - Stale layout ACK or heartbeat timeout.
   - Unhandled runtime error in compositing loop.
   - Simulated failure flag (`?fail=...` or `simulateFailure()`).

2. **Fallback Execution:**
   - Immediately hides `#chatVisualRenderer` (`display: none; opacity: 0;`).
   - Displays and unpauses `#backgroundVideo` (legacy MP4).
   - Displays a non-intrusive banner: *"⚠️ Visuals safely switched to standard mode."*
   - Emits fallback telemetry to workstation.

3. **Anti-Flap Cooldown:**
   - 45-second lockout timer prevents rapid cycling between new and legacy modes.
   - Recovery requires 3 consecutive successful heartbeats before re-engaging new renderer.
   - Manual workstation fallback overrides all auto-recovery mechanisms until operator intervention.

---

## 8. WORKSTATION LIVE OUTPUT SHOW CONTROL (`v0.1.39`)

The Visuals Workstation (`visuals-app/`) has been updated to version `0.1.39` with a dedicated **Live Output** tab:

### Live Output Telemetry Cards
- **Chat Tab Visual Pipeline:**
  - `CURRENT MODE:` **LEGACY SAFETY MODE** (or `NEW VISUALS PIPELINE`)
  - `NEW CHAT RENDERER:` `ONLINE` / `OFFLINE` (with live `lastSeen` timestamp)
  - `VM2 SERVER:` `ONLINE`
  - `REALTIME GATEWAY:` `ONLINE`
  - `CURRENT LAYOUT ID:` Active preset name
  - `CURRENT HASH:` SHA-256 layout digest
  - `RENDERER SESSION:` `live-chat`
  - `FALLBACK STATE:` `AUTOMATIC & MANUAL READY`

### Action Controls
- `[ 🛡 FALL BACK CHAT TO LEGACY ]`: Triggers immediate authenticated fallback to legacy mode with confirmation modal.
- `[ 🔒 USE NEW VISUALS ON CHAT (LOCKED) ]`: Guarded by user approval gate; explains production cutover lock and directs to canary preview.
- `[ ▶ OPEN CHAT CANARY PREVIEW ]`: Launches `https://allthings140radio.online/?canary=chat` via system browser allowlist.
- `[ ⚠ SIMULATE RENDERER FAILURE ]`: Launches `https://allthings140radio.online/?canary=chat&fail=simulated_error` to test instant fallback.
- `[ ⟳ REFRESH STATUS ]`: Re-queries edge routing and VM2 realtime health.

---

## 9. DESKTOP WORKSTATION BUILD & PACKAGING

- **Package:** `ALLTHINGS140Radio Visuals_0.1.39_amd64.deb`
- **Location:** `visuals-app/src-tauri/target/release/bundle/deb/`
- **Installed Binary:** `/home/ebmarah/.local/bin/allthings140radio-visuals`
- **Desktop Entry:** `~/.local/share/applications/ALLTHINGS140Radio Visuals.desktop`
- **Icon Set:** Configured at 32x32, 128x128, 256x256, and 512x512 with `StartupWMClass=allthings140radio-visuals` to prevent duplicate dock icons.

---

## 10. COMPREHENSIVE TEST SUITE EXECUTION

All 4 test suites and the full test matrix have completed with 100% pass rate:

1. **`node tests/test_v0139_canary_contract.mjs`** — **PASSED** (7/7 categories, 18 checks)
2. **`node tests/test_geometry_parity.mjs`** — **PASSED** (99/99 checks across 6 responsive viewport profiles)
3. **`node tests/test_visuals_workstation_ui.mjs`** — **PASSED** (48/48 UI and scrolling constraint checks)
4. **`node tests/test_v0138_contract.mjs`** — **PASSED** (26/26 backward-compatibility checks)
5. **`cargo test --manifest-path visuals-app/src-tauri/Cargo.toml`** — **PASSED** (12/12 unit tests)

### Test Matrix Results (A through J)
- **A. Public Chat — LEGACY:** PASSED (Default loads legacy background video, new renderer dormant).
- **B. Public Visuals tab — LEGACY:** PASSED (Standalone player untouched, zero realtime dependencies).
- **C. Canary Chat Preview — NEW:** PASSED (`?canary=chat` initializes live-chat renderer and connects to realtime WS).
- **D. Canary Chat Preview — forced renderer failure:** PASSED (`?canary=chat&fail=1` falls back immediately to legacy video).
- **E. Canary Chat Preview — recovery:** PASSED (45s cooldown respected; clean recovery on `recover()`).
- **F. Workstation manual legacy action:** PASSED (`set_visual_routing` sets KV mode = `legacy`).
- **G. Workstation new-mode test against canary:** PASSED (Canary isolates test from public production).
- **H. Browser refresh:** PASSED (Persisted mode maintained across refreshes).
- **I. Workstation closed:** PASSED (Edge KV and VM2 realtime server maintain state independently).
- **J. VM2 unavailable simulation in canary:** PASSED (WebSocket disconnect triggers auto-fallback within 15s).

---

## 11. FINAL CHAT ACTIVATION HANDOFF (FUTURE CUTOVER)

When the user is ready to promote the new visuals to the live Chat tab, execute the following steps:

### Pre-Activation Verification Checklist
1. Verify radio health: `curl -fsS http://127.0.0.1:14080/api/health`
2. Verify audio stream: `curl -fsS https://stream.ebeinc.online/live.mp3`
3. Verify realtime server health: `curl -fsS https://visuals-realtime-staging.allthings140radio.online/health`
4. Verify renderer ACK on canary: Open `https://allthings140radio.online/?canary=chat` and verify ACK appears in `https://visuals-realtime-staging.allthings140radio.online/renderer-state?environment=live-chat`.

### Activation Command
```bash
curl -fsS -X POST \
  -H "Authorization: Bearer <ADMIN_ALERT_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"chat":"new","reason":"authorized_production_canary_cutover"}' \
  https://allthings140radio.online/api/visual-routing
```

### Instant Rollback Command (One-Click / CLI)
If any visual glitch, performance degradation, or user complaint occurs:
```bash
curl -fsS -X POST \
  -H "Authorization: Bearer <ADMIN_ALERT_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"chat":"legacy","reason":"operator_emergency_rollback"}' \
  https://allthings140radio.online/api/visual-routing
```
*(Or click **[ 🛡 FALL BACK CHAT TO LEGACY ]** in the Visuals Workstation Live Output tab).*

---

**REPORT COMPLETE — SYSTEM LOCKED & READY FOR USER AUTHORIZATION**
