import tempfile
import urllib.request
from pathlib import Path

from updater import _cache_busted_url, _normalize_sha256, verify_file_sha256


DOWNLOAD_CHUNK_SIZE = 8 * 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 30


def download_update_with_progress(download_url, expected_sha256, progress_callback=None):
    """Download and verify an already-authorised update with minimal startup delay."""
    if not download_url.lower().startswith("https://"):
        raise ValueError("Update downloads must use HTTPS.")

    expected = _normalize_sha256(expected_sha256)
    if not expected:
        raise RuntimeError("Update is missing a valid SHA-256 integrity value.")

    def report(value):
        if progress_callback:
            progress_callback(max(0, min(100, int(value))))

    report(0)
    target = Path(tempfile.gettempdir()) / "Senton_Control_Update.exe"
    req = urllib.request.Request(
        _cache_busted_url(download_url),
        headers={
            "User-Agent": "Senton-Control-Updater",
            "Cache-Control": "no-cache, no-store, max-age=0",
            "Pragma": "no-cache",
        },
    )

    report(2)
    downloaded = 0
    with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response, open(target, "wb") as f:
        total = int(response.headers.get("Content-Length") or 0)
        while True:
            chunk = response.read(DOWNLOAD_CHUNK_SIZE)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                report(5 + (downloaded / total) * 85)

    if not target.exists() or target.stat().st_size < 1024 * 1024:
        target.unlink(missing_ok=True)
        raise RuntimeError("Downloaded update file is missing or unexpectedly small.")

    report(92)
    try:
        verify_file_sha256(target, expected)
    except Exception:
        target.unlink(missing_ok=True)
        raise

    report(100)
    return target
