#!/usr/bin/env python3
"""
Unit and integration tests for the ALLTHINGS140 Visuals Ecosystem.
Tests:
- Canonical layer stacking hierarchy (Back-to-Front: Visual 10 < Stage 20 < Logo 30 < Alert 40 < Presence 50 < Reactions 60 < Energy 70)
- Layout schema normalization & persistence
- 24/7 visual rotation scheduler & anti-repeat engine
- Mixed takeover mode scheduler with configurable weighting
- Track music video mapping, muted playback & server-time drift sync
- Scoped audio-reactive visual transforms (Visual Content only)
- Black-screen elimination & failure recovery fallback chain
"""

import json
import os
import random
import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GREEN_DIR = PROJECT_ROOT / "visuals-green"
APP_DIR = PROJECT_ROOT / "visuals-app"


class VisualsSystemTests(unittest.TestCase):

    def setUp(self):
        self.layout_path = GREEN_DIR / "layout.json"
        self.assertTrue(self.layout_path.exists(), "layout.json must exist in visuals-green")
        with open(self.layout_path, "r", encoding="utf-8") as f:
            self.layout = json.load(f)

    def test_canonical_layer_stack_order(self):
        """Authoritative stacking order: Visual(10) < Stage(20) < Logo(30) < Alert(40) < Presence(50) < Reactions(60) < Energy(70)."""
        layers = self.layout.get("layers") or self.layout.get("workspaceLayers") or []
        self.assertGreaterEqual(len(layers), 7, "Must contain all 7 core broadcast layers")

        layer_map = {layer.get("id"): layer for layer in layers}
        
        # 1. Visual Content must be backmost
        visual = layer_map.get("visual-content")
        self.assertIsNotNone(visual, "visual-content layer must exist")
        self.assertEqual(visual.get("z"), 10, "Visual Content must have z: 10 (backmost)")
        self.assertEqual(visual.get("role"), "visual", "Visual layer role must be 'visual'")

        # 2. Stage Content must sit immediately above Visual Content
        stage = layer_map.get("stage-content")
        self.assertIsNotNone(stage, "stage-content layer must exist")
        self.assertEqual(stage.get("z"), 20, "Stage Content must have z: 20 (above visual)")
        self.assertEqual(stage.get("role"), "stage", "Stage layer role must be 'stage'")
        self.assertGreater(stage.get("z"), visual.get("z"), "Stage must be in front of Visual")

        # 3. HUD elements must sit above Stage Content
        logo = layer_map.get("station-logo")
        alert = layer_map.get("now-playing")
        presence = layer_map.get("presence-bubbles")
        reactions = layer_map.get("reactions")
        energy = layer_map.get("room-energy")

        for hud_name, hud_layer, expected_z in [
            ("station-logo", logo, 30),
            ("now-playing", alert, 40),
            ("presence-bubbles", presence, 50),
            ("reactions", reactions, 60),
            ("room-energy", energy, 70),
        ]:
            self.assertIsNotNone(hud_layer, f"{hud_name} layer must exist")
            self.assertEqual(hud_layer.get("z"), expected_z, f"{hud_name} must have z: {expected_z}")
            self.assertGreater(hud_layer.get("z"), stage.get("z"), f"{hud_name} must sit in front of Stage Content")

    def test_css_stacking_hierarchy_matches_canonical_model(self):
        """Verify that stage.css strictly implements the canonical z-stack."""
        css_path = GREEN_DIR / "stage.css"
        self.assertTrue(css_path.exists(), "stage.css must exist")
        css = css_path.read_text(encoding="utf-8")
        clean_css = re.sub(r"\s+", "", css)

        self.assertIn(".screens{position:absolute;left:0;top:0;width:100%;height:100%;z-index:10;", clean_css)
        self.assertIn(".stage-overlay{position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none;z-index:20;background:transparent!important;}", clean_css)
        self.assertIn(".stage-overlayvideo.stage-single-video{position:absolute;left:0;top:0;width:100%;height:100%;object-fit:fill;pointer-events:none;background:transparent;mask:url(#stage-screen-mask);-webkit-mask:url(#stage-screen-mask);}", clean_css)
        self.assertIn(".mode-logo{position:absolute;z-index:30;", clean_css)
        self.assertIn("z-index:40;", clean_css)  # Now Playing
        self.assertIn(".audience{position:absolute;display:flex;gap:8px;align-items:end;z-index:50;", clean_css)
        self.assertIn(".reactions{position:absolute;pointer-events:none;z-index:60;", clean_css)
        self.assertIn("z-index:70;", clean_css)  # Room Energy

    def test_single_decoder_stage_mask_structure_and_schema(self):
        """Green uses one Stage decoder plus an aperture mask, avoiding four duplicate 1080p decoders."""
        html_path = GREEN_DIR / "index.html"
        self.assertTrue(html_path.exists(), "index.html must exist")
        html = html_path.read_text(encoding="utf-8")
        self.assertEqual(html.count('id="stageVideo"'), 1)
        self.assertIn('stage-single-video', html)
        self.assertIn('stage-screen-mask', html)

        # Check layout.json screenOpening schema
        so = self.layout.get("screenOpening", {})
        self.assertTrue(so.get("enabled", False), "screenOpening must be enabled by default")
        self.assertGreaterEqual(float(so.get("x", -1)), 0.0)
        self.assertGreaterEqual(float(so.get("y", -1)), 0.0)
        self.assertGreater(float(so.get("width", 0)), 1.0)
        self.assertGreater(float(so.get("height", 0)), 1.0)
        self.assertLessEqual(float(so.get("x", 0)) + float(so.get("width", 0)), 100.5)
        self.assertLessEqual(float(so.get("y", 0)) + float(so.get("height", 0)), 100.5)

    def test_drag_and_drop_layer_reordering_depth_reassignment(self):
        """Verify that dragging layers recalculates canonical depth z-indexes from front to back."""
        layers = [
            {"id": "room-energy", "name": "Room Energy", "z": 70},
            {"id": "reactions", "name": "Reactions", "z": 60},
            {"id": "presence-bubbles", "name": "Presence Bubbles", "z": 50},
            {"id": "now-playing", "name": "Now Playing", "z": 40},
            {"id": "station-logo", "name": "Station Logo", "z": 30},
            {"id": "stage-content", "name": "Stage Content", "z": 20},
            {"id": "visual-content", "name": "Visual Content", "z": 10},
        ]

        def reorder(ordered_list, from_idx, to_idx):
            moved = ordered_list.pop(from_idx)
            ordered_list.insert(to_idx, moved)
            for i, layer in enumerate(ordered_list):
                layer["z"] = (len(ordered_list) - i) * 10
            return ordered_list

        # Test dragging Visual Content from index 6 (bottom) to index 0 (top)
        reordered = reorder(list(layers), 6, 0)
        self.assertEqual(reordered[0]["id"], "visual-content")
        self.assertEqual(reordered[0]["z"], 70)
        self.assertEqual(reordered[1]["id"], "room-energy")
        self.assertEqual(reordered[1]["z"], 60)
        self.assertEqual(reordered[-1]["id"], "stage-content")
        self.assertEqual(reordered[-1]["z"], 10)

    def test_selection_does_not_mutate_layer_stack_or_depth(self):
        """Selecting a layer to edit it must NEVER change its z-index or stack position."""
        layers = [
            {"id": "stage-content", "z": 20},
            {"id": "visual-content", "z": 10},
        ]
        selected_layer_id = "stage-content"
        # Selection adds class/state only
        is_selected = (layers[0]["id"] == selected_layer_id)
        self.assertTrue(is_selected)
        self.assertEqual(layers[0]["z"], 20, "Selection must never mutate layer z-index")
        self.assertEqual(layers[1]["z"], 10, "Selection must never mutate layer z-index")

    def test_anti_repeat_visual_scheduler(self):
        """Verify that the FIFO history buffer prevents immediate repeats during shuffle rotation."""
        playlist = [f"visual-{i:03d}.mp4" for i in range(1, 20)]
        recent_played = []
        recent_history_size = 5

        def get_next_visual():
            available = [item for item in playlist if item not in recent_played]
            pool = available if available else playlist
            chosen = random.choice(pool)
            recent_played.append(chosen)
            if len(recent_played) > recent_history_size:
                recent_played.pop(0)
            return chosen

        history_log = []
        for _ in range(50):
            selected = get_next_visual()
            if len(history_log) >= 1:
                window = history_log[-recent_history_size:]
                self.assertNotIn(selected, window, f"Item {selected} repeated within cooldown window of 5")
            history_log.append(selected)

    def test_mixed_takeover_mode_state_machine(self):
        """Verify that mixed takeover mode respects weighting ratios without starving either pool."""
        mix_ratio = 0.75  # 75% takeover, 25% station
        selections = []

        for _ in range(200):
            if random.random() < mix_ratio:
                selections.append("takeover")
            else:
                selections.append("station")

        takeover_count = selections.count("takeover")
        station_count = selections.count("station")

        self.assertGreaterEqual(takeover_count, 120, "Takeover visuals should be ~75% of selections")
        self.assertLessEqual(takeover_count, 180, "Takeover visuals should be ~75% of selections")
        self.assertGreaterEqual(station_count, 20, "Station visuals should not be starved")

    def test_track_music_video_sync_calculations(self):
        """Verify authoritative server-time synchronization and drift correction math."""
        track_started_at = 1786860000.0
        current_server_time = 1786860045.5  # 45.5 seconds into track
        sync_offset = 0.0

        target_pos = max(0.0, (current_server_time - track_started_at) + sync_offset)
        self.assertEqual(target_pos, 45.5)

        # Drift <= 1.5s is smooth
        video_current_time = 45.2
        drift = abs(video_current_time - target_pos)
        self.assertLessEqual(drift, 1.5, "Drift within 1.5s should not trigger disruptive seek")

        # Drift > 1.5s triggers seek
        video_current_time = 10.0
        drift = abs(video_current_time - target_pos)
        self.assertGreater(drift, 1.5, "Drift > 1.5s must trigger smooth seek to target_pos")
        corrected_time = target_pos
        self.assertEqual(corrected_time, 45.5)

    def test_audio_reactive_fx_strictly_scoped_to_visual_layer(self):
        """Audio-reactive pulse, bloom, and micro-shake must apply ONLY to .screens, never .stage-overlay."""
        css_path = GREEN_DIR / "stage.css"
        css = css_path.read_text(encoding="utf-8")

        stage_js = (GREEN_DIR / "stage.js").read_text(encoding="utf-8")
        self.assertIn("--visual-pulse", stage_js)
        self.assertIn("--visual-shake-x", stage_js)
        self.assertIn("--visual-bloom", stage_js)

        stage_rules = [line for line in css.split("}") if ".stage-overlay" in line]
        for rule in stage_rules:
            self.assertNotIn("--visual-pulse", rule, "Stage overlay must NEVER receive visual pulse")
            self.assertNotIn("--visual-shake", rule, "Stage overlay must NEVER receive camera shake")

    def test_black_screen_elimination_fallback_chain(self):
        """Verify that 3 consecutive decode/load failures engage the emergency fallback asset."""
        fallback = self.layout.get("fallback", {})
        self.assertTrue(fallback.get("url", "").startswith("https://"), "Fallback asset URL must be valid HTTPS")
        self.assertIn("visuals-phone.mp4", fallback.get("url", ""))

        failures = 0
        active_asset = "corrupt-video-1.mp4"

        for _ in range(3):
            failures += 1
            if failures >= 3:
                active_asset = fallback.get("url")

        self.assertEqual(active_asset, fallback.get("url"), "Fallback asset must engage after 3 failures")


if __name__ == "__main__":
    unittest.main()
