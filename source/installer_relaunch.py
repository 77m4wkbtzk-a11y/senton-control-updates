import hashlib
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

LEGACY_MAIN_EXE = Path(r"C:\Users\Admin\Desktop\senton_dashboard\dist\Senton Control.exe")


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


def _ps_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install_update_and_relaunch(downloaded_exe):
    """Replace the running verified EXE after exit, verify the copied bytes, then relaunch it cleanly."""
    downloaded_exe = Path(downloaded_exe).resolve()
    if not downloaded_exe.exists():
        raise FileNotFoundError(f"Downloaded update was not found: {downloaded_exe}")
    if downloaded_exe.stat().st_size < 1024 * 1024:
        raise RuntimeError("Downloaded update is unexpectedly small.")

    expected_sha256 = _sha256(downloaded_exe)
    main_exe = _current_app_exe().resolve()
    backup_exe, backup_marker = _backup_paths(main_exe)
    main_exe.parent.mkdir(parents=True, exist_ok=True)

    temp_dir = Path(tempfile.gettempdir())
    helper_path = temp_dir / "senton_control_apply_update_and_relaunch.ps1"
    log_path = temp_dir / "senton_control_update.log"
    status_path = temp_dir / "senton_control_update.status"
    current_pid = os.getpid()

    q_main = _ps_literal(main_exe)
    q_download = _ps_literal(downloaded_exe)
    q_backup = _ps_literal(backup_exe)
    q_marker = _ps_literal(backup_marker)
    q_log = _ps_literal(log_path)
    q_status = _ps_literal(status_path)
    q_expected = _ps_literal(expected_sha256)

    script = f"""
$ErrorActionPreference = 'Stop'
$pidToWait = {current_pid}
$mainExe = {q_main}
$downloadedExe = {q_download}
$backupExe = {q_backup}
$backupMarker = {q_marker}
$logFile = {q_log}
$statusFile = {q_status}
$expectedSha256 = {q_expected}

function Write-SentonLog([string]$message) {{
    $stamp = [DateTimeOffset]::Now.ToString('yyyy-MM-dd HH:mm:ss zzz')
    Add-Content -LiteralPath $logFile -Value ("$stamp $message") -Encoding UTF8
}}

function Reset-PyInstallerEnvironment {{
    Get-ChildItem Env: | Where-Object {{ $_.Name -like '_PYI_*' }} | ForEach-Object {{
        Remove-Item -LiteralPath ("Env:" + $_.Name) -ErrorAction SilentlyContinue
    }}
    $env:PYINSTALLER_RESET_ENVIRONMENT = '1'
}}

function Start-SentonExecutable([string]$exePath) {{
    Reset-PyInstallerEnvironment
    $workingDirectory = Split-Path -Parent $exePath
    $launched = Start-Process -FilePath $exePath -WorkingDirectory $workingDirectory -PassThru
    if ($null -eq $launched) {{ throw 'Windows did not return a process for the relaunched Senton executable.' }}
    Start-Sleep -Milliseconds 500
    Write-SentonLog ("Relaunch requested successfully; PID=" + $launched.Id)
    return $launched
}}

try {{
    Remove-Item -LiteralPath $statusFile -Force -ErrorAction SilentlyContinue
    Write-SentonLog 'Updater helper started (replace, verify, clean relaunch mode).'

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
                $actualSha256 = (Get-FileHash -LiteralPath $mainExe -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($actualSha256 -ne $expectedSha256) {{
                    throw 'Installed executable SHA-256 does not match the verified download.'
                }}
                $installed = $true
                break
            }}
        }} catch {{
            Write-SentonLog ("Replacement attempt $attempt failed: " + $_.Exception.Message)
        }}
        Start-Sleep -Milliseconds 750
    }}

    if (-not $installed) {{ throw 'Could not replace and verify the Senton Control executable.' }}

    Remove-Item -LiteralPath $downloadedExe -Force -ErrorAction SilentlyContinue
    Write-SentonLog 'New executable installed and verified. Relaunching Senton Control with a clean PyInstaller environment.'
    $newProcess = Start-SentonExecutable $mainExe
    Set-Content -LiteralPath $statusFile -Value 'success-relaunched' -Encoding ASCII
}} catch {{
    Write-SentonLog ('Update failed: ' + $_.Exception.Message)
    Set-Content -LiteralPath $statusFile -Value ('failed: ' + $_.Exception.Message) -Encoding UTF8
    if (Test-Path -LiteralPath $backupExe) {{
        Copy-Item -LiteralPath $backupExe -Destination $mainExe -Force -ErrorAction SilentlyContinue
        Write-SentonLog 'Previous executable restored after failed update.'
        try {{ Start-SentonExecutable $mainExe | Out-Null }} catch {{
            Write-SentonLog ('Backup relaunch also failed: ' + $_.Exception.Message)
        }}
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
            f"The Senton update installer could not start (code {return_code}). Diagnostic log: {log_path}"
        )
    return True
