import sys
from PySide6.QtWidgets import QApplication
from dashboard import SentonDashboard
from config import APP_NAME, APP_VERSION
from cleanup import cleanup_obsolete_update_artifacts
from branding import install_branded_update_ui
from universal_updater_ui import install_universal_update_button
from phone_link_server import start_phone_link


if __name__ == "__main__":
    cleanup_obsolete_update_artifacts()

    phone_link_server = None
    phone_link_url = None
    try:
        phone_link_server, phone_link_url = start_phone_link()
        print(f"Senton Link bridge ready at {phone_link_url}")
    except OSError as exc:
        # Keep Senton Control usable if the bridge port is unavailable.
        print(f"Senton Link bridge unavailable: {exc}")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    install_branded_update_ui()
    window = SentonDashboard(APP_VERSION)
    install_universal_update_button(window)
    window.show()

    exit_code = app.exec()
    if phone_link_server is not None:
        try:
            phone_link_server.shutdown()
            phone_link_server.server_close()
        except Exception:
            pass
    sys.exit(exit_code)
