"""
ALLTHINGS140 Hub — In-App Operator Guide & Safety System View
Comprehensive, searchable operations manual and safety documentation for non-developer operators.
Explains ecosystem architecture, 24/7 independence, application ownership, page-by-page guides, and safety tiers.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from hub.ui.components.safety_badge import SafetyBadge
from hub.ui.theme import (
    ACCENT_CYAN,
    ACCENT_PINK,
    ACCENT_PURPLE,
    BG_CARD,
    BG_DARK,
    BG_SURFACE,
    BORDER_LIGHT,
    BORDER_SUBTLE,
    SAFETY_GREEN,
    SAFETY_ORANGE,
    SAFETY_RED,
    SAFETY_YELLOW,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

# Comprehensive In-App Guide Articles Data
GUIDE_ARTICLES: List[Dict[str, str]] = [
    {
        "id": "start-here",
        "category": "START HERE",
        "title": "Welcome & Ecosystem Fundamentals",
        "tags": "hub, overview, safety, 24/7, architecture, beginner, start",
        "content": """# ALLTHINGS140 Hub — Operator Guide

Welcome to the **ALLTHINGS140 Hub**, the unified command center for the ALLTHINGS140 Radio ecosystem.

---

## 🛡️ Critical Operator Rule: 24/7 Radio Independence

> **KEY TAKEAWAY FOR OPERATORS:**
> **Closing this Hub application does NOT stop the radio station.**
> The live stream runs 24/7 on dedicated cloud servers (**Oracle VM 1**). You can open and close the Hub at any time with **zero risk** to the broadcast.

* **What the Hub Controls:** Monitoring station health, launching local applications, generating AI coding prompts, managing website CMS content, reviewing engineering handoffs, and initiating guarded Cloudflare deployments.
* **What the Hub Does NOT Control Directly:** Audio playback streams directly from Oracle VM 1 to Cloudflare and listener devices.
* **Workstation Role:** This computer acts as an operations console. Live listeners will continue hearing audio even if this computer is shut down.

---

## 🌐 The Four Operational Planes

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
│ • AI Coding Agents & local project/media tooling     │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔒 Safety System Levels

Every action in the Hub is color-coded so you know exactly what is safe:

1. 🟢 **GREEN (Safe / Read-Only):** Checks health, refreshes stats, views logs. No data is modified.
2. 🟡 **YELLOW (Local Change):** Modifies local workstation files or CMS drafts. Does NOT change production.
3. 🟠 **ORANGE (Remote Service Change):** Restarts or interacts with VM services. Requires confirmation.
4. 🔴 **RED (Production / Destructive):** Deploys to live website, deletes files, or rolls back. Requires structured confirmation.
"""
    },
    {
        "id": "app-roles",
        "category": "WHAT EACH APP DOES",
        "title": "Application Roles & Ownership Map",
        "tags": "apps, dj, visuals, server, vm1, vm2, android, discord, roles",
        "content": """# What Each ALLTHINGS140 Application Does

Understand the exact boundaries of each component so you know what you are operating:

---

### 1. ALLTHINGS140 Hub (This Application)
* **Purpose:** Central management, telemetry monitoring, deployment gating, and AI agent coordination.
* **Safe to Close?** **YES.** Fully independent from the radio broadcast.
* **Tech Stack:** Python 3, PySide6 (Qt6), SQLite / JSON config.

---

### 2. Desktop DJ App (`tools/dj_app.py`)
* **Purpose:** Station playlist curation, reviewing newly submitted tracks, setting AutoDJ rotation tiers, and scheduling live takeover broadcasts.
* **Location:** Installed at `/opt/allthings140radio-dj/` and runnable from source.
* **Safe to Close?** **YES.** The AutoDJ engine on VM 1 continues playing from SQLite rotation state even when the DJ app is closed.

---

### 3. ALLTHINGS140 Visuals (`visuals-app/`)
* **Purpose:** Professional 7-layer canvas show-control workstation. Renders animated festival stages, audio reactive shaders, stage lighting, and track cutouts at canonical 16:9 geometry.
* **Tech Stack:** Rust (Tauri v2), Vite, HTML5 Canvas, FFmpeg.
* **Staging Sync:** Deploys verified builds to Green Web Stage (`visuals-green`).

