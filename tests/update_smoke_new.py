import os
import tempfile
from pathlib import Path

marker = Path(tempfile.gettempdir()) / "senton_update_smoke_new_started.txt"
marker.write_text(f"started pid={os.getpid()}", encoding="utf-8")
