from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
main_java = (ROOT / "phone-app/app/src/main/java/au/com/senton/link/MainActivity.java").read_text(encoding="utf-8")
update_java = (ROOT / "phone-app/app/src/main/java/au/com/senton/link/UpdateProgressActivity.java").read_text(encoding="utf-8")
manifest = (ROOT / "phone-app/app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
gradle = (ROOT / "phone-app/app/build.gradle").read_text(encoding="utf-8")

# Required platform permissions and network policy.
assert 'android.permission.INTERNET' in manifest
assert 'android.permission.REQUEST_INSTALL_PACKAGES' in manifest
assert 'android:usesCleartextTraffic="true"' in manifest

# Launcher integrity: MainActivity remains the single app launcher and is also an optional HOME target.
assert manifest.count('<action android:name="android.intent.action.MAIN" />') == 1
assert manifest.count('<category android:name="android.intent.category.LAUNCHER" />') == 1
assert manifest.count('<category android:name="android.intent.category.HOME" />') == 1
assert manifest.count('<category android:name="android.intent.category.DEFAULT" />') == 1
assert 'android:name=".MainActivity"' in manifest
assert 'android:name=".UpdateProgressActivity"' in manifest
assert 'android:exported="false"' in manifest
assert 'TestModeActivity' not in manifest
assert not (ROOT / "phone-app/app/src/main/java/au/com/senton/link/TestModeActivity.java").exists()

# Launcher/kiosk foundation must stay reversible and non-privileged.
for required_launcher in [
    'Launcher Mode',
    'Launcher mode   Ready',
    'applyImmersiveLauncherUi()',
    'SYSTEM_UI_FLAG_IMMERSIVE_STICKY',
    'SYSTEM_UI_FLAG_FULLSCREEN',
    'SYSTEM_UI_FLAG_HIDE_NAVIGATION',
    'HOLD FOR ANDROID MAINTENANCE',
    'setOnLongClickListener',
    'Settings.ACTION_SETTINGS',
    'Long-press only. Opens Android settings',
]:
    assert required_launcher in main_java, required_launcher
assert 'DevicePolicyManager' not in main_java
assert 'startLockTask()' not in main_java
assert 'stopLockTask()' not in main_java

# Hard-test mode is allowed only inside MainActivity. It must remain selected across
# foreground/background transitions, request keep-screen-on only while foregrounded,
# and must not auto-dismiss on a timer or lifecycle transition.
for required_test_mode in [
    'EXTRA_TEST_MODE = "senton_test_mode"',
    'getBooleanExtra(EXTRA_TEST_MODE, false)',
    'UNDER TESTING',
    'TEMPORARY HARD-TEST SESSION',
    'VEHICLE CONTROLS LOCKED',
    'FLAG_KEEP_SCREEN_ON',
]:
    assert required_test_mode in main_java, required_test_mode
assert 'TestModeActivity' not in main_java
assert 'BuildConfig.TEST_MODE' not in main_java
assert "putBoolean(EXTRA_TEST_MODE" not in main_java
assert "putString(EXTRA_TEST_MODE" not in main_java
assert 'senton_test_mode' not in update_java
assert 'UNDER TESTING' not in update_java
assert 'senton_test_mode' not in manifest

resume_start = main_java.index('@Override protected void onResume()')
pause_start = main_java.index('@Override protected void onPause()')
system_start = main_java.index('private String systemText()', pause_start)
resume_block = main_java[resume_start:pause_start]
pause_block = main_java[pause_start:system_start]
assert 'if (testMode)' in resume_block
assert 'getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)' in resume_block
assert 'if (testMode)' in pause_block
assert 'getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)' in pause_block
for forbidden_auto_exit in [
    'TEST_MODE_MAX_MS',
    'postDelayed(',
    'exitTemporaryTestMode',
    'removeExtra(EXTRA_TEST_MODE)',
    'testMode = false',
]:
    assert forbidden_auto_exit not in main_java, forbidden_auto_exit
assert 'testBanner.setVisibility(View.GONE)' not in pause_block

# Windows Link was intentionally removed. No old PC-control surface may remain.
for removed in [
    'WINDOWS LINK',
    'KEY_PC_ADDRESS',
    'DEFAULT_PC_URL',
    'pcRequestInFlight',
    'connectToPc(',
    'sendTestMessage(',
    '/senton/status',
    '/senton/test-message',
    'SEND TEST',
    'button("CONNECT"',
]:
    assert removed not in main_java, removed
assert 'Speed          0 km/h' in main_java
assert 'SENTON PI DISCONNECTED — SAFE MODE' in main_java
assert 'Vehicle link    Disconnected' in main_java
assert 'Safety mode     Active' in main_java

# Solar charging feature has been removed from Senton Link.
for removed_solar in [
    'SOLAR CHARGE',
    'Solar input',
    'Charging        OFF',
    'Charge timer',
    'START CHARGE',
    'STOP CHARGE',
]:
    assert removed_solar not in main_java, removed_solar

# Test sighting SMS must be user-reviewed in the phone's messaging app.
for required_sms in [
    'TEST SIGHTING SMS',
    'showTestSmsDialog()',
    'Intent.ACTION_SENDTO',
    'Uri.parse("smsto:" + Uri.encode(recipient))',
    'sms.putExtra("sms_body", body)',
    'Unverified possible sighting photo',
    'Do not treat it as confirmed identification',
]:
    assert required_sms in main_java, required_sms
assert 'android.permission.SEND_SMS' not in manifest
assert 'SmsManager' not in main_java
assert '.sendTextMessage(' not in main_java

# Update page must be in-app, explicitly closable, and reopening it must resume update state.
assert 'new Intent(this, UpdateProgressActivity.class)' in main_java
for required_ui in [
    'SENTON LINK UPDATE',
    'BACK TO DASHBOARD',
    'CHECK FOR UPDATE',
    'You can close this page and return to the dashboard.',
    'Closing this page does not cancel a queued update.',
    'ProgressBar',
    'Installed: ',
]:
    assert required_ui in update_java, required_ui
assert 'close.setOnClickListener(v -> finish())' in update_java
assert 'if (!resumePendingUpdateIfAny()) checkForUpdateAutomatically();' in update_java
assert 'WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON' in update_java

# The updater must fail closed on malformed manifests and non-HTTPS APK URLs.
assert 'remoteVersion.isEmpty()' in update_java
assert '!apkUrl.startsWith("https://")' in update_java
assert 'sha.matches("[0-9a-f]{64}")' in update_java
assert 'throw new SecurityException("Invalid update manifest")' in update_java
assert 'MAX_RESPONSE_CHARS' in update_java
assert 'Response too large' in update_java
assert 'setConnectTimeout(10000)' in update_java
assert 'setReadTimeout(10000)' in update_java
assert 'setUseCaches(false)' in update_java
assert 'Cache-Control' in update_java

# Repeated update taps/checks must not collide.
assert 'AtomicBoolean updateCheckInFlight' in update_java
assert 'updateCheckInFlight.compareAndSet(false, true)' in update_java
assert 'updateCheckInFlight.set(false)' in update_java

# Download state and checksum must survive closing/reopening or process restart.
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

# New update checks must never replace the checksum associated with an existing download.
assert 'startUpdateDownload(apkUrl, remoteVersion, sha)' in update_java
assert 'private void startUpdateDownload(String apkUrl, String version, String sha)' in update_java
check_start = update_java.index('private void checkForUpdateAutomatically()')
download_start = update_java.index('private void startUpdateDownload(')
resume_start = update_java.index('private boolean resumePendingUpdateIfAny()')
check_block = update_java[check_start:download_start]
download_block = update_java[download_start:resume_start]
assert 'expectedSha = sha;' not in check_block
assert 'savePendingDownloadState(id, sha);' in download_block
assert 'long id = dm.enqueue(request);' in download_block

# Download destination must be unique and APK-specific.
assert 'System.currentTimeMillis() + ".apk"' in update_java
assert 'application/vnd.android.package-archive' in update_java
assert 'VISIBILITY_VISIBLE_NOTIFY_COMPLETED' in update_java

# Real byte progress must be shown while downloading.
for required_progress in [
    'COLUMN_BYTES_DOWNLOADED_SO_FAR',
    'COLUMN_TOTAL_SIZE_BYTES',
    'refreshDownloadProgress()',
    'handler.postDelayed(this, 1000)',
    'progress.setProgress(p)',
    'percent.setText(p + "%")',
]:
    assert required_progress in update_java, required_progress

# Every completed APK must be SHA-256 checked before Android installer launch.
assert 'MessageDigest.getInstance("SHA-256")' in update_java
assert 'expectedSha.equalsIgnoreCase(sha256(uri))' in update_java
verify_pos = update_java.index('expectedSha.equalsIgnoreCase(sha256(uri))')
installer_pos = update_java.index('startActivity(install)')
assert verify_pos < installer_pos
assert 'Update blocked: SHA-256 verification failed' in update_java
assert 'FLAG_GRANT_READ_URI_PERMISSION' in update_java

# Android unknown-app install permission must be handled explicitly and must not discard a verified APK before permission is granted.
for required_permission_flow in [
    'canRequestPackageInstalls()',
    'Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES',
    'Uri.parse("package:" + getPackageName())',
    'INSTALL PERMISSION REQUIRED',
    'Allow from this source',
    'if (!canInstallPackages())',
    'openInstallPermissionSettings()',
    'if (downloadId != -1 && canInstallPackages() && isDownloadSuccessful())',
]:
    assert required_permission_flow in update_java, required_permission_flow
launch_start = update_java.index('private void launchInstaller(Uri uri)')
launch_end = update_java.index('private String sha256(Uri uri)')
launch_block = update_java[launch_start:launch_end]
permission_gate = launch_block.index('if (!canInstallPackages())')
clear_state = launch_block.index('clearPendingDownloadState();')
assert permission_gate < clear_state
assert 'openInstallPermissionSettings();\n            return;' in launch_block

# Required visible lifecycle states.
for required_status in [
    'CHECKING FOR UPDATE',
    'UP TO DATE',
    'UPDATE CHECK FAILED',
    'Update in progress — download already queued',
    'Update in progress — downloading Senton Link ',
    'Update in progress — verifying downloaded update…',
    'Update in progress — verified, opening Android installer…',
    'UPDATE DOWNLOAD FAILED',
    'UPDATE VERIFICATION FAILED',
    'INSTALL PERMISSION REQUIRED',
]:
    assert required_status in update_java, required_status

# Vehicle controls remain fail-closed and non-actuating in normal, launcher and test mode.
assert 'button("DRIVE", true)' not in main_java
assert 'button("DRIVE", false)' in main_java

# No direct shell/root/device-admin style execution should exist in this beta app.
for forbidden in [
    'Runtime.getRuntime().exec',
    'ProcessBuilder(',
    'su -c',
    'DevicePolicyManager',
]:
    assert forbidden not in main_java, forbidden
    assert forbidden not in update_java, forbidden

# Exact build identity gate.
version_name = re.search(r"versionName\s+'([^']+)'", gradle).group(1)
version_code = int(re.search(r"versionCode\s+(\d+)", gradle).group(1))
assert version_name == "2.3.4-beta", version_name
assert version_code == 2304, version_code

print("Senton Link 2.3.4 EXTREME static hard-test gates passed")
