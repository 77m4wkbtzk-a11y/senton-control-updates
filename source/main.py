import sys
from PySide6.QtWidgets import QApplication
from dashboard import SentonDashboard
from updater import cleanup_expired_backup

APP_VERSION = "1.2.5"

if __name__ == "__main__":
    cleanup_expired_backup()
    app = QApplication(sys.argv)
    app.setApplicationName("Senton Control")
    window = SentonDashboard(APP_VERSION)
    window.show()
    sys.exit(app.exec())
