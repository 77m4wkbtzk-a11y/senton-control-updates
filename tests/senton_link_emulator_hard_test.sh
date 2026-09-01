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
    dismiss_unrelated_system_dialogs
    dismiss_android_immersive_cling
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
  dismiss_unrelated_system_dialogs
  dismiss_android_immersive_cling
  scroll_to_top
  for pass in $(seq 1 10); do
    dismiss_unrelated_system_dialogs
    if ui_has_text "$value"; then
      scroll_to_top
      return 0
    fi
    scroll_forward
  done
  scroll_to_top
  die "UI text missing after scrolling dashboard: $value"
}

wait_for_text_current() {
  local value="$1"
  local seconds="${2:-25}"
  local _
  scroll_to_top
  for _ in $(seq 1 "$seconds"); do
    dismiss_unrelated_system_dialogs
    dismiss_android_immersive_cling
    if ui_has_text "$value"; then
      return 0
    fi
    sleep 1
  done
  die "Timed out waiting for UI text: $value"
}

forbid_text_current() {
  local value="$1"
  dismiss_unrelated_system_dialogs
  dismiss_android_immersive_cling
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
  dismiss_unrelated_system_dialogs
  dismiss_android_immersive_cling
  scroll_to_top
  for pass in $(seq 1 10); do
    dismiss_unrelated_system_dialogs
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

dismiss_unrelated_system_dialogs() {
  local xy
  dump_ui || return 0

  # Never hide an app failure. A Senton ANR is a real test failure and must stop CI.
  if grep -Fq "Senton Link isn't responding" "$TMP/window.xml"; then
    die "Senton Link ANR dialog detected"
  fi

  # Disposable Android images can occasionally surface launcher/System UI ANRs while
  # the Senton activity underneath is healthy. Close only those unrelated system
  # dialogs so they cannot mask the app from UIAutomator.
  if grep -Fq "isn't responding" "$TMP/window.xml"; then
    if xy=$(control_xy_in_view "Close app"); then
      adb shell input tap $xy >/dev/null 2>&1 || true
      sleep 0.35
      return 0
    fi
  fi
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
  dismiss_unrelated_system_dialogs
  dismiss_android_immersive_cling
  scroll_to_top
  for pass in $(seq 1 10); do
    dismiss_unrelated_system_dialogs
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
  # Normal mode proves fail-closed behavior by state and the actual DRIVE control.
  # Solar charging was intentionally removed, so runtime must also prove those old
  # controls do not reappear. The explicit VEHICLE CONTROLS LOCKED warning is a
  # Test Mode requirement and is checked separately in require_test_banner().
  dismiss_unrelated_system_dialogs
  dismiss_android_immersive_cling
  scroll_to_top
  require_text_current "SENTON PI DISCONNECTED"
  require_text_current "SAFE MODE"
  require_text_anywhere "Safety mode     Active"
  require_disabled_button_anywhere "DRIVE"
  forbid_text_current "START CHARGE"
  forbid_text_current "STOP CHARGE"
  scroll_to_top
}

require_test_banner() {
  dismiss_unrelated_system_dialogs
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
  dismiss_unrelated_system_dialogs
  dismiss_android_immersive_cling
}

start_test_mode() {
  adb shell am start -W -n "$MAIN" --ez senton_test_mode true >/dev/null
  dismiss_unrelated_system_dialogs
  dismiss_android_immersive_cling
}

emulator_network_off() {
  # Use multiple emulator-only controls. The loopback proxy is the deterministic
  # application-level block; radio/airplane toggles additionally exercise Android's
  # connectivity-loss lifecycle without touching any physical device.
  adb shell settings put global http_proxy 127.0.0.1:9
  adb shell svc wifi disable >/dev/null 2>&1 || true
  adb shell svc data disable >/dev/null 2>&1 || true
  adb shell cmd connectivity airplane-mode enable >/dev/null 2>&1 || {
    adb shell settings put global airplane_mode_on 1 >/dev/null 2>&1 || true
    adb shell am broadcast -a android.intent.action.AIRPLANE_MODE --ez state true >/dev/null 2>&1 || true
  }
  sleep 2
  local proxy
  proxy=$(adb shell settings get global http_proxy 2>/dev/null | tr -d '\r')
  [ "$proxy" = "127.0.0.1:9" ] || die "Disposable emulator did not apply the offline proxy"
}

emulator_network_restore() {
  adb shell settings put global http_proxy :0 >/dev/null 2>&1 || true
  adb shell cmd connectivity airplane-mode disable >/dev/null 2>&1 || {
    adb shell settings put global airplane_mode_on 0 >/dev/null 2>&1 || true
    adb shell am broadcast -a android.intent.action.AIRPLANE_MODE --ez state false >/dev/null 2>&1 || true
  }
  adb shell svc wifi enable >/dev/null 2>&1 || true
  adb shell svc data enable >/dev/null 2>&1 || true
  sleep 3
  local proxy
  proxy=$(adb shell settings get global http_proxy 2>/dev/null | tr -d '\r')
  case "$proxy" in
    ""|":0"|"null") ;;
    *) die "Disposable emulator proxy did not clear after network restoration: $proxy" ;;
  esac
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
# fail-closed dashboard with DRIVE disabled and removed solar controls absent.
for _ in $(seq 1 20); do
  adb shell am force-stop "$PKG"
  start_normal
  require_safe_dashboard
  forbid_text_current "UNDER TESTING"
  adb shell am start -W -n "$MAIN" >/dev/null
  dismiss_unrelated_system_dialogs
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
# Senton Activity. Use Android Settings as the temporary foreground activity so
# the lifecycle test does not depend on Pixel Launcher health on the disposable VM.
for _ in $(seq 1 10); do
  adb shell am start -W -a android.settings.SETTINGS >/dev/null
  sleep 0.25
  require_keep_screen_released
  adb shell am start -W --activity-reorder-to-front -n "$MAIN" >/dev/null
  dismiss_unrelated_system_dialogs
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