---

### 4. Oracle VM 1 (Broadcast Plane)
* **Purpose:** The 24/7 broadcast authority. Runs the AutoDJ engine, Icecast 2 streaming audio server, SQLite station database, catalog integrity validator, and Cloudflare Tunnel.
* **Access:** Securely managed over Tailscale (`tailscale ssh ebmarah@allthings140radio-server`).

---

### 5. Oracle VM 2 (Visuals Plane)
* **Purpose:** Visuals realtime WebSocket server (`visuals-realtime/app.py`). Handles live audience chat, room energy calculation, emojis, and stage synchronization.
* **Access:** Tailscale (`allthings140-visuals-realtime`).

---

### 6. Public Website & Cloudflare Pages
* **Purpose:** The listener web portal (`https://allthings140radio.online`). Features the PWA audio stream player, live takeover flyers, transmission archive, and sponsors.
* **Hosting:** Cloudflare Pages with edge workers for authentication and chat.

---

### 7. Android Mobile App (`android/mobile-app/`)
* **Purpose:** Native Android listener application with Media3 ExoPlayer background audio playback service and lockscreen media controls.

---

### 8. Emergency Audio Mirror (`/srv/allthings140radio/`)
* **Purpose:** Server-side fallback music library used for playback resilience. Current file count and integrity must be verified from the server/catalog authority rather than assumed by Hub.
"""
    },
    {
        "id": "page-dashboard",
        "category": "PAGE BY PAGE",
        "title": "Dashboard View",
        "tags": "dashboard, metrics, now playing, telemetry, quick operations",
        "content": """# Page Guide: Dashboard

The **Dashboard** is the primary high-level command center for the station.

---

## 📊 Live Gauges Explained

* **Now Broadcasting Banner:** Shows the active track title, artist name, and whether the station is in automated AutoDJ rotation or a LIVE artist takeover.
* **Public Stream:** Verified from an actual read of `https://stream.ebeinc.online/live.mp3`. `ONLINE` means the probe received stream bytes; otherwise the Hub shows `UNKNOWN/OFFLINE` rather than guessing.
* **Broadcast Engine:** Derived from live station authority evidence plus VM reachability; it starts as `UNKNOWN` until checked.
* **Active Listeners:** Live concurrent listener count across website, mobile apps, and direct stream relays.
* **Catalog Integrity:** Shown only when an authoritative status source reports it. `UNKNOWN` means the Hub could not verify it; the Hub does not assume fixed track counts.
* **Visuals Workstation & Realtime:** Version and connectivity state of the show-control engine and Oracle VM 2 WebSocket server.
* **Hot Cache:** Status of pre-fetched emergency tracks on VM 1.
* **Station Backups:** Inventory state only. `verified` means a tar archive could actually be opened/read; directories are labelled present rather than falsely verified.

---

## ⚡ Quick Operations
* **▶ Open Live Player:** Opens `https://allthings140radio.online` in default web browser (🟢 Safe).
* **🤖 Work on Station Server / Visuals:** Routes to AI Coding Agents with context pre-loaded (🟢 Safe).
* **📻 Launch Desktop DJ App:** Opens DJ curation window (🟢 Safe).
* **🎨 Launch Visuals Show-Control:** Opens Tauri visuals desktop window (🟢 Safe).
* **🩺 Run Full Diagnostics:** Triggers deep diagnostic suite (🟢 Safe).
* **🖥️ SSH to Oracle VM 1 / VM 2:** Launches secure SSH terminal over Tailscale (🟢 Safe).
"""
    },
    {
        "id": "page-health",
        "category": "PAGE BY PAGE",
        "title": "Health & Diagnostics View",
        "tags": "health, diagnostics, tests, endpoints, latency, stream check",
        "content": """# Page Guide: Health & Diagnostics

Monitors every public and private endpoint in the ALLTHINGS140 infrastructure.

---

## 🩺 Diagnostic Tests Run

When you click **Run Diagnostics**, the Hub executes `tools/allthings140-diagnose.py` in read-only mode:

