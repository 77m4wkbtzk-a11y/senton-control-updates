import tempfile
import urllib.request
from pathlib import Path

import config
from updater import _cache_busted_url, _fetch_manifest, _normalize_sha256, verify_file_sha256


def download_update_with_progress(download_url, progress_callback=None):
    """Download and verify the update while reporting 0-100 progress."""
    if not download_url.lower().startswith("https://"):
        raise ValueError("Update downloads must use HTTPS.")

    def report(value):
        if progress_callback:
            progress_callback(max(0, min(100, int(value))))

    report(0)
    manifest_url = getattr(config, "UPDATE_MANIFEST_URL", "").strip()
    if not manifest_url:
        raise RuntimeError("Cannot verify update because the update manifest is not configured.")

    manifest = _fetch_manifest(manifest_url)
    manifest_download_url = str(manifest.get("download_url", "")).strip()
    if manifest_download_url != download_url:
        raise RuntimeError("Update download does not match the current verified manifest.")

    expected = _normalize_sha256(manifest.get("sha256", ""))
    if not expected:
        raise RuntimeError("Update manifest is missing a valid SHA-256 integrity value.")

    target = Path(tempfile.gettempdir()) / "Senton_Control_Update.exe"
    req = urllib.request.Request(
        _cache_busted_url(download_url),
        headers={"User-Agent": "Senton-Control-Updater", "Cache-Control": "no-cache"},
    )

    report(2)
    downloaded = 0
    with urllib.request.urlopen(req, timeout=45) as response, open(target, "wb") as f:
        total = int(response.headers.get("Content-Length") or 0)
        while True:
            chunk = response.read(4 * 1024 * 1024)
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
