#!/usr/bin/env bash
set -euo pipefail

APK="${1:-phone-app/app/build/outputs/apk/debug/app-debug.apk}"
PKG="com.senton.link"
MAIN="com.senton.link/.MainActivity"
UPDATE="com.senton.link/.UpdateProgressActivity"
TMP="${RUNNER_TEMP:-/tmp}/senton-link-emulator-test"
mkdir -p "$TMP"

die() {
  echo "SENTON EMULATOR HARD TEST FAILED: $*" >&2
  exit 1
}

wait_boot() {
  adb wait-for-device
  timeout 180 bash -c 'until [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d "\r")" = "1" ]; do sleep 2; done'
}

dump_ui() {
  adb shell uiautomator dump /sdcard/senton-window.xml >/dev/null
  adb pull /sdcard/senton-window.xml "$TMP/window.xml" >/dev/null
}

require_text() {
  local value="$1"
  dump_ui
  grep -Fq "$value" "$TMP/window.xml" || die "UI text missing: $value"
}

forbid_text() {
  local value="$1"
  dump_ui
  if grep -Fq "$value" "$TMP/window.xml"; then
    die "Unexpected UI text present: $value"
  fi
}

require_disabled_button() {
  local label="$1"
  dump_ui
  python3 - "$TMP/window.xml" "$label" <<'PY'
import sys
import xml.etree.ElementTree as ET
path, label = sys.argv[1:]
root = ET.parse(path).getroot()
for node in root.iter('node'):
    if node.attrib.get('text') == label:
        if node.attrib.get('enabled') != 'false':
            raise SystemExit(f'{label} unexpectedly enabled')
        raise SystemExit(0)
raise SystemExit(f'{label} button missing')
PY
}

require_safe_dashboard() {
  require_text "SENTON PI DISCONNECTED — SAFE MODE"
  require_text "Safety mode     Active"
  require_disabled_button "DRIVE"
  require_disabled_button "START CHARGE"
  require_disabled_button "STOP CHARGE"
}

require_test_banner() {
  require_text "UNDER TESTING"
  require_text "TEMPORARY HARD-TEST SESSION"
  require_text "VEHICLE CONTROLS LOCKED"
}

require_keep_screen_on() {
  adb shell dumpsys window > "$TMP/window-dump.txt"
  grep -Eq 'mHoldScreenWindow=.*com\.senton\.link|KEEP_SCREEN_ON.*com\.senton\.link' "$TMP/window-dump.txt" \
    || die "Test Mode did not request keep-screen-on while foregrounded"
}

require_keep_screen_released() {
  adb shell dumpsys window > "$TMP/window-dump.txt"
  if grep -Eq 'mHoldScreenWindow=.*com\.senton\.link|KEEP_SCREEN_ON.*com\.senton\.link' "$TMP/window-dump.txt"; then
    die "Senton Link retained keep-screen-on while backgrounded"
  fi
}

start_normal() {
  adb shell am start -W -n "$MAIN" >/dev/null
}

start_test_mode() {
  adb shell am start -W -n "$MAIN" --ez senton_test_mode true >/dev/null
}

wait_boot
[ -s "$APK" ] || die "APK missing: $APK"
adb install -r -t "$APK" >/dev/null
adb shell pm clear "$PKG" >/dev/null

# The app must be a valid HOME target, but this emulator test does not need to
# change the user's real phone launcher/default-app settings.
adb shell cmd package query-activities -a android.intent.action.MAIN -c android.intent.category.HOME > "$TMP/home.txt"
grep -Fq "$PKG" "$TMP/home.txt" || die "Senton Link is not registered as a HOME activity"

# Repeated force-stop/cold-start/rapid relaunch cycles must always return to a
# fail-closed dashboard with all vehicle/charge controls disabled.
for _ in $(seq 1 20); do
  adb shell am force-stop "$PKG"
  start_normal
  require_safe_dashboard
  forbid_text "UNDER TESTING"
  adb shell am start -W -n "$MAIN" >/dev/null
  require_safe_dashboard
done

# Explicit Test Mode must visibly warn, remain fail-closed, and request screen
# wake only while the Activity is actually in the foreground.
adb shell am force-stop "$PKG"
start_test_mode
require_safe_dashboard
require_test_banner
require_keep_screen_on

# Exercise repeated foreground/background transitions without creating a new
# Activity. REORDER_TO_FRONT brings the same Test Mode instance back.
for _ in $(seq 1 10); do
  adb shell input keyevent KEYCODE_HOME
  sleep 0.25
  require_keep_screen_released
  adb shell am start -W --activity-reorder-to-front -n "$MAIN" >/dev/null
  require_test_banner
  require_safe_dashboard
  require_keep_screen_on
done

# A force-stop ends the temporary Test Mode session. A normal cold start must
# still be Safe Mode, but must not falsely claim it is under test.
adb shell am force-stop "$PKG"
start_normal
require_safe_dashboard
forbid_text "UNDER TESTING"

# Exercise updater failure/retry behavior on the emulator by forcing the
# Android global HTTP proxy to an unreachable local endpoint. This contains
# network disruption to the disposable emulator only.
adb shell settings put global http_proxy 127.0.0.1:9
adb shell am force-stop "$PKG"
adb shell am start -W -n "$UPDATE" >/dev/null || true
sleep 12
require_text "UPDATE CHECK FAILED"

# Restore network routing and rapidly relaunch/retry the updater. Regardless of
# remote availability/version, the app must stay alive and return to a defined
# updater state instead of crashing or enabling vehicle controls.
adb shell settings put global http_proxy :0
for _ in $(seq 1 5); do
  adb shell am force-stop "$PKG"
  adb shell am start -W -n "$UPDATE" >/dev/null || true
  sleep 1
  adb shell pidof "$PKG" >/dev/null || die "Updater process died during retry cycle"
done

# Final cold start after network restoration must always be fail-closed.
adb shell am force-stop "$PKG"
start_normal
require_safe_dashboard

# Scan app process crashes/ANRs from this isolated emulator run.
adb shell dumpsys activity processes > "$TMP/activity-processes.txt" || true
adb logcat -d -v brief > "$TMP/logcat.txt"
if grep -E 'FATAL EXCEPTION:.*|ANR in com\.senton\.link|Process: com\.senton\.link.*FATAL' "$TMP/logcat.txt"; then
  die "Crash/ANR signature found in emulator logcat"
fi

echo "Senton Link Android EMULATOR hard test passed: 20 cold starts, rapid relaunches, 10 background/foreground cycles, Test Mode warning/keep-screen-on checks, updater network-loss/retry cycles, and fail-closed controls"
