import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.catalog_integrity import scan_catalog
from tools.recover_playback_assets import run as recover_assets


class CatalogIntegrityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.master = self.root / "drive"
        self.emergency = self.root / "emergency"
        self.cache = self.root / "cache"
        for path in (self.master, self.emergency, self.cache):
            path.mkdir()
        self.db = self.root / "station.db"
        db = sqlite3.connect(self.db)
        db.executescript("""
            CREATE TABLE tracks(id INTEGER PRIMARY KEY,title TEXT,artist TEXT,filename TEXT UNIQUE,
              source_url TEXT DEFAULT '',rights_confirmed INTEGER,approved INTEGER,enabled INTEGER,
              added_by INTEGER,created_at INTEGER);
            CREATE TABLE audio_assets(id INTEGER PRIMARY KEY,track_id INTEGER UNIQUE,sha256 TEXT,
              source_path TEXT,size_bytes INTEGER,codec TEXT,sample_rate INTEGER,channels INTEGER,
              duration REAL,metadata_confidence TEXT,ingested_at INTEGER);
            CREATE TABLE audit_log(id INTEGER PRIMARY KEY,user_id INTEGER,action TEXT,detail TEXT,created_at INTEGER);
        """)
        db.close()

    def tearDown(self):
        self.temp.cleanup()

    def add(self, track_id, title, artist, filename, content=None, approved=1, enabled=1, rights=1):
        db = sqlite3.connect(self.db)
        db.execute("INSERT INTO tracks VALUES(?,?,?,?,?,?,?,?,?,?)", (track_id, title, artist, filename, "", rights, approved, enabled, None, track_id))
        db.commit(); db.close()
        if content is not None:
            (self.master / filename).write_bytes(content)

    def scan(self, resolver=None, hashes=True):
        resolver = resolver or (lambda name: self.emergency / name)
        return scan_catalog(self.db, self.master, self.emergency, resolver, compute_hashes=hashes)

    def test_same_metadata_different_audio_is_review_only(self):
        self.add(1, "Song", "Artist", "a.wav", b"different-a")
        self.add(2, "Song", "Artist", "b.wav", b"different-b")
        groups = self.scan()["duplicate_groups"]
        self.assertEqual(groups[0]["confidence"], "review_only")
        self.assertFalse(groups[0]["automatic_cleanup_eligible"])

    def test_identical_hash_is_exact_duplicate(self):
        self.add(1, "Song", "Artist", "a.wav", b"same-audio")
        self.add(2, "Song copy", "Artist", "b.wav", b"same-audio")
        groups = self.scan()["duplicate_groups"]
        self.assertEqual(groups[0]["classification"], "EXACT_AUDIO_DUPLICATE")
        self.assertTrue(groups[0]["automatic_cleanup_eligible"])

    def test_shared_canonical_file_is_never_auto_cleanup(self):
        shared = self.root / "shared.wav"
        shared.write_bytes(b"shared-audio")
        self.add(1, "One", "Artist", "one.wav")
        self.add(2, "Two", "Artist", "two.wav")
        (self.master / "one.wav").symlink_to(shared)
        (self.master / "two.wav").symlink_to(shared)
        groups = self.scan(hashes=False)["duplicate_groups"]
        self.assertEqual(groups[0]["classification"], "SHARED_CANONICAL_FILE")
        self.assertFalse(groups[0]["automatic_cleanup_eligible"])

    def test_missing_approved_degrades_but_unapproved_does_not(self):
        self.add(1, "Missing", "Artist", "missing.wav")
        report = self.scan()
        self.assertEqual(report["health"], "degraded")
        self.assertEqual(report["counts"]["missing_approved_audio"], 1)
        self.add(2, "Unapproved", "Artist", "unapproved.wav", approved=0)
        report = self.scan()
        self.assertEqual(report["counts"]["missing_approved_audio"], 1)
        self.assertEqual(next(r for r in report["records"] if r["id"] == 2)["status"], "UNAPPROVED")

    def test_drive_only_is_not_missing_but_not_playback_ready(self):
        self.add(1, "Stored", "Artist", "stored.wav", b"audio")
        report = self.scan()
        self.assertEqual(report["health"], "healthy")
        self.assertEqual(report["counts"]["missing_approved_audio"], 0)
        self.assertEqual(report["counts"]["stored_not_playback_ready"], 1)

    def test_variants_are_metadata_collision_not_auto_delete(self):
        self.add(1, "Song VIP", "Artist", "vip.wav", b"vip")
        self.add(2, "Song VIP", "Artist", "vip-live.wav", b"live")
        group = self.scan()["duplicate_groups"][0]
        self.assertEqual(group["classification"], "METADATA_COLLISION")
        self.assertFalse(group["automatic_cleanup_eligible"])

    def test_recovery_dry_run_never_writes(self):
        self.add(1, "Song", "Artist", "song.wav", b"not-real-audio")
        ledger = self.root / "ledger.json"
        result = recover_assets(self.db, self.master, self.emergency, ledger, False)
        self.assertFalse((self.emergency / "song.wav").exists())
        self.assertTrue(ledger.exists())
        self.assertIn(result["items"][0]["status"], {"FOUND_IN_PRIMARY_DRIVE", "MANUAL_REVIEW"})


if __name__ == "__main__":
    unittest.main()
