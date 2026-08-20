"""
ALLTHINGS140 Hub — Comprehensive Functional Test Suite
Tests every major feature: Guide searching/rendering, Content CMS operations, Prompt formatting,
Diagnostics execution, and Version checking.
"""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication

from hub.config import HubConfig, get_config
from hub.registry.app_registry import AppRegistry
from hub.services.activity_service import ActivityService
from hub.services.agent_service import AgentService
from hub.services.cloudflare_deployment_service import CloudflareDeploymentService
from hub.services.handoff_service import HandoffService
from hub.services.health_service import HealthService
from hub.services.prompt_service import PromptService
from hub.services.report_service import ReportService
from hub.services.server_service import ServerService
from hub.services.site_content_service import SiteContentService
from hub.services.update_service import UpdateService
from hub.ui.main_window import MainWindow


class TestHubFunctional(unittest.TestCase):
    """Functional tests for Hub services and UI interactions."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication(["--platform", "offscreen"])
        cls.config = get_config()
        cls.config.first_run_tour_completed = True
        cls.main_win = MainWindow(cls.config)

    def test_guide_search_and_render(self):
        """Test searching guide and rendering markdown article."""
        guide_view = self.main_win.v_guide
        guide_view.search_input.setText("24/7")
        self.assertGreater(guide_view.topic_table.rowCount(), 0)
        guide_view.topic_table.selectRow(0)
        self.assertIn("Radio Independence", guide_view.article_browser.toPlainText())

    def test_app_registry_and_search(self):
        """Test app registry filtering and retrieval."""
        reg = AppRegistry()
        apps = reg.all()
        self.assertGreater(len(apps), 5)
        search_results = reg.search("Visuals")
        self.assertTrue(any("Visuals" in a.displayName for a in search_results))

    def test_site_content_service(self):
        """Test SiteContentService CRUD operations."""
        cs = SiteContentService()
        init_count = len(cs.announcements)
        test_ann = cs.add_announcement(
            title="Functional Test Bulletin",
            content="Testing automated CMS operations.",
            ann_type="info",
            target_planes=["web"]
        )
        self.assertEqual(len(cs.announcements), init_count + 1)
        cs.delete_announcement(test_ann.id)
        self.assertEqual(len(cs.announcements), init_count)

    def test_smart_prompt_generation(self):
        """Test AI agent prompt generation with architecture context."""
        reg = AppRegistry()
        app = reg.get("web-frontend")
        self.assertIsNotNone(app)
        agent_svc = AgentService()
        smart_prompt = agent_svc.generate_smart_prompt(app, "Fix navigation styling", "Ensure all buttons align.")
        self.assertIn("allthings140radio-web", smart_prompt)
        self.assertIn("Fix navigation styling", smart_prompt)
        self.assertIn("DO NOT BREAK", smart_prompt)

    def test_health_service_snapshot(self):
        """Test health service returns valid snapshot structure."""
        hs = HealthService()
        snapshot = hs.run_check()
        self.assertIsNotNone(snapshot)
        self.assertIn(snapshot.status.lower(), ["healthy", "warning", "critical", "offline", "unknown"])
        self.assertGreater(len(snapshot.checks), 0)

    def test_update_service_version_matrix(self):
        """Test update service matrix generation."""
        reg = AppRegistry()
        us = UpdateService()
        matrix = us.get_version_matrix(reg.all())
        self.assertEqual(len(matrix), len(reg.all()))


if __name__ == "__main__":
    unittest.main()
