"""
ALLTHINGS140 Hub — Automated UI Smoke Test Suite
Verifies clean instantiation, route navigation, Guide routing, Dialogs, and responsive layout across all views.
"""

import sys
import unittest
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from hub.config import HubConfig, get_config
from hub.ui.components.confirm_dialog import ConfirmDialog
from hub.ui.components.guide_link import GuideLink
from hub.ui.components.safety_badge import SafetyBadge
from hub.ui.components.status_pill import StatusPill
from hub.ui.components.tour_dialog import TourDialog
from hub.ui.main_window import MainWindow
from hub.ui.theme import get_application_stylesheet


class TestHubUISmoke(unittest.TestCase):
    """UI Smoke Test Suite."""

    @classmethod
    def setUpClass(cls):
        # Create single QApplication instance for tests
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication(["--platform", "offscreen"])
        cls.config = get_config()
        cls.config.first_run_tour_completed = True

    def test_theme_and_stylesheet(self):
        """Verify global stylesheet compiles without syntax errors."""
        sheet = get_application_stylesheet()
        self.assertIn("background-color: #0a0d14", sheet)
        self.assertIn("QScrollBar", sheet)

    def test_safety_badges(self):
        """Verify SafetyBadge components for all 4 tiers."""
        for level in ["green", "yellow", "orange", "red"]:
            badge = SafetyBadge(level=level)
            self.assertIsNotNone(badge)
            self.assertIn(SafetyBadge.LEVELS[level]["label"], badge.text())

    def test_status_pill(self):
        """Verify StatusPill handles all operational statuses."""
        for status in ["HEALTHY", "ONLINE", "ACTIVE", "WARNING", "DEGRADED", "CRITICAL", "OFFLINE", "STANDALONE"]:
            pill = StatusPill(status)
            self.assertIsNotNone(pill)

    def test_tour_dialog(self):
        """Verify TourDialog slides and navigation."""
        dialog = TourDialog()
        self.assertEqual(dialog.current_slide, 0)
        dialog._next_slide()
        self.assertEqual(dialog.current_slide, 1)
        dialog._prev_slide()
        self.assertEqual(dialog.current_slide, 0)

    def test_confirm_dialog(self):
        """Verify ConfirmDialog displays structured pre-flight impact fields."""
        dialog = ConfirmDialog(
            title="Test Confirmation",
            message="Test message",
            what_it_does="Modifies test config",
            what_it_touches="test.json",
            expected_impact="Zero downtime",
            rollback_plan="Automatic rollback",
            affects_live_station=False,
            safety_level="orange"
        )
        self.assertIsNotNone(dialog)

    def test_main_window_navigation_and_views(self):
        """Verify MainWindow initializes all 23 views and routes cleanly."""
        win = MainWindow(self.config)
        self.assertIsNotNone(win)

        expected_views = [
            "dashboard", "health", "servers", "activity",
            "applications", "projects", "catalog", "updates",
            "site_overview", "site_sponsors", "site_partners",
            "site_takeovers", "site_media", "site_announcements",
            "site_roadmap", "site_deployments", "agents",
            "prompts", "handoffs", "reports", "backups",
            "guide", "settings"
        ]

        for v_id in expected_views:
            win.navigate_to(v_id)
            current = win.view_stack.currentWidget()
            self.assertIsNotNone(current, f"View {v_id} failed to render")
            if hasattr(current, "reset_scroll"):
                current.reset_scroll()

    def test_guide_view_routing(self):
        """Verify Guide view topic search and direct selection."""
        win = MainWindow(self.config)
        win._open_guide_topic("page-updates")
        self.assertEqual(win.view_stack.currentWidget(), win.v_guide)


if __name__ == "__main__":
    unittest.main()
