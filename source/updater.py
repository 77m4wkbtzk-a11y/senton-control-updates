import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
import config

LEGACY_MAIN_EXE = Path(r"C:\Users\Admin\Desktop\senton_dashboard\dist\Senton Control.exe")
BACKUP_RETENTION_SECONDS = 24 * 60 * 60


def _version_tuple(version):
    try:
        return tuple(int(part) for part in version.strip().split("."))
    except Exception:
        return (0,)


def _cache_busted_url(url):
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    query.append(("senton_ts", str(int(time.time() * 1000))))
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(query), parts.fragment))


def _fetch_manifest(url):
    req = urllib.request.Request(
        _cache_busted_url(url),
        headers={
            "User-Agent": "Senton-Control-Updater",
            "Cache-Control": "no-cache, no-store, max-age=0",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=8) as response:
        return json.loads(response.read().decode("utf-8-sig"))


def _normalize_sha256(value):
    value = str(value or "").strip().lower()
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        return ""
    return value


def verify_file_sha256(path, expected_sha256):
    expected = _normalize_sha256(expected_sha256)
    if not expected:
        raise ValueError("Update is missing a valid SHA-256 integrity value.")

    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            digest.update(chunk)

    if digest.hexdigest().lower() != expected:
        raise RuntimeError("Update integrity check failed. Installation blocked.")
    return True


def check_for_update(current_version):
    url = getattr(config, "UPDATE_MANIFEST_URL", "").strip()
    if not url:
        return {"ok": False, "reason": "Update server is not configured yet."}

    try:
        manifest = _fetch_manifest(url)
        latest = str(manifest.get("version", "0.0.0"))
        return {
            "ok": True,
            "update_available": _version_tuple(latest) > _version_tuple(current_version),
            "latest_version": latest,
            "download_url": str(manifest.get("download_url", "")).strip(),
            "notes": str(manifest.get("notes", "")).strip(),
            "required": bool(manifest.get("required", False)),
            "sha256": str(manifest.get("sha256", "")).strip().lower(),
            "channel": str(manifest.get("channel", "public")).strip().lower(),
        }
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}


def download_update(download_url, expected_sha256=""):
    if not download_url.lower().startswith("https://"):
        raise ValueError("Update downloads must use HTTPS.")

    expected = ""
    if expected_sha256:
        expected = _normalize_sha256(expected_sha256)
        if not expected:
            raise ValueError("Update is missing a valid SHA-256 integrity value.")
    else:
        manifest_url = getattr(config, "UPDATE_MANIFEST_URL", "").strip()
        if not manifest_url:
            raise RuntimeError("Cannot verify update because the update manifest is not configured.")
        manifest = _fetch_manifest(manifest_url)
        manifest_download_url = str(manifest.get("download_url", "")).strip()
        if manifest_download_url != download_url:
            raise RuntimeError("Update download does not match the current verified manifest.")
        expected = _normalize_sha256(manifest.get("sha256", ""))
        if not expected:
            raise RuntimeError("Update manifest is missing a valid SHA-256 integrity value.")

    target = Path(tempfile.gettempdir()) / "Senton_Control_Update.exe"
    req = urllib.request.Request(
        _cache_busted_url(download_url),
        headers={"User-Agent": "Senton-Control-Updater", "Cache-Control": "no-cache"},
    )
    with urllib.request.urlopen(req, timeout=45) as response, open(target, "wb") as f:
        while True:
            chunk = response.read(4 * 1024 * 1024)
            if not chunk:
                break
            f.write(chunk)

    if not target.exists() or target.stat().st_size < 1024 * 1024:
        target.unlink(missing_ok=True)
        raise RuntimeError("Downloaded update file is missing or unexpectedly small.")

    try:
        verify_file_sha256(target, expected)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target


def _current_app_exe():
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        if exe.exists():
            return exe
    if LEGACY_MAIN_EXE.exists():
        return LEGACY_MAIN_EXE
    raise FileNotFoundError("Could not locate the running Senton Control executable.")


