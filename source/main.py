import sys
from PySide6.QtWidgets import QApplication
from dashboard import SentonDashboard

APP_VERSION = "1.2.2"

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Senton Control")
    window = SentonDashboard(APP_VERSION)
    window.show()
    sys.exit(app.exec())
