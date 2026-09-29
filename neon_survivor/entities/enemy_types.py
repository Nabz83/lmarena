"""Data-driven definition of every enemy archetype.

Keeping the stats in a table (instead of in the ``Enemy`` class hierarchy)
makes it trivial to balance and to assert on in the tests.  ``behavior``
selects the AI routine implemented in :mod:`neon_survivor.entities.enemy`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class EnemyArchetype:
    """Immutable blueprint for an enemy type."""

    key: str
    display_name: str
    behavior: str
    health: float
    speed: float
    radius: float
    touch_damage: float
    score: int
    mass: float = 1.0
    color: Tuple[int, int, int] = (255, 90, 120)
    accent: Tuple[int, int, int] = (255, 200, 220)
    glow: int = 10

    # -- behaviour knobs -------------------------------------------------
    #: Firearm archetype.
    shoot_interval: float = 0.0
    shoot_speed: float = 0.0
    shoot_damage: float = 0.0
    preferred_range: float = 0.0

    #: Charger: idle -> windup -> dash -> recover.
    charge_speed: float = 0.0
    charge_windup: float = 0.0
    charge_duration: float = 0.0
    charge_cooldown: float = 0.0

    #: Splitter: children spawned on death.
    split_into: int = 0
    split_radius_scale: float = 0.6
    split_health_scale: float = 0.35

    #: Weaver: lateral sine offset while chasing.
    weave_amplitude: float = 0.0
    weave_frequency: float = 0.0

    #: Boss specific.
    is_boss: bool = False
    boss_rage_speed: float = 0.0
    boss_radial_bullets: int = 0
    spawn_weight_hint: float = 1.0

    def scaled_health(self, multiplier: float) -> float:
        return self.health * max(0.1, multiplier)

    def scaled_speed(self, multiplier: float) -> float:
        return self.speed * max(0.1, multiplier)


#: Difficulty order matters: the spawner never needs to sort it.
ARCHETYPES: Dict[str, EnemyArchetype] = {
    "grunt": EnemyArchetype(
        key="grunt",
        display_name="Drifter",
        behavior="chase",
        health=26.0,
        speed=74.0,
        radius=17.0,
        touch_damage=9.0,
        score=10,
        color=(255, 92, 120),
        accent=(255, 214, 224),
    ),
    "runner": EnemyArchetype(
        key="runner",
        display_name="Skimmer",
        behavior="chase",
        health=17.0,
        speed=142.0,
        radius=13.0,
        touch_damage=7.0,
        score=16,
        mass=0.7,
        color=(255, 178, 62),
        accent=(255, 238, 200),
        weave_amplitude=34.0,
        weave_frequency=2.6,
    ),
    "shooter": EnemyArchetype(
        key="shooter",
        display_name="Spitter",
        behavior="shooter",
        health=30.0,
        speed=66.0,
        radius=16.0,
        touch_damage=8.0,
        score=24,
        color=(150, 120, 255),
        accent=(226, 218, 255),
        shoot_interval=1.9,
        shoot_speed=300.0,
        shoot_damage=11.0,
        preferred_range=360.0,
    ),
    "tank": EnemyArchetype(
        key="tank",
        display_name="Bulwark",
        behavior="chase",
        health=135.0,
        speed=48.0,
        radius=27.0,
        touch_damage=18.0,
        score=42,
        mass=3.4,
        color=(72, 224, 190),
        accent=(206, 255, 246),
        glow=16,
    ),
    "charger": EnemyArchetype(
        key="charger",
        display_name="Lancer",
        behavior="charger",
        health=42.0,
        speed=62.0,
        radius=18.0,
        touch_damage=14.0,
        score=34,
        color=(255, 120, 72),
        accent=(255, 224, 208),
        charge_speed=470.0,
        charge_windup=0.62,
        charge_duration=0.55,
        charge_cooldown=1.6,
    ),
    "splitter": EnemyArchetype(
        key="splitter",
        display_name="Mitosis",
        behavior="chase",
        health=54.0,
        radius=21.0,
        speed=82.0,
        touch_damage=10.0,
        score=30,
        color=(120, 255, 140),
        accent=(220, 255, 228),
        split_into=2,
        split_radius_scale=0.55,
        split_health_scale=0.42,
    ),
    "weaver": EnemyArchetype(
        key="weaver",
        display_name="Lattice",
        behavior="weaver",
        health=44.0,
        speed=104.0,
        radius=16.0,
        touch_damage=10.0,
        score=34,
        color=(96, 210, 255),
        accent=(222, 246, 255),
        weave_amplitude=96.0,
        weave_frequency=1.35,
        shoot_interval=2.6,
        shoot_speed=250.0,
        shoot_damage=9.0,
        preferred_range=300.0,
    ),
    "boss": EnemyArchetype(
        key="boss",
        display_name="Warden",
        behavior="boss",
        health=760.0,
        speed=58.0,
        radius=52.0,
        touch_damage=24.0,
        score=400,
        mass=14.0,
        color=(255, 66, 122),
        accent=(255, 226, 236),
        glow=30,
        is_boss=True,
        boss_rage_speed=104.0,
        boss_radial_bullets=12,
        shoot_interval=1.25,
        shoot_speed=300.0,
        shoot_damage=13.0,
        preferred_range=280.0,
    ),
}

#: Extra contact damage a charger inflicts while dashing.
CHARGER_DASH_DAMAGE_MULTIPLIER = 1.6

#: Splitter lineage: a child may split again only below this depth.
MAX_SPLIT_DEPTH = 1

#: When a boss dies it also releases a couple of escorts.
BOSS_ESCORTS = ("runner", "shooter")


def get_archetype(key: str) -> EnemyArchetype:
    try:
        return ARCHETYPES[key]
    except KeyError as exc:  # pragma: no cover - programming error
        raise KeyError(f"unknown enemy archetype: {key!r}") from exc


__all__ = [
    "EnemyArchetype",
    "ARCHETYPES",
    "BOSS_ESCORTS",
    "MAX_SPLIT_DEPTH",
    "CHARGER_DASH_DAMAGE_MULTIPLIER",
    "get_archetype",
]
