"""Pick-ups dropped by enemies: health, power-ups, score gems and specials."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

from neon_survivor.config import (
    PICKUP_BLINK_TIME,
    PICKUP_LIFETIME,
    PICKUP_MAGNET_RADIUS,
    PICKUP_MAGNET_SPEED,
    PICKUP_RADIUS,
)

@dataclass(frozen=True)
class PickupType:
    key: str
    label: str
    color: Tuple[int, int, int]
    accent: Tuple[int, int, int]
    score: int = 0
    weight: float = 0.0
    #: Probability of being selected among the weighted random rolls.
    healing: float = 0.0
    power: float = 0.0
    speed: float = 0.0
    shield: float = 0.0
    nuke: bool = False
    magnet: bool = False


PICKUP_TYPES: Dict[str, PickupType] = {
    "health": PickupType(
        key="health",
        label="+25 HP",
        color=(86, 240, 140),
        accent=(220, 255, 234),
        weight=30.0,
        healing=25.0,
    ),
    "power": PickupType(
        key="power",
        label="Weapon +1",
        color=(120, 190, 255),
        accent=(222, 240, 255),
        weight=22.0,
        power=1,
    ),
    "speed": PickupType(
        key="speed",
        label="Overdrive",
        color=(255, 208, 84),
        accent=(255, 244, 210),
        weight=14.0,
        speed=9.0,
    ),
    "shield": PickupType(
        key="shield",
        label="Shield",
        color=(168, 132, 255),
        accent=(232, 224, 255),
        weight=12.0,
        shield=45.0,
    ),
    "nuke": PickupType(
        key="nuke",
        label="Pulse Bomb",
        color=(255, 92, 92),
        accent=(255, 220, 214),
        weight=6.0,
        nuke=True,
    ),
    "magnet": PickupType(
        key="magnet",
        label="Magnet",
        color=(86, 226, 226),
        accent=(220, 255, 255),
        weight=8.0,
        magnet=True,
    ),
    "gem": PickupType(
        key="gem",
        label="+Score",
        color=(255, 240, 160),
        accent=(255, 255, 235),
        score=45,
        weight=0.0,  # spawned separately, never from the random roll
    ),
}

#: Relative spawn weights for the random drop table.
DROP_TABLE: Sequence[Tuple[str, float]] = tuple(
    (key, t.weight) for key, t in PICKUP_TYPES.items() if t.weight > 0
)


def roll_pickup(rng: random.Random) -> Optional[str]:
    """Weighted random choice among the droppable pickup types."""
    total = sum(weight for _, weight in DROP_TABLE)
    if total <= 0:
        return None
    roll = rng.random() * total
    cumulative = 0.0
    for key, weight in DROP_TABLE:
        cumulative += weight
        if roll < cumulative:
            return key
    return DROP_TABLE[-1][0]


class Pickup:
    """A floating collectible."""

    __slots__ = (
        "type",
        "x",
        "y",
        "vx",
        "vy",
        "radius",
        "life",
        "value",
        "pulled",
        "age",
        "spin",
    )

    def __init__(
        self,
        pickup_type: str,
        x: float,
        y: float,
        value: float = 1.0,
        vx: float = 0.0,
        vy: float = 0.0,
    ) -> None:
        self.type = PICKUP_TYPES[pickup_type]
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.radius = PICKUP_RADIUS
        self.life = PICKUP_LIFETIME
        self.value = value
        self.pulled = False
        self.age = 0.0
        self.spin = 0.0

    # -- visuals ---------------------------------------------------------
    @property
    def blinking(self) -> bool:
        return self.life <= PICKUP_BLINK_TIME

    @property
    def bob(self) -> float:
        return math.sin(self.age * 3.2 + self.spin) * 3.5

    def update(self, dt: float, player_x: float, player_y: float, player_alive: bool = True) -> None:
        self.age += dt
        self.spin += dt
        self.life -= dt

        if player_alive:
            dist = math.hypot(player_x - self.x, player_y - self.y)
            if self.pulled or dist <= PICKUP_MAGNET_RADIUS:
                self.pulled = True
                if dist > 1e-3:
                    ux = (player_x - self.x) / dist
                    uy = (player_y - self.y) / dist
                    self.vx = ux * PICKUP_MAGNET_SPEED
                    self.vy = uy * PICKUP_MAGNET_SPEED

        self.x += self.vx * dt
        self.y += self.vy * dt
        # Outward impulse decays quickly once magnetised.
        damp = math.exp(-6.0 * dt)
        self.vx *= damp
        self.vy *= damp

    def should_despawn(self) -> bool:
        return self.life <= 0.0


@dataclass
class PickupResult:
    """What happened when the player collected a pickup."""

    label: str
    color: Tuple[int, int, int]
    score: int = 0


def apply_pickup(pickup: Pickup, player, game) -> PickupResult:
    """Apply *pickup* to the player; ``game`` may be ``None`` in tests."""
    ptype = pickup.type
    gained_score = ptype.score

    if ptype.healing > 0.0:
        player.heal(ptype.healing * pickup.value)
    elif ptype.power > 0:
        player.upgrade_weapon(int(ptype.power * pickup.value))
    elif ptype.speed > 0.0:
        player.speed_boost = max(player.speed_boost, ptype.speed * pickup.value)
    elif ptype.shield > 0.0:
        player.shield = min(120.0, player.shield + ptype.shield * pickup.value)
    elif ptype.nuke:
        if game is not None and hasattr(game, "trigger_nuke"):
            game.trigger_nuke(pickup)
    elif ptype.magnet:
        if game is not None and hasattr(game, "trigger_magnet"):
            game.trigger_magnet(pickup)

    return PickupResult(label=ptype.label, color=ptype.accent, score=gained_score)


__all__ = [
    "Pickup",
    "PickupType",
    "PickupResult",
    "PICKUP_TYPES",
    "DROP_TABLE",
    "roll_pickup",
    "apply_pickup",
]
