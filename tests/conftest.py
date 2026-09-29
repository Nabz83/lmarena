"""Shared pytest fixtures.

Every test runs head-less: SDL is pointed at its dummy video and audio
drivers so the suite works on CI without a display or a sound card.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Make the package importable when pytest is run from the repository root.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


@pytest.fixture(scope="session")
def pygame_module():
    import pygame

    pygame.init()
    yield pygame
    pygame.quit()


@pytest.fixture(scope="session")
def display(pygame_module):
    """A small offscreen surface usable as a draw target."""
    surface = pygame_module.Surface((320, 180))
    yield surface


@pytest.fixture()
def settings(tmp_path):
    from neon_survivor.settings import Settings

    return Settings()


@pytest.fixture()
def arena():
    from neon_survivor.core.world import Arena

    return Arena(seed=1234)


@pytest.fixture()
def game_scene(pygame_module):
    """A fresh :class:`GameScene` with a fixed seed and no audio."""
    from neon_survivor.game import GameScene
    from neon_survivor.settings import Settings

    scene = GameScene(Settings(), audio=None, seed=99)
    scene.resize(640, 360)
    scene.camera.snap_to(scene.player.x, scene.player.y)
    scene.camera.clamp_to_world(scene.arena.width, scene.arena.height)
    yield scene
    scene.particles.clear()
