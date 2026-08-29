import concurrent.futures
import http.client
import json
import socket
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))

from phone_link_server import (
    MAX_BODY_BYTES,
    PROTOCOL_VERSION,
    REQUEST_BODY_TIMEOUT_SECONDS,
    REQUEST_QUEUE_SIZE,
    start_phone_link,
)


def get_json(url: str):
    with urlopen(url, timeout=3) as response:
        assert response.status == 200
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=3) as response:
        assert response.status == 200
        return json.loads(response.read().decode("utf-8"))


def expect_http_error(req: Request, expected: int):
    try:
        urlopen(req, timeout=3)
    except HTTPError as exc:
        assert exc.code == expected, (exc.code, expected)
        return json.loads(exc.read().decode("utf-8"))
    raise AssertionError(f"Expected HTTP {expected}")


def first_status_line(raw: socket.socket) -> bytes:
    return raw.recv(512).split(b"\r\n", 1)[0]


def main():
    assert REQUEST_QUEUE_SIZE >= 64

    server, base = start_phone_link("127.0.0.1", 0)
    port = server.server_address[1]
    try:
        status = get_json(base + "/senton/status")
        assert status["service"] == "Senton Control"
        assert status["protocol"] == PROTOCOL_VERSION
        assert status["safe_mode"] is True
        assert status["pi_connected"] is False
        assert status["speed_kmh"] == 0
        assert status["preview_active"] is False

        ping = get_json(base + "/senton/ping")
        assert ping == {
            "ok": True,
            "service": "Senton Control",
            "protocol": PROTOCOL_VERSION,
            "safe_mode": True,
        }

        preview = post_json(base + "/senton/preview", {"message": "TEST MODE PREVIEW — SAFE MODE ACTIVE"})
        assert preview["ok"] is True
        assert preview["safe_mode"] is True
        assert preview["preview_active"] is True
        status = get_json(base + "/senton/status")
        assert status["message"] == "TEST MODE PREVIEW — SAFE MODE ACTIVE"
        assert status["preview_active"] is True
        assert status["safe_mode"] is True
        assert status["pi_connected"] is False
        assert status["speed_kmh"] == 0

        for route in [
            "/senton/drive",
            "/senton/start-charge",
            "/senton/stop-charge",
            "/senton/solar-charge",
            "/senton/throttle",
        ]:
            blocked = expect_http_error(Request(base + route, data=b"{}", method="POST"), 403)
            assert blocked["error"] == "command_locked"
            assert blocked["safe_mode"] is True

        malformed = expect_http_error(
            Request(
                base + "/senton/test-message",
                data=b"{not-json",
                method="POST",
                headers={"Content-Type": "application/json"},
            ),
            400,
        )
        assert malformed["error"] == "bad_json"

        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        conn.request("POST", "/senton/test-message", body=b"{}", headers={"Content-Length": str(MAX_BODY_BYTES + 1)})
        response = conn.getresponse()
        assert response.status == 413
        response.read()
        conn.close()

        raw = socket.create_connection(("127.0.0.1", port), timeout=3)
        raw.sendall(
            b"POST /senton/test-message HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Content-Length: banana\r\n"
            b"Connection: close\r\n\r\n"
        )
        assert b" 400 " in first_status_line(raw)
        raw.close()

        truncated = socket.create_connection(("127.0.0.1", port), timeout=3)
        truncated.sendall(
            b"POST /senton/test-message HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: 64\r\n"
            b"Connection: close\r\n\r\n"
            b'{"message":"short"}'
        )
        truncated.shutdown(socket.SHUT_WR)
        assert b" 400 " in first_status_line(truncated)
        truncated.close()

        stalled = socket.create_connection(("127.0.0.1", port), timeout=REQUEST_BODY_TIMEOUT_SECONDS + 3)
        stalled.sendall(
            b"POST /senton/test-message HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: 64\r\n"
            b"Connection: close\r\n\r\n"
            b"{"
        )
        started = time.monotonic()
        stalled_line = first_status_line(stalled)
        elapsed = time.monotonic() - started
        stalled.close()
        assert b" 408 " in stalled_line, stalled_line
        assert elapsed <= REQUEST_BODY_TIMEOUT_SECONDS + 2.0, elapsed

        def send(i: int):
            result = post_json(base + "/senton/test-message", {"message": f"test-{i}"})
            assert result["ok"] is True
            assert result["safe_mode"] is True
            assert result["protocol"] == PROTOCOL_VERSION
            return result["echo"]

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
            echoes = list(pool.map(send, range(100)))
        assert len(echoes) == 100
        assert all(e.startswith("test-") for e in echoes)

        with concurrent.futures.ThreadPoolExecutor(max_workers=64) as pool:
            burst_echoes = list(pool.map(send, range(400, 900)))
        assert len(burst_echoes) == 500
        assert all(e.startswith("test-") for e in burst_echoes)

        for _ in range(100):
            dropped = socket.create_connection(("127.0.0.1", port), timeout=3)
            dropped.sendall(
                b"GET /senton/status HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                b"Connection: close\r\n\r\n"
            )
            dropped.close()

        status = get_json(base + "/senton/status")
        assert status["safe_mode"] is True
        assert status["pi_connected"] is False
        assert status["speed_kmh"] == 0
    finally:
        server.shutdown()
        server.server_close()

    for _ in range(10):
        restarted, restarted_base = start_phone_link("127.0.0.1", port)
        try:
            status = get_json(restarted_base + "/senton/status")
            assert status["safe_mode"] is True
            assert status["pi_connected"] is False
            assert status["speed_kmh"] == 0
        finally:
            restarted.shutdown()
            restarted.server_close()

    print("Senton phone-link hard integration test passed")


if __name__ == "__main__":
    main()
