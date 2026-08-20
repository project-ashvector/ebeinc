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

spec = importlib.util.spec_from_file_location("at140_visuals_realtime", APP_PATH)
rt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rt)


class RealtimeHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._old_token = os.environ.get("ADMIN_TOKEN")
        self.tmp = tempfile.TemporaryDirectory()
        self.app = rt.create_app(str(Path(self.tmp.name) / "realtime.db"))
        self.app["origins"] = {"https://allthings140-visuals-green.pages.dev", "https://allthings140radio.online"}
        self.server = TestServer(self.app)
        self.client = TestClient(self.server)
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        self.tmp.cleanup()
        if self._old_token is None:
            os.environ.pop("ADMIN_TOKEN", None)
        else:
            os.environ["ADMIN_TOKEN"] = self._old_token

    async def open_renderer(self, origin, environment):
        ws = await self.client.ws_connect("/ws", headers={"Origin": origin})
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
                "Origin": "https://allthings140-visuals-green.pages.dev",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        self.assertEqual(res.status, 204)
        self.assertEqual(
            res.headers.get("Access-Control-Allow-Origin"),
            "https://allthings140-visuals-green.pages.dev",
        )
        self.assertIn("POST", res.headers.get("Access-Control-Allow-Methods", ""))

    async def test_admin_publish_fails_closed_without_token(self):
        os.environ.pop("ADMIN_TOKEN", None)
        res = await self.client.post(
            "/admin/layout",
            json={"layoutHash": "x" * 64, "layers": []},
        )
        self.assertEqual(res.status, 503)

    async def test_publish_and_renderer_ack_round_trip(self):
        os.environ["ADMIN_TOKEN"] = "test-only-secret-that-never-leaves-this-process"
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
        res = await self.client.post(
            "/admin/layout",
            data=json.dumps(layout).encode(),
            headers={
                "Authorization": "Bearer test-only-secret-that-never-leaves-this-process",
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(res.status, 200)
        body = await res.json()
        self.assertEqual(body["layoutHash"], layout["layoutHash"])

        state = await (await self.client.get("/layout-state")).json()
        self.assertEqual(state["layoutHash"], layout["layoutHash"])
        self.assertEqual(state["layout"]["screenOpening"]["x"], 0)

        ws, sid = await self.open_renderer("https://allthings140-visuals-green.pages.dev", "green-staging")
        ack = {
            "rendererSessionId": sid,
            "environment": "green-staging",
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
            headers={"Origin": "https://allthings140-visuals-green.pages.dev"},
        )
        self.assertEqual(res.status, 200)
        self.assertEqual(
            res.headers.get("Access-Control-Allow-Origin"),
            "https://allthings140-visuals-green.pages.dev",
        )
        renderer = await (await self.client.get("/renderer-state")).json()
        self.assertEqual(renderer["ack"]["layoutHash"], layout["layoutHash"])
        self.assertEqual(renderer["ack"]["renderStatus"], "RENDERED")
        await ws.close()

    async def test_http_renderer_ack_rejects_inactive_session_and_stale_hash(self):
        os.environ["ADMIN_TOKEN"] = "test-only-secret-that-never-leaves-this-process"
        layout = {"layoutId":"active", "layoutHash":"e"*64, "layers":[]}
        res = await self.client.post("/admin/layout", data=json.dumps(layout).encode(), headers={
            "Authorization":"Bearer test-only-secret-that-never-leaves-this-process",
            "Content-Type":"application/json",
        })
        self.assertEqual(res.status, 200)
        res = await self.client.post("/renderer-ack", json={
            "rendererSessionId":"not-active", "environment":"green-staging", "layoutHash":"e"*64, "renderStatus":"rendered"
        }, headers={"Origin":"https://allthings140-visuals-green.pages.dev"})
        self.assertEqual(res.status, 409)
        ws, sid = await self.open_renderer("https://allthings140-visuals-green.pages.dev", "green-staging")
        res = await self.client.post("/renderer-ack", json={
            "rendererSessionId":sid, "environment":"green-staging", "layoutHash":"f"*64, "renderStatus":"rendered"
        }, headers={"Origin":"https://allthings140-visuals-green.pages.dev"})
        self.assertEqual(res.status, 409)
        await ws.close()

    async def test_live_chat_cors_and_environment_isolation(self):
        os.environ["ADMIN_TOKEN"] = "test-only-secret-that-never-leaves-this-process"
        green_ws, green_sid = await self.open_renderer("https://allthings140-visuals-green.pages.dev", "green-staging")
        live_ws, live_sid = await self.open_renderer("https://allthings140radio.online", "live-chat")

        async def publish(hash_value, layout_id):
            res = await self.client.post("/admin/layout", data=json.dumps({
                "layoutId":layout_id, "layoutHash":hash_value, "layers":[]
            }).encode(), headers={
                "Authorization":"Bearer test-only-secret-that-never-leaves-this-process",
                "Content-Type":"application/json",
            })
            self.assertEqual(res.status, 200)

        await publish("b"*64, "layout-green")
        green_ack={"rendererSessionId":green_sid,"environment":"green-staging","layoutId":"layout-green","layoutHash":"b"*64,"stageAssetId":"stage-green","visualAssetId":"visual-green","videoReadyState":4,"stageReadyState":4,"renderStatus":"rendered"}
        res=await self.client.post("/renderer-ack",json=green_ack,headers={"Origin":"https://allthings140-visuals-green.pages.dev"})
        self.assertEqual(res.status,200)

        await publish("c"*64, "layout-live")
        live_ack={"rendererSessionId":live_sid,"environment":"live-chat","layoutId":"layout-live","layoutHash":"c"*64,"stageAssetId":"stage-live","visualAssetId":"visual-live","videoReadyState":4,"stageReadyState":4,"renderStatus":"rendered"}
        res=await self.client.post("/renderer-ack",json=live_ack,headers={"Origin":"https://allthings140radio.online"})
        self.assertEqual(res.status,200)
        self.assertEqual(res.headers.get("Access-Control-Allow-Origin"),"https://allthings140radio.online")

        green=await (await self.client.get("/renderer-state?environment=green-staging")).json()
        live=await (await self.client.get("/renderer-state?environment=live-chat")).json()
        self.assertEqual(green["layoutHash"],green_ack["layoutHash"])
        self.assertEqual(green["environment"],"green-staging")
        self.assertEqual(live["layoutHash"],live_ack["layoutHash"])
        self.assertEqual(live["environment"],"live-chat")
        self.assertNotEqual(green["layoutHash"],live["layoutHash"])
        await green_ws.close(); await live_ws.close()

    async def test_legacy_visual_mode_does_not_keep_render_ack_fresh(self):
        os.environ["ADMIN_TOKEN"] = "test-only-secret-that-never-leaves-this-process"
        layout={"layoutId":"mode-test","layoutHash":"9"*64,"layers":[]}
        await self.client.post("/admin/layout",data=json.dumps(layout).encode(),headers={"Authorization":"Bearer test-only-secret-that-never-leaves-this-process","Content-Type":"application/json"})
        ws, sid=await self.open_renderer("https://allthings140radio.online","live-chat")
        await ws.send_json({"type":"renderer_ack","environment":"live-chat","layoutId":"mode-test","layoutHash":"9"*64,"videoReadyState":4,"stageReadyState":4,"renderStatus":"rendered"})
        for _ in range(8):
            msg=await ws.receive_json()
            if msg.get("type")=="renderer_ack_received": break
        await ws.send_json({"type":"renderer_heartbeat","environment":"live-chat","layoutHash":"9"*64,"videoReadyState":4,"visualMode":"legacy"})
        for _ in range(8):
            msg=await ws.receive_json()
            if msg.get("type")=="renderer_heartbeat_ack": break
        state=await (await self.client.get("/renderer-state?environment=live-chat")).json()
        self.assertEqual(state["visualMode"],"legacy")
        self.assertFalse(state["renderingCurrentLayout"])
        await ws.close()


    async def test_renderer_environment_is_locked_per_session(self):
        ws, _sid = await self.open_renderer("https://allthings140radio.online", "live-chat")
        await ws.send_json({
            "type":"renderer_heartbeat",
            "environment":"green-staging",
            "layoutHash":"",
            "videoReadyState":0,
            "visualMode":"new",
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
        os.environ["ADMIN_TOKEN"] = "test-only-secret-that-never-leaves-this-process"
        layout={"layoutId":"strict-session","layoutHash":"7"*64,"layers":[]}
        await self.client.post("/admin/layout",data=json.dumps(layout).encode(),headers={"Authorization":"Bearer test-only-secret-that-never-leaves-this-process","Content-Type":"application/json"})
        ws1, sid1 = await self.open_renderer("https://allthings140radio.online", "live-chat")
        ws2, _sid2 = await self.open_renderer("https://allthings140radio.online", "live-chat")
        res=await self.client.post("/renderer-ack",json={
            "rendererSessionId":sid1,"environment":"live-chat","layoutId":"strict-session","layoutHash":"7"*64,
            "videoReadyState":4,"stageReadyState":4,"renderStatus":"rendered"
        },headers={"Origin":"https://allthings140radio.online"})
        self.assertEqual(res.status,200)
        state=await (await self.client.get("/renderer-state?environment=live-chat")).json()
        self.assertTrue(state["renderingCurrentLayout"])
        self.assertEqual(state["rendererClients"],2)
        await ws1.close()
        # A different public renderer may still be connected and heartbeating, but it
        # must not inherit the departed renderer's proof-of-rendering.
        await ws2.send_json({"type":"renderer_heartbeat","environment":"live-chat","layoutHash":"7"*64,"videoReadyState":4,"visualMode":"new"})
        for _ in range(8):
            msg=await ws2.receive_json()
            if msg.get("type")=="renderer_heartbeat_ack": break
        state=await (await self.client.get("/renderer-state?environment=live-chat")).json()
        self.assertTrue(state["rendererConnected"])
        self.assertEqual(state["rendererClients"],1)
        self.assertFalse(state["ackSessionLive"])
        self.assertFalse(state["renderingCurrentLayout"])
        await ws2.close()


    async def test_operator_renderer_does_not_inflate_public_presence_or_energy(self):
        observer = await self.client.ws_connect("/ws", headers={"Origin":"https://allthings140-visuals-green.pages.dev"})
        welcome = await observer.receive_json(); self.assertEqual(welcome.get("type"),"welcome")
        await observer.send_json({"type":"join","name":"Green Operator","avatar":"orb-purple","audience":False})
        # Drain until the room-state caused by join is observed.
        for _ in range(8):
            msg=await observer.receive_json()
            if msg.get("type")=="room_state":
                self.assertEqual(msg.get("presence"),0)
                break
        else:
            self.fail("observer room_state not received")
        await observer.send_json({"type":"reaction","reaction":"fire"})
        for _ in range(8):
            msg=await observer.receive_json()
            if msg.get("type")=="error":
                self.assertEqual(msg.get("code"),"observer_cannot_react")
                break
        else:
            self.fail("observer reaction was not rejected")

        audience = await self.client.ws_connect("/ws", headers={"Origin":"https://allthings140radio.online"})
        aw = await audience.receive_json(); self.assertEqual(aw.get("type"),"welcome")
        await audience.send_json({"type":"join","name":"Listener Test","avatar":"orb-cyan","audience":True})
        for _ in range(8):
            msg=await audience.receive_json()
            if msg.get("type")=="room_state" and msg.get("presence")==1:
                break
        else:
            self.fail("audience join was not reflected in room state")
        snap=self.app["room"].snapshot()
        self.assertEqual(snap["presence"],1)
        self.assertEqual([p["name"] for p in snap["profiles"]],["Listener Test"])
        await observer.close(); await audience.close()

    async def test_websocket_renderer_connection_is_environment_specific(self):
        ws = await self.client.ws_connect(
            "/ws",
            headers={"Origin": "https://allthings140radio.online"},
        )
        # Consume initial welcome plus any immediate room-state fanout.
        first = await ws.receive_json()
        self.assertEqual(first.get("type"), "welcome")
        await ws.send_json({
            "type": "renderer_heartbeat",
            "environment": "live-chat",
            "layoutHash": "d" * 64,
            "videoReadyState": 4,
        })
        # Wait for the direct heartbeat ACK (room_state may arrive first).
        for _ in range(4):
            msg = await ws.receive_json()
            if msg.get("type") == "renderer_heartbeat_ack":
                break
        else:
            self.fail("renderer heartbeat ACK not received")

        live = await (await self.client.get("/renderer-state?environment=live-chat")).json()
        green = await (await self.client.get("/renderer-state?environment=green-staging")).json()
        self.assertTrue(live["rendererConnected"])
        self.assertFalse(green["rendererConnected"])
        await ws.close()



if __name__ == "__main__":
    unittest.main()
