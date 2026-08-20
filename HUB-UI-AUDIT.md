# ALLTHINGS140 Hub — Comprehensive UI & Visual Audit Report

**Date:** 2026-08-17  
**Application:** ALLTHINGS140 Hub  
**Version:** 1.2.0 (Upgraded from 1.1.0)  
**Target Environment:** Zorin OS 17 (Linux x86_64, Qt6 / PySide6)

---

## 1. Executive Summary & Screencast Analysis

Following the operator directive to halt new major feature development and make the existing Hub visually solid, predictable, and testable, an exhaustive UI audit was performed against the recorded screencasts:
- `Screencast from 2026-08-17 02-22-56.mp4`
- `Screencast from 2026-08-17 02-05-19.mp4`
- `Screencast from 2026-08-17 01-42-09.mp4`

### Key Visual & Ergonomic Failures Identified in Baseline:
1. **Vertical Transparency Seam / Splitter Bleed:** A vertical divider across screens allowed background desktop and terminal windows to shine through intermediate Qt containers.
2. **Brand / Sidebar Text Truncation:** Sidebar title displayed as `"ALLTHINGS1."` with the right half of the logo and wordmark clipped.
3. **Table Column Header Truncation:** Headers like `"LOCAL VERSION"` and `"DEPLOYED VERSION"` were clipped to `"OCAL VERSIOI"` and `"PLOYED VERSI"`. Wide tables caused horizontal scroll leaks or stretched the main application window.
4. **Poor Contrast & Unexplained Disabled States:** Disabled buttons appeared as low-contrast dark gray on dark background without tooltips explaining *why* they were disabled.
5. **Scroll Position Leaks:** Navigating between sidebar tabs retained scroll offsets from previous views instead of resetting to top.
6. **Inaccurate Safety Labeling in Media Library:** Assets were marked "Safe to purge" simply because static HTML scan didn't detect them, ignoring dynamic takeover flyers or staging media.
7. **Raw Underscore Identifiers:** Sidebar and view headers exposed raw internal identifiers (e.g., `Takeovers_Archive`, `Health_Diagnostics`).

---

## 2. Root Cause Analysis & Deep Fixes

### A. The Vertical Transparency Seam
* **Root Cause:** In the baseline `hub/ui/theme.py`, the global QSS rule `QWidget { background-color: transparent; }` stripped the background fill from intermediate containers (`QStackedWidget`, `QScrollArea`, `central_widget`, `QSplitter`). On X11/Wayland compositors, unpainted pixel gaps between adjacent frames revealed the desktop background underneath.
* **Resolution:** 
  1. Rewrote `hub/ui/theme.py` with solid, opaque backgrounds (`BG_DARK = "#0a0d14"`, `BG_SURFACE = "#101522"`, `BG_CARD = "#161d2e"`).
  2. Styled `QSplitter::handle` with solid `BORDER_SUBTLE = "#222c3f"` (3px width) with hover highlights.
  3. Ensured every container, scroll viewport, and central widget explicitly paints a solid background.

### B. Brand Wordmark Clipping
* **Root Cause:** The sidebar frame width was fixed at 240px with heavy internal padding (24px), leaving insufficient horizontal width for `"ALLTHINGS140"`.
* **Resolution:**
  1. Set sidebar width to `260px` with ergonomic 14px horizontal margins.
  2. Grouped navigation into 5 clean, collapsible category headers (`Operations`, `Apps & Projects`, `Website & CMS`, `AI & Agents`, `System & Safety`).
  3. Formatted brand title with tight letter-spacing: `"ALLTHINGS140"` and `"RADIO HUB v1.2.0 • 24/7 OPS"`.

### C. Table Column Header Truncation & Sizing
* **Root Cause:** Default `QTableWidget` section sizing used fixed pixel widths without wrapping or automatic column stretch modes.
* **Resolution:** Created a reusable `DataTable` component:
  - Configures `QHeaderView.ResizeToContents` for compact columns (Status, Version, Date).
  - Configures `QHeaderView.Stretch` on the primary description/URL column.
  - Sets `wordWrap(True)` and minimum row heights (38px).
  - Customizes header QSS with uppercase bold text and clean 1px border dividers.

### D. Scroll Leaks on Route Changes
* **Root Cause:** Navigation in `view_stack.setCurrentWidget(widget)` simply swapped the visible widget without resetting scroll coordinates.
* **Resolution:**
  - Built `PageShell` wrapping every view in a standardized single-scroll area.
  - `MainWindow.navigate_to(view_id)` invokes `target_view.reset_scroll()` on every transition, ensuring operators always arrive at the top of the page.

---

## 3. Responsive Geometry & Resolution Testing Matrix

The redesigned Hub was tested across the four canonical workstation desktop resolutions:

| Target Resolution | Status | Visual Verification |
|-------------------|--------|---------------------|
| **1280 × 720** (HD 720p) | PASS | Fits cleanly; single-scroll vertical movement; zero horizontal clipping. |
| **1366 × 768** (Standard Laptop) | PASS | Default launch resolution; generous whitespace, full stat cards visible. |
| **1600 × 900** (HD+) | PASS | 2-column and 4-column grids balance symmetrically. |
| **1920 × 1080** (Full HD 1080p) | PASS | High-contrast typography; expanded splitters and data tables remain crisp. |

---

## 4. Design Tokens & Palette Standardization

| Token Constant | Hex / RGBA Value | Purpose |
|----------------|------------------|---------|
| `BG_DARK` | `#0a0d14` | Solid deep cosmic root canvas |
| `BG_SURFACE` | `#101522` | Header bar and panel backgrounds |
| `BG_CARD` | `#161d2e` | Elevated cards and containers |
| `BG_CARD_HOVER` | `#1e2840` | Interactive card hover state |
| `BG_SIDEBAR` | `#0c1018` | Navigation sidebar background |
| `BORDER_SUBTLE` | `#222c3f` | 1px clean container outlines |
| `TEXT_PRIMARY` | `#f8fafc` | 100% white high-contrast headers |
| `TEXT_SECONDARY` | `#cbd5e1` | Slate 300 readable paragraph copy |
| `TEXT_MUTED` | `#8295b0` | Slate 400 sub-headers and metadata |
| `ACCENT_CYAN` | `#00f0ff` | Primary neon brand accent |
| `ACCENT_PURPLE` | `#a855f7` | Secondary dubstep purple accent |
| `SAFETY_GREEN` | `#10b981` | Tier 1: Safe / Read-Only |
| `SAFETY_YELLOW` | `#f59e0b` | Tier 2: Local Workspace Change |
| `SAFETY_ORANGE` | `#f97316` | Tier 3: Remote Service Restart |
| `SAFETY_RED` | `#ef4444` | Tier 4: Production / Destructive |
