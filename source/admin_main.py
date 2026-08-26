import hashlib
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

import config
from dashboard import SentonDashboard
from updater import (
    check_for_update,
    cleanup_expired_backup,
    download_update,
    install_update_to_main_desktop,
)


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def run_admin_update_check(window):
    result = check_for_update(config.APP_VERSION)
    if not result.get("ok"):
        window._log(f"ADMIN CHANNEL check unavailable: {result.get('reason', 'Unknown error')}")
        return
    if not result.get("update_available"):
        window._log("ADMIN CHANNEL: no newer admin build available")
        return

    download_url = result.get("download_url", "").strip()
    expected_hash = result.get("sha256", "").strip().lower()
    if not download_url or not expected_hash:
        window._log("ADMIN CHANNEL: update metadata incomplete; install blocked")
        return

    try:
        window.update_status.setText(
            f"Admin update v{result.get('latest_version', '?')} found. Downloading and verifying..."
        )
        window._log("ADMIN CHANNEL: downloading verified update")
        path = download_update(download_url)
        actual_hash = _sha256(path)
        if actual_hash != expected_hash:
            raise RuntimeError("Admin update integrity check failed. Installation blocked.")

        window.update_status.setText(
            f"Admin update v{result.get('latest_version', '?')} downloaded and verified."
        )
        answer = QMessageBox.question(
            window,
            "Verified admin update ready",
            f"Senton Control admin update v{result.get('latest_version', '?')} has been downloaded and verified.\n\nInstall it now?"
        )
        if answer != QMessageBox.Yes:
            window._log("ADMIN CHANNEL: verified update left pending by admin")
            return

        window._log("ADMIN CHANNEL: verified update approved for installation")
        install_update_to_main_desktop(path)
        QApplication.quit()
    except Exception as exc:
        window._log(f"ADMIN CHANNEL update failed: {exc}")
        window.update_status.setText(f"Admin update failed: {exc}")


if __name__ == "__main__":
    cleanup_expired_backup()
    app = QApplication(sys.argv)
    app.setApplicationName("Senton Control Admin")
    window = SentonDashboard(config.APP_VERSION)
    window.setWindowTitle(f"Senton Control v{config.APP_VERSION} — ADMIN")
    window.show()

    # Admin channel checks automatically after launch and downloads only verified updates.
    QTimer.singleShot(2500, lambda: run_admin_update_check(window))
    sys.exit(app.exec())
