import importlib.util
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import base64
import re
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


class RadioSystemTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        base = Path(cls.temp.name)
        os.environ.update({
            "ALLTHINGS140_CONFIG_DIR": str(base / "etc"),
            "ALLTHINGS140_DATA_DIR": str(base / "data"),
            "ALLTHINGS140_MUSIC_DIR": str(base / "data/music"),
            "ALLTHINGS140_AD_DIR": str(base / "data/ads"),
            "ALLTHINGS140_DB_PATH": str(base / "data/station.db"),
            "ALLTHINGS140_CONFIG_PATH": str(base / "etc/config.json"),
            "ALLTHINGS140_ROTATION_STATE_PATH": str(base / "data/rotation-state.json"),
            "ALLTHINGS140_EVENT_LOG_PATH": str(base / "data/events.jsonl"),
        })
        sys.path.insert(0, str(TOOLS))
        spec = importlib.util.spec_from_file_location("allthings140_server_test", TOOLS / "server.py")
        cls.app = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.app
        spec.loader.exec_module(cls.app)
        cls.app.init_db()
        cls.httpd = cls.app.ReusableThreadingHTTPServer(("127.0.0.1", 0), cls.app.PublicGatewayHandler)
        cls.base_url = f"http://127.0.0.1:{cls.httpd.server_port}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.private_httpd = cls.app.ReusableThreadingHTTPServer(("127.0.0.1", 0), cls.app.Handler)
        cls.private_base_url = f"http://127.0.0.1:{cls.private_httpd.server_port}"
        cls.private_thread = threading.Thread(target=cls.private_httpd.serve_forever, daemon=True)
        cls.private_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=3)
        cls.private_httpd.shutdown()
        cls.private_httpd.server_close()
        cls.private_thread.join(timeout=3)
        cls.temp.cleanup()

    def request(self, path, method="GET", payload=None):
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Accept": "application/json", "X-Client-IP": "203.0.113.15"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base_url + path, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                return response.status, dict(response.headers), json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), json.loads(exc.read())

    def private_request(self, path, method="GET", payload=None, token=""):
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(self.private_base_url + path, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_public_status_and_health(self):
        status, _, health = self.request("/health")
        self.assertEqual((status, health["ok"]), (200, True))
        status, _, station = self.request("/api/public/status")
        self.assertEqual(status, 200)
        self.assertEqual(station["stream_url"], "https://stream.ebeinc.online/live.mp3")
        self.assertEqual(station["station_generation_id"], self.app.STATION_GENERATION_ID)
        self.assertIsInstance(station["station_sequence"], int)
        self.assertIsInstance(station["server_time"], float)
        status, _, schedule = self.request("/api/public/schedule")
        self.assertEqual((status, schedule["takeovers"]), (200, []))

    def test_public_alert_catalog_uses_opaque_ids_and_safe_flags(self):
        self.app.AD_DIR.mkdir(parents=True, exist_ok=True)
        alert_path = self.app.AD_DIR / "private-server-name.mp3"
        alert_path.write_bytes(b"ID3test-alert")
        self.app.save_ad_meta({
            "interval_seconds": 900,
            "server_stream_alert_injection_enabled": True,
            "client_account_alerts_enabled": False,
            "ads": {alert_path.name: {"enabled": True, "client_delivery_enabled": True, "duration_seconds": 7.25}},
        })
        status, _, catalog = self.request("/api/public/alert-catalog")
        self.assertEqual(status, 200)
        self.assertEqual(catalog["interval_seconds"], 900)
        self.assertTrue(catalog["server_stream_alert_injection_enabled"])
        self.assertFalse(catalog["client_account_alerts_enabled"])
        self.assertEqual(len(catalog["alerts"]), 1)
        item = catalog["alerts"][0]
        self.assertNotIn(alert_path.name, json.dumps(item))
        self.assertRegex(item["id"], r"^[a-f0-9]{32}$")
        request = urllib.request.Request(self.base_url + item["url"], headers={"Range": "bytes=0-2"})
        with urllib.request.urlopen(request, timeout=3) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(response.read(), b"ID3")

    def test_rotation_audit_is_not_publicly_exposed(self):
        status, _, _ = self.request("/api/rotation-audit")
        self.assertEqual(status, 404)

    def test_submission_validation_honeypot_and_rate_limit(self):
        invalid, _, _ = self.request("/api/public/submissions", "POST", {"artist": "A"})
        self.assertEqual(invalid, 400)
        accepted, _, _ = self.request("/api/public/submissions", "POST", {"website": "spam.example"})
        self.assertEqual(accepted, 202)
        for index in range(3):
            mix_fields = {
                "submission_type": "recorded_mix", "duration_minutes": 60,
                "rights_confirmed": True, "genres": "dubstep", "tracklist": "Artist - Track",
            } if index == 0 else {}
            status, _, result = self.request("/api/public/submissions", "POST", {
                "artist": f"Artist {index}", "title": f"Track {index}",
                "track_url": f"https://example.com/track-{index}", "email": f"artist{index}@example.com",
                **mix_fields,
            })
            self.assertEqual((status, result["ok"]), (201, True))
        with self.app.DB_LOCK, self.app.db_connect() as db:
            mix = db.execute("SELECT genre,notes FROM review_queue WHERE source_url=?", ("https://example.com/track-0",)).fetchone()
        self.assertEqual(mix["genre"], "public recorded mix")
        self.assertEqual(json.loads(mix["notes"])["duration_minutes"], 60)
        limited, headers, _ = self.request("/api/public/submissions", "POST", {
            "artist": "Limited", "title": "Limited", "track_url": "https://example.com/limited", "email": "limited@example.com",
        })
        self.assertEqual(limited, 429)
        self.assertIn("Retry-After", headers)

    def test_reminder_signup_requires_consent(self):
        invalid, _, _ = self.request("/api/public/newsletter", "POST", {"email": "listener@example.com"})
        self.assertEqual(invalid, 400)
        accepted, _, payload = self.request("/api/public/newsletter", "POST", {"email": "listener@example.com", "consent": True})
        self.assertEqual((accepted, payload["ok"]), (201, True))

    def test_rotation_state_round_trip(self):
        manager = self.app.AutoDJManager()
        manager.rotation_order = [7, 4, 9]
        manager.rotation_seen = {7, 4}
        manager.rotation_index = 2
        manager.save_rotation_state()
        restored = self.app.AutoDJManager()
        self.assertEqual(restored.rotation_order, [7, 4, 9])
        self.assertEqual(restored.rotation_seen, {7, 4})
        self.assertEqual(restored.rotation_index, 2)

    def test_artist_cooldown_avoids_adjacent_repeat(self):
        rows=[{"id":1,"artist":"A"},{"id":2,"artist":"A"},{"id":3,"artist":"B"},{"id":4,"artist":"C"},{"id":5,"artist":"D"}]
        order=self.app.AutoDJManager.cooldown_order(rows,3)
        artists={x["id"]:x["artist"] for x in rows}
        sequence=[artists[x] for x in order]
        self.assertNotEqual(sequence[0],sequence[1])
        self.assertEqual(sorted(order),[1,2,3,4,5])

    def test_encoder_write_recovers_without_restarting_track(self):
        manager = self.app.AutoDJManager()
        writes = []

        class Input:
            def __init__(self, fail=False):
                self.fail = fail
            def write(self, data):
                if self.fail:
                    raise BrokenPipeError("simulated Icecast source reset")
                writes.append(data)
            def flush(self):
                return None

        class Encoder:
            def __init__(self, fail, pid):
                self.stdin = Input(fail)
                self.pid = pid

        encoders = [Encoder(True, 1), Encoder(False, 2)]
        manager.encoder = encoders.pop(0)
        manager.start_encoder = lambda: setattr(manager, "encoder", manager.encoder or encoders.pop(0))
        manager.stop_encoder = lambda: setattr(manager, "encoder", None)
        manager.write_pcm(b"pcm")
        self.assertEqual(writes, [b"pcm"])

    def test_icecast_relay_replaces_client_authorization(self):
        spec = importlib.util.spec_from_file_location("icecast_auth_relay_test", TOOLS / "icecast_auth_relay.py")
        relay = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(relay)
        request = b"SOURCE /live.mp3 HTTP/1.1\r\nAuthorization: Basic unsafe\r\nContent-Type: audio/mpeg\r\n\r\naudio"
        secured = relay.authenticated_header(request, "rotated-test-secret")
        expected = base64.b64encode(b"source:rotated-test-secret")
        self.assertIn(b"Authorization: Basic " + expected, secured)
        self.assertNotIn(b"unsafe", secured)
        self.assertTrue(secured.endswith(b"audio"))

    def test_metadata_filename_parser_is_conservative(self):
        spec = importlib.util.spec_from_file_location("audio_ingest_test", TOOLS / "audio_ingest.py")
        ingest = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ingest)
        self.assertEqual(ingest.parse_filename("Artist - Track.wav"), ("Artist", "Track", "high"))
        self.assertEqual(ingest.parse_filename("Artist_–_Track.mp3"), ("Artist", "Track", "high"))
        artist, title, confidence = ingest.parse_filename("Ambiguous Track Name.flac")
        self.assertEqual((artist, title, confidence), ("", "Ambiguous Track Name", "low"))

    def test_upload_retries_transient_failure_with_same_request_id(self):
        spec = importlib.util.spec_from_file_location("dj_upload_retry_test", TOOLS / "dj_app.py")
        dj = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dj)
        api = dj.API("http://station.invalid")
        request_ids = []

        def attempt(path, fields, progress, upload_id):
            request_ids.append(upload_id)
            if len(request_ids) == 1:
                error = dj.APIError("connection reset")
                error.transient = True
                raise error
            return {"ok": True}

        api._upload_once = attempt
        with mock.patch.object(dj.time, "sleep"):
            result = api.upload(Path("track.wav"), {})
        self.assertEqual(result, {"ok": True})
        self.assertEqual(len(request_ids), 2)
        self.assertEqual(request_ids[0], request_ids[1])

    def test_ingest_schema_rejects_duplicate_content_hash(self):
        spec = importlib.util.spec_from_file_location("audio_ingest_schema_test", TOOLS / "audio_ingest.py")
        ingest = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ingest)
        db_path = Path(self.temp.name) / "ingest-schema.db"
        with self.app.sqlite3.connect(db_path) as db:
            db.execute("CREATE TABLE tracks(id INTEGER PRIMARY KEY, title TEXT, artist TEXT, filename TEXT)")
            ingest.ensure_schema(db)
            db.execute("INSERT INTO audio_assets(track_id,sha256,source_path,size_bytes,codec,sample_rate,channels,duration,metadata_confidence,ingested_at) VALUES(NULL,'abc','one',1,'mp3',44100,2,60,'high',1)")
            with self.assertRaises(self.app.sqlite3.IntegrityError):
                db.execute("INSERT INTO audio_assets(track_id,sha256,source_path,size_bytes,codec,sample_rate,channels,duration,metadata_confidence,ingested_at) VALUES(NULL,'abc','two',1,'mp3',44100,2,60,'high',1)")

    def test_takeover_invite_round_trip(self):
        token = "artist-form-test-token"
        now = int(time.time())
        with self.app.DB_LOCK, self.app.db_connect() as db:
            db.execute(
                "INSERT INTO takeover_invites(token_hash,label,status,created_by,created_at,expires_at) VALUES(?,?,'open',NULL,?,?)",
                (self.app.hashlib.sha256(token.encode()).hexdigest(), "Test Artist", now, now + 3600),
            )
            db.commit()
        payload, status = self.app.submit_takeover_invite(token, {
            "artist": "Test Artist", "title": "Test Takeover",
            "starts_at": now + 7200, "ends_at": now + 10800,
            "timezone": "America/New_York",
            "logo_data": "data:image/png;base64,AAAA",
            "socials": [{"platform": "Twitch", "url": "https://twitch.tv/test"}],
        })
        self.assertEqual(status, 400)
        payload, status = self.app.submit_takeover_invite(token, {
            "artist": "Test Artist", "title": "Test Takeover",
            "starts_at": now + 7200, "ends_at": now + 10800,
            "timezone": "America/New_York",
            "socials": [{"platform": "Twitch", "url": "https://twitch.tv/test"}],
        })
        self.assertEqual((status, payload["ok"]), (201, True))
        self.assertEqual(self.app.takeover_rows(True), [])
        row = self.app.takeover_rows(False)[0]
        self.assertEqual(row["socials"][0]["platform"], "Twitch")
        self.assertEqual(row["timezone"], "America/New_York")
        self.assertEqual(row["status"], "pending")

    def test_worker_and_service_worker_guards(self):
        worker = (ROOT / "_worker.js").read_text(encoding="utf-8")
        service_worker = (ROOT / "radio/sw-v47.js").read_text(encoding="utf-8")
        app = (ROOT / "radio/app.js").read_text(encoding="utf-8")
        self.assertNotIn('ebmarah-laptop-ai.tail', worker)
        self.assertIn('const OBS_STREAM_ORIGIN = "https://stream.ebeinc.online/live.mp3"', worker)
        self.assertIn('url.pathname.startsWith("/api/")', service_worker)
        self.assertIn('fetch("/api/public/submissions"', app)
        self.assertIn('allthings140-radio-v63', service_worker)
        self.assertIn('support.css?v=1.1.0', service_worker)
        self.assertIn('support.js?v=1.1.0', service_worker)
        self.assertIn('const networkFirst =', service_worker)

    def test_listener_status_reads_do_not_change_broadcast_sequence(self):
        before = self.app.AUTODJ.snapshot()["sequence"]
        for _ in range(5):
            self.app.public_status()
        self.assertEqual(self.app.AUTODJ.snapshot()["sequence"], before)

    def test_catalog_unlink_is_idempotent_and_preserves_audio(self):
        status, login = self.private_request("/api/login", "POST", {"username": "ebmarah", "password": self.app.DEFAULT_PASSWORD})
        self.assertEqual(status, 200)
        token = login["token"]
        audio = self.app.MUSIC_DIR / "shared-proof.wav"
        audio.write_bytes(b"preserve-this-asset")
        with self.app.DB_LOCK, self.app.db_connect() as db:
            cursor = db.execute(
                "INSERT INTO tracks(title,artist,filename,rights_confirmed,approved,enabled,created_at) VALUES('Proof','Artist',?,1,1,1,?)",
                (audio.name, int(time.time())),
            )
            track_id = int(cursor.lastrowid); db.commit()
        operation_id = "timeout-safe-proof-001"
        status, first = self.private_request("/api/catalog-operations", "POST", {"operation_id": operation_id, "action": "unlink_catalog_records", "track_ids": [track_id]}, token)
        self.assertEqual(status, 200)
        self.assertEqual(first["items"][0]["result"], "CATALOG_RECORD_REMOVED")
        self.assertTrue(audio.is_file())
        status, replay = self.private_request("/api/catalog-operations", "POST", {"operation_id": operation_id, "action": "unlink_catalog_records", "track_ids": [track_id]}, token)
        self.assertEqual(status, 200)
        self.assertTrue(replay["idempotent_replay"])
        self.assertTrue(audio.is_file())
        status, observed = self.private_request(f"/api/catalog-operations/{operation_id}", token=token)
        self.assertEqual((status, observed["status"]), (200, "COMPLETED"))

    def test_orphan_quarantine_and_restore_round_trip(self):
        status, login = self.private_request("/api/login", "POST", {"username": "ebmarah", "password": self.app.DEFAULT_PASSWORD})
        self.assertEqual(status, 200)
        token = login["token"]
        audio = self.app.MUSIC_DIR / "orphan-proof.wav"
        original = b"quarantine-round-trip"
        audio.write_bytes(original)
        operation_id = "quarantine-proof-001"
        status, quarantined = self.private_request("/api/catalog-quarantine", "POST", {"operation_id": operation_id, "filename": audio.name}, token)
        self.assertEqual((status, quarantined["result"]), (200, "FILE_QUARANTINED"))
        self.assertFalse(audio.exists())
        status, restored = self.private_request(f"/api/catalog-quarantine/{operation_id}/restore", "POST", {}, token)
        self.assertEqual((status, restored["result"]), (200, "RESTORED"))
        self.assertEqual(audio.read_bytes(), original)

    def test_mix_ad_pcm_frame_alignment(self):
        autodj = self.app.AUTODJ
        # Frame size is 4 bytes (2 channels * 2 bytes/sample)
        # Test 1: exact frame (8 bytes)
        music_exact = b"\x00\x00\x10\x00\x20\x00\x30\x00"
        res = autodj.mix_ad(music_exact)
        self.assertEqual(len(res), len(music_exact))

        # Test 2: odd number of bytes (e.g. 7 bytes) — should truncate safely without ValueError
        music_odd = b"\x00\x00\x10\x00\x20\x00\x30"
        res_odd = autodj.mix_ad(music_odd)
        self.assertEqual(len(res_odd) % 4, 0)
        self.assertEqual(len(res_odd), 4)

        # Test 3: empty bytes
        self.assertEqual(autodj.mix_ad(b""), b"")

    def test_remediation_guards(self):
        worker = (ROOT / "radio/_worker.js").read_text(encoding="utf-8")
        sw = (ROOT / "radio/sw.js").read_text(encoding="utf-8")
        sw_v47 = (ROOT / "radio/sw-v47.js").read_text(encoding="utf-8")
        app = (ROOT / "radio/app.js").read_text(encoding="utf-8")
        stage_css = (ROOT / "visuals-green/stage.css").read_text(encoding="utf-8")
        overlay_css = (ROOT / "visuals-green/overlay.css").read_text(encoding="utf-8")
        dj_app = (ROOT / "tools/dj_app.py").read_text(encoding="utf-8")
        server = (ROOT / "tools/server.py").read_text(encoding="utf-8")
        discord = (ROOT / "discord-bot/index.js").read_text(encoding="utf-8")
        restore_script = ROOT / "operations/restore-vm.sh"

        # Worker auth check
        self.assertIn("env.ADMIN_ALERT_KEY || env.TAKEOVER_ALERT_KEY || env.ADMIN_TOKEN", worker)
        self.assertIn("Response.json({ error: \"Unauthorized\" }, { status: 401", worker)

        # SW audio bypass
        self.assertIn('(?:mp4|webm|mp3|m3u8|ts)', sw)
        self.assertIn('url.pathname.startsWith("/obs/")', sw)
        self.assertIn('(?:mp4|webm|mp3|m3u8|ts)', sw_v47)

        # App.js safe DOM and background resume
        self.assertIn("mode.replaceChildren(", app)
        self.assertIn("header.replaceChildren(", app)

        # Visuals layer stacking
        clean_stage_css = re.sub(r"\s+", "", stage_css)
        clean_overlay_css = re.sub(r"\s+", "", overlay_css)
        self.assertIn(".audience{position:absolute;display:flex;gap:8px;align-items:end;z-index:50", clean_stage_css)
        self.assertIn(".energy{position:absolute;z-index:70;background:#08020ddd;border:1pxsolid#7d26d9;", clean_stage_css)
        self.assertIn(".mode-logo{position:absolute;z-index:30", clean_overlay_css)

        # DJ App queue fix and async alert
        self.assertNotIn("self.render_rotation([])", dj_app.split("def set_takeover_status")[1].split("def _scroll_rotation_with_mouse")[0])
        self.assertIn("threading.Thread(target=send_alert", dj_app)
        self.assertIn('"DECODER", "HOT CACHE"', dj_app)
        self.assertIn("self.health_labels.get(key)", dj_app)
        self.assertIn("STATION STATUS UNKNOWN", dj_app)
        self.assertIn("threading.BoundedSemaphore(max_request_threads)", server)

        # Discord Bot keys
        self.assertIn("data.current_title", discord)
        self.assertIn("data.current_artist", discord)

        # Restore script
        self.assertTrue(restore_script.is_file())
        self.assertTrue(os.access(restore_script, os.X_OK))


if __name__ == "__main__":
    unittest.main()
