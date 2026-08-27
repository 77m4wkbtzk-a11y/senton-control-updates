from pathlib import Path
import tempfile

from updater import check_for_update


UPDATE_STATUS_FILE = Path(tempfile.gettempdir()) / "senton_control_update.status"
UPDATE_LOG_FILE = Path(tempfile.gettempdir()) / "senton_control_update.log"


def _show_previous_update_result(window):
    """Surface the previous updater helper result instead of failing silently."""
    if not UPDATE_STATUS_FILE.exists():
        return

    try:
        status = UPDATE_STATUS_FILE.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return

    if status == "success":
        window.update_status.setText(
            f"Senton Control v{window.version} started after a successful update."
        )
        window._log("Previous update completed successfully and Senton Control restarted")
        UPDATE_STATUS_FILE.unlink(missing_ok=True)
        return

    if status.startswith("failed:"):
        reason = status.partition(":")[2].strip() or "Unknown installer error"
        window.update_status.setText("Previous update failed: " + reason)
        window._log("Previous update failed: " + reason)
        if UPDATE_LOG_FILE.exists():
            window._log("Updater diagnostic log: " + str(UPDATE_LOG_FILE))


def install_universal_update_button(window):
    """Make update controls always re-check the live channel before installing."""

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
    _show_previous_update_result(window)
