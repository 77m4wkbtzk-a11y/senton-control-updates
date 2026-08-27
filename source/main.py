import sys
from PySide6.QtWidgets import QApplication
from dashboard import SentonDashboard
from config import APP_NAME, APP_VERSION
from cleanup import cleanup_obsolete_update_artifacts
from branding import install_branded_update_ui

if __name__ == "__main__":
    cleanup_obsolete_update_artifacts()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    install_branded_update_ui()
    window = SentonDashboard(APP_VERSION)
    window.show()
    sys.exit(app.exec())
