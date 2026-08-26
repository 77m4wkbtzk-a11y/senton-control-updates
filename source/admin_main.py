import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import config
from dashboard import SentonDashboard
from updater import (
    check_for_update,
    cleanup_expired_backup,
    download_update,
    install_update_to_main_desktop,
)


def run_admin_auto_update(window):
    if not getattr(config, "AUTO_INSTALL_ADMIN_UPDATES", False):
        return

    result = check_for_update(config.APP_VERSION)
    if not result.get("ok") or not result.get("update_available"):
        return

    download_url = result.get("download_url", "").strip()
    if not download_url:
        return

    try:
        window.update_status.setText(
            f"Admin update v{result.get('latest_version', '?')} found. Installing automatically..."
        )
        window._log("ADMIN CHANNEL: automatic update started")
        path = download_update(download_url)
        install_update_to_main_desktop(path)
        QApplication.quit()
    except Exception as exc:
        window._log(f"ADMIN CHANNEL update failed: {exc}")
        window.update_status.setText(f"Admin automatic update failed: {exc}")


if __name__ == "__main__":
    cleanup_expired_backup()
    app = QApplication(sys.argv)
    app.setApplicationName("Senton Control Admin")
    window = SentonDashboard(config.APP_VERSION)
    window.setWindowTitle(f"Senton Control v{config.APP_VERSION} — ADMIN")
    window.show()

    # Give the UI time to load, then silently check the separate admin channel.
    QTimer.singleShot(2500, lambda: run_admin_auto_update(window))
    sys.exit(app.exec())