def _backup_paths(main_exe):
    return (
        main_exe.with_name("Senton Control.backup.exe"),
        main_exe.with_name("Senton Control.backup.timestamp"),
    )


def cleanup_expired_backup():
    try:
        main_exe = _current_app_exe()
        backup_exe, backup_marker = _backup_paths(main_exe)
        if not backup_exe.exists():
            backup_marker.unlink(missing_ok=True)
            return False

        if backup_marker.exists():
            created = float(backup_marker.read_text(encoding="utf-8").strip())
        else:
            created = backup_exe.stat().st_mtime

        if time.time() - created >= BACKUP_RETENTION_SECONDS:
            backup_exe.unlink(missing_ok=True)
            backup_marker.unlink(missing_ok=True)
            return True
    except Exception:
        pass
    return False


def install_update_to_main_desktop(downloaded_exe):
    """Replace the exact running Senton Control EXE using a fast detached helper."""
    downloaded_exe = Path(downloaded_exe)
    if not downloaded_exe.exists():
        raise FileNotFoundError(f"Downloaded update was not found: {downloaded_exe}")

    main_exe = _current_app_exe()
    backup_exe, backup_marker = _backup_paths(main_exe)
    main_exe.parent.mkdir(parents=True, exist_ok=True)

    bat_path = Path(tempfile.gettempdir()) / "senton_control_apply_update.bat"
    current_pid = os.getpid()

    commands = [
        "@echo off",
        "setlocal EnableExtensions",
        "title Senton Control Updater",
        "echo Installing Senton Control update...",
        "",
        "rem Short grace period, then close only the current Senton process.",
        "timeout /t 1 /nobreak >nul",
        f'tasklist /FI "PID eq {current_pid}" 2>NUL | find "{current_pid}" >NUL',
        "if not errorlevel 1 (",
        f'  taskkill /PID {current_pid} /T /F >nul 2>&1',
        ")",
        "",
        "rem Give Windows one moment to release the executable handle.",
        "timeout /t 1 /nobreak >nul",
        f'if exist "{backup_exe}" del /q "{backup_exe}" >nul 2>&1',
        f'if exist "{backup_marker}" del /q "{backup_marker}" >nul 2>&1',
        f'if exist "{main_exe}" copy /y "{main_exe}" "{backup_exe}" >nul',
        "if errorlevel 1 goto update_failed",
        f'powershell -NoProfile -Command "[IO.File]::WriteAllText(\'{backup_marker}\', [string]([DateTimeOffset]::UtcNow.ToUnixTimeSeconds()))"',
        "",
        "set RETRIES=0",
        ":replace_retry",
        f'copy /y "{downloaded_exe}" "{main_exe}" >nul 2>&1',
        "if not errorlevel 1 goto replace_ok",
        "set /a RETRIES+=1",
        "if %RETRIES% GEQ 8 goto update_failed",
        "timeout /t 1 /nobreak >nul",
        "goto replace_retry",
        "",
        ":replace_ok",
        f'if not exist "{main_exe}" goto update_failed',
        f'for %%I in ("{main_exe}") do if %%~zI LSS 1048576 goto update_failed',
        f'start "" explorer.exe "{main_exe}"',
        f'del /q "{downloaded_exe}" >nul 2>&1',
        'del "%~f0"',
        "exit /b 0",
        "",
        ":update_failed",
        "echo Senton Control update failed. Restoring previous version...",
        f'if exist "{backup_exe}" copy /y "{backup_exe}" "{main_exe}" >nul 2>&1',
        f'if exist "{main_exe}" start "" explorer.exe "{main_exe}"',
        "pause",
        "exit /b 1",
    ]

    bat_path.write_text("\r\n".join(commands), encoding="utf-8")
    subprocess.Popen(
        ["cmd.exe", "/c", str(bat_path)],
        creationflags=(
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
        ),
        close_fds=True,
    )
    return True
