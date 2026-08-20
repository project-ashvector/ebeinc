import asyncio
import json
import os
import sqlite3
import tempfile
import unittest

from aiohttp.test_utils import AioHTTPTestCase

from app import Room, create_app

GREEN = "green-staging"
LIVE = "live"
ORIGIN = "https://allthings140-visuals-green.pages.dev"


def layout(layout_hash, environment, playlist=None):
    return {
        "layoutId": f"layout-{layout_hash}",
        "layoutHash": layout_hash,
        "environment": environment,
        "layers": [{"id": "visual-content", "role": "visual"}],
        "playlist": playlist or [],
        "previewMode": False,
    }


class RealtimeIsolationTest(AioHTTPTestCase):
    async def get_application(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ.update({
            "ALLOWED_ORIGINS": ORIGIN,
            "GREEN_ADMIN_TOKEN": "green-test-token",
            "LIVE_ADMIN_TOKEN": "live-test-token",
        })
        return create_app(self.tmp.name + "/state.db")

    async def event(self, ws, kind, timeout=1.0):
        async def receive():
            for _ in range(30):
                value = await ws.receive_json()
                if value.get("type") == kind:
                    return value
            self.fail(f"event {kind} not received")
        return await asyncio.wait_for(receive(), timeout)

    async def publish(self, environment, token, value):
        return await self.client.post(
            f"/admin/layout?environment={environment}",
            headers={"Authorization": f"Bearer {token}", "Origin": ORIGIN},
            json=value,
        )

    async def test_health_chat_reaction_and_explicit_environment(self):
        self.assertEqual((await self.client.get("/health")).status, 200)
        self.assertEqual((await self.client.get("/layout-state")).status, 400)
        self.assertEqual((await self.client.get("/visuals-state?environment=unknown")).status, 400)
        self.assertEqual((await self.client.get(f"/ws?environment={GREEN}", headers={"Origin": "https://evil.example"})).status, 403)
        ws = await self.client.ws_connect(f"/ws?environment={GREEN}", origin=ORIGIN)
        welcome = await ws.receive_json()
        self.assertEqual(welcome["environment"], GREEN)
        await ws.send_json({"type": "join", "environment": GREEN, "name": "<b>Bass</b>", "avatar": "orb-fire"})
        await self.event(ws, "room_state")
        await ws.send_json({"type": "message", "text": "<script>x</script>hello"})
        event = await self.event(ws, "message")
        self.assertNotIn("<", event["message"]["text"])
        await ws.send_json({"type": "reaction", "reaction": "fire", "event_id": "one"})
        self.assertGreater((await self.event(ws, "reaction"))["energy"], 0)
        await ws.close()

    async def test_layout_storage_authority_and_broadcast_are_isolated(self):
        green_ws = await self.client.ws_connect(f"/ws?environment={GREEN}", origin=ORIGIN)
        live_ws = await self.client.ws_connect(f"/ws?environment={LIVE}", origin=ORIGIN)
        await green_ws.receive_json(); await live_ws.receive_json()
        response = await self.publish(GREEN, "green-test-token", layout("green-hash", GREEN))
        self.assertEqual(response.status, 200)
        self.assertEqual((await self.event(green_ws, "layout_update"))["environment"], GREEN)
        with self.assertRaises(asyncio.TimeoutError):
            await self.event(live_ws, "layout_update", timeout=0.15)
        green_state = await (await self.client.get(f"/layout-state?environment={GREEN}")).json()
        live_state = await (await self.client.get(f"/layout-state?environment={LIVE}")).json()
        self.assertEqual(green_state["layoutHash"], "green-hash")
        self.assertEqual(live_state["layoutHash"], "")
        self.assertEqual((await self.publish(LIVE, "green-test-token", layout("bad-live", LIVE))).status, 401)
        self.assertEqual((await self.publish(LIVE, "live-test-token", layout("live-hash", LIVE))).status, 200)
        self.assertEqual((await (await self.client.get(f"/layout-state?environment={GREEN}")).json())["layoutHash"], "green-hash")
        await green_ws.close(); await live_ws.close()

    async def test_renderer_ack_is_environment_scoped(self):
        await self.publish(GREEN, "green-test-token", layout("green-ack", GREEN))
        ws = await self.client.ws_connect(f"/ws?environment={GREEN}", origin=ORIGIN)
        welcome = await ws.receive_json()
        await ws.send_json({"type": "renderer_ack", "environment": GREEN, "layoutHash": "green-ack", "renderStatus": "rendered"})
        await self.event(ws, "renderer_ack_received")
        green = await (await self.client.get(f"/renderer-state?environment={GREEN}")).json()
        live = await (await self.client.get(f"/renderer-state?environment={LIVE}")).json()
        self.assertEqual(green["layoutHash"], "green-ack")
        self.assertEqual(live["layoutHash"], "")
        self.assertNotEqual(welcome["environment"], LIVE)
        await ws.close()

    async def test_schedules_are_environment_scoped(self):
        now = 2_000_000_000_000
        body = {"environment": GREEN, "title": "test", "artist": "artist", "visual_url": "https://example.test/v.mp4", "start_at": now, "end_at": now + 60000}
        response = await self.client.post(f"/admin/schedule?environment={GREEN}", headers={"Authorization": "Bearer green-test-token"}, json=body)
        self.assertEqual(response.status, 201)
        rows = self.app["room"].db.execute("SELECT environment FROM schedules").fetchall()
        self.assertEqual([row[0] for row in rows], [GREEN])
        self.assertIsNone((await (await self.client.get(f"/visuals-state?environment={LIVE}")).json())["takeover"])

    async def test_corrupt_layout_survives_and_service_stays_alive(self):
        self.app["room"].db.execute("INSERT OR REPLACE INTO stats(key,value) VALUES(?,?)", (f"active_layout:{GREEN}", "{bad"))
        self.app["room"].db.commit()
        response = await self.client.get(f"/layout-state?environment={GREEN}")
        body = await response.json()
        self.assertEqual(response.status, 200)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "stored_layout_invalid")
        self.assertEqual((await self.client.get("/health")).status, 200)

    async def test_duplicate_playlist_ids_rejected(self):
        item = {"id": "same", "url": "https://example.test/a.mp4"}
        response = await self.publish(GREEN, "green-test-token", layout("duplicate", GREEN, [item, item]))
        self.assertEqual(response.status, 400)
        self.assertEqual((await response.json())["error"], "duplicate_playlist_asset_id")


class MigrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = self.tmp.name + "/legacy.db"

    def legacy_db(self, value):
        db = sqlite3.connect(self.path)
        db.executescript("CREATE TABLE stats(key TEXT PRIMARY KEY,value INTEGER NOT NULL); CREATE TABLE schedules(id TEXT PRIMARY KEY,title TEXT,artist TEXT,visual_url TEXT,start_at INTEGER,end_at INTEGER,enabled INTEGER);")
        db.execute("INSERT INTO stats VALUES('active_layout',?)", (json.dumps(value),))
        db.commit(); db.close()

    def test_preview_legacy_layout_migrates_to_green_only_and_is_idempotent(self):
        self.legacy_db({"layoutHash": "preview", "previewMode": True})
        room = Room(self.path); room.db.close()
        room = Room(self.path)
        keys = dict(room.db.execute("SELECT key,value FROM stats WHERE key LIKE 'active_layout:%'"))
        self.assertIn("active_layout:green-staging", keys)
        self.assertNotIn("active_layout:live", keys)
        columns = {row[1] for row in room.db.execute("PRAGMA table_info(schedules)")}
        self.assertIn("environment", columns)
        room.db.close()

    def test_non_preview_legacy_layout_migrates_to_live(self):
        self.legacy_db({"layoutHash": "public", "previewMode": False})
        room = Room(self.path)
        self.assertIsNotNone(room.db.execute("SELECT value FROM stats WHERE key='active_layout:live'").fetchone())
        room.db.close()


class StartupValidationTest(unittest.TestCase):
    def test_missing_origins_and_shared_tokens_fail_closed(self):
        old = dict(os.environ)
        try:
            os.environ.update({"ALLOWED_ORIGINS": "", "GREEN_ADMIN_TOKEN": "g", "LIVE_ADMIN_TOKEN": "l"})
            with self.assertRaisesRegex(RuntimeError, "ALLOWED_ORIGINS"):
                create_app(":memory:")
            os.environ.update({"ALLOWED_ORIGINS": ORIGIN, "GREEN_ADMIN_TOKEN": "same", "LIVE_ADMIN_TOKEN": "same"})
            with self.assertRaisesRegex(RuntimeError, "different"):
                create_app(":memory:")
        finally:
            os.environ.clear(); os.environ.update(old)


if __name__ == "__main__":
    unittest.main()
