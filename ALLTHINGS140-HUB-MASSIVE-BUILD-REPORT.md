# ALLTHINGS140 Hub — Massive Build & Delivery Report

**Date:** 2026-08-17  
**Author:** Antigravity (Google Deepmind)  
**Target System:** Zorin OS 17 (Linux x86_64)  
**Project Root:** `/home/ebmarah/Projects/AllThings140Radio`  
**Hub Package Version:** `v1.0.0` (Debian Package: `dist/allthings140-hub_1.0.0_amd64.deb`)  
**Installed Executable:** `/home/ebmarah/.local/bin/allthings140-hub`  
**Installed Desktop Entry:** `/home/ebmarah/.local/share/applications/allthings140-hub.desktop`  

---

## 1. Executive Summary

The **ALLTHINGS140 Hub** has been engineered, validated, and installed as the authoritative **OPERATING CENTER** for the entire ALLTHINGS140 Radio ecosystem. 

Rather than creating a disconnected utility or reimplementing station logic, the Hub acts as a native show-control and administrative cockpit that unifies:
- **Plane 1 (Public Listener & Web):** Cloudflare Pages PWA, live HLS video visualizers, edge workers.
- **Plane 2 (24/7 Broadcast Authority):** Oracle Cloud VM 1, AutoDJ engine (`tools/server.py`), Icecast 2 streaming, catalog integrity scanner, and predictive hot cache.
- **Plane 3 (Visuals & Realtime Server):** Oracle Cloud VM 2, WebSocket realtime energy hub, Green web staging (`visuals-green`).
- **Plane 4 (Management & Workstation):** Desktop DJ workstation (`tools/dj_app.py`), Visuals show-control workstation (`visuals-app`), Android listener APK, Discord community bot, backup recovery suites, and AI coding agent runtimes.

The Hub runs natively on Zorin OS with proper Wayland/X11 `StartupWMClass` matching, ensuring a single unified dock icon without generic gear or duplicate icon issues.

---

## 2. Architectural Structure & Implemented Modules

The Hub codebase is structured under `/home/ebmarah/Projects/AllThings140Radio/hub/`:

```
hub/
├── __init__.py                  # Package root (v1.0.0)
├── config.py                    # Durable configuration (~/.config/allthings140-hub/config.json)
├── main.py                      # Qt6 GUI entrypoint (QApplication + WM_CLASS matching)
├── cli.py                       # Headless CLI interface
├── install.sh                   # Native Zorin OS installer & icon cache updater
├── uninstall.sh                 # Safe uninstaller
├── build_deb.sh                 # Debian package (.deb) builder
├── assets/
│   └── icons/                   # Multi-resolution PNG icon suite (16x16 through 512x512)
├── registry/
│   ├── app_registry.py          # 16-component ecosystem registry with live git enrichment
│   └── project_registry.py      # Project workspaces and repository tracking
├── services/
│   ├── health_service.py        # Realtime async polling for stream, endpoints, and telemetry
│   ├── git_service.py           # Non-destructive branch, commit, dirty-state, and diff tracking
│   ├── agent_service.py         # Multi-provider AI abstraction (Antigravity, Codex, OpenCode, Ollama)
│   ├── prompt_service.py        # Reusable prompt library, presets, and CRUD persistence
│   ├── handoff_service.py       # Cross-agent engineering handoffs & ChatGPT export
│   ├── report_service.py        # Report library scanner and integrated markdown reader
│   ├── backup_service.py        # Backup discovery, tarball snapshot creator, retention tracker
│   ├── update_service.py        # Local vs Deployed version matrix & 10-step safe update wizard
│   ├── server_service.py        # Oracle VM 1 & VM 2 SSH launcher and service monitoring
│   ├── activity_service.py      # Chronological audit trail & notification alert system
│   └── system_service.py        # Terminal launchers, xdg-open integration, and process runner
├── ui/
│   ├── theme.py                 # Custom cyberpunk dark QSS theme (Cyan/Purple/Dark bass aesthetic)
│   ├── main_window.py           # Main window shell, sidebar navigation, top telemetry bar
│   ├── components/
│   │   ├── status_pill.py       # Color-coded operational status badges
│   │   ├── stat_box.py          # High-impact metric telemetry cards
│   │   ├── app_card.py          # Interactive application card with direct action triggers
│   │   └── confirm_dialog.py    # Safeguard modal dialogs for critical actions
│   └── views/
│       ├── dashboard_view.py    # Main operational command center & Now Playing ticker
│       ├── applications_view.py # Categorized application registry (All, Broadcast, Visuals, Web, etc.)
│       ├── project_view.py      # Repository explorer, git branch inspector, and commit log
│       ├── agents_view.py       # AI coding agent launcher with Smart Context Prompt generator
│       ├── prompts_view.py      # Prompt library with search, tags, and preset execution
│       ├── handoffs_view.py     # Engineering handoff browser and ChatGPT exporter
│       ├── reports_view.py      # Report library scanner and split-view markdown reader
│       ├── health_view.py       # Endpoint latency table, check matrix, diagnostic test runner
│       ├── servers_view.py      # Oracle VM 1 & VM 2 metrics and Tailscale SSH triggers
│       ├── backups_view.py      # Station snapshot table and backup creation modal
│       ├── updates_view.py      # Version diff matrix and 10-step safe update runner
│       ├── activity_view.py     # Audit trail table and actionable notification dismisser
│       ├── catalog_view.py      # Internal ALLTHINGS140 app store / package manager
│       └── settings_view.py     # Modular configuration tabs (Projects, AI, PCs, Folders, Advanced)
└── tests/
    └── test_hub_suite.py        # 13 comprehensive automated unit and integration tests
```

