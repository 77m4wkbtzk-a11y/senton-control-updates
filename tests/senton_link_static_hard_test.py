from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
java = (ROOT / "phone-app/app/src/main/java/au/com/senton/link/MainActivity.java").read_text(encoding="utf-8")
manifest = (ROOT / "phone-app/app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
gradle = (ROOT / "phone-app/app/build.gradle").read_text(encoding="utf-8")

# The local Windows bridge is intentionally HTTP during beta/USB/LAN testing.
assert 'android:usesCleartextTraffic="true"' in manifest
assert 'android.permission.INTERNET' in manifest

# Normal dashboard must be the only launcher and legacy Test Mode must be gone.
assert 'android:name=".MainActivity"' in manifest
assert '<action android:name="android.intent.action.MAIN" />' in manifest
assert '<category android:name="android.intent.category.LAUNCHER" />' in manifest
assert 'TestModeActivity' not in manifest
assert 'TEST_MODE' not in gradle
assert 'BuildConfig.TEST_MODE' not in java
assert 'UNDER TESTING' not in java
assert 'KEEP USB CONNECTED' not in java
assert not (ROOT / "phone-app/app/src/main/java/au/com/senton/link/TestModeActivity.java").exists()

# Cold launch / reconnect / telemetry refresh hardening.
assert 'SharedPreferences' in java
assert 'KEY_PC_ADDRESS' in java
assert 'pollHandler.postDelayed(this, 3000)' in java
assert 'pcRequestInFlight.compareAndSet(false, true)' in java
assert 'setConnectTimeout(3000)' in java
assert 'setReadTimeout(3000)' in java
assert 'setPcDisconnected' in java
assert 'Speed          0 km/h' in java

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
for required_status in [
    'Update in progress — download already queued',
    'Update in progress — downloading Senton Link ',
    'Update in progress — verifying downloaded update…',
    'Update in progress — verified, opening Android installer…',
]:
    assert required_status in java, required_status
assert 'System.currentTimeMillis() + ".apk"' in java
assert 'sha.matches("[0-9a-f]{64}")' in java
assert '!apkUrl.startsWith("https://")' in java
assert 'expectedSha.equalsIgnoreCase(sha256(uri))' in java
assert 'MAX_RESPONSE_CHARS' in java

# Force-stop/relaunch must not lose an in-flight updater download or its checksum.
for required_persistence in [
    'KEY_DOWNLOAD_ID',
    'KEY_EXPECTED_SHA',
    'prefs.getLong(KEY_DOWNLOAD_ID, -1)',
    'prefs.getString(KEY_EXPECTED_SHA, "")',
    'resumePendingUpdateIfAny()',
    'savePendingDownloadState(id, sha)',
    '.putLong(KEY_DOWNLOAD_ID, id)',
    '.putString(KEY_EXPECTED_SHA, sha)',
    '.remove(KEY_DOWNLOAD_ID)',
    '.remove(KEY_EXPECTED_SHA)',
    'clearPendingDownloadState()',
]:
    assert required_persistence in java, required_persistence

# A new manifest check while an APK is already downloading must not overwrite
# the checksum that belongs to the in-flight APK. Bind the checksum only when
# the download itself is queued and persist it with that DownloadManager id.
assert 'startUpdateDownload(apkUrl, remoteVersion, sha)' in java
assert 'private void startUpdateDownload(String apkUrl, String version, String sha)' in java
check_start = java.index('private void checkForUpdateAutomatically()')
download_start = java.index('private void startUpdateDownload(')
resume_start = java.index('private boolean resumePendingUpdateIfAny()')
check_block = java[check_start:download_start]
download_block = java[download_start:resume_start]
assert 'expectedSha = sha;' not in check_block
assert 'savePendingDownloadState(id, sha);' in download_block

version_name = re.search(r"versionName\s+'([^']+)'", gradle).group(1)
version_code = int(re.search(r"versionCode\s+(\d+)", gradle).group(1))
assert version_name == "2.3.1-beta", version_name
assert version_code == 2301, version_code

print("Senton Link Android static hard-test gates passed")
