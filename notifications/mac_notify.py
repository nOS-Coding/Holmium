import asyncio
import json

import websockets


async def _send_ws(host: str, port: int, payload: dict) -> bool:
    try:
        uri = f"ws://{host}:{port}/notify"
        async with websockets.connect(uri, ping_interval=10, close_timeout=5) as ws:
            await ws.send(json.dumps(payload))
            ack = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(ack)
            return data.get("ok", False)
    except (asyncio.TimeoutError, websockets.WebSocketException, json.JSONDecodeError):
        return False


def send_mac_notification(title: str, body: str) -> bool:
    try:
        return asyncio.run(_send_ws("10.0.0.2", 9876, {
            "type": "notification",
            "title": title,
            "body": body,
        }))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_send_ws("10.0.0.2", 9876, {
                "type": "notification",
                "title": title,
                "body": body,
            }))
        finally:
            loop.close()