---

## 3. Registered Application Inventory (16 Ecosystem Components)

| App ID | Name | Plane / Category | Environment | Version | Status |
|---|---|---|---|---|---|
| `radio-server` | Station Broadcast Server | Plane 2: Broadcast | Oracle VM 1 | 0.8.0 | Active Production |
| `dj-app` | Desktop DJ Workstation | Plane 4: Tools | Zorin Desktop | 0.7.0 | Active Tool |
| `web-frontend` | Web Listener Frontend (PWA) | Plane 1: Public Web | Cloudflare Pages | 1.6.1 | Active Production |
| `visuals-workstation` | Visuals Desktop Show-Control | Plane 4: Visuals | Zorin Desktop | 0.1.32 | Active Workstation |
| `visuals-green` | Green Web Stage (Staging) | Plane 1/3: Visuals | Cloudflare Pages | 0.1.32-green | Active Staging |
| `visuals-realtime` | Visuals Realtime Server | Plane 3: Visuals | Oracle VM 2 | 0.1.0-staging | Active Staging |
| `android-app` | Android Mobile App | Plane 1: Mobile | Android (Media3) | 1.1.0 | Active Artifact |
| `discord-bot` | Discord Community Bot | Plane 1: Chat | Node.js Worker | 1.0.0 | Standalone |
| `ai-host` | AI Host & Interstitial Engine | Plane 2: Broadcast | Oracle VM 1 | 1.0.0 | Integrated |
| `hot-cache` | Predictive Hot Cache Manager | Plane 2: Broadcast | Oracle VM 1 | 1.0.0 | Active Service |
| `catalog-integrity` | Catalog Integrity System | Plane 2: Broadcast | Oracle VM 1 | 1.0.0 | Active Service |
| `backup-recovery` | Backup & Recovery Suite | Plane 4: Tools | Workstation | 1.0.0 | Active Tool |
| `radio-diagnostics` | Diagnostics & Health Suite | Plane 4: Tools | Workstation | 1.0.0 | Active Tool |
| `cloudflare-workers` | Edge Cloudflare Workers | Plane 1: Web | Cloudflare Edge | 1.2.0 | Active Production |
| `oracle-vm1` | Oracle VM 1 (Broadcast Plane) | Plane 2: Infra | Oracle Linux 9.8 | N/A | Active Production |
| `oracle-vm2` | Oracle VM 2 (Visuals Plane) | Plane 3: Infra | Oracle Linux 9.8 | N/A | Active Staging |

---

## 4. Desktop Integration & Zorin OS Dock Verification

### WM_CLASS Matching & Icon Identity
To eliminate generic gear icons or duplicate dock entries:
1. **Desktop Entry:** `~/.local/share/applications/allthings140-hub.desktop` contains `StartupWMClass=allthings140-hub`.
2. **Qt Application Identity:** `app.setApplicationName("allthings140-hub")`, `app.setDesktopFileName("allthings140-hub.desktop")`.
3. **Window Identity:** `window.setObjectName("allthings140-hub")`.
4. **Icon Asset Tree:** 8 high-resolution PNG icons installed in `~/.local/share/icons/hicolor/<size>x<size>/apps/allthings140-hub.png` (16x16, 24x24, 32x32, 48x48, 64x64, 128x128, 256x256, 512x512).
5. **System Caches:** Updated with `gtk-update-icon-cache` and `update-desktop-database`.

---

## 5. AI & Coding Agent Control Center

The Hub abstracts and orchestrates multiple AI coding providers:
- **Google Antigravity (`agy`):** Connected via `/home/ebmarah/.local/bin/agy`.
- **OpenAI Codex (`codex`):** Connected via `/home/ebmarah/.local/bin/codex`.
- **OpenCode (`opencode`):** Connected via `/home/ebmarah/.opencode/bin/opencode`.
- **Local Ollama (`ollama`):** Connected via `/usr/local/bin/ollama` (model `llama3.2:3b`).

