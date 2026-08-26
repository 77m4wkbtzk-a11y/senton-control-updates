import hashlib
import json
import sys
import urllib.request

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import config
from dashboard import SentonDashboard
from updater import cleanup_expired_backup, download_update, install_update_to_main_desktop


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def _version_tuple(version):
    try:
        return tuple(int(part) for part in str(version).strip().split("."))
    except Exception:
        return (0,)


def _read_manifest(url, channel_name):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Senton-Control-Owner-Admin-Updater"})
        with urllib.request.urlopen(req, timeout=8) as response:
            manifest = json.loads(response.read().decode("utf-8-sig"))
        manifest["_channel_name"] = channel_name
        return manifest
    except Exception:
        return None


def _latest_available_update(current_version):
    candidates = []
    admin = _read_manifest(getattr(config, "UPDATE_MANIFEST_URL", ""), "ADMIN")
    public = _read_manifest(getattr(config, "PUBLIC_UPDATE_MANIFEST_URL", ""), "PUBLIC")

    for manifest in (admin, public):
        if not manifest:
            continue
        version = str(manifest.get("version", "0.0.0"))
        if _version_tuple(version) > _version_tuple(current_version):
            candidates.append(manifest)

    if not candidates:
        return None
    return max(candidates, key=lambda m: _version_tuple(m.get("version", "0.0.0")))


def run_admin_update_check(window):
    result = _latest_available_update(config.APP_VERSION)
    if not result:
        window._log("OWNER ADMIN UPDATE: no newer verified update available")
        return

    latest = str(result.get("version", "?"))
    channel = result.get("_channel_name", "UNKNOWN")
    download_url = str(result.get("download_url", "")).strip()
    expected_hash = str(result.get("sha256", "")).strip().lower()

    # Owner-admin automatic installs are allowed only for hash-verified packages.
    if not download_url or not expected_hash:
        window._log(f"OWNER ADMIN UPDATE: v{latest} missing verified metadata; automatic install blocked")
        return

    try:
        window.update_status.setText(f"{channel} update v{latest} found. Updating automatically...")
        window._log(f"OWNER ADMIN UPDATE: downloading v{latest} from {channel} channel")
        path = download_update(download_url)
        actual_hash = _sha256(path)
        if actual_hash != expected_hash:
            raise RuntimeError("Update integrity check failed. Automatic installation blocked.")

        window._log(f"OWNER ADMIN UPDATE: v{latest} verified; automatic installation starting")
        window.update_status.setText(f"Verified v{latest}. Restarting to install...")
        install_update_to_main_desktop(path)
        QApplication.quit()
    except Exception as exc:
        window._log(f"OWNER ADMIN UPDATE failed: {exc}")
        window.update_status.setText(f"Admin automatic update failed: {exc}")


if __name__ == "__main__":
    cleanup_expired_backup()
    app = QApplication(sys.argv)
    app.setApplicationName("Senton Control Owner Admin")
    window = SentonDashboard(config.APP_VERSION)
    window.setWindowTitle(f"Senton Control v{config.APP_VERSION} — OWNER ADMIN")
    window.show()

    # Owner-admin build checks both channels automatically after startup.
    QTimer.singleShot(2500, lambda: run_admin_update_check(window))
    sys.exit(app.exec())
