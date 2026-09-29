"""Launcher script used by the PyInstaller spec and by ``python main.py``.

Keeping a tiny top-level module means the built executable has a stable,
dependency-free entry point.
"""

from __future__ import annotations

import sys


def main() -> int:
    from neon_survivor.__main__ import main as run

    return run()


if __name__ == "__main__":
    sys.exit(main())
