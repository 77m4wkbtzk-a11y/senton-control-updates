import hashlib
import json
import os
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
import config

MAIN_INSTALL_DIR = Path(r"C:\Users\Admin\Desktop\senton_dashboard")
MAIN_EXE = MAIN_INSTALL_DIR / "dist" / "Senton Control.exe"
BACKUP_EXE = MAIN_INSTALL_DIR / "dist" / "Senton Control.backup.exe"
BACKUP_MARKER = MAIN_INSTALL_DIR / "dist" / "Senton Control.backup.timestamp"
BACKUP_RETENTION_SECONDS = 24 * 60 * 60


def _version_tuple(version):
    try:
        return tuple(int(part) for part in version.strip().split("."))
    except Exception:
        return (0,)


def _fetch_manifest(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Senton-Control-Updater"})
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
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
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
    req = urllib.request.Request(download_url, headers={"User-Agent": "Senton-Control-Updater"})
    with urllib.request.urlopen(req, timeout=60) as response, open(target, "wb") as f:
        while True:
            chunk = response.read(1024 * 1024)
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


def cleanup_expired_backup():
    """Keep the previous EXE for one day, then remove it on a later app start."""
    try:
        if not BACKUP_EXE.exists():
            if BACKUP_MARKER.exists():
                BACKUP_MARKER.unlink(missing_ok=True)
            return False

        if BACKUP_MARKER.exists():
            created = float(BACKUP_MARKER.read_text(encoding="utf-8").strip())
        else:
            created = BACKUP_EXE.stat().st_mtime

        if time.time() - created >= BACKUP_RETENTION_SECONDS:
            BACKUP_EXE.unlink(missing_ok=True)
            BACKUP_MARKER.unlink(missing_ok=True)
            return True
    except Exception:
        pass
    return False


def install_update_to_main_desktop(downloaded_exe):
    """Apply an update after Senton Control fully releases its EXE.

    The helper waits for every Senton Control.exe process to close, adds a
    short Windows file-release delay, retries locked-file replacement, keeps
    a 24-hour rollback copy, and relaunches through Explorer.
    """
    downloaded_exe = Path(downloaded_exe)
    if not MAIN_INSTALL_DIR.exists():
        raise FileNotFoundError(f"Main Senton Control folder was not found: {MAIN_INSTALL_DIR}")
    if not downloaded_exe.exists():
        raise FileNotFoundError(f"Downloaded update was not found: {downloaded_exe}")

    MAIN_EXE.parent.mkdir(parents=True, exist_ok=True)
    bat_path = Path(tempfile.gettempdir()) / "senton_control_apply_update.bat"

    commands = [
        "@echo off",
        "setlocal EnableExtensions",
        "title Senton Control Updater",
        "echo Senton Control is closing for update...",
        "",
        ":wait_for_all_senton",
        'tasklist /FI "IMAGENAME eq Senton Control.exe" 2>NUL | find /I "Senton Control.exe" >NUL',
        "if not errorlevel 1 (",
        "  timeout /t 1 /nobreak >nul",
        "  goto wait_for_all_senton",
        ")",
        "",
        "rem Give Windows/antivirus time to release the executable handle.",
        "timeout /t 3 /nobreak >nul",
        "echo Installing Senton Control update...",
        "",
        f'if exist "{BACKUP_EXE}" del /q "{BACKUP_EXE}" >nul 2>&1',
        f'if exist "{BACKUP_MARKER}" del /q "{BACKUP_MARKER}" >nul 2>&1',
        f'if exist "{MAIN_EXE}" copy /y "{MAIN_EXE}" "{BACKUP_EXE}" >nul',
        "if errorlevel 1 goto update_failed",
        f'powershell -NoProfile -Command "[IO.File]::WriteAllText(\'{BACKUP_MARKER}\', [string]([DateTimeOffset]::UtcNow.ToUnixTimeSeconds()))"',
        "",
        "set RETRIES=0",
        ":replace_retry",
        f'copy /y "{downloaded_exe}" "{MAIN_EXE}" >nul 2>&1',
        "if not errorlevel 1 goto replace_ok",
        "set /a RETRIES+=1",
        "if %RETRIES% GEQ 12 goto update_failed",
        "echo Update file is still locked. Retrying... (%RETRIES%/12)",
        "timeout /t 2 /nobreak >nul",
        "goto replace_retry",
        "",
        ":replace_ok",
        f'if not exist "{MAIN_EXE}" goto update_failed',
        f'for %%I in ("{MAIN_EXE}") do if %%~zI LSS 1048576 goto update_failed',
        "echo Update complete. Relaunching Senton Control...",
        "timeout /t 2 /nobreak >nul",
        f'start "" explorer.exe "{MAIN_EXE}"',
        f'del /q "{downloaded_exe}" >nul 2>&1',
        'del "%~f0"',
        "exit /b 0",
        "",
        ":update_failed",
        "echo Senton Control update failed. Restoring previous version...",
        f'if exist "{BACKUP_EXE}" copy /y "{BACKUP_EXE}" "{MAIN_EXE}" >nul 2>&1',
        "timeout /t 2 /nobreak >nul",
        f'if exist "{MAIN_EXE}" start "" explorer.exe "{MAIN_EXE}"',
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
