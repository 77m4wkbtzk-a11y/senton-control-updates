#!/usr/bin/env bash
set -euo pipefail

APK="${1:-phone-app/app/build/outputs/apk/debug/app-debug.apk}"
PKG="com.senton.link"
MAIN="com.senton.link/.MainActivity"
TMP="${RUNNER_TEMP:-/tmp}/senton-link-emulator-test"
mkdir -p "$TMP"

diagnostics() {
  echo "--- Senton emulator diagnostics ---" >&2
  adb shell dumpsys activity activities > "$TMP/activity-dump.txt" 2>&1 || true
  adb shell dumpsys window > "$TMP/window-dump.txt" 2>&1 || true
  adb exec-out screencap -p > "$TMP/screenshot.png" 2>/dev/null || true
  if [ -s "$TMP/window.xml" ]; then
    cat "$TMP/window.xml" >&2 || true
  fi
  echo "--- top resumed activity ---" >&2
  grep -E 'mResumedActivity|topResumedActivity|ResumedActivity' "$TMP/activity-dump.txt" >&2 || true
  echo "--- end diagnostics ---" >&2
}

die() {
  echo "SENTON EMULATOR HARD TEST FAILED: $*" >&2
  diagnostics
  exit 1
}

wait_boot() {
  adb wait-for-device
  timeout 180 bash -c 'until [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d "\r")" = "1" ]; do sleep 2; done'
}

dump_ui() {
  local attempt
  for attempt in 1 2 3; do
    if adb shell uiautomator dump --compressed /sdcard/senton-window.xml >/dev/null 2>&1 \
      && adb pull /sdcard/senton-window.xml "$TMP/window.xml" >/dev/null 2>&1 \
      && [ -s "$TMP/window.xml" ]; then
      return 0
    fi
    sleep 0.25
  done
  return 1
}

ui_has_text() {
  local value="$1"
  dump_ui || return 1
  grep -Fq -- "$value" "$TMP/window.xml"
}

scroll_to_top() {
  local _
  for _ in 1 2 3 4 5; do
    adb shell input swipe 540 500 540 1500 100 >/dev/null 2>&1 || true
  done
  sleep 0.15
}

scroll_forward() {
  adb shell input swipe 540 1500 540 500 140 >/dev/null 2>&1 || true
  sleep 0.12
}

require_text_current() {
  local value="$1"
  local _
  for _ in $(seq 1 20); do
    if ui_has_text "$value"; then
      return 0
    fi
    sleep 0.25
  done
  die "UI text missing from current viewport: $value"
}

require_text_anywhere() {
  local value="$1"
  local pass
  scroll_to_top
  for pass in $(seq 1 10); do
    if ui_has_text "$value"; then
      scroll_to_top
      return 0
    fi
    scroll_forward
  done
  scroll_to_top
  die "UI text missing after scrolling dashboard: $value"
}

forbid_text_current() {
  local value="$1"
  dump_ui || die "Unable to dump UI while checking forbidden text: $value"
  if grep -Fq -- "$value" "$TMP/window.xml"; then
    die "Unexpected UI text present: $value"
  fi
}

button_state_in_view() {
  local label="$1"
  dump_ui || return 3
  python3 - "$TMP/window.xml" "$label" <<'PY'
import sys
import xml.etree.ElementTree as ET
path, label = sys.argv[1:]
root = ET.parse(path).getroot()
for node in root.iter('node'):
    if node.attrib.get('text') == label:
        if node.attrib.get('enabled') == 'false':
            raise SystemExit(0)
        raise SystemExit(2)
raise SystemExit(3)
PY
}

require_disabled_button_anywhere() {
  local label="$1"
  local pass rc
  scroll_to_top
  for pass in $(seq 1 10); do
    if button_state_in_view "$label"; then
      scroll_to_top
      return 0
    else
      rc=$?
      if [ "$rc" -eq 2 ]; then
        scroll_to_top
        die "$label unexpectedly enabled"
      fi
    fi
    scroll_forward
  done
  scroll_to_top
  die "$label button missing after scrolling dashboard"
}

control_xy_in_view() {
  local label="$1"
  dump_ui || return 1
  python3 - "$TMP/window.xml" "$label" <<'PY'
import re
import sys
import xml.etree.ElementTree as ET
path, label = sys.argv[1:]
root = ET.parse(path).getroot()
for node in root.iter('node'):
    if node.attrib.get('text') == label:
        m = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.attrib.get('bounds', ''))
        if not m:
            raise SystemExit(1)
        x1, y1, x2, y2 = map(int, m.groups())
        print((x1 + x2) // 2, (y1 + y2) // 2)
        raise SystemExit(0)
raise SystemExit(1)
PY
}

dismiss_android_immersive_cling() {
  local xy
  # Fresh Android emulators display a system-owned "Viewing full screen" education
  # overlay the first time an app enters immersive mode. It is not Senton UI and
  # otherwise masks the dashboard from UIAutomator, so dismiss it on this disposable VM.
  for _ in $(seq 1 8); do
    if xy=$(control_xy_in_view "Got it"); then
      adb shell input tap $xy >/dev/null 2>&1 || true
      sleep 0.25
      continue
    fi
    return 0
  done
  die "Android immersive-mode education overlay could not be dismissed"
}

