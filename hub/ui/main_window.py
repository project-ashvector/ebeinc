"""
ALLTHINGS140 Hub — Main Window (Qt6 / PySide6)
Command center window with collapsible categorized sidebar, 24/7 telemetry header, in-app guide routing, and zero-downtime safety workflows.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QSize, Qt, QTimer, QThreadPool
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from hub.config import HubConfig, get_config, save_config
from hub.registry.app_registry import AppRegistry
from hub.services.activity_service import ActivityService
from hub.services.agent_service import AgentService
from hub.services.backup_service import BackupService
from hub.services.cloudflare_deployment_service import CloudflareDeploymentService
from hub.services.handoff_service import HandoffService
from hub.services.health_service import HealthService, StationHealthSnapshot
from hub.services.project_service import ProjectService
from hub.services.prompt_service import PromptService
from hub.services.report_service import ReportService
from hub.services.server_service import ServerService
from hub.services.site_content_service import SiteContentService
from hub.services.system_service import SystemService
from hub.services.update_service import UpdateService
from hub.ui.components.safety_badge import SafetyBadge
from hub.ui.components.status_pill import StatusPill
from hub.ui.worker import Worker
from hub.ui.components.tour_dialog import TourDialog
from hub.ui.theme import (
    ACCENT_CYAN,
    ACCENT_PINK,
    ACCENT_PURPLE,
    BG_CARD,
    BG_CARD_HOVER,
    BG_DARK,
    BG_SIDEBAR,
    BG_SURFACE,
    BORDER_LIGHT,
    BORDER_SUBTLE,
    SAFETY_GREEN,
    SAFETY_YELLOW,
    STATUS_GREEN,
    STATUS_RED,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from hub.ui.views.activity_view import ActivityView
from hub.ui.views.agents_view import AgentsView
from hub.ui.views.announcements_view import AnnouncementsView
from hub.ui.views.applications_view import ApplicationsView
from hub.ui.views.backups_view import BackupsView
from hub.ui.views.catalog_view import CatalogView
from hub.ui.views.dashboard_view import DashboardView
from hub.ui.views.guide_view import GuideView
from hub.ui.views.handoffs_view import HandoffsView
from hub.ui.views.health_view import HealthView
from hub.ui.views.media_library_view import MediaLibraryView
from hub.ui.views.partners_view import PartnersView
from hub.ui.views.project_view import ProjectView
from hub.ui.views.prompts_view import PromptsView
from hub.ui.views.reports_view import ReportsView
from hub.ui.views.roadmap_view import RoadmapView
from hub.ui.views.servers_view import ServersView
from hub.ui.views.settings_view import SettingsView
from hub.ui.views.site_deployments_view import SiteDeploymentsView
from hub.ui.views.site_overview_view import SiteOverviewView
from hub.ui.views.sponsors_view import SponsorsView
from hub.ui.views.takeovers_view import TakeoversView
from hub.ui.views.updates_view import UpdatesView

logger = logging.getLogger("allthings140-hub")


class CategoryHeader(QPushButton):
    """Collapsible category header button in sidebar."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.category_title = title
        self.is_expanded = True
        self.setCheckable(False)
        self._update_text()
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {TEXT_MUTED};
                font-size: 11px;
                font-weight: 800;
                letter-spacing: 0.5px;
                text-align: left;
                padding: 10px 14px 4px 14px;
            }}
            QPushButton:hover {{
                color: {ACCENT_CYAN};
            }}
        """)
        self.clicked.connect(self.toggle)

    def toggle(self) -> None:
        self.is_expanded = not self.is_expanded
        self._update_text()

    def _update_text(self) -> None:
        chevron = "▼" if self.is_expanded else "▶"
        self.setText(f"{chevron}  {self.category_title.upper()}")


class MainWindow(QMainWindow):
    """Primary ALLTHINGS140 Hub Window."""

    def __init__(self, config: Optional[HubConfig] = None, parent=None):
        super().__init__(parent)
        self.config = config or get_config()

        self.setWindowTitle("ALLTHINGS140 Hub — Operations & Safety Console")
        self.resize(1366, 820)
        self.setMinimumSize(1180, 680)

        # Initialize Services
        self._init_services()

        # Build UI Architecture
        self._init_ui()

        # Setup Telemetry Timers
        self._setup_timers()

        # Check First-Run Tour
        QTimer.singleShot(400, self._check_first_run_tour)

    def _init_services(self) -> None:
        # Resolve the configured project root exactly once for this Hub session so every
        # service sees the same workspace. Settings changes intentionally require restart.
        project_root = Path(self.config.current_project_path).expanduser().resolve()
        self.app_registry = AppRegistry(project_root=project_root)
        self.health_service = HealthService(project_root=project_root)
        self.activity_service = ActivityService()
        self.update_service = UpdateService(project_root=project_root)
        self.content_service = SiteContentService(project_root=project_root)
        self.deploy_service = CloudflareDeploymentService(project_root=project_root)
        self.agent_service = AgentService(project_root=project_root)
        self.prompt_service = PromptService()
        self.handoff_service = HandoffService()
        self.report_service = ReportService(project_root=project_root)
        self.backup_service = BackupService(project_root=project_root)
        self.server_service = ServerService()
        self.project_service = ProjectService(base_dir=project_root.parent)

    def _init_ui(self) -> None:
        # Central Container with solid dark background (Eliminates transparency seam)
        central = QWidget()
        central.setObjectName("CentralWidget")
        central.setStyleSheet(f"background-color: {BG_DARK};")
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Left Sidebar Navigation
        self.sidebar_frame = QFrame()
        self.sidebar_frame.setObjectName("SidebarFrame")
        self.sidebar_frame.setFixedWidth(260)
        self.sidebar_frame.setStyleSheet(f"""
            QFrame#SidebarFrame {{
                background-color: {BG_SIDEBAR};
                border-right: 1px solid {BORDER_SUBTLE};
            }}
        """)
        sidebar_layout = QVBoxLayout(self.sidebar_frame)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # 1a. Brand Header (Comfortably fits without truncation)
        brand_frame = QFrame()
        brand_frame.setFixedHeight(64)
        brand_frame.setStyleSheet(f"background-color: {BG_SIDEBAR}; border-bottom: 1px solid {BORDER_SUBTLE}; padding: 12px 14px;")
        b_layout = QVBoxLayout(brand_frame)
        b_layout.setContentsMargins(0, 0, 0, 0)
        b_layout.setSpacing(2)

        self.brand_title = QLabel("ALLTHINGS140")
        self.brand_title.setStyleSheet(f"font-size: 15px; font-weight: 900; color: {TEXT_PRIMARY}; letter-spacing: 0.5px;")

        self.brand_subtitle = QLabel("RADIO HUB v1.2.1 • 24/7 OPS")
        self.brand_subtitle.setStyleSheet(f"font-size: 10px; font-weight: bold; color: {ACCENT_CYAN}; letter-spacing: 0.5px;")

        b_layout.addWidget(self.brand_title)
        b_layout.addWidget(self.brand_subtitle)
        sidebar_layout.addWidget(brand_frame)

        # 1b. Scrollable Navigation List with Collapsible Categories
        nav_scroll = QScrollArea()
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setFrameShape(QFrame.NoFrame)
        nav_scroll.setStyleSheet(f"background-color: {BG_SIDEBAR}; border: none;")

        nav_container = QWidget()
        nav_container.setStyleSheet(f"background-color: {BG_SIDEBAR};")
        self.nav_layout = QVBoxLayout(nav_container)
        self.nav_layout.setContentsMargins(0, 8, 0, 16)
        self.nav_layout.setSpacing(2)

        self.nav_buttons: Dict[str, QPushButton] = {}
        self.category_groups: Dict[str, Tuple[CategoryHeader, List[QPushButton]]] = {}

        # Define 5 Core Navigation Categories
        categories_def = [
            ("Operations", [
                ("dashboard", "📊 Station Dashboard"),
                ("health", "🩺 Health & Diagnostics"),
                ("servers", "🖥️ Cloud Servers (VM 1/2)"),
                ("activity", "📜 Operational Activity")
            ]),
            ("Apps & Projects", [
                ("applications", "📦 Applications"),
                ("projects", "📂 Workspaces & Git"),
                ("catalog", "🛒 Internal App Catalog"),
                ("updates", "🚀 Update Center (10-Step)")
            ]),
            ("Website & CMS", [
                ("site_overview", "🌐 Public Website"),
                ("site_sponsors", "⚡ Sponsors CMS"),
                ("site_partners", "🤝 Partners CMS"),
                ("site_takeovers", "🎧 Takeovers & Archive"),
                ("site_media", "🖼️ Media Asset Library"),
                ("site_announcements", "📢 Public Announcements"),
                ("site_roadmap", "🗺️ Station Roadmap"),
                ("site_deployments", "🚀 Cloudflare Deployment")
            ]),
            ("AI & Agents", [
                ("agents", "🤖 AI Coding Agents"),
                ("prompts", "📝 Prompt Library"),
                ("handoffs", "🤝 Engineering Handoffs"),
                ("reports", "📄 Reports & Audits")
            ]),
            ("System & Safety", [
                ("backups", "💾 Backups & Recovery"),
                ("guide", "📖 Guide & Safety System"),
                ("settings", "⚙️ Hub Preferences")
            ])
        ]

        for cat_name, items in categories_def:
            header_btn = CategoryHeader(cat_name)
            self.nav_layout.addWidget(header_btn)
            child_buttons = []

            for item_id, item_label in items:
                btn = QPushButton(item_label)
                btn.setCheckable(True)
                btn.setAutoExclusive(True)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        text-align: left;
                        padding: 7px 16px;
                        border-radius: 6px;
                        margin: 1px 8px;
                        color: {TEXT_SECONDARY};
                        font-size: 12px;
                        font-weight: 500;
                        border: 1px solid transparent;
                    }}
                    QPushButton:hover {{
                        color: {TEXT_PRIMARY};
                        background-color: {BG_CARD_HOVER};
                    }}
                    QPushButton:checked {{
                        color: {ACCENT_CYAN};
                        background-color: rgba(0, 240, 255, 0.1);
                        border: 1px solid rgba(0, 240, 255, 0.25);
                        font-weight: bold;
                    }}
                """)
                btn.clicked.connect(lambda checked=False, iid=item_id: self.navigate_to(iid))
                self.nav_layout.addWidget(btn)
                self.nav_buttons[item_id] = btn
                child_buttons.append(btn)

            self.category_groups[cat_name] = (header_btn, child_buttons)
            header_btn.clicked.connect(lambda checked=False, cn=cat_name: self._toggle_category(cn))

        self.nav_layout.addStretch()
        nav_scroll.setWidget(nav_container)
        sidebar_layout.addWidget(nav_scroll)

        # 1c. Bottom Operator Mode & Guide Strip
        bottom_bar = QFrame()
        bottom_bar.setFixedHeight(54)
        bottom_bar.setStyleSheet(f"background-color: {BG_CARD}; border-top: 1px solid {BORDER_SUBTLE}; padding: 6px 12px;")
        btm_layout = QHBoxLayout(bottom_bar)
        btm_layout.setContentsMargins(0, 0, 0, 0)
        btm_layout.setSpacing(6)

        self.btn_guide_quick = QPushButton("📖 In-App Guide")
        self.btn_guide_quick.setStyleSheet(f"color: {ACCENT_CYAN}; font-size: 11px; font-weight: bold;")
        self.btn_guide_quick.clicked.connect(lambda: self.navigate_to("guide"))
        btm_layout.addWidget(self.btn_guide_quick)

        btm_layout.addStretch()

        self.prot_mode_lbl = QLabel("🛡️ PROTECTED")
        self.prot_mode_lbl.setStyleSheet(f"color: {SAFETY_GREEN}; font-size: 10px; font-weight: 800;")
        btm_layout.addWidget(self.prot_mode_lbl)

        sidebar_layout.addWidget(bottom_bar)
        root_layout.addWidget(self.sidebar_frame)

        # 2. Main Content Area (Header + Stacked View Area)
        content_area = QWidget()
        content_area.setObjectName("ContentArea")
        content_area.setStyleSheet(f"background-color: {BG_DARK};")
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # 2a. Global Header Bar (54px fixed)
        self.header_bar = QFrame()
        self.header_bar.setFixedHeight(54)
        self.header_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_SURFACE};
                border-bottom: 1px solid {BORDER_SUBTLE};
                padding: 0px 20px;
            }}
        """)
        h_layout = QHBoxLayout(self.header_bar)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(14)

        # Left: Station Health Pill & Now Playing Telemetry
        self.header_status_pill = StatusPill("UNKNOWN")
        h_layout.addWidget(self.header_status_pill)

        self.header_np_lbl = QLabel("Now Playing: Connecting to 24/7 broadcast authority…")
        self.header_np_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: bold;")
        h_layout.addWidget(self.header_np_lbl, 1)

        # Right: Listeners, Safe Mode, Refresh
        self.header_listeners_lbl = QLabel("🎧 0 Listeners")
        self.header_listeners_lbl.setStyleSheet(f"color: {ACCENT_PURPLE}; font-size: 11px; font-weight: bold;")
        h_layout.addWidget(self.header_listeners_lbl)

        btn_diag = QPushButton("🩺 Diagnostics")
        btn_diag.clicked.connect(lambda: self.navigate_to("health"))
        h_layout.addWidget(btn_diag)

        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.setToolTip("Query live station health endpoints")
        btn_refresh.clicked.connect(self._refresh_health)
        h_layout.addWidget(btn_refresh)

        content_layout.addWidget(self.header_bar)

        # 2b. View Stack (QStackedWidget with all 22 registered views)
        self.view_stack = QStackedWidget()
        self.view_stack.setObjectName("ViewStack")
        self.view_stack.setStyleSheet(f"background-color: {BG_DARK};")

        self.views: Dict[str, QWidget] = {}
        self._init_views()

        content_layout.addWidget(self.view_stack, 1)
        root_layout.addWidget(content_area, 1)

        # Default to Dashboard
        self.navigate_to("dashboard")

    def _init_views(self) -> None:
        # 1. Dashboard View
        self.v_dashboard = DashboardView(self.app_registry, self.health_service, self.activity_service)
        self.v_dashboard.navigate_to.connect(self.navigate_to)
        self.v_dashboard.quick_action.connect(self._handle_quick_action)
        self.v_dashboard.open_guide.connect(self._open_guide_topic)
        self._register_view("dashboard", self.v_dashboard)

        # 2. Health View
        self.v_health = HealthView(self.health_service)
        self.v_health.open_guide.connect(self._open_guide_topic)
        self.v_health.refresh_requested.connect(self._refresh_health)
        self._register_view("health", self.v_health)

        # 3. Servers View
        self.v_servers = ServersView(self.server_service)
        self.v_servers.open_guide.connect(self._open_guide_topic)
        self._register_view("servers", self.v_servers)

        # 4. Activity View
        self.v_activity = ActivityView(self.activity_service)
        self.v_activity.open_guide.connect(self._open_guide_topic)
        self._register_view("activity", self.v_activity)

        # 5. Applications View
        self.v_apps = ApplicationsView(self.app_registry)
        self.v_apps.launch_agent.connect(self._launch_agent_for_app)
        self.v_apps.open_guide.connect(self._open_guide_topic)
        self._register_view("applications", self.v_apps)

        # 6. Projects View
        self.v_projects = ProjectView(self.project_service)
        self.v_projects.open_guide.connect(self._open_guide_topic)
        self._register_view("projects", self.v_projects)

        # 7. Catalog View
        self.v_catalog = CatalogView(self.app_registry)
        self.v_catalog.open_guide.connect(self._open_guide_topic)
        self._register_view("catalog", self.v_catalog)

        # 8. Updates View
        self.v_updates = UpdatesView(self.app_registry, self.update_service)
        self.v_updates.open_guide.connect(self._open_guide_topic)
        self._register_view("updates", self.v_updates)

        # 9. Site Overview
        self.v_site_overview = SiteOverviewView(self.deploy_service, self.health_service)
        self.v_site_overview.navigate_tab.connect(self.navigate_to)
        self.v_site_overview.open_guide.connect(self._open_guide_topic)
        self._register_view("site_overview", self.v_site_overview)

        # 10. Sponsors
        self.v_sponsors = SponsorsView(self.content_service)
        self.v_sponsors.open_guide.connect(self._open_guide_topic)
        self._register_view("site_sponsors", self.v_sponsors)

        # 11. Partners
        self.v_partners = PartnersView(self.content_service)
        self.v_partners.open_guide.connect(self._open_guide_topic)
        self._register_view("site_partners", self.v_partners)

        # 12. Takeovers
        self.v_takeovers = TakeoversView(self.content_service)
        self.v_takeovers.open_guide.connect(self._open_guide_topic)
        self._register_view("site_takeovers", self.v_takeovers)

        # 13. Media Library
        self.v_media = MediaLibraryView(self.content_service)
        self.v_media.open_guide.connect(self._open_guide_topic)
        self._register_view("site_media", self.v_media)

        # 14. Announcements
        self.v_announcements = AnnouncementsView(self.content_service)
        self.v_announcements.open_guide.connect(self._open_guide_topic)
        self._register_view("site_announcements", self.v_announcements)

        # 15. Roadmap
        self.v_roadmap = RoadmapView(self.content_service)
        self.v_roadmap.open_guide.connect(self._open_guide_topic)
        self._register_view("site_roadmap", self.v_roadmap)

        # 16. Site Deployments
        self.v_deployments = SiteDeploymentsView(self.deploy_service)
        self.v_deployments.open_guide.connect(self._open_guide_topic)
        self._register_view("site_deployments", self.v_deployments)

        # 17. Agents
        self.v_agents = AgentsView(self.app_registry, self.agent_service, self.prompt_service, self.activity_service)
        self.v_agents.open_guide.connect(self._open_guide_topic)
        self._register_view("agents", self.v_agents)

        # 18. Prompts
        self.v_prompts = PromptsView(self.prompt_service)
        self.v_prompts.run_prompt.connect(self._run_prompt_with_agent)
        self.v_prompts.open_guide.connect(self._open_guide_topic)
        self._register_view("prompts", self.v_prompts)

        # 19. Handoffs
        self.v_handoffs = HandoffsView(self.handoff_service)
        self.v_handoffs.open_guide.connect(self._open_guide_topic)
        self._register_view("handoffs", self.v_handoffs)

        # 20. Reports
        self.v_reports = ReportsView(self.report_service)
        self.v_reports.open_guide.connect(self._open_guide_topic)
        self._register_view("reports", self.v_reports)

        # 21. Backups
        self.v_backups = BackupsView(self.backup_service)
        self.v_backups.open_guide.connect(self._open_guide_topic)
        self._register_view("backups", self.v_backups)

        # 22. Guide & Safety
        self.v_guide = GuideView()
        self._register_view("guide", self.v_guide)

        # 23. Settings
        self.v_settings = SettingsView()
        self.v_settings.open_guide.connect(self._open_guide_topic)
        self._register_view("settings", self.v_settings)

    def _register_view(self, view_id: str, view_widget: QWidget) -> None:
        self.views[view_id] = view_widget
        self.view_stack.addWidget(view_widget)

    def _toggle_category(self, cat_name: str) -> None:
        header_btn, buttons = self.category_groups[cat_name]
        for btn in buttons:
            btn.setVisible(header_btn.is_expanded)

    def navigate_to(self, view_id: str) -> None:
        if view_id in self.views:
            target_view = self.views[view_id]
            self.view_stack.setCurrentWidget(target_view)

            # Highlight correct navigation button
            if view_id in self.nav_buttons:
                self.nav_buttons[view_id].setChecked(True)

            # Auto reset scroll position on view route
            if hasattr(target_view, "reset_scroll"):
                target_view.reset_scroll()

    def _open_guide_topic(self, topic_key: str) -> None:
        self.navigate_to("guide")
        self.v_guide.select_topic(topic_key)

    def _launch_agent_for_app(self, app_id: str) -> None:
        self.navigate_to("agents")
        self.v_agents.set_target_app(app_id)

    def _run_prompt_with_agent(self, prompt_text: str, title: str) -> None:
        self.navigate_to("agents")
        self.v_agents.task_title_input.setText(title)
        self.v_agents.prompt_preview.setPlainText(prompt_text)

    def _handle_quick_action(self, action_key: str) -> None:
        if action_key == "open-stream":
            SystemService.open_url("https://allthings140radio.online")
        elif action_key == "work-server":
            self._launch_agent_for_app("radio-server")
        elif action_key == "work-visuals":
            self._launch_agent_for_app("visuals-workstation")
        elif action_key == "launch-dj":
            SystemService.open_terminal(str(self.health_service.project_root), "ALLTHINGS140 — Desktop DJ", "python3 tools/dj_app.py")
        elif action_key == "launch-visuals":
            self._launch_registered_app("visuals-workstation")
        elif action_key == "open-web":
            SystemService.open_url("https://allthings140radio.online")
        elif action_key == "open-green":
            SystemService.open_url("https://allthings140-visuals-green.pages.dev/")
        elif action_key == "run-diagnostics":
            self.navigate_to("health")
            self.v_health._run_diagnostics()
        elif action_key == "create-backup":
            self.navigate_to("backups")
            self.v_backups._create_snapshot()
        elif action_key == "ssh-vm1":
            self.server_service.launch_ssh_terminal("oracle-vm1")
        elif action_key == "ssh-vm2":
            self.server_service.launch_ssh_terminal("oracle-vm2")

    def _setup_timers(self) -> None:
        self._health_worker_active = False
        self._thread_pool = QThreadPool.globalInstance()
        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.setInterval(max(5, self.config.poll_interval_seconds) * 1000)
        self.telemetry_timer.timeout.connect(self._refresh_health)
        if self.config.auto_refresh_health:
            self.telemetry_timer.start()
        self._refresh_health()

    def _refresh_health(self) -> None:
        # Never perform network/Tailscale probes on the Qt GUI thread.
        if getattr(self, "_health_worker_active", False):
            return
        self._health_worker_active = True
        self.header_status_pill.set_status("CHECKING")
        worker = Worker(self.health_service.run_check)
        worker.signals.result.connect(self._dispatch_health_snapshot)
        worker.signals.error.connect(self._health_refresh_error)
        worker.signals.finished.connect(self._health_refresh_finished)
        self._thread_pool.start(worker)

    def _health_refresh_finished(self) -> None:
        self._health_worker_active = False

    def _health_refresh_error(self, error: str) -> None:
        logger.error("Health refresh failed: %s", error)
        self.header_status_pill.set_status("UNKNOWN")
        self.header_np_lbl.setText("Now Playing: health data unavailable — station state unknown")

    def _dispatch_health_snapshot(self, snapshot: StationHealthSnapshot) -> None:
        # This method is invoked by a Qt signal, so all widget mutations happen
        # on the GUI thread.
        self._update_header_telemetry(snapshot)
        for view in (self.v_dashboard, self.v_health, self.v_site_overview, self.v_servers):
            updater = getattr(view, "update_health", None)
            if updater:
                updater(snapshot)

    def _launch_registered_app(self, app_id: str) -> None:
        app = self.app_registry.get(app_id)
        if not app or not app.launchCommand:
            return
        # VM/cloud components are not workstation applications.
        if app.environment not in ("workstation", "local"):
            self.navigate_to("applications")
            return
        SystemService.open_terminal(app.workingDirectory, f"ALLTHINGS140 — {app.displayName}", app.launchCommand)

    def _update_header_telemetry(self, snapshot: StationHealthSnapshot) -> None:
        self.header_status_pill.set_status(snapshot.status)
        if snapshot.current_title:
            artist = snapshot.current_artist or "AllThings140"
            self.header_np_lbl.setText(f"Now Playing: {artist} — {snapshot.current_title}")
        else:
            self.header_np_lbl.setText("Now Playing: Connecting to 24/7 broadcast authority…")
        self.header_listeners_lbl.setText(f"🎧 {snapshot.listeners} Listeners" if snapshot.authority_status_verified else "🎧 Listeners: Unknown")

    def _check_first_run_tour(self) -> None:
        if not self.config.first_run_tour_completed:
            tour = TourDialog(self)
            if tour.exec_() == TourDialog.Accepted or tour.dont_show_again():
                self.config.first_run_tour_completed = True
                save_config(self.config)
