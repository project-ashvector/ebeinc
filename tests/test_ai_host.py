import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from tools.ai_host import AIConfig, AIHost, AIReadyQueue, AnnouncementScheduler, PersonaLibrary, ReadyAnnouncement, Takeover, VoiceLibrary, safe_comedy, takeover_context

class AIHostTest(unittest.TestCase):
    def test_disabled_by_default_and_discovers_files_without_source_changes(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root); voices = base / "voices" / "custom"; voices.mkdir(parents=True)
            (voices / "voice.json").write_text(json.dumps({"id": "custom", "displayName": "Custom", "provider": "piper"}), encoding="utf-8")
            personas = base / "personas"; personas.mkdir()
            (personas / "host.json").write_text(json.dumps({"id": "host", "systemPrompt": "Be funny."}), encoding="utf-8")
            host = AIHost(AIConfig(), base / "voices", personas, base / "out")
            self.assertFalse(host.status()["enabled"])
            self.assertEqual([v.id for v in VoiceLibrary(base / "voices").discover()], ["custom"])
            self.assertEqual([p.id for p in PersonaLibrary(personas).discover()], ["host"])
            self.assertIsNone(host.generate("STATION_ID", {}))

    def test_takeover_context_is_structured_and_status_calculated(self):
        now = int(time.time())
        takeover = Takeover("1", "Artist", "Display", now + 3600, now + 7200, timezone="UTC")
        context = takeover_context([takeover], now)
        self.assertEqual(context["artist"], "Display")
        self.assertEqual(context["startTimestamp"], now + 3600)
        self.assertEqual(context["status"], "STARTING_SOON")

    def test_comedy_guard_blocks_real_harm_and_allows_profanity(self):
        self.assertTrue(safe_comedy("Turn it up, you magnificent bastard."))
        self.assertFalse(safe_comedy("This is a bomb threat."))
        self.assertFalse(safe_comedy("kill yourself"))

    def test_ready_queue_discards_stale_event_facts(self):
        queue = AIReadyQueue(3)
        queue.add(ReadyAnnouncement("ARTIST_TAKEOVER_PROMO", "old", "old-signature", 1))
        queue.add(ReadyAnnouncement("STATION_ID", "fresh", "new-signature", 2))
        queue.invalidate("new-signature")
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue.pop("new-signature").text, "fresh")
        self.assertIsNone(queue.pop("old-signature"))

    def test_song_gate_stays_within_four_to_seven_songs(self):
        scheduler = AnnouncementScheduler()
        decisions = [scheduler.track_finished() for _ in range(7)]
        self.assertTrue(any(decisions))
        scheduler.break_completed()
        self.assertEqual(scheduler.songs_since_break, 0)

    def test_prune_cache_bounds_ephemeral_storage(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root); out = base / "out"; out.mkdir()
            host = AIHost(AIConfig(), base / "voices", base / "personas", out)
            for i in range(10):
                f = out / f"test-{i:02d}.wav"
                f.write_bytes(b"mock audio")
                os.utime(f, (time.time() - (10 - i) * 3600, time.time() - (10 - i) * 3600))
            # Test pruning with max_files=5
            pruned = host.prune_cache(max_files=5, max_age_seconds=86400)
            self.assertEqual(pruned, 5)
            self.assertEqual(len(list(out.glob("*.wav"))), 5)


if __name__ == "__main__":
    unittest.main()
