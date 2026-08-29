"""Local Senton Link phone <-> Windows bridge.

Status/test-only bridge. Vehicle motion and charge actuation are intentionally
not exposed here. Bind to LAN only when explicitly started by Senton Control.
"""
from __future__ import annotations

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8765
_state = {
    "service": "Senton Control",
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
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class Handler(BaseHTTPRequestHandler):
    server_version = "SentonLink/1.0"

    def _json(self, code: int, payload: dict) -> None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path == "/senton/status":
            payload = dict(_state)
            payload["updated"] = int(time.time())
            self._json(200, payload)
        elif self.path == "/senton/ping":
            self._json(200, {"ok": True, "service": "Senton Control", "safe_mode": True})
        else:
            self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        # Test messaging only. No drive/charge commands are accepted.
        if self.path != "/senton/test-message":
            self._json(403, {"error": "command_locked", "safe_mode": True})
            return
        length = min(int(self.headers.get("Content-Length", "0") or 0), 2048)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self._json(400, {"error": "bad_json"})
            return
        message = str(body.get("message", ""))[:200]
        _state["message"] = message or "Phone test received"
        _state["updated"] = int(time.time())
        self._json(200, {"ok": True, "echo": _state["message"], "safe_mode": True})

    def log_message(self, fmt: str, *args) -> None:
        return


def start_phone_link(host: str = "0.0.0.0", port: int = PORT):
    server = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, name="senton-phone-link", daemon=True)
    thread.start()
    return server, f"http://{local_ip()}:{port}"


if __name__ == "__main__":
    server, url = start_phone_link()
    print(f"Senton Link bridge listening at {url}")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.shutdown()
