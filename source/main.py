import sys
from PySide6.QtWidgets import QApplication
from dashboard import SentonDashboard
from config import APP_NAME, APP_VERSION
from cleanup import cleanup_obsolete_update_artifacts

if __name__ == "__main__":
    cleanup_obsolete_update_artifacts()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = SentonDashboard(APP_VERSION)
    window.show()
    sys.exit(app.exec())
