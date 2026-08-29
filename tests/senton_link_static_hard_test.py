from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
java = (ROOT / "phone-app/app/src/main/java/au/com/senton/link/MainActivity.java").read_text(encoding="utf-8")
manifest = (ROOT / "phone-app/app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
gradle = (ROOT / "phone-app/app/build.gradle").read_text(encoding="utf-8")

# The local Windows bridge is intentionally HTTP during beta/USB/LAN testing.
assert 'android:usesCleartextTraffic="true"' in manifest
assert 'android.permission.INTERNET' in manifest

# Cold launch / reconnect / telemetry refresh hardening.
assert 'SharedPreferences' in java
assert 'KEY_PC_ADDRESS' in java
assert 'pollHandler.postDelayed(this, 3000)' in java
assert 'pcRequestInFlight.compareAndSet(false, true)' in java
assert 'setConnectTimeout(3000)' in java
assert 'setReadTimeout(3000)' in java
assert 'setPcDisconnected' in java
assert 'Speed          0 km/h' in java

# Test Mode must be explicit, visible and keep the test phone awake while the app is active.
assert "buildConfigField 'boolean', 'TEST_MODE', 'true'" in gradle
assert 'BuildConfig.TEST_MODE' in java
assert 'WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON' in java
assert 'UNDER TESTING' in java
assert 'KEEP USB CONNECTED' in java
assert 'testing.setVisibility(BuildConfig.TEST_MODE ? View.VISIBLE : View.GONE)' in java
assert 'BuildConfig.TEST_MODE ? "TESTING" : "OK"' in java

# Responses fail closed: wrong service/protocol or safe_mode=false cannot be trusted.
assert '"Senton Control".equals(json.optString("service", ""))' in java
assert 'json.optInt("protocol", -1) != SENTON_PROTOCOL' in java
assert 'json.optBoolean("safe_mode", false)' in java
assert 'Untrusted or unsafe PC response' in java

# Vehicle and charger actuation must stay disabled until authenticated Pi/car work exists.
for forbidden in [
    'button("DRIVE", true)',
    'button("START CHARGE", true)',
    'button("STOP CHARGE", true)',
]:
    assert forbidden not in java, forbidden
for required in [
    'button("DRIVE", false)',
    'button("START CHARGE", false)',
    'button("STOP CHARGE", false)',
]:
    assert required in java, required

# Repeated updater checks/downloads must not collide and every APK must be SHA-256 verified.
assert 'updateCheckInFlight.compareAndSet(false, true)' in java
assert 'UPDATE IN PROGRESS' in java
assert 'downloading' in java.lower()
assert 'verifying' in java.lower()
assert 'opening Android installer' in java
assert 'System.currentTimeMillis() + ".apk"' in java
assert 'sha.matches("[0-9a-f]{64}")' in java
assert '!apkUrl.startsWith("https://")' in java
assert 'expectedSha.equalsIgnoreCase(sha256(uri))' in java
assert 'MAX_RESPONSE_CHARS' in java

# A new manifest check while an APK is already downloading must not overwrite
# the checksum that belongs to the in-flight APK. Bind the checksum only when
# the download itself is queued.
assert 'startUpdateDownload(apkUrl, remoteVersion, sha)' in java
assert 'private void startUpdateDownload(String apkUrl, String version, String sha)' in java
check_start = java.index('private void checkForUpdateAutomatically()')
download_start = java.index('private void startUpdateDownload(')
handle_start = java.index('private void handleDownloadedUpdate()')
check_block = java[check_start:download_start]
download_block = java[download_start:handle_start]
assert 'expectedSha = sha;' not in check_block
assert 'expectedSha = sha;' in download_block
assert 'expectedSha = "";' in java

version_name = re.search(r"versionName\s+'([^']+)'", gradle).group(1)
version_code = int(re.search(r"versionCode\s+(\d+)", gradle).group(1))
assert version_name == "2.3.1-beta", version_name
assert version_code == 2301, version_code

print("Senton Link Android static hard-test gates passed")
