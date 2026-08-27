import sys
from pathlib import Path

from installer_relaunch import install_update_and_relaunch


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: update_smoke_old.py <downloaded-new-exe>")
    downloaded = Path(sys.argv[1]).resolve()
    install_update_and_relaunch(downloaded)


if __name__ == "__main__":
    main()
