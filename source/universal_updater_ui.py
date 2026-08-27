from pathlib import Path
import tempfile

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressBar

from installer_relaunch import install_update_and_relaunch
from progress_updater import download_update_with_progress
from updater import check_for_update


UPDATE_STATUS_FILE = Path(tempfile.gettempdir()) / "senton_control_update.status"
UPDATE_LOG_FILE = Path(tempfile.gettempdir()) / "senton_control_update.log"


class ProgressUpdateThread(QThread):
    progress = Signal(int)
    downloaded = Signal(object)
    failed = Signal(str)

    def __init__(self, url, expected_sha256, parent=None):
        super().__init__(parent)
        self.url = url
        self.expected_sha256 = expected_sha256

    def run(self):
        try:
            path = download_update_with_progress(
                self.url,
                self.expected_sha256,
                self.progress.emit,
            )
            self.downloaded.emit(path)
        except Exception as exc:
            self.failed.emit(str(exc))


def _show_previous_update_result(window):
    if not UPDATE_STATUS_FILE.exists():
        return

    try:
        status = UPDATE_STATUS_FILE.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return

    if status in {"success", "success-no-relaunch", "success-relaunched"}:
        window.update_status.setText(f"Senton Control v{window.version} is installed and running.")
        window._log("Previous update completed successfully")
        UPDATE_STATUS_FILE.unlink(missing_ok=True)
        return

    if status.startswith("failed:"):
        reason = status.partition(":")[2].strip() or "Unknown installer error"
        window.update_status.setText("Previous update failed: " + reason)
        window._log("Previous update failed: " + reason)
        if UPDATE_LOG_FILE.exists():
            window._log("Updater diagnostic log: " + str(UPDATE_LOG_FILE))


def install_universal_update_button(window):
    """Fast verified updater that installs, verifies the installed EXE, and relaunches automatically."""

    progress_bar = QProgressBar(window)
    progress_bar.setRange(0, 100)
    progress_bar.setValue(0)
    progress_bar.setFormat("Update progress: %p%")
    progress_bar.setVisible(False)

    update_layout = window.update_status.parentWidget().layout()
    if update_layout is not None:
        update_layout.insertWidget(2, progress_bar)

    window.update_progress_bar = progress_bar
    window.universal_update_thread = None
    window.update_sha256 = ""

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
            window.update_sha256 = ""
            window.update_status.setText(f"You're up to date. Latest version: v{latest}")
            window.install_update_btn.setEnabled(True)
            window.check_update_btn.setEnabled(True)
            return False

        window.update_url = result.get("download_url", "").strip()
        window.update_sha256 = result.get("sha256", "").strip().lower()
        if not window.update_url:
            window.update_status.setText(f"v{latest} is available, but its download URL is missing.")
            window.install_update_btn.setEnabled(True)
            window.check_update_btn.setEnabled(True)
            window._log("Update blocked: live manifest has no download URL")
            return False
        if len(window.update_sha256) != 64:
            window.update_status.setText(f"v{latest} is available, but its verification hash is invalid.")
            window.install_update_btn.setEnabled(True)
            window.check_update_btn.setEnabled(True)
            window._log("Update blocked: live manifest has no valid SHA-256")
            return False

        notes = result.get("notes", "").strip()
        text = f"Update available: v{latest}"
        if notes:
            text += "\n" + notes
        window.update_status.setText(text)
        window.install_update_btn.setEnabled(True)
        return True

    def set_progress(value):
        progress_bar.setVisible(True)
        progress_bar.setValue(value)
        if value < 92:
            window.update_status.setText(f"Downloading Senton Control update… {value}%")
        elif value < 100:
            window.update_status.setText("Download complete. Verifying update integrity…")
        else:
            window.update_status.setText("Update verified. Installing and restarting Senton Control…")

    def update_failed(message):
        progress_bar.setVisible(True)
        progress_bar.setValue(0)
        window.update_status.setText("Update failed. Senton Control has remained open.")
        window.install_update_btn.setEnabled(True)
        window.check_update_btn.setEnabled(True)
        window._log("Update failed: " + message)
        QMessageBox.critical(window, "Update Failed", message)

    def update_downloaded(path):
        window.downloaded_update_path = path
        progress_bar.setVisible(True)
        progress_bar.setValue(100)
        window.update_status.setText(
            "Update downloaded and verified at 100%. Installing now; Senton Control will restart automatically."
        )
        window._log(f"Update downloaded and verified: {path}; starting verified install-and-relaunch handoff")
        try:
            install_update_and_relaunch(path)
            QApplication.quit()
        except Exception as exc:
            update_failed(str(exc))

    def start_download():
        progress_bar.setVisible(True)
        progress_bar.setValue(0)
        window.install_update_btn.setEnabled(False)
        window.check_update_btn.setEnabled(False)
        window.update_status.setText("Starting Senton Control update… 0%")
        window._log("Secure background update download started")

        thread = ProgressUpdateThread(window.update_url, window.update_sha256, window)
        window.universal_update_thread = thread
        window.update_thread = thread
        thread.progress.connect(set_progress)
        thread.downloaded.connect(update_downloaded)
        thread.failed.connect(update_failed)
        thread.start()

    def check_now():
        if window.universal_update_thread and window.universal_update_thread.isRunning():
            return
        window.update_status.setText("Checking live Senton update channel…")
        window.check_update_btn.setEnabled(False)
        result = check_for_update(window.version)
        show_result(result)

    def update_now():
        if window.universal_update_thread and window.universal_update_thread.isRunning():
            return

        window.update_status.setText("Checking for the newest Senton Control update…")
        window.install_update_btn.setEnabled(False)
        window.check_update_btn.setEnabled(False)
        result = check_for_update(window.version)
        if not show_result(result):
            return

        answer = QMessageBox.question(
            window,
            "Install Senton Control update",
            "Download and install the newest Senton Control version now?\n\nSenton Control will stay open during download and verification. After verification reaches 100%, the current app will close, the verified EXE will replace it, and Senton Control will restart automatically."
        )
        if answer != QMessageBox.Yes:
            window.install_update_btn.setEnabled(True)
            window.check_update_btn.setEnabled(True)
            return

        window._log("Universal updater confirmed a newer live release")
        start_download()

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
