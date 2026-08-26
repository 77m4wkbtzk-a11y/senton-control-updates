import json
import subprocess
import tempfile
import urllib.request
from pathlib import Path
import config

MAIN_INSTALL_DIR = Path(r"C:\Users\Admin\Desktop\senton_dashboard")
MAIN_EXE = MAIN_INSTALL_DIR / "dist" / "Senton Control.exe"
BACKUP_EXE = MAIN_INSTALL_DIR / "dist" / "Senton Control.backup.exe"

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
            manifest = json.loads(response.read().decode("utf-8"))

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
    return target

def install_update_to_main_desktop(downloaded_exe):
    downloaded_exe = Path(downloaded_exe)
    if not MAIN_INSTALL_DIR.exists():
        raise FileNotFoundError(f"Main Senton Control folder was not found: {MAIN_INSTALL_DIR}")

    MAIN_EXE.parent.mkdir(parents=True, exist_ok=True)
    bat_path = Path(tempfile.gettempdir()) / "senton_control_apply_update.bat"

    commands = [
        "@echo off",
        "timeout /t 2 /nobreak >nul",
        f'if exist "{BACKUP_EXE}" del /q "{BACKUP_EXE}"',
        f'if exist "{MAIN_EXE}" copy /y "{MAIN_EXE}" "{BACKUP_EXE}" >nul',
        f'copy /y "{downloaded_exe}" "{MAIN_EXE}" >nul',
        "if errorlevel 1 (",
        f'  if exist "{BACKUP_EXE}" copy /y "{BACKUP_EXE}" "{MAIN_EXE}" >nul',
        "  echo Senton Control update failed. Previous version restored.",
        "  pause",
        "  exit /b 1",
        ")",
        f'start "" "{MAIN_EXE}"',
        'del "%~f0"',
    ]

    bat_path.write_text("\n".join(commands), encoding="utf-8")
    subprocess.Popen(["cmd.exe", "/c", str(bat_path)])
    return True
