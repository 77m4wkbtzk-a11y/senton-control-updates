APP_NAME = "Senton Control"
APP_VERSION = "1.2.6"

# Self-updating is intentionally disabled in the v1.2.6 desktop build.
# This PC will receive v1.2.6 as the final self-update, then future updates
# must be installed manually unless this setting is deliberately re-enabled.
UPDATE_MANIFEST_URL = ""
PUBLIC_UPDATE_MANIFEST_URL = ""
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
