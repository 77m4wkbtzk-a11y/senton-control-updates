import concurrent.futures
import http.client
import json
import socket
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))

from phone_link_server import MAX_BODY_BYTES, PROTOCOL_VERSION, start_phone_link


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


def main():
    server, base = start_phone_link("127.0.0.1", 0)
    port = server.server_address[1]
    try:
        status = get_json(base + "/senton/status")
        assert status["service"] == "Senton Control"
        assert status["protocol"] == PROTOCOL_VERSION
        assert status["safe_mode"] is True
        assert status["pi_connected"] is False
        assert status["speed_kmh"] == 0

        ping = get_json(base + "/senton/ping")
        assert ping == {
            "ok": True,
            "service": "Senton Control",
            "protocol": PROTOCOL_VERSION,
            "safe_mode": True,
        }

        blocked = expect_http_error(
            Request(base + "/senton/drive", data=b"{}", method="POST"), 403
        )
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
        conn.request(
            "POST",
            "/senton/test-message",
            body=b"{}",
            headers={"Content-Length": str(MAX_BODY_BYTES + 1)},
        )
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
        first_line = raw.recv(256).split(b"\r\n", 1)[0]
        raw.close()
        assert b" 400 " in first_line, first_line

        def send(i: int):
            result = post_json(base + "/senton/test-message", {"message": f"test-{i}"})
            assert result["ok"] is True
            assert result["safe_mode"] is True
            assert result["protocol"] == PROTOCOL_VERSION
            return result["echo"]

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            echoes = list(pool.map(send, range(30)))
        assert len(echoes) == 30
        assert all(e.startswith("test-") for e in echoes)

        status = get_json(base + "/senton/status")
        assert status["safe_mode"] is True
        assert status["pi_connected"] is False
    finally:
        server.shutdown()
        server.server_close()

    # Cold restart/reconnect on the same port must work immediately.
    server2, base2 = start_phone_link("127.0.0.1", port)
    try:
        assert get_json(base2 + "/senton/ping")["safe_mode"] is True
    finally:
        server2.shutdown()
        server2.server_close()

    print("Senton phone-link hard integration test passed")


if __name__ == "__main__":
    main()
