"""
ALLTHINGS140 Hub — Site Control Overview View
Monitors public website health, Cloudflare Pages state, latency, and deployment status.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hub.services.cloudflare_deployment_service import CloudflareDeploymentService
from hub.services.health_service import HealthService, StationHealthSnapshot
from hub.services.system_service import SystemService
from hub.ui.components.page_shell import PageShell
from hub.ui.components.section_card import SectionCard
from hub.ui.components.stat_box import StatBox
from hub.ui.components.status_pill import StatusPill
from hub.ui.theme import (
    ACCENT_CYAN,
    ACCENT_PURPLE,
    BG_CARD,
    BG_DARK,
    BG_SURFACE,
    BORDER_LIGHT,
    BORDER_SUBTLE,
    STATUS_GREEN,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class SiteOverviewView(QWidget):
    """Website operations and public endpoint overview."""

    navigate_tab = Signal(str)
    open_guide = Signal(str)

    def __init__(self, deploy_service: CloudflareDeploymentService, health_service: HealthService, parent=None):
        super().__init__(parent)
        self.deploy_service = deploy_service
        self.health_service = health_service
        self._init_ui()

    def _init_ui(self) -> None:
        self.shell = PageShell(
            title="Public Website & Edge Portal Overview",
            subtitle="Real-time status of allthings140radio.online, Cloudflare Pages CDN edge routes, and CMS content.",
            guide_key="page-cloudflare",
            safety_level="green"
        )
        self.shell.open_guide.connect(lambda k: self.open_guide.emit(k))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.shell)

        # 1. Telemetry Gauges Card
        stat_card = SectionCard(
            title="WEBSITE METRICS & EDGE STATUS",
            subtitle="Global CDN distribution and edge response latency",
            guide_key="page-cloudflare",
            safety_level="green"
        )

        btn_open_live = QPushButton("🌐 Open Live Website")
        btn_open_live.setProperty("primary", "true")
        btn_open_live.setToolTip("Open https://allthings140radio.online")
        btn_open_live.clicked.connect(lambda: SystemService.open_url("https://allthings140radio.online"))
        stat_card.header_actions.addWidget(btn_open_live)

        grid = QGridLayout()
        grid.setSpacing(12)

        self.stat_site_status = StatBox("Public Website", "UNKNOWN", "Waiting for live HTTP probe", TEXT_MUTED)
        self.stat_cf_pages = StatBox("Cloudflare Deployment", "UNKNOWN", "Local deployment records only until verified", TEXT_MUTED)
        self.stat_latency = StatBox("Response Latency", "UNKNOWN", "Waiting for live HTTP probe", TEXT_MUTED)
        self.stat_rollback = StatBox("Rollback Safety", "LOCAL ONLY", "Production rollback requires Cloudflare deployment", TEXT_MUTED)

        grid.addWidget(self.stat_site_status, 0, 0)
        grid.addWidget(self.stat_cf_pages, 0, 1)
        grid.addWidget(self.stat_latency, 0, 2)
        grid.addWidget(self.stat_rollback, 0, 3)

        stat_card.add_layout(grid)
        self.shell.add_widget(stat_card)

        # 2. Production Status Banner Card
        latest_prod = self.deploy_service.get_latest_production()
        prod_card = SectionCard(
            title="PRODUCTION DEPLOYMENT STATE",
            subtitle="Active build live on Cloudflare edge",
            guide_key="page-cloudflare",
            safety_level="green"
        )
        prod_card.header_actions.addWidget(StatusPill("RECORDED" if latest_prod else "UNKNOWN"))

        if latest_prod:
            prod_info = QLabel(f"<b>Live URL:</b> <a href='{latest_prod.productionUrl}' style='color:#00f0ff'>{latest_prod.productionUrl}</a><br><b>Branch:</b> {latest_prod.branchName} • <b>Deployed:</b> {latest_prod.formattedDate}<br><b>Smoke Test:</b> {latest_prod.smokeTestDetails}")
            prod_info.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; line-height: 1.4;")
            prod_info.setOpenExternalLinks(True)
            prod_card.add_widget(prod_info)
        else:
            p_lbl = QLabel("No verified production deployment record is available. Use live health checks and Cloudflare before assuming sync.")
            p_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
            prod_card.add_widget(p_lbl)

        self.shell.add_widget(prod_card)

        # 3. Content Navigation Operations Card
        act_card = SectionCard(
            title="WEBSITE CONTENT OPERATIONS",
            subtitle="Manage local site content. Publishing still requires the site deployment workflow in this release.",
            guide_key="page-cloudflare",
            safety_level="yellow"
        )

        btn_grid = QGridLayout()
        btn_grid.setSpacing(10)

        btns = [
            ("⚡ Manage Sponsors", "site_sponsors", "default", "Manage public sponsors, tiers, and logos"),
            ("🤝 Manage Partners", "site_partners", "default", "Manage partner record labels and collectives"),
            ("🎧 Takeovers & Transmission Archive", "site_takeovers", "default", "Manage live takeover DJ bios and tracklists"),
            ("🖼️ Site Media Asset Library", "site_media", "default", "Inspect and clean public image/video assets"),
            ("📢 Public Station Announcements", "site_announcements", "default", "Post news bulletins to listener page"),
            ("🗺️ Public Station Roadmap", "site_roadmap", "default", "Update station development milestones"),
            ("🚀 Cloudflare Deployment Center", "site_deployments", "primary", "Build previews and promote production releases")
        ]

        for idx, (lbl, tab_key, btype, tooltip) in enumerate(btns):
            b = QPushButton(lbl)
            b.setToolTip(tooltip)
            if btype == "primary":
                b.setProperty("primary", "true")
            b.clicked.connect(lambda checked=False, k=tab_key: self.navigate_tab.emit(k))
            row = idx // 2
            col = idx % 2
            btn_grid.addWidget(b, row, col)

        act_card.add_layout(btn_grid)
        self.shell.add_widget(act_card)
        self.shell.add_stretch()

    def reset_scroll(self) -> None:
        self.shell.reset_scroll()


    def update_health(self, snapshot: StationHealthSnapshot) -> None:
        status = snapshot.website_status.upper()
        self.stat_site_status.update_stat(status, "allthings140radio.online live HTTP probe")
        latency = f"{snapshot.website_latency_ms:.0f} ms" if snapshot.website_latency_ms > 0 else "UNKNOWN"
        self.stat_latency.update_stat(latency, "Measured during latest live HTTP probe")
        self.stat_cf_pages.update_stat("REACHABLE" if snapshot.website_status == "online" else "UNKNOWN", "Public edge reachability; not an account/API auth check")