tap_text_anywhere() {
  local label="$1"
  local pass xy
  scroll_to_top
  for pass in $(seq 1 10); do
    if xy=$(control_xy_in_view "$label"); then
      adb shell input tap $xy
      sleep 0.15
      return 0
    fi
    scroll_forward
  done
  die "$label control missing after scrolling"
}

require_safe_dashboard() {
  # Wait for the freshly launched Activity to finish rendering before testing it.
  dismiss_android_immersive_cling
  scroll_to_top
  require_text_current "SENTON PI DISCONNECTED"
  require_text_current "SAFE MODE"
  require_text_current "VEHICLE CONTROLS LOCKED"
  require_text_anywhere "Safety mode     Active"
  require_disabled_button_anywhere "DRIVE"
  require_disabled_button_anywhere "START CHARGE"
  require_disabled_button_anywhere "STOP CHARGE"
  scroll_to_top
}

require_test_banner() {
  dismiss_android_immersive_cling
  scroll_to_top
  require_text_current "UNDER TESTING"
  require_text_anywhere "TEMPORARY HARD-TEST SESSION"
  require_text_anywhere "VEHICLE CONTROLS LOCKED"
  scroll_to_top
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
  dismiss_android_immersive_cling
}

start_test_mode() {
  adb shell am start -W -n "$MAIN" --ez senton_test_mode true >/dev/null
  dismiss_android_immersive_cling
}

wait_boot
[ -s "$APK" ] || die "APK missing: $APK"
adb install -r -t "$APK" >/dev/null
adb shell pm clear "$PKG" >/dev/null
adb logcat -c

# The app must be a valid HOME target, but this emulator test does not change
# any launcher/default-app setting on the user's physical phone.
adb shell cmd package query-activities -a android.intent.action.MAIN -c android.intent.category.HOME > "$TMP/home.txt"
grep -Fq "$PKG" "$TMP/home.txt" || die "Senton Link is not registered as a HOME activity"

# Repeated force-stop/cold-start/rapid relaunch cycles must always return to a
# fail-closed dashboard with all vehicle/charge controls disabled.
for _ in $(seq 1 20); do
  adb shell am force-stop "$PKG"
  start_normal
  require_safe_dashboard
  forbid_text_current "UNDER TESTING"
  adb shell am start -W -n "$MAIN" >/dev/null
  dismiss_android_immersive_cling
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
  dismiss_android_immersive_cling
  require_test_banner
  require_safe_dashboard
  require_keep_screen_on
done

# A force-stop ends the temporary Test Mode session. A normal cold start must
# still be Safe Mode, but must not falsely claim it is under test.
adb shell am force-stop "$PKG"
start_normal
require_safe_dashboard
forbid_text_current "UNDER TESTING"

# Exercise updater failure/retry behavior by routing only the disposable
# emulator through an unreachable proxy. Open UPDATE through the real app UI so
# the non-exported update Activity is tested the same way a user reaches it.
adb shell settings put global http_proxy 127.0.0.1:9
tap_text_anywhere "UPDATE"
sleep 12
require_text_anywhere "UPDATE CHECK FAILED"

# Repeated taps must not crash or create overlapping unsafe UI state.
for _ in $(seq 1 8); do
  tap_text_anywhere "CHECK FOR UPDATE"
done
sleep 1
adb shell pidof "$PKG" >/dev/null || die "Updater process died during failed retry burst"

# Restore emulator networking and retry repeatedly. The remote channel may say
# up-to-date, may expose a newer build, or may be temporarily unavailable; none
# of those outcomes may crash the app or change fail-closed vehicle controls.
adb shell settings put global http_proxy :0
for _ in $(seq 1 8); do
  tap_text_anywhere "CHECK FOR UPDATE"
done
sleep 12
adb shell pidof "$PKG" >/dev/null || die "Updater process died after network restoration"

# Close updater through its real UI and verify the dashboard is still locked.
tap_text_anywhere "BACK TO DASHBOARD"
sleep 0.5
require_safe_dashboard

# Final cold start after network restoration must always be fail-closed.
adb shell am force-stop "$PKG"
start_normal
require_safe_dashboard

# Scan app-process crashes/ANRs from this isolated emulator run.
adb logcat -d -v brief > "$TMP/logcat.txt"
if grep -E 'FATAL EXCEPTION:.*|ANR in com\.senton\.link|Process: com\.senton\.link.*FATAL' "$TMP/logcat.txt"; then
  die "Crash/ANR signature found in emulator logcat"
fi

echo "Senton Link Android EMULATOR hard test passed: 20 cold starts, rapid relaunches, 10 background/foreground cycles, Test Mode warning/keep-screen-on checks, updater network-loss/retry bursts, and fail-closed controls"
