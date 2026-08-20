"""
ALLTHINGS140 Hub — Comprehensive Automated Test Suite (v1.1.0)
Tests registry models, health services, git state, AI providers, prompts, handoffs,
reports, backups, updates, site content CMS, Cloudflare deployments, and CLI.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from hub.config import HubConfig, get_config
from hub.registry.app_registry import AppRegistry
from hub.registry.project_registry import ProjectRegistry
from hub.services.activity_service import ActivityService
from hub.services.agent_service import AgentService
from hub.services.backup_service import BackupService
from hub.services.cloudflare_deployment_service import CloudflareDeploymentService
from hub.services.git_service import GitService
from hub.services.handoff_service import HandoffService
from hub.services.health_service import HealthService
from hub.services.prompt_service import PromptService
from hub.services.report_service import ReportService
from hub.services.site_content_service import SiteContentService
from hub.services.update_service import UpdateService


class TestHubSuite(unittest.TestCase):

    def setUp(self):
        self.app_registry = AppRegistry()
        self.project_registry = ProjectRegistry()
        self.health_service = HealthService()
        self.agent_service = AgentService()
        self.prompt_service = PromptService()
        self.handoff_service = HandoffService()
        self.report_service = ReportService()
        self.backup_service = BackupService()
        self.update_service = UpdateService()
        self.activity_service = ActivityService()
        self.site_content_service = SiteContentService()
        self.deploy_service = CloudflareDeploymentService()

    # 1. Application Registry Tests
    def test_app_registry_discovery(self):
        apps = self.app_registry.all()
        self.assertGreaterEqual(len(apps), 15, "Should register at least 15 core ecosystem components")
        
        app_ids = {a.id for a in apps}
        self.assertIn("radio-server", app_ids)
        self.assertIn("dj-app", app_ids)
        self.assertIn("web-frontend", app_ids)
        self.assertIn("visuals-workstation", app_ids)
        self.assertIn("visuals-green", app_ids)
        self.assertIn("visuals-realtime", app_ids)
        self.assertIn("hot-cache", app_ids)
        self.assertIn("catalog-integrity", app_ids)

    def test_app_registry_search_and_filter(self):
        visual_apps = self.app_registry.by_category("visuals")
        self.assertGreaterEqual(len(visual_apps), 3)

        search_results = self.app_registry.search("AutoDJ")
        self.assertTrue(any(a.id == "radio-server" for a in search_results))

    # 2. Project Registry Tests
    def test_project_registry_workspace(self):
        active = self.project_registry.get_active()
        self.assertIsNotNone(active)
        self.assertEqual(active.id, "AllThings140Radio")
        self.assertTrue(active.is_git)
        self.assertEqual(active.current_branch, "main")

    # 3. Git Service Tests
    def test_git_service_summary(self):
        sum_res = GitService.get_summary(self.app_registry.project_root)
        self.assertTrue(sum_res.is_git)
        self.assertEqual(sum_res.branch, "main")
        self.assertTrue(len(sum_res.head_hash) >= 7)
        self.assertGreaterEqual(len(sum_res.recent_commits), 1)

    # 4. AI Agent Service & Smart Prompt Tests
    def test_agent_providers_detection(self):
        providers = self.agent_service.get_providers()
        self.assertGreaterEqual(len(providers), 3)
        prov_ids = {p.id for p in providers}
        self.assertIn("antigravity", prov_ids)
        self.assertIn("codex", prov_ids)
        self.assertIn("opencode", prov_ids)

    def test_smart_prompt_generation(self):
        app = self.app_registry.get("visuals-workstation")
        self.assertIsNotNone(app)
        prompt = self.agent_service.generate_smart_prompt(app, "Geometry Parity Audit", "Test all viewports.")
        self.assertIn("TARGET APPLICATION: Visuals Desktop Show-Control Workstation", prompt)
        self.assertIn("DO NOT BREAK RULES", prompt)
        self.assertIn("4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32", prompt)
        self.assertIn("Geometry Parity Audit", prompt)

    # 5. Prompt Library Tests
    def test_prompt_library_presets_and_crud(self):
        prompts = self.prompt_service.all()
        self.assertGreaterEqual(len(prompts), 8)

        created = self.prompt_service.create(
            title="Unit Test Prompt",
            description="Testing prompt creation",
            prompt_text="Inspect system telemetry.",
            tags=["unit-test"]
        )
        self.assertIsNotNone(self.prompt_service.get(created.id))

        dup = self.prompt_service.duplicate(created.id)
        self.assertIsNotNone(dup)
        self.assertIn("Copy", dup.title)

        self.prompt_service.delete(created.id)
        self.prompt_service.delete(dup.id)
        self.assertIsNone(self.prompt_service.get(created.id))

    # 6. Engineering Handoff Tests
    def test_handoff_system_and_chatgpt_export(self):
        handoffs = self.handoff_service.all()
        self.assertGreaterEqual(len(handoffs), 1)

        new_h = self.handoff_service.create(
            app_id="web-frontend",
            app_name="Web Listener Frontend",
            agent_name="Antigravity",
            task_title="Test Suite Execution Handoff",
            changes_made=["Ran full test validation."],
            files_changed=["hub/tests/test_hub_suite.py"],
            tests_executed="All unit tests passed.",
            deployment_status="Staged",
            health_status="HEALTHY",
            remaining_work=["Verify desktop dock icon."],
            recommended_next_task="Package and install debian binary."
        )
        self.assertIsNotNone(new_h)

        export_text = self.handoff_service.export_for_chatgpt(new_h.id)
        self.assertIn("ENGINEERING HANDOFF: Test Suite Execution Handoff", export_text)
        self.assertIn("Authoring Agent", export_text)
        self.assertIn("Antigravity", export_text)
        self.assertIn("RECOMMENDED NEXT TASK", export_text)
        self.assertIn("Package and install debian binary", export_text)

    # 7. Report Library Tests
    def test_report_service_discovery(self):
        reports = self.report_service.all()
        self.assertGreaterEqual(len(reports), 5)
        categories = {r.category for r in reports}
        self.assertTrue(len(categories) >= 3)

        rep = reports[0]
        content = self.report_service.get_content(rep.id)
        self.assertTrue(len(content) > 0)

    # 8. Backup Service Tests
    def test_backup_service_discovery_and_creation(self):
        backups = self.backup_service.all()
        self.assertGreaterEqual(len(backups), 1)

        snap = self.backup_service.create_component_backup(
            component_name="test-snap",
            source_paths=["hub/config.py"]
        )
        self.assertIsNotNone(snap)
        self.assertTrue(os.path.exists(snap.path))
        if os.path.exists(snap.path):
            os.remove(snap.path)

    # 9. Update Service & 10-Step Workflow Tests
    def test_update_service_version_matrix(self):
        matrix = self.update_service.get_version_matrix(self.app_registry.all())
        self.assertGreaterEqual(len(matrix), 15)

    def test_safe_update_workflow_execution(self):
        app = self.app_registry.get("web-frontend")
        self.assertIsNotNone(app)
        steps = self.update_service.execute_safe_workflow(app)
        self.assertEqual(len(steps), 10, "Should execute exactly 10 safe update steps")
        self.assertTrue(all(s.isSuccess for s in steps), "All safe update steps should succeed")

    # 10. Health Service Tests
    def test_health_service_snapshot(self):
        snap = self.health_service.run_check()
        self.assertIn(snap.overall_status, ("healthy", "warning", "critical"))
        self.assertGreaterEqual(len(snap.checks), 5)

    # 11. Site Content CMS Tests
    def test_site_content_sponsors_and_partners(self):
        sponsors = self.site_content_service.sponsors
        self.assertGreaterEqual(len(sponsors), 1)

        # Test add sponsor
        new_sp = self.site_content_service.add_sponsor(
            name="Test Bass Audio",
            logo_url="assets/allthings140-logo-192.webp",
            website="https://allthings140radio.online",
            description="Test sponsor description",
            tier="Stage"
        )
        self.assertIsNotNone(new_sp)
        self.assertTrue(any(s.id == new_sp.id for s in self.site_content_service.sponsors))
        self.site_content_service.delete_sponsor(new_sp.id)

        # Test add partner
        new_pt = self.site_content_service.add_partner(
            name="Test Dubplate Collective",
            logo_url="assets/allthings140-logo-192.webp",
            website="https://allthings140radio.online",
            description="Test partner description",
            category="Collective"
        )
        self.assertIsNotNone(new_pt)
        self.site_content_service.delete_partner(new_pt.id)

    def test_site_content_takeovers_and_media(self):
        takeovers = self.site_content_service.takeovers
        self.assertGreaterEqual(len(takeovers), 1)

        media = self.site_content_service.media_assets
        self.assertGreaterEqual(len(media), 1)
        self.assertTrue(any("radio/index.html" in m.usedIn for m in media))

    # 12. Cloudflare Deployment Service Tests
    def test_deployment_service_smoke_test(self):
        test_res = self.deploy_service.run_smoke_test("https://allthings140radio.online")
        self.assertTrue(test_res.isSuccess)
        self.assertEqual(test_res.httpStatus, 200)
        self.assertTrue(test_res.audioStreamCheck or test_res.siteContentCheck)


if __name__ == "__main__":
    unittest.main()