# Exercise a real connectivity-loss transition on the disposable emulator and
# independently force app HTTP through an unreachable loopback proxy. The prior
# test changed only the proxy and immediately opened the updater; Android could
# race the proxy observer and complete the request online, producing a false test
# failure. Here the connectivity state is settled before opening UPDATE, and the
# updater must fail closed within its bounded 10s connect/read timeouts.
emulator_network_off
tap_text_anywhere "UPDATE"
wait_for_text_current "UPDATE CHECK FAILED" 25

# Repeated taps must not crash or create overlapping unsafe UI state.
for _ in $(seq 1 8); do
  tap_text_anywhere "CHECK FOR UPDATE"
done
sleep 1
adb shell pidof "$PKG" >/dev/null || die "Updater process died during failed retry burst"

# Restore emulator networking and retry repeatedly. The remote channel may say
# up-to-date, may expose a newer build, or may be temporarily unavailable; none
# of those outcomes may crash the app or change fail-closed vehicle controls.
emulator_network_restore
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

# Scan only Senton Link crash/ANR records. System-app crashes on disposable
# emulator images must not be mistaken for Senton failures.
adb logcat -d -v brief > "$TMP/logcat.txt"
python3 - "$TMP/logcat.txt" <<'PY'
import sys
from pathlib import Path
lines = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines()
for i, line in enumerate(lines):
    if "ANR in com.senton.link" in line:
        raise SystemExit("Senton Link ANR found in logcat")
    if "FATAL EXCEPTION" in line:
        window = "\n".join(lines[i:i + 10])
        if "Process: com.senton.link" in window:
            raise SystemExit("Senton Link fatal exception found in logcat")
PY

echo "Senton Link Android EMULATOR hard test passed: 20 cold starts, rapid relaunches, 10 background/foreground cycles, Test Mode warning/keep-screen-on checks, updater network-loss/retry bursts, removed-solar-control checks, and fail-closed controls"