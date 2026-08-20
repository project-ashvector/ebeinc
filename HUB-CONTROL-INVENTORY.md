# ALLTHINGS140 Hub — Comprehensive Control Inventory

**Application:** ALLTHINGS140 Hub v1.2.0  
**Scope:** Complete inventory of all interactive buttons, inputs, dropdowns, tables, and dialogs across 23 views.

---

## 1. Global Navigation & Header Controls

| Control Name | Location | Type | Safety Tier | Action & Target | Confirmation Dialog? |
|--------------|----------|------|-------------|-----------------|----------------------|
| **Brand Wordmark** | Sidebar Header | Label | 🟢 GREEN | Displays application name and version | No |
| **Category Accordions (5)** | Sidebar | Button | 🟢 GREEN | Toggles collapsible category children | No |
| **View Nav Buttons (23)** | Sidebar | PushButton | 🟢 GREEN | Switches active view in stacked widget & resets scroll | No |
| **In-App Guide Button** | Sidebar Bottom | PushButton | 🟢 GREEN | Navigates directly to Guide view | No |
| **Diagnostics Header Button** | Header Bar | PushButton | 🟢 GREEN | Navigates to Health view | No |
| **Refresh Health Button** | Header Bar | PushButton | 🟢 GREEN | Queries station endpoints in read-only mode | No |

---

## 2. View-by-View Control Inventory

### Operations Views
| View | Control | Safety Tier | Purpose / Target | Pre-Flight Guard |
|------|---------|-------------|------------------|------------------|
| **Dashboard** | `▶ Open Live Player` | 🟢 GREEN | Opens `https://allthings140radio.online` in default browser | None |
| **Dashboard** | `🤖 Work on Station Server` | 🟢 GREEN | Navigates to Agents view with station-server context | None |
| **Dashboard** | `📻 Launch Desktop DJ App` | 🟢 GREEN | Launches `python3 tools/dj_app.py` in terminal | None |
| **Dashboard** | `🎨 Launch Visuals Show-Control` | 🟢 GREEN | Launches `npm run tauri dev` in `visuals-app/` | None |
| **Dashboard** | `🩺 Run Full Diagnostics` | 🟢 GREEN | Executes `tools/allthings140-diagnose.py` | None |
| **Dashboard** | `💾 Create Station Backup` | 🟢 GREEN | Creates snapshot in `backups/` | None |
| **Dashboard** | `🖥️ SSH to Oracle VM 1 / VM 2` | 🟢 GREEN | Opens Tailscale SSH terminal | None |
| **Health** | `🩺 Run Diagnostics` | 🟢 GREEN | Executes deep read-only health checks | None |
| **Servers** | `🖥️ Open SSH Terminal` | 🟢 GREEN | Launches SSH session over Tailscale MagicDNS | Disabled if host offline |
| **Servers** | `🔄 Guarded Service Restart` | 🟠 ORANGE | Restarts systemd unit (`allthings140radio-server.service`) | **Structured ConfirmDialog (Orange)** |
| **Activity** | `🗑️ Clear Audit Log` | 🟡 YELLOW | Clears historical logs in `activity.json` | None |

### Apps & Projects Views
| View | Control | Safety Tier | Purpose / Target | Pre-Flight Guard |
|------|---------|-------------|------------------|------------------|
| **Applications** | `Search Input` | 🟢 GREEN | Real-time text filtering of apps | None |
| **Applications** | `Category Tabs (7)` | 🟢 GREEN | Filter apps by operational plane | None |
| **Applications** | `🤖 Work On App` | 🟢 GREEN | Route to Agents view with pre-filled context | None |
| **Applications** | `💻 Terminal` | 🟢 GREEN | Open terminal in app working directory | None |
| **Applications** | `▶ Launch` | 🟢 GREEN | Execute app launch command | Disabled if no GUI command |
| **Applications** | `ℹ️ Details` | 🟢 GREEN | Open modal with architecture specifications | None |
| **Projects** | `📁 Open Folder` | 🟢 GREEN | Open repository in file manager | Disabled if no row selected |
| **Projects** | `💻 Open Terminal` | 🟢 GREEN | Open terminal in workspace root | Disabled if no row selected |
| **Catalog** | `Package Details` | 🟢 GREEN | View package installation metadata | None |
| **Updates** | `Target App Dropdown` | 🟢 GREEN | Select component for safe update | None |
| **Updates** | `🚀 Run Safe Update Wizard` | 🟠 ORANGE | Execute 10-step zero-downtime workflow | **Structured ConfirmDialog (Orange/Red)** |

