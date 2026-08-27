from PySide6.QtWidgets import QMessageBox

from updater import check_for_update


def install_universal_update_button(window):
    """Make the update controls always re-check the live channel before installing.

    This keeps one consistent update-button behaviour for every Senton Control
    release built with this bootstrap: press Update Senton Control, re-check the
    manifest, then hand off to the dashboard's verified background installer.
    """

    def show_result(result):
        if not result.get("ok"):
            reason = result.get("reason", "Unknown update error")
            window.update_status.setText("Update check unavailable: " + reason)
            window.install_update_btn.setEnabled(True)
            window.check_update_btn.setEnabled(True)
            window._log("Update check failed: " + reason)
            return False

        latest = result.get("latest_version", "?")
        if not result.get("update_available"):
            window.update_url = ""
            window.update_status.setText(f"You're up to date. Latest version: v{latest}")
            window.install_update_btn.setEnabled(True)
            window.check_update_btn.setEnabled(True)
            return False

        window.update_url = result.get("download_url", "").strip()
        if not window.update_url:
            window.update_status.setText(f"v{latest} is available, but its download URL is missing.")
            window.install_update_btn.setEnabled(True)
            window.check_update_btn.setEnabled(True)
            window._log("Update blocked: live manifest has no download URL")
            return False

        notes = result.get("notes", "").strip()
        text = f"Update available: v{latest}"
        if notes:
            text += "\n" + notes
        window.update_status.setText(text)
        window.install_update_btn.setEnabled(True)
        return True

    def check_now():
        if window.update_thread and window.update_thread.isRunning():
            return
        window.update_status.setText("Checking live Senton update channel…")
        window.check_update_btn.setEnabled(False)
        result = check_for_update(window.version)
        show_result(result)

    def update_now():
        if window.update_thread and window.update_thread.isRunning():
            return
        window.update_status.setText("Checking for the newest Senton Control update…")
        window.install_update_btn.setEnabled(False)
        window.check_update_btn.setEnabled(False)
        result = check_for_update(window.version)
        if not show_result(result):
            return
        window._log("Universal updater confirmed a newer live release")
        window.install_update()

    try:
        window.check_update_btn.clicked.disconnect()
    except Exception:
        pass
    try:
        window.install_update_btn.clicked.disconnect()
    except Exception:
        pass

    window.check_update_btn.clicked.connect(check_now)
    window.install_update_btn.clicked.connect(update_now)
    window.install_update_btn.setText("UPDATE SENTON CONTROL")
    window.install_update_btn.setEnabled(True)
    window.update_status.setText("Ready to update Senton Control.")
