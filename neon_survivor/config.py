"""Central, dependency-free configuration for Neon Survivor.

Everything that a designer may want to tweak lives here.  The module must
stay import-safe (no pygame import) so that it can be used by the tests.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------
GAME_TITLE = "Neon Survivor"
GAME_SLUG = "neon_survivor"
VERSION = "1.0.0"
ORG_NAME = "lmarena"

# --------------------------------------------------------------------------
# Window / rendering
# --------------------------------------------------------------------------
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
WINDOW_MIN_WIDTH = 960
WINDOW_MIN_HEIGHT = 540
TARGET_FPS = 60
RESIZABLE = True
FULLSCREEN_DEFAULT = False
#: Renderer used for the first window.  "auto" picks the best available one.
RENDERER_PREFERENCE = ("automatic", "opengl", "sdl2")

# --------------------------------------------------------------------------
# World
# --------------------------------------------------------------------------
WORLD_WIDTH = 4800
WORLD_HEIGHT = 4800
WALL_THICKNESS = 64

#: Number of destructible-looking (but static) pillars scattered on the map.
PILLAR_COUNT = 44
PILLAR_MIN_RADIUS = 42.0
PILLAR_MAX_RADIUS = 86.0
#: Extra padding kept between a pillar and the arena border.
PILLAR_BORDER_MARGIN = 180.0

#: Size of the grid used to draw the arena floor.
FLOOR_GRID_SIZE = 96

# --------------------------------------------------------------------------
# Player
# --------------------------------------------------------------------------
PLAYER_MAX_HEALTH = 100
PLAYER_RADIUS = 18.0
PLAYER_SPEED = 235.0
PLAYER_ACCEL = 2400.0
PLAYER_FRICTION = 12.0
PLAYER_INVULN_TIME = 0.85
PLAYER_HIT_FLASH_TIME = 0.25
PLAYER_REGEN_DELAY = 6.0
PLAYER_REGEN_RATE = 1.6  # HP per second once the delay elapsed

# --- Weapon ---
WEAPON_FIRE_RATE = 7.0  # shots per second at power level 1
WEAPON_RELOAD = 1.0 / WEAPON_FIRE_RATE
BULLET_SPEED = 760.0
BULLET_DAMAGE = 9.0
BULLET_RADIUS = 5.0
BULLET_LIFETIME = 1.6
WEAPON_RANGE = 620.0
#: Power level granted by a weapon pickup.
MAX_WEAPON_POWER = 6
#: Bullets fired per shot: 1, 1, 2, 2, 3, 4 ...
WEAPON_SPREAD_TABLE = (1, 1, 2, 2, 3, 4)
WEAPON_DAMAGE_STEP = 0.18  # +18 % damage per power level
WEAPON_FIRE_RATE_STEP = 0.10  # +10 % fire rate per power level
WEAPON_SPREAD_DEGREES = 9.0

# --------------------------------------------------------------------------
# Enemies — base archetype values
# --------------------------------------------------------------------------
ENEMY_TOUCH_DAMAGE = 9.0
ENEMY_KNOCKBACK = 220.0
ENEMY_SEPARATION = 150.0
ENEMY_SPAWN_GRACE = 0.55  # invulnerable flash after spawning
#: Absolute ceiling on live enemies, independent of the wave curve.  It
#: keeps the simulation and the renderer bounded in the worst case.
ENEMY_HARD_CAP = 96
ENEMY_DESPAWN_MARGIN = 320.0

# --------------------------------------------------------------------------
# Pickups
# --------------------------------------------------------------------------
PICKUP_RADIUS = 13.0
PICKUP_MAGNET_RADIUS = 96.0
PICKUP_MAGNET_SPEED = 430.0
PICKUP_LIFETIME = 16.0
PICKUP_BLINK_TIME = 4.0  # starts blinking with this much life left
PICKUP_DROP_CHANCE = 0.16

#: Speed of the Pulse Bomb shock wave, in pixels per second.
NUKE_WAVE_SPEED = 1500.0

# --------------------------------------------------------------------------
# Waves / difficulty  (see core.difficulty for the curves)
# --------------------------------------------------------------------------
WAVE_DURATION = 30.0
BOSS_EVERY = 5
BOSS_WAVE_BONUS_HEALTH = 1.0

# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------
SCORE_COMBO_WINDOW = 2.6
SCORE_COMBO_STEP = 0.12
SCORE_COMBO_MAX = 4.0
SCORE_PER_WAVE = 120
SCORE_SURVIVAL_PER_SECOND = 2.0

# --------------------------------------------------------------------------
# Feedback
# --------------------------------------------------------------------------
SCREEN_SHAKE_ON_HIT = 7.0
SCREEN_SHAKE_ON_BOSS = 12.0
SCREEN_SHAKE_DECAY = 6.0
HIT_STOP_ON_BOSS_DEATH = 0.16
DAMAGE_VIGNETTE_TIME = 0.55
LOW_HEALTH_VIGNETTE = 0.35

# --------------------------------------------------------------------------
# Audio
# --------------------------------------------------------------------------
MASTER_VOLUME = 0.75
MUSIC_VOLUME = 0.38
SFX_VOLUME = 0.85
AUDIO_SAMPLE_RATE = 22050
AUDIO_CHANNELS = 1
AUDIO_BUFFER = 512
#: Number of simultaneous sounds for the same effect.
VOICE_LIMIT = 16

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
ASSETS_DIR_NAME = "assets"
SAVE_FILE_NAME = "settings.json"

__all__ = [name for name in dir() if name.isupper()]
