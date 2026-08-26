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


def check_for_update(current_version):
    url = getattr(config, "UPDATE_MANIFEST_URL", "").strip()
    if not url:
        return {"ok": False, "reason": "Update server is not configured yet."}

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Senton-Control-Updater"})
        with urllib.request.urlopen(req, timeout=8) as response:
            manifest = json.loads(response.read().decode("utf-8-sig"))

        latest = str(manifest.get("version", "0.0.0"))
        return {
            "ok": True,
            "update_available": _version_tuple(latest) > _version_tuple(current_version),
            "latest_version": latest,
            "download_url": str(manifest.get("download_url", "")).strip(),
            "notes": str(manifest.get("notes", "")).strip(),
            "required": bool(manifest.get("required", False)),
        }
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}


def download_update(download_url):
    if not download_url.lower().startswith("https://"):
        raise ValueError("Update downloads must use HTTPS.")

    target = Path(tempfile.gettempdir()) / "Senton_Control_Update.exe"
    req = urllib.request.Request(download_url, headers={"User-Agent": "Senton-Control-Updater"})
    with urllib.request.urlopen(req, timeout=60) as response, open(target, "wb") as f:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)

    if not target.exists() or target.stat().st_size < 1024 * 1024:
        raise RuntimeError("Downloaded update file is missing or unexpectedly small.")
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
    """Close the running app, replace the Desktop EXE, then relaunch it.

    The previous EXE is kept as a rollback copy for 24 hours. If replacement
    fails, the previous EXE is restored and relaunched immediately.
    """
    downloaded_exe = Path(downloaded_exe)
    if not MAIN_INSTALL_DIR.exists():
        raise FileNotFoundError(f"Main Senton Control folder was not found: {MAIN_INSTALL_DIR}")
    if not downloaded_exe.exists():
        raise FileNotFoundError(f"Downloaded update was not found: {downloaded_exe}")

    MAIN_EXE.parent.mkdir(parents=True, exist_ok=True)
    bat_path = Path(tempfile.gettempdir()) / "senton_control_apply_update.bat"
    current_pid = os.getpid()

    commands = [
        "@echo off",
        "setlocal",
        "title Senton Control Updater",
        "echo Senton Control is closing for update...",
        ":wait_for_app_exit",
        f'tasklist /FI "PID eq {current_pid}" 2>NUL | find "{current_pid}" >NUL',
        "if not errorlevel 1 (",
        "  timeout /t 1 /nobreak >nul",
        "  goto wait_for_app_exit",
        ")",
        "echo Installing Senton Control update...",
        f'if exist "{BACKUP_EXE}" del /q "{BACKUP_EXE}"',
        f'if exist "{BACKUP_MARKER}" del /q "{BACKUP_MARKER}"',
        f'if exist "{MAIN_EXE}" copy /y "{MAIN_EXE}" "{BACKUP_EXE}" >nul',
        f'powershell -NoProfile -Command "[IO.File]::WriteAllText(\'{BACKUP_MARKER}\', [string]([DateTimeOffset]::UtcNow.ToUnixTimeSeconds()))"',
        f'copy /y "{downloaded_exe}" "{MAIN_EXE}" >nul',
        "if errorlevel 1 goto update_failed",
        f'if not exist "{MAIN_EXE}" goto update_failed',
        "echo Update complete. Relaunching Senton Control...",
        f'start "" "{MAIN_EXE}"',
        f'del /q "{downloaded_exe}" >nul 2>&1',
        'del "%~f0"',
        "exit /b 0",
        ":update_failed",
        "echo Senton Control update failed. Restoring previous version...",
        f'if exist "{BACKUP_EXE}" copy /y "{BACKUP_EXE}" "{MAIN_EXE}" >nul',
        f'if exist "{MAIN_EXE}" start "" "{MAIN_EXE}"',
        "pause",
        "exit /b 1",
    ]

    bat_path.write_text("\r\n".join(commands), encoding="utf-8")
    subprocess.Popen(
        ["cmd.exe", "/c", str(bat_path)],
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    return True
