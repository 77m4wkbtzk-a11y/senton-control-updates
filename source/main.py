import sys
from PySide6.QtWidgets import QApplication
from dashboard import SentonDashboard
from updater import cleanup_expired_backup
from config import APP_NAME, APP_VERSION

if __name__ == "__main__":
    cleanup_expired_backup()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = SentonDashboard(APP_VERSION)
    window.show()
    sys.exit(app.exec())