1. **Public Website (HTTP 200):** Validates `https://allthings140radio.online` responds with station HTML.
2. **Public Stream Audio Bytes (HTTP 200/206):** Connects to `https://stream.ebeinc.online/live.mp3` and verifies actual audio bytes stream in.
3. **Public Status API:** Validates `https://status.ebeinc.online/api/public/status` reports station online.
4. **Local Broadcast Engine (Port 14080):** Queries local health endpoint.
5. **VM Reachability:** Uses Tailscale reachability checks rather than assuming a VM is online.
6. **Visuals Realtime Server:** Pings Oracle VM 2 WebSocket endpoint.

---

## ⚠️ How to Interpret Warnings
* **DEGRADED Catalog:** Means some approved tracks are temporarily inaccessible in storage. AutoDJ will continue playing available tracks.
* **Stream Offline:** If stream bytes fail, check Oracle VM 1 `allthings140radio-server.service`.
* **Zero Downtime:** Diagnostics are 100% read-only and never interrupt live listeners.
"""
    },
    {
        "id": "page-servers",
        "category": "PAGE BY PAGE",
        "title": "Servers (Oracle VM 1 / VM 2) View",
        "tags": "servers, vm1, vm2, tailscale, systemd, restart, ssh",
        "content": """# Page Guide: Servers (VM 1 / VM 2)

Inspects cloud infrastructure nodes connected through Tailscale MagicDNS.

---

## 🖥️ Server Roles

### Oracle VM 1 (`allthings140radio-server`)
* **Role:** Broadcast Plane (Plane 2 Authority).
* **Systemd Services:**
  * `allthings140radio-server.service` — AutoDJ rotation engine.
  * `icecast2.service` — Audio streaming broadcast server.
  * `cloudflared.service` — Cloudflare Tunnel for secure stream delivery.
  * `tailscaled.service` — Mesh VPN networking.

### Oracle VM 2 (`allthings140-visuals-realtime`)
* **Role:** Visuals Plane (Plane 3 Authority).
* **Systemd Services:**
  * `visuals-realtime.service` — Fast-async WebSocket server for visual stage sync and chat.
  * `cloudflared.service` — Cloudflare Tunnel.

---

## 🟠 Remote Restart Status
* **Current v1.2.1 behavior:** Direct service restart from Hub is **disabled** until a verified transactional management API exists.
* **Why:** v1.2.0 displayed a success message without performing the restart. This release refuses to pretend.
* **Use now:** Open the guarded SSH terminal and follow the documented server runbook. Never assume an interruption duration unless live behavior has been measured.
"""
    },
    {
        "id": "page-updates",
        "category": "PAGE BY PAGE",
        "title": "Update Center & 10-Step Safe Workflow",
        "tags": "updates, safe workflow, deployment, git, staging, rollback",
        "content": """# Page Guide: Update Center

Provides evidence-based version/source state and runs a **local update preflight**. It does not claim a deployed version that it cannot independently verify, and v1.2.1 does not perform remote deployment/restarts from this page.

---

## 🛡️ The 10-Step Safe Update Workflow

Whenever updating any station component, the Hub executes a guarded 10-step protocol:

1. **Detect:** Scans local version vs deployed version and detects uncommitted git edits.
2. **Target:** Identifies target application architecture, dependencies, and unit tests.
3. **Rollback Backup:** Creates an immutable timestamped `.tar.gz` backup in `backups/` BEFORE touching files.
4. **Unit & Integration Tests:** Runs test suite; aborts immediately if any test fails.
5. **Build Release:** Compiles `.deb`, Web bundle, or Rust binary.
6. **Deployment Gate:** Explicitly reports **NOT PERFORMED**; use the target-specific deployment page/runbook.
7. **Restart Gate:** Explicitly reports **NOT PERFORMED**; direct remote restart is disabled in this safety release.
8. **Live Health Gate:** Does not claim health for a change that was never deployed. Run Health after a real deployment.
9. **Rollback Readiness:** Confirms the local preflight snapshot still exists.
10. **Handoff Reminder:** Records that the preflight completed with **no production mutation**.
"""
    },
    {
        "id": "page-media",
        "category": "PAGE BY PAGE",
        "title": "Media Library & Asset Purging",
        "tags": "media, assets, purge, delete, video, images, flyers",
        "content": """# Page Guide: Site Media Library

