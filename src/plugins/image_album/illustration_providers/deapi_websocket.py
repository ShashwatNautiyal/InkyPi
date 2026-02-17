"""
deAPI WebSocket client for real-time job status updates.

Uses Pusher-compatible protocol per https://docs.deapi.ai/execution-modes-and-integrations/websockets
"""

import json
import logging
import threading

import websocket

logger = logging.getLogger(__name__)

PUSHER_KEY = "depin-api-prod-key"
WS_URL = f"wss://soketi.deapi.ai/app/{PUSHER_KEY}?protocol=7&client=inky"
AUTH_URL = "https://api.deapi.ai/broadcasting/auth"


def wait_for_result(
    request_id: str,
    api_token: str,
    client_id: str,
    session,
    timeout: float = 300,
) -> dict | None:
    """
    Connect via WebSocket, wait for request.status.updated with result_url.
    Returns dict with result_url when done, or None on timeout/error.
    """
    result_holder: list[dict | None] = [None]
    done = threading.Event()
    ws_ref: list = []

    def on_message(ws, message):
        try:
            data = json.loads(message)
            event = data.get("event")
            if event == "pusher:connection_established":
                conn_data = json.loads(data.get("data", "{}"))
                socket_id = conn_data.get("socket_id")
                if socket_id:
                    _subscribe_private_channel(ws, api_token, client_id, socket_id, session)
            elif event == "request.status.updated":
                payload = json.loads(data.get("data", "{}"))
                if payload.get("request_id") == request_id:
                    status = payload.get("status")
                    progress = payload.get("progress", "")
                    if progress:
                        logger.info(f"deAPI illustration: {progress}% complete")
                    if status == "done":
                        result_holder[0] = payload
                        done.set()
                        ws.close()
                    elif status == "error":
                        logger.error(f"deAPI job error: {payload}")
                        done.set()
                        ws.close()
        except Exception as e:
            logger.debug(f"WebSocket message parse error: {e}")

    def on_error(ws, error):
        logger.error(f"deAPI WebSocket error: {error}")
        done.set()

    def on_close(ws, close_status, close_msg):
        done.set()

    def run_ws():
        ws = websocket.WebSocketApp(
            WS_URL,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        ws_ref.append(ws)
        ws.run_forever()

    thread = threading.Thread(target=run_ws, daemon=True)
    thread.start()

    if done.wait(timeout=timeout):
        return result_holder[0]
    if ws_ref:
        ws_ref[0].close()
    return None


def _subscribe_private_channel(
    ws, api_token: str, client_id: str, socket_id: str, session
) -> None:
    """Auth and subscribe to private-client.{client_id}."""
    channel = f"private-client.{client_id}"
    resp = session.post(
        AUTH_URL,
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        json={"socket_id": socket_id, "channel_name": channel},
        timeout=10,
    )
    if resp.status_code != 200:
        logger.error(f"deAPI auth failed: {resp.status_code} {resp.text}")
        return
    auth_data = resp.json()
    auth = auth_data.get("auth", "")
    ws.send(
        json.dumps(
            {
                "event": "pusher:subscribe",
                "data": {"channel": channel, "auth": auth},
            }
        )
    )
    logger.debug(f"Subscribed to {channel}")