### Website & CMS Views
| View | Control | Safety Tier | Purpose / Target | Pre-Flight Guard |
|------|---------|-------------|------------------|------------------|
| **Site Overview** | `🌐 Open Live Website` | 🟢 GREEN | Open live listener URL in browser | None |
| **Sponsors** | `➕ Add New Sponsor` | 🟡 YELLOW | Open modal to add sponsor to `sponsors.json` | Modal verification |
| **Sponsors** | `✏️ Edit Selected` | 🟡 YELLOW | Edit selected sponsor record | Disabled if none selected |
| **Sponsors** | `🗑️ Delete Sponsor` | 🟡 YELLOW | Delete sponsor from `sponsors.json` | **ConfirmDialog (Yellow)** |
| **Partners** | `➕ Add / Edit / Delete` | 🟡 YELLOW | Manage `partners.json` entries | **ConfirmDialog on delete** |
| **Takeovers** | `➕ Add / Edit / Delete` | 🟡 YELLOW | Manage live & archive takeovers | **ConfirmDialog on delete** |
| **Media Library** | `🔄 Rescan Assets` | 🟢 GREEN | Rescan static template references | None |
| **Media Library** | `📁 Open Assets Folder` | 🟢 GREEN | Open `radio/assets/` in file manager | None |
| **Media Library** | `🗑️ Delete Asset` | 🔴 RED | Permanently delete asset file from disk | **Structured ConfirmDialog (Red)** |
| **Announcements**| `➕ Post / Delete` | 🟡 YELLOW | Manage public site news bulletins | **ConfirmDialog on delete** |
| **Roadmap** | `➕ Add / Edit / Delete` | 🟡 YELLOW | Manage public roadmap milestones | **ConfirmDialog on delete** |
| **Deployments** | `🚀 Create Preview Deploy` | 🟡 YELLOW | Build & upload private Cloudflare Preview | Pre-flight smoke test |
| **Deployments** | `🌐 Open Selected Preview`| 🟢 GREEN | Open preview URL in browser | Disabled if none selected |
| **Deployments** | `⭐ Promote to Production` | 🔴 RED | Deploy verified preview to live domain | **Structured ConfirmDialog (Red)** |
| **Deployments** | `⏪ Instant Rollback` | 🔴 RED | Restore files from pre-deploy snapshot | **Structured ConfirmDialog (Red)** |

### AI & Agents Views
| View | Control | Safety Tier | Purpose / Target | Pre-Flight Guard |
|------|---------|-------------|------------------|------------------|
| **Agents** | `Target App / Provider` | 🟢 GREEN | Select target repo and AI CLI runtime | None |
| **Agents** | `📋 Copy Prompt` | 🟢 GREEN | Copy generated smart prompt to clipboard | None |
| **Agents** | `🚀 Launch Agent` | 🟡 YELLOW | Open workspace terminal tab with agent | Launches in isolated terminal |
| **Prompts** | `➕ Create / Edit / Dup` | 🟢 GREEN | Manage reusable task presets | None |
| **Prompts** | `🗑️ Delete Prompt` | 🟡 YELLOW | Remove prompt template from disk | **ConfirmDialog (Yellow)** |
| **Handoffs** | `➕ Record Handoff` | 🟢 GREEN | Create engineering audit record | None |
| **Handoffs** | `📋 Export for ChatGPT`| 🟢 GREEN | Format and copy markdown prompt | None |
| **Reports** | `Rescan / Open Folder` | 🟢 GREEN | Scan and view markdown audits | None |

### System & Safety Views
| View | Control | Safety Tier | Purpose / Target | Pre-Flight Guard |
|------|---------|-------------|------------------|------------------|
| **Backups** | `💾 Create New Snapshot` | 🟢 GREEN | Create `.tar.gz` archive in `backups/` | None |
| **Backups** | `📁 Open Backups Folder`| 🟢 GREEN | Open local backups folder in file manager| None |
| **Guide** | `Search Input` | 🟢 GREEN | Real-time search across all 10+ chapters | None |
| **Guide** | `Topic Selection Table` | 🟢 GREEN | Select article and render formatted Markdown | None |
| **Settings** | `Protected Mode Checkbox` | 🟢 GREEN | Enforces pre-flight structured modals | None |
| **Settings** | `▶ Launch Tour` | 🟢 GREEN | Open 5-slide interactive orientation modal| None |
| **Settings** | `💾 Save Preferences` | 🟢 GREEN | Write configuration to `config.json` | None |