Manages public site logos, takeover artwork, and background videos in `radio/assets/`.

---

## ⚠️ Safe Purging Guidelines

> **CRITICAL RULE:**
> Assets marked **'Unreferenced in Static Templates'** might still be loaded dynamically (e.g., live takeover flyers, background videos for upcoming stages, or staging assets).
> **Never delete an asset unless you are 100% certain it is obsolete.**

* **Referenced in Code (Green):** The asset is actively linked in `radio/index.html`, `radio/styles.css`, or CMS data. Deleting will break public UI.
* **Unreferenced in Static Templates (Amber):** The asset was not found in static code scans. Verify if it is used for dynamic takeovers before deleting.
* **Quarantine Asset (Red):** The Hub first refuses assets with known references. If no known reference is found and you confirm, the asset is moved into a timestamped quarantine under `backups/site-media-quarantine/` rather than permanently deleted. A scan cannot prove every possible dynamic reference, so review unknown assets carefully.
"""
    },
    {
        "id": "page-cloudflare",
        "category": "PAGE BY PAGE",
        "title": "Cloudflare Deployment Center",
        "tags": "cloudflare, pages, deploy, preview, promote, rollback",
        "content": """# Page Guide: Cloudflare Deployment Center

Deploys web listener pages and visuals stages to Cloudflare edge CDN.

---

## 🚀 Guarded Deployment Workflow

1. **Create Preview Deployment (Yellow):**
   * Builds and uploads the website to a unique preview URL (e.g., `https://random-hash.allthings140.pages.dev`).
   * **Live production (`allthings140radio.online`) is NOT touched.**
   * Automated smoke tests verify HTTP 200, logo assets, and player markup.
2. **Open Selected Preview (Green):**
   * Opens the preview URL in your browser so you can visually verify changes.
3. **Promote to Production (Red):**
   * Re-runs preview smoke tests, verifies the staged artifact SHA-256 has not changed, then deploys that **same immutable artifact** to the production branch.
   * Protected Operator Mode requires typing `CONFIRM` before a RED action is unlocked.
4. **Verified Rollback (Red):**
   * Offered only when Hub retains an artifact from a previously verified Hub-managed production deployment. It redeploys that retained artifact to Cloudflare and smoke-tests production. A local source tarball is **not** presented as a production rollback.
"""
    },
    {
        "id": "page-agents",
        "category": "PAGE BY PAGE",
        "title": "AI Coding Agents & Prompt Library",
        "tags": "ai, agents, codex, antigravity, opencode, ollama, prompts",
        "content": """# Page Guide: AI Coding Agents

Orchestrates autonomous and pair-programming AI coding tools.

---

## 🤖 Supported Providers

* **Google Antigravity (`agy`):** CLI and IDE agent with deep codebase awareness and subagent execution.
* **OpenAI Codex CLI (`codex`):** Fast terminal coding assistant.
* **OpenCode CLI (`opencode`):** Autonomous terminal workflow engine.
* **Local Ollama LLM (`ollama`):** Offline open-weights models running directly on your workstation.

---

## 🛡️ Agent Safety Rules
* **Target Application:** Selecting a target application generates architectural constraints, DO NOT BREAK rules, and key paths into a Hub context file stored outside the repository. Provider CLIs vary, so the Hub opens the terminal and clearly tells the agent where that context file is; it does **not** falsely claim the provider consumed it automatically.
* **Concurrency Warning:** Avoid running multiple autonomous coding agents on the same repository simultaneously to avoid git conflicts.
"""
    },
    {
        "id": "page-backups",
        "category": "PAGE BY PAGE",
        "title": "Backups & Disaster Recovery",
        "tags": "backups, recovery, restore, snapshots, emergency, disaster",
        "content": """# Page Guide: Backups & Recovery

Manages immutable snapshot archives and emergency recovery assets.

---

## 💾 Snapshot Types

