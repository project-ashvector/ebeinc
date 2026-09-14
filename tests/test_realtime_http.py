#!/usr/bin/env python3
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

from aiohttp.test_utils import TestClient, TestServer

ROOT = Path(__file__).resolve().parent.parent
APP_PATH = ROOT / "visuals-realtime" / "app.py"

GREEN_ENV = "green-staging"
LIVE_ENV = "live"
GREEN_ORIGIN = "https://allthings140-visuals-green.pages.dev"
LIVE_ORIGIN = "https://allthings140radio.online"
GREEN_TOKEN = "test-green-admin-token"
LIVE_TOKEN = "test-live-admin-token"

spec = importlib.util.spec_from_file_location("at140_visuals_realtime", APP_PATH)
rt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rt)


class RealtimeHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._old_env = {k: os.environ.get(k) for k in (
            "ALLOWED_ORIGINS", "GREEN_ADMIN_TOKEN", "LIVE_ADMIN_TOKEN", "MEDIA_ROOT",
        )}
        self.tmp = tempfile.TemporaryDirectory()
        media_root = Path(self.tmp.name) / "media"
        media_root.mkdir()
        os.environ["ALLOWED_ORIGINS"] = f"{GREEN_ORIGIN},{LIVE_ORIGIN}"
        os.environ["GREEN_ADMIN_TOKEN"] = GREEN_TOKEN
        os.environ["LIVE_ADMIN_TOKEN"] = LIVE_TOKEN
        os.environ["MEDIA_ROOT"] = str(media_root)
        self.app = rt.create_app(str(Path(self.tmp.name) / "realtime.db"))
        self.app["origins"] = {GREEN_ORIGIN, LIVE_ORIGIN}
        self.server = TestServer(self.app)
        self.client = TestClient(self.server)
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        self.tmp.cleanup()
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def admin_headers(self, environment):
        token = GREEN_TOKEN if environment == GREEN_ENV else LIVE_TOKEN
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def publish_layout(self, environment, layout):
        payload = dict(layout)
        payload["environment"] = environment
        return await self.client.post(
            f"/admin/layout?environment={environment}",
            data=json.dumps(payload).encode(),
            headers=self.admin_headers(environment),
        )

    async def open_renderer(self, origin, environment):
        ws = await self.client.ws_connect(
            f"/ws?environment={environment}",
            headers={"Origin": origin},
        )
        first = await ws.receive_json()
        self.assertEqual(first.get("type"), "welcome")
        sid = first.get("session_id")
        self.assertTrue(sid)
        await ws.send_json({
            "type": "renderer_heartbeat",
            "environment": environment,
            "layoutHash": "",
            "videoReadyState": 0,
            "visualMode": "new",
        })
        for _ in range(6):
            msg = await ws.receive_json()
            if msg.get("type") == "renderer_heartbeat_ack":
                break
        else:
            self.fail("renderer heartbeat ACK not received")
        return ws, sid

    async def test_cors_preflight_for_green_renderer_ack(self):
        res = await self.client.options(
            "/renderer-ack",
            headers={
                "Origin": GREEN_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        self.assertEqual(res.status, 204)
        self.assertEqual(res.headers.get("Access-Control-Allow-Origin"), GREEN_ORIGIN)
        self.assertIn("POST", res.headers.get("Access-Control-Allow-Methods", ""))

    async def test_admin_publish_fails_closed_without_token(self):
        res = await self.client.post(
            f"/admin/layout?environment={GREEN_ENV}",
            json={"layoutHash": "x" * 64, "layers": [], "environment": GREEN_ENV},
        )
        self.assertEqual(res.status, 401)

    async def test_publish_and_renderer_ack_round_trip(self):
        layout = {
            "schemaVersion": 2,
            "layoutId": "layout-test",
            "layoutHash": "a" * 64,
            "previewMode": True,
            "layers": [
                {"id": "visual-content", "role": "visual", "z": 10},
                {"id": "stage-content", "role": "stage", "z": 20},
            ],
            "screenOpening": {
                "x": 0,
                "y": 0,
                "width": 50,
                "height": 50,
                "enabled": True,
            },
        }
        res = await self.publish_layout(GREEN_ENV, layout)
        self.assertEqual(res.status, 200)
        body = await res.json()
        self.assertEqual(body["layoutHash"], layout["layoutHash"])

        state = await (await self.client.get(f"/layout-state?environment={GREEN_ENV}")).json()
        self.assertEqual(state["layoutHash"], layout["layoutHash"])
        self.assertEqual(state["layout"]["screenOpening"]["x"], 0)

        ws, sid = await self.open_renderer(GREEN_ORIGIN, GREEN_ENV)
        ack = {
            "rendererSessionId": sid,
            "environment": GREEN_ENV,
            "layoutId": layout["layoutId"],
            "layoutHash": layout["layoutHash"],
            "stageAssetId": "stage-a",
            "visualAssetId": "visual-b",
            "renderAppliedAt": 1234,
            "videoReadyState": 4,
            "renderStatus": "RENDERED",
        }
        res = await self.client.post(
            "/renderer-ack",
            json=ack,
            headers={"Origin": GREEN_ORIGIN},
        )
        self.assertEqual(res.status, 200)
        self.assertEqual(res.headers.get("Access-Control-Allow-Origin"), GREEN_ORIGIN)
        renderer = await (await self.client.get(f"/renderer-state?environment={GREEN_ENV}")).json()
        self.assertEqual(renderer["ack"]["layoutHash"], layout["layoutHash"])
        self.assertEqual(renderer["ack"]["renderStatus"], "RENDERED")
        await ws.close()

    async def test_http_renderer_ack_rejects_inactive_session_and_stale_hash(self):
        layout = {"layoutId": "active", "layoutHash": "e" * 64, "layers": []}
        res = await self.publish_layout(GREEN_ENV, layout)
        self.assertEqual(res.status, 200)
        res = await self.client.post("/renderer-ack", json={
            "rendererSessionId": "not-active",
            "environment": GREEN_ENV,
            "layoutHash": "e" * 64,
            "renderStatus": "rendered",
        }, headers={"Origin": GREEN_ORIGIN})
        self.assertEqual(res.status, 409)
        ws, sid = await self.open_renderer(GREEN_ORIGIN, GREEN_ENV)
        res = await self.client.post("/renderer-ack", json={
            "rendererSessionId": sid,
            "environment": GREEN_ENV,
            "layoutHash": "f" * 64,
            "renderStatus": "rendered",
        }, headers={"Origin": GREEN_ORIGIN})
        self.assertEqual(res.status, 409)
        await ws.close()

    async def test_live_chat_cors_and_environment_isolation(self):
        green_ws, green_sid = await self.open_renderer(GREEN_ORIGIN, GREEN_ENV)
        live_ws, live_sid = await self.open_renderer(LIVE_ORIGIN, LIVE_ENV)

        res = await self.publish_layout(GREEN_ENV, {"layoutId": "layout-green", "layoutHash": "b" * 64, "layers": []})
        self.assertEqual(res.status, 200)
        green_ack = {
            "rendererSessionId": green_sid,
            "environment": GREEN_ENV,
            "layoutId": "layout-green",
            "layoutHash": "b" * 64,
            "stageAssetId": "stage-green",
            "visualAssetId": "visual-green",
            "videoReadyState": 4,
            "stageReadyState": 4,
            "renderStatus": "rendered",
        }
        res = await self.client.post("/renderer-ack", json=green_ack, headers={"Origin": GREEN_ORIGIN})
        self.assertEqual(res.status, 200)

        res = await self.publish_layout(LIVE_ENV, {"layoutId": "layout-live", "layoutHash": "c" * 64, "layers": []})
        self.assertEqual(res.status, 200)
        live_ack = {
            "rendererSessionId": live_sid,
            "environment": LIVE_ENV,
            "layoutId": "layout-live",
            "layoutHash": "c" * 64,
            "stageAssetId": "stage-live",
            "visualAssetId": "visual-live",
            "videoReadyState": 4,
            "stageReadyState": 4,
            "renderStatus": "rendered",
        }
        res = await self.client.post("/renderer-ack", json=live_ack, headers={"Origin": LIVE_ORIGIN})
        self.assertEqual(res.status, 200)
        self.assertEqual(res.headers.get("Access-Control-Allow-Origin"), LIVE_ORIGIN)

        green = await (await self.client.get(f"/renderer-state?environment={GREEN_ENV}")).json()
        live = await (await self.client.get(f"/renderer-state?environment={LIVE_ENV}")).json()
        self.assertEqual(green["layoutHash"], green_ack["layoutHash"])
        self.assertEqual(green["environment"], GREEN_ENV)
        self.assertEqual(live["layoutHash"], live_ack["layoutHash"])
        self.assertEqual(live["environment"], LIVE_ENV)
        self.assertNotEqual(green["layoutHash"], live["layoutHash"])
        await green_ws.close()
        await live_ws.close()

    async def test_legacy_visual_mode_does_not_keep_render_ack_fresh(self):
        layout = {"layoutId": "mode-test", "layoutHash": "9" * 64, "layers": []}
        await self.publish_layout(LIVE_ENV, layout)
        ws, sid = await self.open_renderer(LIVE_ORIGIN, LIVE_ENV)
        await ws.send_json({
            "type": "renderer_ack",
            "environment": LIVE_ENV,
            "layoutId": "mode-test",
            "layoutHash": "9" * 64,
            "videoReadyState": 4,
            "stageReadyState": 4,
            "renderStatus": "rendered",
        })
        for _ in range(8):
            msg = await ws.receive_json()
            if msg.get("type") == "renderer_ack_received":
                break
        await ws.send_json({
            "type": "renderer_heartbeat",
            "environment": LIVE_ENV,
            "layoutHash": "9" * 64,
            "videoReadyState": 4,
            "visualMode": "legacy",
        })
        for _ in range(8):
            msg = await ws.receive_json()
            if msg.get("type") == "renderer_heartbeat_ack":
                break
        state = await (await self.client.get(f"/renderer-state?environment={LIVE_ENV}")).json()
        self.assertEqual(state["visualMode"], "legacy")
        self.assertFalse(state["renderingCurrentLayout"])
        await ws.close()

    async def test_renderer_environment_is_locked_per_session(self):
        ws, _sid = await self.open_renderer(LIVE_ORIGIN, LIVE_ENV)
        await ws.send_json({
            "type": "renderer_heartbeat",
            "environment": GREEN_ENV,
            "layoutHash": "",
            "videoReadyState": 0,
            "visualMode": "new",
        })
        for _ in range(8):
            msg = await ws.receive_json()
            if msg.get("type") == "error":
                self.assertEqual(msg.get("code"), "renderer_environment_mismatch")
                break
        else:
            self.fail("environment switch was not rejected")
        await ws.close()

    async def test_other_renderer_heartbeat_cannot_keep_old_ack_alive(self):
        layout = {"layoutId": "strict-session", "layoutHash": "7" * 64, "layers": []}
        await self.publish_layout(LIVE_ENV, layout)
        ws1, sid1 = await self.open_renderer(LIVE_ORIGIN, LIVE_ENV)
        ws2, _sid2 = await self.open_renderer(LIVE_ORIGIN, LIVE_ENV)
        res = await self.client.post("/renderer-ack", json={
            "rendererSessionId": sid1,
            "environment": LIVE_ENV,
            "layoutId": "strict-session",
            "layoutHash": "7" * 64,
            "videoReadyState": 4,
            "stageReadyState": 4,
            "renderStatus": "rendered",
        }, headers={"Origin": LIVE_ORIGIN})
        self.assertEqual(res.status, 200)
        state = await (await self.client.get(f"/renderer-state?environment={LIVE_ENV}")).json()
        self.assertTrue(state["renderingCurrentLayout"])
        self.assertEqual(state["rendererClients"], 2)
        await ws1.close()
        await ws2.send_json({
            "type": "renderer_heartbeat",
            "environment": LIVE_ENV,
            "layoutHash": "7" * 64,
            "videoReadyState": 4,
            "visualMode": "new",
        })
        for _ in range(8):
            msg = await ws2.receive_json()
            if msg.get("type") == "renderer_heartbeat_ack":
                break
        state = await (await self.client.get(f"/renderer-state?environment={LIVE_ENV}")).json()
        self.assertTrue(state["rendererConnected"])
        self.assertEqual(state["rendererClients"], 1)
        self.assertFalse(state["ackSessionLive"])
        self.assertFalse(state["renderingCurrentLayout"])
        await ws2.close()

    async def test_operator_renderer_does_not_inflate_public_presence_or_energy(self):
        observer = await self.client.ws_connect(
            f"/ws?environment={GREEN_ENV}",
            headers={"Origin": GREEN_ORIGIN},
        )
        welcome = await observer.receive_json()
        self.assertEqual(welcome.get("type"), "welcome")
        await observer.send_json({
            "type": "join",
            "environment": GREEN_ENV,
            "name": "Green Operator",
            "avatar": "orb-purple",
            "audience": False,
        })
        for _ in range(8):
            msg = await observer.receive_json()
            if msg.get("type") == "room_state":
                self.assertEqual(msg.get("presence"), 0)
                break
        else:
            self.fail("observer room_state not received")
        await observer.send_json({"type": "reaction", "reaction": "fire"})
        for _ in range(8):
            msg = await observer.receive_json()
            if msg.get("type") == "error":
                self.assertEqual(msg.get("code"), "observer_cannot_react")
                break
        else:
            self.fail("observer reaction was not rejected")

        audience = await self.client.ws_connect(
            f"/ws?environment={LIVE_ENV}",
            headers={"Origin": LIVE_ORIGIN},
        )
        aw = await audience.receive_json()
        self.assertEqual(aw.get("type"), "welcome")
        await audience.send_json({
            "type": "join",
            "environment": LIVE_ENV,
            "name": "Listener Test",
            "avatar": "orb-cyan",
            "audience": True,
        })
        for _ in range(8):
            msg = await audience.receive_json()
            if msg.get("type") == "room_state" and msg.get("presence") == 1:
                break
        else:
            self.fail("audience join was not reflected in room state")
        snap = self.app["room"].snapshot()
        self.assertEqual(snap["presence"], 1)
        self.assertEqual([p["name"] for p in snap["profiles"]], ["Listener Test"])
        await observer.close()
        await audience.close()

    async def test_websocket_renderer_connection_is_environment_specific(self):
        ws = await self.client.ws_connect(
            f"/ws?environment={LIVE_ENV}",
            headers={"Origin": LIVE_ORIGIN},
        )
        first = await ws.receive_json()
        self.assertEqual(first.get("type"), "welcome")
        await ws.send_json({
            "type": "renderer_heartbeat",
            "environment": LIVE_ENV,
            "layoutHash": "d" * 64,
            "videoReadyState": 4,
        })
        for _ in range(4):
            msg = await ws.receive_json()
            if msg.get("type") == "renderer_heartbeat_ack":
                break
        else:
            self.fail("renderer heartbeat ACK not received")

        live = await (await self.client.get(f"/renderer-state?environment={LIVE_ENV}")).json()
        green = await (await self.client.get(f"/renderer-state?environment={GREEN_ENV}")).json()
        self.assertTrue(live["rendererConnected"])
        self.assertFalse(green["rendererConnected"])
        await ws.close()


if __name__ == "__main__":
    unittest.main()
