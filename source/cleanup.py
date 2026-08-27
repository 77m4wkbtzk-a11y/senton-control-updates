from pathlib import Path
import tempfile

DEFAULT_INSTALL_DIR = Path(r"C:\Users\Admin\Desktop\senton_dashboard")

# Only delete Senton Control updater artifacts we explicitly own.
DIST_ARTIFACT_NAMES = (
    "Senton Control.backup.exe",
    "Senton Control.backup.timestamp",
    "Senton Control.old.exe",
    "Senton Control.prev.exe",
)

TEMP_ARTIFACT_NAMES = (
    "Senton_Control_Update.exe",
    "senton_control_apply_update.bat",
)


def cleanup_obsolete_update_artifacts(install_dir=None, temp_dir=None):
    """Remove obsolete Senton updater/rollback artifacts after a new build starts.

    The active `Senton Control.exe` is never targeted. Only known, explicitly
    named Senton updater files are removed. The operation is safe to call more
    than once and returns the paths that were actually deleted.
    """
    install_dir = Path(install_dir) if install_dir is not None else DEFAULT_INSTALL_DIR
    temp_dir = Path(temp_dir) if temp_dir is not None else Path(tempfile.gettempdir())
    dist_dir = install_dir / "dist"

    targets = [dist_dir / name for name in DIST_ARTIFACT_NAMES]
    targets.extend(temp_dir / name for name in TEMP_ARTIFACT_NAMES)

    removed = []
    for path in targets:
        try:
            if path.exists() and path.is_file():
                path.unlink()
                removed.append(str(path))
        except OSError:
            # A locked helper can be retried on the next app launch.
            continue

    return removed
