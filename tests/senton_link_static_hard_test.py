from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
main_java = (ROOT / "phone-app/app/src/main/java/au/com/senton/link/MainActivity.java").read_text(encoding="utf-8")
update_java = (ROOT / "phone-app/app/src/main/java/au/com/senton/link/UpdateProgressActivity.java").read_text(encoding="utf-8")
manifest = (ROOT / "phone-app/app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
gradle = (ROOT / "phone-app/app/build.gradle").read_text(encoding="utf-8")

# The local Windows bridge is intentionally HTTP during beta/USB/LAN testing.
assert 'android:usesCleartextTraffic="true"' in manifest
assert 'android.permission.INTERNET' in manifest

# Normal dashboard remains the launcher; legacy Test Mode must stay gone.
assert 'android:name=".MainActivity"' in manifest
assert '<action android:name="android.intent.action.MAIN" />' in manifest
assert '<category android:name="android.intent.category.LAUNCHER" />' in manifest
assert 'TestModeActivity' not in manifest
assert 'TEST_MODE' not in gradle
assert 'BuildConfig.TEST_MODE' not in main_java
assert 'UNDER TESTING' not in main_java
assert not (ROOT / "phone-app/app/src/main/java/au/com/senton/link/TestModeActivity.java").exists()

# Update progress is a separate in-app page that can be closed without cancelling a queued download.
assert 'android:name=".UpdateProgressActivity"' in manifest
assert 'android:exported="false"' in manifest
assert 'new Intent(this, UpdateProgressActivity.class)' in main_java
for required_ui in [
    'SENTON LINK UPDATE',
    'BACK TO DASHBOARD',
    'You can close this page and return to the dashboard.',
    'Closing this page does not cancel a queued update.',
    'ProgressBar',
]:
    assert required_ui in update_java, required_ui

# The legacy Android-side Windows-link panel was intentionally removed from the dashboard.
# Keep that network/command surface absent while preserving the fail-safe idle dashboard state.
for removed in [
    'KEY_PC_ADDRESS',
    'DEFAULT_PC_URL',
    'pcRequestInFlight',
    'pollHandler.postDelayed(this, 3000)',
    'connectToPc(',
    'sendTestMessage(',
    'setPcDisconnected(',
    'Untrusted or unsafe PC response',
]:
    assert removed not in main_java, removed
assert 'Speed          0 km/h' in main_java
assert 'SENTON PI DISCONNECTED — SAFE MODE' in main_java
assert 'Vehicle link    Disconnected' in main_java
assert 'Safety mode     Active' in main_java

# Vehicle and charger actuation must stay disabled until authenticated Pi/car work exists.
for forbidden in [
    'button("DRIVE", true)',
    'button("START CHARGE", true)',
    'button("STOP CHARGE", true)',
]:
    assert forbidden not in main_java, forbidden
for required in [
    'button("DRIVE", false)',
    'button("START CHARGE", false)',
    'button("STOP CHARGE", false)',
]:
    assert required in main_java, required

# Repeated updater checks/downloads must not collide and every APK must be SHA-256 verified.
assert 'updateCheckInFlight.compareAndSet(false, true)' in update_java
for required_status in [
    'Update in progress — download already queued',
    'Update in progress — downloading Senton Link ',
    'Update in progress — verifying downloaded update…',
    'Update in progress — verified, opening Android installer…',
]:
    assert required_status in update_java, required_status
assert 'System.currentTimeMillis() + ".apk"' in update_java
assert 'sha.matches("[0-9a-f]{64}")' in update_java
assert '!apkUrl.startsWith("https://")' in update_java
assert 'expectedSha.equalsIgnoreCase(sha256(uri))' in update_java
assert 'MAX_RESPONSE_CHARS' in update_java

# Force-stop/reopen of the progress page must not lose an in-flight updater download or checksum.
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
    assert required_persistence in update_java, required_persistence

# Progress page must expose real DownloadManager byte progress while remaining safe to close.
assert 'COLUMN_BYTES_DOWNLOADED_SO_FAR' in update_java
assert 'COLUMN_TOTAL_SIZE_BYTES' in update_java
assert 'refreshDownloadProgress()' in update_java
assert 'handler.postDelayed(this, 1000)' in update_java

# The update page may keep its own screen awake while visible, but no legacy Test Mode is revived.
assert 'WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON' in update_java
assert 'finish()' in update_java  # user-initiated BACK TO DASHBOARD only

# A new manifest check while an APK is already downloading must not overwrite
# the checksum that belongs to the in-flight APK.
assert 'startUpdateDownload(apkUrl, remoteVersion, sha)' in update_java
assert 'private void startUpdateDownload(String apkUrl, String version, String sha)' in update_java
check_start = update_java.index('private void checkForUpdateAutomatically()')
download_start = update_java.index('private void startUpdateDownload(')
resume_start = update_java.index('private boolean resumePendingUpdateIfAny()')
check_block = update_java[check_start:download_start]
download_block = update_java[download_start:resume_start]
assert 'expectedSha = sha;' not in check_block
assert 'savePendingDownloadState(id, sha);' in download_block

version_name = re.search(r"versionName\s+'([^']+)'", gradle).group(1)
version_code = int(re.search(r"versionCode\s+(\d+)", gradle).group(1))
assert version_name == "2.3.3-beta", version_name
assert version_code == 2303, version_code

print("Senton Link Android static hard-test gates passed")
