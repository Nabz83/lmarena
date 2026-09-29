# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Neon Survivor Windows executable.

Build it with::

    python -m PyInstaller NeonSurvivor.spec --noconfirm

The spec is deliberately dependency-free and reads its version straight from
``neon_survivor/config.py`` so the executable metadata can never drift from
the code.  The application icon is generated from source by
``tools/make_icon.py`` (the repository ships no binary asset); if that step
was skipped the build still works, just without an icon.
"""

import sys
from pathlib import Path

# --- Paths (PyInstaller executes the spec with its directory as CWD) --------
ROOT = Path(SPECPATH).resolve() if "SPECPATH" in globals() else Path.cwd()
sys.path.insert(0, str(ROOT))

from neon_survivor.config import GAME_TITLE, ORG_NAME, VERSION  # noqa: E402

# --- Metadata --------------------------------------------------------------
PRODUCT = GAME_TITLE.replace(" ", "")
COPYRIGHT = f"(c) 2026 {ORG_NAME}"
ICON = ROOT / "build_assets" / "icon.ico"

block_cipher = None

# --- Optional files bundled next to the executable -------------------------
EXTRA_FILES = [
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "LICENSE-NOTES.md"), "."),
    (str(ROOT / "README.md"), "."),
]
EXTRA_FILES = [(src, dest) for src, dest in EXTRA_FILES if Path(src).is_file()]

# --- Modules that must never end up in the bundle -------------------------
EXCLUDES = [
    # tk / Qt / GTK bindings: pygame-ce only needs SDL2.
    "tkinter", "unittest", "pydoc_data", "doctest", "test",
    "numpy", "scipy", "pandas", "matplotlib", "PIL", "IPython",
    "PyQt5", "PyQt6", "PySide2", "PySide6", "gi",
    # Not used by the game and heavy.
    "setuptools", "pip", "wheel", "email", "http", "xmlrpc",
    "pdb", "distutils", "sqlite3", "asyncio", "multiprocessing",
    "venv", "ensurepip", "lib2to3", "pygame.examples",
    "pygame.tests", "pygame.demos", "pygame.freetype",
    "pygame.gp2", "pygame.sdl2",
]


a = Analysis(
    [str(ROOT / "neon_survivor" / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=EXTRA_FILES,
    hiddenimports=[
        "neon_survivor",
        "neon_survivor.app",
        "neon_survivor.game",
        "pygame", "pygame.gfxdraw",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=PRODUCT,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    # One single self-contained .exe: the artifact users download and run.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON) if ICON.is_file() else None,
    version_info=None,
)
