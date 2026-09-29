# Third-party licences

Neon Survivor ships **no binary asset at all**: every sprite, particle,
animation frame, sound effect and music track is generated at runtime from
code.  The repository therefore only contains the licence of the code itself
plus the licences of the runtime dependencies that are *bundled* into the
Windows executable.

## The game — MIT

`LICENSE` in the repository root covers every line of `neon_survivor/` and
`tests/`.  You may use, modify and redistribute the game, including in
commercial or closed-source products.

## Runtime dependency

| Component | Version used | Licence | Notes |
| --- | --- | --- | --- |
| [pygame-ce](https://github.com/pygame-community/pygame-ce) | 2.5.8 | **LGPL-2.1-or-later** | The only runtime dependency. pygame-ce is a community-maintained fork of pygame; its SDL2 dependencies also ship under the zlib licence. |

LGPL-2.1 permits linking and redistribution. The Windows `.exe` produced by
the build workflow therefore:

* keeps this `LICENSE-NOTES.md` and `LICENSE` next to the executable,
* allows a user to replace the bundled `pygame-ce` / SDL2 libraries with a
  modified version, and
* makes the complete corresponding source of the game available on request
  (it is simply this repository).

## Build-only dependency (not shipped)

| Component | Version used | Licence | Notes |
| --- | --- | --- | --- |
| [PyInstaller](https://pyinstaller.org/) | 6.22.3 | **GPL-2.0-or-later WITH a special exception** | Used only at build time. The "bundling exception" that ships with PyInstaller explicitly permits creating and distributing a proprietary or differently-licensed executable that embeds PyInstaller, so the resulting `.exe` is **not** forced to be GPL. |

## Python

The `.exe` bundles **python.org** CPython, distributed under the
[PSF-2.0](https://docs.python.org/3/license.html) licence.

## Fonts, music, art

* The font is the `freesansbold.ttf` that ships **inside pygame-ce itself**
  (GNU FreeFont family, GPL with the font embedding exception) — it is not a
  third-party download and carries no additional obligation for a game.
* All music and sound effects are synthesised from sine/triangle/saw/noise
  oscillators written in `neon_survivor/audio/`; they are therefore original
  works released under the same MIT licence as the game and are free of any
  sampling or royalty.
