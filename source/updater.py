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


def _ps_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def install_update_to_main_desktop(downloaded_exe):
    """Reliably replace the exact running Senton Control EXE using a detached PowerShell helper."""
    downloaded_exe = Path(downloaded_exe).resolve()
    if not downloaded_exe.exists():
        raise FileNotFoundError(f"Downloaded update was not found: {downloaded_exe}")

    main_exe = _current_app_exe().resolve()
    backup_exe, backup_marker = _backup_paths(main_exe)
    main_exe.parent.mkdir(parents=True, exist_ok=True)

    temp_dir = Path(tempfile.gettempdir())
    helper_path = temp_dir / "senton_control_apply_update.ps1"
    log_path = temp_dir / "senton_control_update.log"
    status_path = temp_dir / "senton_control_update.status"
    current_pid = os.getpid()

    q_main = _ps_literal(main_exe)
    q_download = _ps_literal(downloaded_exe)
    q_backup = _ps_literal(backup_exe)
    q_marker = _ps_literal(backup_marker)
    q_log = _ps_literal(log_path)
    q_status = _ps_literal(status_path)

    script = f"""
$ErrorActionPreference = 'Stop'
$pidToWait = {current_pid}
$mainExe = {q_main}
$downloadedExe = {q_download}
$backupExe = {q_backup}
$backupMarker = {q_marker}
$logFile = {q_log}
$statusFile = {q_status}

function Write-SentonLog([string]$message) {{
    $stamp = [DateTimeOffset]::Now.ToString('yyyy-MM-dd HH:mm:ss zzz')
    Add-Content -LiteralPath $logFile -Value ("$stamp $message") -Encoding UTF8
}}

try {{
    Remove-Item -LiteralPath $statusFile -Force -ErrorAction SilentlyContinue
    Write-SentonLog 'Updater helper started.'

    for ($i = 0; $i -lt 40; $i++) {{
        if (-not (Get-Process -Id $pidToWait -ErrorAction SilentlyContinue)) {{ break }}
        Start-Sleep -Milliseconds 250
    }}

    if (Get-Process -Id $pidToWait -ErrorAction SilentlyContinue) {{
        Write-SentonLog 'App did not exit in time; forcing only the current Senton process closed.'
        Stop-Process -Id $pidToWait -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 750
    }}

    if (Test-Path -LiteralPath $backupExe) {{ Remove-Item -LiteralPath $backupExe -Force }}
    if (Test-Path -LiteralPath $backupMarker) {{ Remove-Item -LiteralPath $backupMarker -Force }}

    if (Test-Path -LiteralPath $mainExe) {{
        Copy-Item -LiteralPath $mainExe -Destination $backupExe -Force
        [IO.File]::WriteAllText($backupMarker, [string]([DateTimeOffset]::UtcNow.ToUnixTimeSeconds()))
        Write-SentonLog 'Previous executable backed up.'
    }}

    $installed = $false
    for ($attempt = 1; $attempt -le 12; $attempt++) {{
        try {{
            Copy-Item -LiteralPath $downloadedExe -Destination $mainExe -Force
            if ((Test-Path -LiteralPath $mainExe) -and ((Get-Item -LiteralPath $mainExe).Length -ge 1048576)) {{
                $installed = $true
                break
            }}
        }} catch {{
            Write-SentonLog ("Replacement attempt $attempt failed: " + $_.Exception.Message)
        }}
        Start-Sleep -Milliseconds 750
    }}

    if (-not $installed) {{ throw 'Could not replace the Senton Control executable.' }}

    Write-SentonLog 'New executable installed. Restarting Senton Control.'
    Set-Content -LiteralPath $statusFile -Value 'success' -Encoding ASCII
    Start-Process -FilePath $mainExe -WorkingDirectory (Split-Path -Parent $mainExe)
    Remove-Item -LiteralPath $downloadedExe -Force -ErrorAction SilentlyContinue
}} catch {{
    Write-SentonLog ('Update failed: ' + $_.Exception.Message)
    Set-Content -LiteralPath $statusFile -Value ('failed: ' + $_.Exception.Message) -Encoding UTF8
    if (Test-Path -LiteralPath $backupExe) {{
        Copy-Item -LiteralPath $backupExe -Destination $mainExe -Force -ErrorAction SilentlyContinue
        Write-SentonLog 'Previous executable restored.'
    }}
    if (Test-Path -LiteralPath $mainExe) {{
        Start-Process -FilePath $mainExe -WorkingDirectory (Split-Path -Parent $mainExe) -ErrorAction SilentlyContinue
    }}
    exit 1
}}
""".strip()

    helper_path.write_text(script, encoding="utf-8")
    log_path.unlink(missing_ok=True)
    status_path.unlink(missing_ok=True)

    creationflags = (
        getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )
    proc = subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-File",
            str(helper_path),
        ],
        creationflags=creationflags,
        close_fds=True,
    )

    time.sleep(0.25)
    return_code = proc.poll()
    if return_code is not None and return_code != 0:
        raise RuntimeError(
            f"The Senton update installer could not start (code {return_code}). "
            f"Diagnostic log: {log_path}"
        )
    return True
