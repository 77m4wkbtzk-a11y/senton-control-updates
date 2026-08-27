APP_NAME = "Senton Control"
APP_VERSION = "1.2.8.1"

# APP_VERSION above is the single authoritative version used by the app.
# v1.2.8.1 is a small OTA update-path test from the v1.2.8 baseline.
UPDATE_MANIFEST_URL = "https://raw.githubusercontent.com/77m4wkbtzk-a11y/senton-control-updates/main/update.json"
PUBLIC_UPDATE_MANIFEST_URL = UPDATE_MANIFEST_URL
ADMIN_UPDATE_MANIFEST_URL = ""

PI_HOST = "192.168.1.50"
PI_PORT = 8765

TAKEOVER_DELAY_SECONDS = 10
SESSION_LIMIT_SECONDS = 30 * 60

DEMO_MAX_SPEED_KMH = 2.0
NORMAL_AUTO_MAX_SPEED_KMH = 5.0

STOP_ON_REMOTE_LOSS_UNLESS_AUTO_ARMED = True
STOP_ON_SENSOR_FAILURE = True
STOP_ON_CAMERA_FAILURE = True
