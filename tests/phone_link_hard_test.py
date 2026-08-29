import concurrent.futures
import http.client
import json
import socket
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
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


def assert_safe(status: dict):
    assert status["safe_mode"] is True
    assert status["pi_connected"] is False
    assert status["speed_kmh"] == 0


def stalled_request(port: int):
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
    line = first_status_line(stalled)
    elapsed = time.monotonic() - started
    stalled.close()
    assert b" 408 " in line, line
    assert elapsed <= REQUEST_BODY_TIMEOUT_SECONDS + 2.0, elapsed
    return elapsed


def main():
    assert REQUEST_QUEUE_SIZE >= 64

    server, base = start_phone_link("127.0.0.1", 0)
    port = server.server_address[1]
    try:
        status = get_json(base + "/senton/status")
        assert status["service"] == "Senton Control"
        assert status["protocol"] == PROTOCOL_VERSION
        assert status["preview_active"] is False
        assert_safe(status)

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
        assert_safe(status)

        locked_routes = [
            "/senton/drive",
            "/senton/start-charge",
            "/senton/stop-charge",
            "/senton/solar-charge",
            "/senton/throttle",
            "/senton/brake",
            "/senton/steering",
        ]
        lock_payloads = [
            b"{}",
            b'{"authenticated":true,"value":100}',
            b'{"pi_connected":true,"safe_mode":false}',
            b'{"command":"drive","speed":100}',
        ]
        for route in locked_routes:
            for payload in lock_payloads:
                blocked = expect_http_error(Request(base + route, data=payload, method="POST"), 403)
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

        negative = socket.create_connection(("127.0.0.1", port), timeout=3)
        negative.sendall(
            b"POST /senton/test-message HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Content-Length: -1\r\n"
            b"Connection: close\r\n\r\n"
        )
        assert b" 413 " in first_status_line(negative)
        negative.close()

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

        # Hold several partial requests open at once while telemetry continues to poll.
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            stalled_futures = [pool.submit(stalled_request, port) for _ in range(8)]
            for _ in range(50):
                assert_safe(get_json(base + "/senton/status"))
            stalled_elapsed = [future.result() for future in stalled_futures]
        assert max(stalled_elapsed) <= REQUEST_BODY_TIMEOUT_SECONDS + 2.0

        def send(i: int):
            if i % 4 == 0:
                result = get_json(base + "/senton/status")
                assert_safe(result)
                return "status"
            result = post_json(base + "/senton/test-message", {"message": f"test-{i}"})
            assert result["ok"] is True
            assert result["safe_mode"] is True
            assert result["protocol"] == PROTOCOL_VERSION
            return result["echo"]

        with concurrent.futures.ThreadPoolExecutor(max_workers=96) as pool:
            mixed = list(pool.map(send, range(1200)))
        assert len(mixed) == 1200

        for _ in range(150):
            dropped = socket.create_connection(("127.0.0.1", port), timeout=3)
            dropped.sendall(
                b"GET /senton/status HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                b"Connection: close\r\n\r\n"
            )
            dropped.close()

        assert_safe(get_json(base + "/senton/status"))
    finally:
        server.shutdown()
        server.server_close()

    # Simulated bridge/network loss must make the endpoint unreachable, never actuating.
    try:
        get_json(base + "/senton/status")
    except (URLError, ConnectionError, OSError):
        pass
    else:
        raise AssertionError("Bridge remained reachable after shutdown")

    # Cold stop/rebind cycles must always return in Safe Mode with actuation locked,
    # and transient Test Mode preview state must never leak across a bridge restart.
    for _ in range(20):
        restarted, restarted_base = start_phone_link("127.0.0.1", port)
        try:
            restarted_status = get_json(restarted_base + "/senton/status")
            assert_safe(restarted_status)
            assert restarted_status["preview_active"] is False
            assert restarted_status["message"] == "Windows link ready"
            for route in ("/senton/drive", "/senton/solar-charge"):
                blocked = expect_http_error(Request(restarted_base + route, data=b"{}", method="POST"), 403)
                assert blocked["error"] == "command_locked"
                assert blocked["safe_mode"] is True
        finally:
            restarted.shutdown()
            restarted.server_close()

    # Rapid overlapping relaunches on different sockets must not share or reset
    # transient Test Mode state between bridge instances. Each instance must remain
    # independently fail-closed with actuation locked.
    first, first_base = start_phone_link("127.0.0.1", 0)
    second = None
    try:
        preview = post_json(first_base + "/senton/preview", {"message": "INSTANCE A TEST MODE"})
        assert preview["preview_active"] is True
        first_before = get_json(first_base + "/senton/status")
        assert first_before["message"] == "INSTANCE A TEST MODE"
        assert first_before["preview_active"] is True
        assert_safe(first_before)

        second, second_base = start_phone_link("127.0.0.1", 0)
        first_after = get_json(first_base + "/senton/status")
        second_status = get_json(second_base + "/senton/status")
        assert first_after["message"] == "INSTANCE A TEST MODE"
        assert first_after["preview_active"] is True
        assert second_status["message"] == "Windows link ready"
        assert second_status["preview_active"] is False
        assert_safe(first_after)
        assert_safe(second_status)

        for bridge_base in (first_base, second_base):
            for route in ("/senton/drive", "/senton/solar-charge"):
                blocked = expect_http_error(
                    Request(
                        bridge_base + route,
                        data=b'{"authenticated":true,"pi_connected":true,"safe_mode":false}',
                        method="POST",
                    ),
                    403,
                )
                assert blocked["error"] == "command_locked"
                assert blocked["safe_mode"] is True
    finally:
        if second is not None:
            second.shutdown()
            second.server_close()
        first.shutdown()
        first.server_close()

    print("Senton phone-link EXTREME hard integration test passed")


if __name__ == "__main__":
    main()