* **Update Preflight Snapshots:** A verified local tar snapshot is mandatory before registered tests/builds run.
* **Cloudflare Source Snapshots:** Preview creation also retains a verified source snapshot, while production rollback requires a separately retained previously deployed artifact.
* **Manual Snapshots:** Created on-demand from the Backups tab.
* **Emergency Music Mirror:** Server-side fallback repository at `/srv/allthings140radio/data/music/`. The Hub never treats a fixed historical file count as current health; verify the live server/catalog source.

---

## 🔄 Restore Consequences
* Restoring a snapshot overwrites the corresponding local source files with the snapshot's contents.
* Always check the date and component name before executing a rollback.
"""
    }
]


class GuideView(QWidget):
    """Integrated searchable operator guide and safety reference."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 24)
        main_layout.setSpacing(14)

        # Header with Search
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        title_lbl = QLabel("ALLTHINGS140 OPERATOR GUIDE & SAFETY SYSTEM")
        title_lbl.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {TEXT_PRIMARY}; letter-spacing: 0.5px;")
        header_row.addWidget(title_lbl)

        header_row.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search guide (e.g. 24/7, restart, cloudflare, vm1, safety)…")
        self.search_input.setFixedWidth(380)
        self.search_input.textChanged.connect(self.filter_topics)
        header_row.addWidget(self.search_input)

        main_layout.addLayout(header_row)

        # Splitter: Left Article Index + Right Markdown Reader
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet(f"QSplitter::handle {{ background-color: {BORDER_SUBTLE}; width: 3px; }}")

        # Left: Topic Index Table
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        idx_lbl = QLabel("GUIDE TOPICS & CHAPTERS")
        idx_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;")
        left_layout.addWidget(idx_lbl)

        self.topic_table = QTableWidget()
        self.topic_table.setColumnCount(2)
        self.topic_table.setHorizontalHeaderLabels(["Category", "Topic Title"])
        self.topic_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.topic_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.topic_table.setSelectionMode(QTableWidget.SingleSelection)
        self.topic_table.itemSelectionChanged.connect(self._on_topic_selected)
        left_layout.addWidget(self.topic_table)

        splitter.addWidget(left_panel)

        # Right: Article Reader
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.article_browser = QTextBrowser()
        self.article_browser.setOpenExternalLinks(True)
        self.article_browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {BG_DARK};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 8px;
                padding: 18px 22px;
                color: {TEXT_PRIMARY};
                font-size: 13px;
                line-height: 1.5;
            }}
        """)
        right_layout.addWidget(self.article_browser)

        splitter.addWidget(right_panel)
        splitter.setSizes([320, 760])

        main_layout.addWidget(splitter)
        self.filter_topics()

    def filter_topics(self) -> None:
        query = self.search_input.text().strip().lower()
        matched = []
        for art in GUIDE_ARTICLES:
            if not query:
                matched.append(art)
            elif (query in art["title"].lower() or 
                  query in art["category"].lower() or 
                  query in art["tags"].lower() or 
                  query in art["content"].lower()):
                matched.append(art)

        self.topic_table.setRowCount(len(matched))
        for row_idx, art in enumerate(matched):
            c_item = QTableWidgetItem(art["category"])
            c_item.setData(Qt.UserRole, art["id"])
            c_item.setForeground(Qt.cyan if art["category"] == "START HERE" else Qt.white)

            t_item = QTableWidgetItem(art["title"])
            self.topic_table.setItem(row_idx, 0, c_item)
            self.topic_table.setItem(row_idx, 1, t_item)

        if matched:
            self.topic_table.selectRow(0)

    def _on_topic_selected(self) -> None:
        selected_items = self.topic_table.selectedItems()
        if not selected_items:
            return
        row = self.topic_table.currentRow()
        cat_item = self.topic_table.item(row, 0)
        if not cat_item:
            return
        art_id = cat_item.data(Qt.UserRole)
        art = next((a for a in GUIDE_ARTICLES if a["id"] == art_id), None)
        if art:
            self.article_browser.setMarkdown(art["content"])

    def select_topic(self, topic_id: str) -> None:
        """Select and display a specific guide topic by key."""
        self.search_input.clear()
        for row in range(self.topic_table.rowCount()):
            item = self.topic_table.item(row, 0)
            if item and item.data(Qt.UserRole) == topic_id:
                self.topic_table.selectRow(row)
                return
