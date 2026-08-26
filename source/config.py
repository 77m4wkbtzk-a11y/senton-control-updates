APP_NAME = "Senton Control"
APP_VERSION = "1.2.4"

# Owner-admin beta channel. This build also watches the public manifest for
# owner-admin-compatible packages without replacing itself with the public EXE.
UPDATE_MANIFEST_URL = "https://raw.githubusercontent.com/77m4wkbtzk-a11y/senton-control-updates/admin-beta/admin/update.json"
ADMIN_UPDATE_MANIFEST_URL = UPDATE_MANIFEST_URL
PUBLIC_UPDATE_MANIFEST_URL = "https://raw.githubusercontent.com/77m4wkbtzk-a11y/senton-control-updates/main/update.json"
ADMIN_UPDATE_CHANNEL = True
AUTO_DOWNLOAD_ADMIN_UPDATES = True
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
