APP_NAME = "Senton Control"
APP_VERSION = "1.2.3"

# Admin-only beta update channel. The public main/update.json remains on hold.
UPDATE_MANIFEST_URL = "https://raw.githubusercontent.com/77m4wkbtzk-a11y/senton-control-updates/admin-beta/admin/update.json"
ADMIN_UPDATE_CHANNEL = True
AUTO_INSTALL_ADMIN_UPDATES = True

PI_HOST = "192.168.1.50"
PI_PORT = 8765

TAKEOVER_DELAY_SECONDS = 10
SESSION_LIMIT_SECONDS = 30 * 60

DEMO_MAX_SPEED_KMH = 2.0
NORMAL_AUTO_MAX_SPEED_KMH = 5.0

STOP_ON_REMOTE_LOSS_UNLESS_AUTO_ARMED = True
STOP_ON_SENSOR_FAILURE = True
STOP_ON_CAMERA_FAILURE = True
