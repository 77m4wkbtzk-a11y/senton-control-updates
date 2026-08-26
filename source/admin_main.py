import hashlib
import json
import sys
import urllib.request

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

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
        req = urllib.request.Request(url, headers={"User-Agent": "Senton-Control-Admin-Updater"})
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
        window._log("ADMIN UPDATE WATCH: no newer update available on admin or public channel")
        return

    latest = str(result.get("version", "?"))
    channel = result.get("_channel_name", "UNKNOWN")
    download_url = str(result.get("download_url", "")).strip()
    expected_hash = str(result.get("sha256", "")).strip().lower()

    if not download_url:
        window._log(f"ADMIN UPDATE WATCH: v{latest} metadata incomplete; download blocked")
        return

    try:
        window.update_status.setText(
            f"{channel} update v{latest} found. Downloading and verifying..."
        )
        window._log(f"ADMIN UPDATE WATCH: downloading v{latest} from {channel} channel")
        path = download_update(download_url)

        # Admin builds must carry a SHA-256. Public builds are verified when a hash is supplied.
        if channel == "ADMIN" and not expected_hash:
            raise RuntimeError("Admin update is missing its SHA-256 integrity value.")
        if expected_hash:
            actual_hash = _sha256(path)
            if actual_hash != expected_hash:
                raise RuntimeError("Update integrity check failed. Installation blocked.")

        window.update_status.setText(f"Update v{latest} downloaded and verified.")
        answer = QMessageBox.question(
            window,
            "Senton Control update ready",
            f"Senton Control update v{latest} from the {channel.lower()} channel is ready.\n\nInstall it now?",
        )
        if answer != QMessageBox.Yes:
            window._log(f"ADMIN UPDATE WATCH: v{latest} left pending by admin")
            return

        window._log(f"ADMIN UPDATE WATCH: v{latest} approved for installation")
        install_update_to_main_desktop(path)
        QApplication.quit()
    except Exception as exc:
        window._log(f"ADMIN UPDATE WATCH failed: {exc}")
        window.update_status.setText(f"Admin update failed: {exc}")


if __name__ == "__main__":
    cleanup_expired_backup()
    app = QApplication(sys.argv)
    app.setApplicationName("Senton Control Admin")
    window = SentonDashboard(config.APP_VERSION)
    window.setWindowTitle(f"Senton Control v{config.APP_VERSION} — ADMIN")
    window.show()

    # Check both admin and public update channels after startup.
    QTimer.singleShot(2500, lambda: run_admin_update_check(window))
    sys.exit(app.exec())
