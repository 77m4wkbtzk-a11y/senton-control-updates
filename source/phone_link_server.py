"""Local Senton Link phone <-> Windows bridge.

Status/test-only bridge. Vehicle motion and charge actuation are intentionally
not exposed here. The Android client treats any unsafe/malformed response as a
disconnect and keeps all vehicle controls locked.
"""
from __future__ import annotations

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8765
PROTOCOL_VERSION = 1
MAX_BODY_BYTES = 2048
REQUEST_BODY_TIMEOUT_SECONDS = 3.0
REQUEST_QUEUE_SIZE = 128

_state_lock = threading.Lock()
_state = {
    "service": "Senton Control",
    "protocol": PROTOCOL_VERSION,
    "pc_connected": True,
    "pi_connected": False,
    "safe_mode": True,
    "speed_kmh": 0,
    "battery_v": None,
    "signal": None,
    "message": "Windows link ready",
    "updated": 0,
}


def local_ip() -> str:
    """Best-effort LAN address for display; no packet needs to be sent."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def snapshot_state() -> dict:
    with _state_lock:
        payload = dict(_state)
    payload["updated"] = int(time.time())
    return payload


class SentonThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    # The Android client polls frequently and reconnect storms can create a
    # short burst of simultaneous TCP handshakes. The stdlib default listen
    # backlog is intentionally small, which can reset otherwise valid clients
    # under stress. A bounded larger queue absorbs the burst without changing
    # any command/safety behavior.
    request_queue_size = REQUEST_QUEUE_SIZE


class Handler(BaseHTTPRequestHandler):
    server_version = "SentonLink/1.1"
    timeout = REQUEST_BODY_TIMEOUT_SECONDS

    def _json(self, code: int, payload: dict) -> None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Senton-Protocol", str(PROTOCOL_VERSION))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, socket.timeout, OSError):
            # Force-stop, network-loss and rapid reconnect tests deliberately
            # drop clients mid-response. Treat an already-gone client as a
            # normal disconnect rather than emitting an exception traceback.
            pass
        finally:
            self.close_connection = True

    def do_GET(self) -> None:
        if self.path == "/senton/status":
            self._json(200, snapshot_state())
        elif self.path == "/senton/ping":
            self._json(
                200,
                {
                    "ok": True,
                    "service": "Senton Control",
                    "protocol": PROTOCOL_VERSION,
                    "safe_mode": True,
                },
            )
        else:
            self._json(404, {"error": "not_found", "safe_mode": True})

    def do_POST(self) -> None:
        # Test messaging only. No drive/charge commands are accepted.
        if self.path != "/senton/test-message":
            self._json(403, {"error": "command_locked", "safe_mode": True})
            return

        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except (TypeError, ValueError):
            self._json(400, {"error": "bad_content_length", "safe_mode": True})
            return
        if length < 0 or length > MAX_BODY_BYTES:
            self._json(413, {"error": "body_too_large", "safe_mode": True})
            return

        try:
            raw_body = self.rfile.read(length)
        except (socket.timeout, TimeoutError, OSError):
            self._json(408, {"error": "request_timeout", "safe_mode": True})
            return
        if len(raw_body) != length:
            self._json(400, {"error": "truncated_body", "safe_mode": True})
            return

        try:
            body = json.loads(raw_body or b"{}")
            if not isinstance(body, dict):
                raise ValueError("JSON body must be an object")
        except Exception:
            self._json(400, {"error": "bad_json", "safe_mode": True})
            return

        message = str(body.get("message", ""))[:200]
        now = int(time.time())
        with _state_lock:
            _state["message"] = message or "Phone test received"
            _state["updated"] = now
            echo = _state["message"]
        self._json(
            200,
            {
                "ok": True,
                "echo": echo,
                "protocol": PROTOCOL_VERSION,
                "safe_mode": True,
            },
        )

    def log_message(self, fmt: str, *args) -> None:
        return


def start_phone_link(host: str = "0.0.0.0", port: int = PORT):
    server = SentonThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(
        target=server.serve_forever,
        name="senton-phone-link",
        daemon=True,
    )
    thread.start()
    actual_port = int(server.server_address[1])
    display_host = "127.0.0.1" if host in {"127.0.0.1", "localhost"} else local_ip()
    return server, f"http://{display_host}:{actual_port}"


if __name__ == "__main__":
    server, url = start_phone_link()
    print(f"Senton Link bridge listening at {url}")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.shutdown()
        server.server_close()