### Smart Context Prompt Generation
When launching an agent from the Hub, it automatically compiles:
1. Target application name, tech stack, and exact working directory.
2. Current version, active git branch, and HEAD commit hash.
3. Target deployment environment (`production`, `staging`, `workstation`, `cloudflare`).
4. DO NOT BREAK rules (Zero Downtime, Visuals baseline SHA-256 preservation, untouched mobile visualizer).
5. Explicit prohibition on leaking or committing private keys, secrets, or bot tokens.
6. Launches directly in a dedicated GNOME Terminal / X-Terminal window inside the target app's directory.

---

## 6. Prompt Library & Engineering Handoff System

### Built-in Reusable Prompt Presets
- `Deep Dive Investigation`: Complete architecture, data flows, and bottleneck discovery.
- `Targeted Bug Hunt & Fix`: Minimal reproduction, surgical fix, regression tests.
- `Production Pre-Flight Audit`: Multi-endpoint health, baseline hashes, clean working tree checks.
- `Visuals Workstation Review`: 7-layer compositing, 16:9 geometry parity, async Rust tasks.
- `Safe Update & Deploy Workflow`: Step-by-step update pipeline with rollback backups.
- `Security & Secrets Audit`: Scans for exposed tokens, Stripe keys, Cloudflare secrets.
- `Backup & Disaster Recovery Audit`: Validates database snapshots and emergency audio mirrors.
- `Full Test Suite Execution`: Comprehensive unit, parity, and diagnostics runs.

### Cross-Agent Engineering Handoffs
- Tracks session summaries, modified files, verification test results, deployment status, and next tasks.
- Includes a 1-click **"Export for ChatGPT"** formatter that outputs clean markdown suitable for passing context between chat sessions.

---

## 7. 10-Step Safe Update Workflow

The Hub enforces the 10-step safe update workflow to guarantee zero downtime:
1. **Detect Current State:** Inspects git branch, dirty files, and active version.
2. **Identify Target:** Confirms target environment and deployment rules.
3. **Create Rollback Backup:** Creates timestamped tarball archive in `backups/`.
4. **Run Pre-Flight Tests:** Executes test suites before any deployment action.
5. **Build Production Package:** Compiles application bundles (Vite, Rust, etc.).
6. **Deploy Update:** Deploys to target host (Cloudflare Pages, VM1, local workstation).
7. **Restart Targeted Services:** Performs guarded systemd service restarts.
8. **Verify Live Health:** Checks HTTP 200 health, audio byte stream, and catalog state.
9. **Verify Rollback Readiness:** Confirms rollback point is intact if needed.
10. **Record Engineering Handoff:** Logs completed update to Hub activity log.

---

## 8. Automated Test Suite Results

All 13 test suites in `hub/tests/test_hub_suite.py` passed with 100% success:

```
test_app_registry_discovery ........................... PASS
test_app_registry_search_and_filter ................... PASS
test_project_registry_workspace ....................... PASS
test_git_service_summary .............................. PASS
test_agent_providers_detection ........................ PASS
test_smart_prompt_generation .......................... PASS
test_prompt_library_presets_and_crud .................. PASS
test_handoff_system_and_chatgpt_export ................ PASS
test_report_service_discovery ......................... PASS
test_backup_service_discovery_and_creation ............ PASS
test_update_service_version_matrix .................... PASS
test_safe_update_workflow_execution ................... PASS
test_health_service_snapshot .......................... PASS

Ran 13 tests in 21.029s — OK (0 failures, 0 errors)
```

---

## 9. Usage & Quick Reference

### Launching the Graphical User Interface (GUI)
- From Zorin OS Application Menu: Search **"ALLTHINGS140 Hub"**
- From Terminal: `allthings140-hub` or `allthings140-hub --gui`
- Direct Python: `/home/ebmarah/.local/share/allthings140-hub/.venv/bin/python3 /home/ebmarah/Projects/AllThings140Radio/hub/main.py`

### Headless Command Line Interface (CLI)
```bash
# Check station health and telemetry
allthings140-hub status

# List all registered ecosystem applications
allthings140-hub apps

# Run endpoint health check
allthings140-hub health

# List prompt templates
allthings140-hub prompts

# List engineering handoffs
allthings140-hub handoffs

# Export handoff for ChatGPT
allthings140-hub handoffs --export <handoff-id>

# Generate smart context prompt for an application
allthings140-hub smart-prompt --app visuals-workstation --task "Geometry Parity Audit"

# Check version comparison matrix
allthings140-hub updates
```
