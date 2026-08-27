import os
import subprocess
import tempfile
import time
from pathlib import Path

from updater import _backup_paths, _current_app_exe, _ps_literal


def install_update_without_relaunch(downloaded_exe):
    """Replace the running Senton Control EXE after exit, without relaunching it."""
    downloaded_exe = Path(downloaded_exe).resolve()
    if not downloaded_exe.exists():
        raise FileNotFoundError(f"Downloaded update was not found: {downloaded_exe}")

    main_exe = _current_app_exe().resolve()
    backup_exe, backup_marker = _backup_paths(main_exe)
    main_exe.parent.mkdir(parents=True, exist_ok=True)

    temp_dir = Path(tempfile.gettempdir())
    helper_path = temp_dir / "senton_control_apply_update_no_relaunch.ps1"
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
    Write-SentonLog 'Updater helper started (no relaunch mode).'

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

    Write-SentonLog 'New executable installed. Automatic relaunch disabled.'
    Set-Content -LiteralPath $statusFile -Value 'success-no-relaunch' -Encoding ASCII
    Remove-Item -LiteralPath $downloadedExe -Force -ErrorAction SilentlyContinue
}} catch {{
    Write-SentonLog ('Update failed: ' + $_.Exception.Message)
    Set-Content -LiteralPath $statusFile -Value ('failed: ' + $_.Exception.Message) -Encoding UTF8
    if (Test-Path -LiteralPath $backupExe) {{
        Copy-Item -LiteralPath $backupExe -Destination $mainExe -Force -ErrorAction SilentlyContinue
        Write-SentonLog 'Previous executable restored. Automatic relaunch remains disabled.'
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
