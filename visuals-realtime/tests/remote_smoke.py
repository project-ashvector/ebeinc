#!/usr/bin/env python3
"""Non-destructive smoke test for a deployed staging gateway."""
import argparse
import asyncio
import json
import secrets

import aiohttp


async def receive_type(ws, expected, attempts=20):
    for _ in range(attempts):
        message = await ws.receive(timeout=8)
        if message.type != aiohttp.WSMsgType.TEXT:
            continue
        payload = json.loads(message.data)
        if payload.get("type") == expected:
            return payload
    raise AssertionError(f"did not receive {expected}")


async def run(base_url, origin):
    ws_url = base_url.replace("https://", "wss://", 1).rstrip("/") + "/ws"
    async with aiohttp.ClientSession() as session:
        health = await (await session.get(base_url.rstrip("/") + "/health")).json()
        assert health["ok"] and health["environment"] == "staging"

        clients = [await session.ws_connect(ws_url, origin=origin) for _ in range(3)]
        try:
            welcomes = [await receive_type(ws, "welcome") for ws in clients]
            assert len({item["session_id"] for item in welcomes}) == 3

            await clients[0].send_json({"type": "join", "name": "RemoteSmoke", "avatar": "orb-fire"})
            await receive_type(clients[0], "room_state")

            marker = "smoke-" + secrets.token_hex(4)
            await clients[0].send_json({"type": "message", "text": f"<script>x</script>{marker}"})
            chat = await receive_type(clients[1], "message")
            assert marker in chat["message"]["text"] and "<" not in chat["message"]["text"]

            event_id = secrets.token_hex(8)
            await clients[0].send_json({"type": "reaction", "reaction": "fire", "event_id": event_id})
            reaction = await receive_type(clients[2], "reaction")
            assert reaction["energy"] > 0

            await clients[0].send_json({"type": "ping"})
            pong = await receive_type(clients[0], "pong")
            assert isinstance(pong["server_time"], int)
        finally:
            await asyncio.gather(*(ws.close() for ws in clients))

        try:
            await session.ws_connect(ws_url, origin="https://not-allowed.invalid")
        except aiohttp.WSServerHandshakeError as error:
            assert error.status == 403
        else:
            raise AssertionError("invalid Origin unexpectedly accepted")

    print("REMOTE STAGING SMOKE: PASS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--origin", required=True)
    args = parser.parse_args()
    asyncio.run(run(args.url, args.origin))
