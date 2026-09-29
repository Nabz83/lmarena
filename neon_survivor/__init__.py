"""Neon Survivor — a 2D top-down action / survival game.

The package is split in small, mostly decoupled modules so that the pure
game logic (difficulty, spawning, collision, scoring...) can be unit-tested
without a display or a sound card.

Layout
------
``config``     global tunables (window, world, gameplay constants)
``settings``   persistent user data (high score, options)
``core``       engine-ish helpers: math, collision, camera, particles, world
``entities``   player, enemies, bullets, pickups
``ui``         theme, HUD and full-screen menus
``audio``      procedural synthesis (no third-party sound files)
``gfx``        procedurally generated sprites and visual effects
``app``        window, scene stack and the main loop
``game``       the play scene itself
"""

from neon_survivor.config import GAME_TITLE, VERSION

__all__ = ["GAME_TITLE", "VERSION", "__version__"]

__version__ = VERSION
