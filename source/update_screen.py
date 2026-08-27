from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QProgressBar, QVBoxLayout


class SentonInstallScreen(QDialog):
    """Branded Senton Control install/progress screen for desktop updates."""

    def __init__(self, version="", parent=None):
        super().__init__(parent)
        self.version = version
        self.setWindowTitle("Senton Control Update")
        self.setFixedSize(560, 380)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog {
                background: #0f1115;
                color: #f2f2f2;
            }
            QLabel {
                color: #f2f2f2;
            }
            QProgressBar {
                background: #20242a;
                border: 1px solid #30343b;
                border-radius: 7px;
                min-height: 18px;
                text-align: center;
                color: white;
            }
            QProgressBar::chunk {
                background: #3b82f6;
                border-radius: 6px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(38, 34, 38, 34)
        layout.setSpacing(15)

        logo = QLabel("SENTON\nCONTROL")
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet(
            "font-size:34px;font-weight:900;letter-spacing:5px;"
            "border:2px solid #3b82f6;border-radius:16px;padding:18px;"
            "background:#111827;"
        )
        layout.addWidget(logo)

        self.title_label = QLabel("INSTALLING SENTON CONTROL UPDATE")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-size:18px;font-weight:800;")
        layout.addWidget(self.title_label)

        self.version_label = QLabel(f"Version {version}" if version else "Preparing update")
        self.version_label.setAlignment(Qt.AlignCenter)
        self.version_label.setStyleSheet("color:#93c5fd;font-size:15px;font-weight:600;")
        layout.addWidget(self.version_label)

        self.status_label = QLabel("Preparing Senton Control for installation...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        footer = QLabel("SENTON CONTROL • VERIFIED UPDATE")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("color:#86efac;font-size:12px;font-weight:700;")
        layout.addWidget(footer)

    def set_stage(self, stage, percent=None):
        stages = {
            "checking": "Checking update package...",
            "downloading": "Downloading Senton Control update...",
            "closing": "Closing the current Senton Control...",
            "installing": "Installing the new Senton Control version...",
            "cleaning": "Removing obsolete Senton update files...",
            "restarting": "Starting the new Senton Control...",
            "complete": "Update complete.",
            "error": "Update could not be completed.",
        }
        self.status_label.setText(stages.get(stage, str(stage)))
        if percent is not None:
            self.progress.setRange(0, 100)
            self.progress.setValue(max(0, min(100, int(percent))))
        elif stage in {"downloading", "installing", "cleaning", "restarting"}:
            self.progress.setRange(0, 0)


def preview(version="1.2.8"):
    app = QApplication.instance() or QApplication([])
    dlg = SentonInstallScreen(version)
    dlg.set_stage("installing")
    dlg.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(preview())
