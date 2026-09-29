"""Visual effects: particles, floating text, vignette, screen flash."""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import pygame

from neon_survivor.core.particles import ParticleSystem
from neon_survivor.gfx import draw, fonts
from neon_survivor.ui.theme import with_alpha

RGB = Tuple[int, int, int]


# --------------------------------------------------------------------------
# Particles
# --------------------------------------------------------------------------
def draw_particles(
    target: pygame.Surface,
    particles: ParticleSystem,
    to_screen,
    size_scale: float = 1.0,
    additive: bool = True,
) -> None:
    """Render every particle through the world->screen mapper *to_screen*."""
    flags = pygame.BLEND_RGBA_ADD if additive else 0
    for p in particles.particles:
        sx, sy = to_screen(p.x, p.y)
        if sx < -60 or sy < -60:
            continue
        ratio = p.life_ratio
        radius = max(0.6, (p.size + (p.end_size - p.size) * (1.0 - ratio)) * size_scale)
        if radius < 0.7:
            continue
        color = draw.mix_color(p.color, p.color_end, 1.0 - ratio)
        if p.shape == "square":
            rect = pygame.Rect(0, 0, int(radius * 2), int(radius * 2))
            rect.center = (int(sx), int(sy))
            layer = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(layer, (*color, int(255 * ratio)), layer.get_rect())
            target.blit(layer, rect, special_flags=flags)
        elif p.shape == "spark":
            dx, dy = p.vx, p.vy
            mag = math.hypot(dx, dy)
            if mag < 1e-3:
                continue
            ux, uy = dx / mag, dy / mag
            length = min(16.0, mag * 0.035) * size_scale
            pts = [
                (sx - ux * length, sy - uy * length),
                (sx + ux * radius, sy + uy * radius),
                (sx - ux * length * 0.3, sy - uy * length * 0.3),
            ]
            pygame.draw.lines(target, color, False, [(int(a), int(b)) for a, b in pts], max(1, int(radius)))
        else:
            pygame.draw.circle(
                target, color, (int(sx), int(sy)), max(1, int(radius))
            )
            if p.glow and radius > 1.5:
                draw.draw_glow(target, (sx, sy), radius * 2.4, color, ratio * 0.30)


# --------------------------------------------------------------------------
# Floating combat text
# --------------------------------------------------------------------------
class FloatingText:
    """A short-lived label such as ``+120`` or ``CRITICAL``."""

    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "text", "color", "size")

    def __init__(self, x, y, text, color, life=0.9, size=18, vx=0.0, vy=-52.0):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.text = text
        self.color = color
        self.size = size

    def update(self, dt: float) -> bool:
        self.life -= dt
        if self.life <= 0.0:
            return False
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy *= math.exp(-2.2 * dt)
        return True

    def draw(self, target: pygame.Surface, to_screen) -> None:
        ratio = max(0.0, min(1.0, self.life / self.max_life))
        sx, sy = to_screen(self.x, self.y)
        # Pop in, then fade out.
        pop = 1.0 + 0.25 * (1.0 - min(1.0, (1.0 - ratio) * 5.0))
        size = max(8, int(self.size * pop))
        alpha = ratio if ratio > 0.4 else ratio / 0.4
        surface = fonts.get_font(size, True).render(self.text, True, self.color)
        surface = surface.copy()
        surface.set_alpha(int(255 * max(0.0, min(1.0, alpha))))
        target.blit(surface, surface.get_rect(center=(int(sx), int(sy))))


class FloatingTextManager:
    def __init__(self, capacity: int = 60) -> None:
        self.capacity = capacity
        self.items: List[FloatingText] = []

    def add(self, x, y, text, color, life=0.9, size=18, vy=-52.0) -> None:
        if len(self.items) >= self.capacity:
            del self.items[0]
        self.items.append(FloatingText(x, y, text, color, life, size, vy=vy))

    def update(self, dt: float) -> None:
        self.items = [t for t in self.items if t.update(dt)]

    def draw(self, target: pygame.Surface, to_screen) -> None:
        for item in self.items:
            item.draw(target, to_screen)

    def clear(self) -> None:
        self.items.clear()

    def __len__(self) -> int:
        return len(self.items)


# --------------------------------------------------------------------------
# Screen effects
# --------------------------------------------------------------------------
_VIGNETTE_CACHE: dict = {}
_VIGNETTE_MASK: Optional[pygame.Surface] = None
_VIGNETTE_MASK_SIZE = 96


def _vignette_mask() -> pygame.Surface:
    """A small square falloff, stretched to the window when needed.

    Nested rectangles would be cheaper but leave visible banding rings, so
    a per-pixel falloff is baked once at low resolution and smoothed up.
    """
    global _VIGNETTE_MASK
    if _VIGNETTE_MASK is None:
        size = _VIGNETTE_MASK_SIZE
        mask = pygame.Surface((size, size), pygame.SRCALPHA)
        half = size / 2.0
        for y in range(size):
            dy = (y - half) / half
            for x in range(size):
                dx = (x - half) / half
                # Normalised Chebyshev distance to the nearest border.
                d = max(abs(dx), abs(dy))
                if d >= 1.0:
                    continue
                t = 1.0 - d
                mask.set_at((x, y), (0, 0, 0, int(255 * (t ** 2.6))))
        _VIGNETTE_MASK = mask
    return _VIGNETTE_MASK


def vignette_surface(size: Tuple[int, int], strength: float = 0.55) -> pygame.Surface:
    """A cached corner-darkening overlay.

    *strength* is quantised to 1/32 steps: each cache entry is a full-screen
    RGBA surface, so an animating strength must not allocate a new one every
    frame.
    """
    quantised = round(max(0.0, min(1.0, strength)) * 32) / 32.0
    key = (size, quantised)
    cached = _VIGNETTE_CACHE.get(key)
    if cached is not None:
        return cached
    surface = pygame.transform.smoothscale(_vignette_mask(), size)
    if quantised < 0.999:
        k = int(quantised * 255)
        surface.fill((255, 255, 255, k), special_flags=pygame.BLEND_RGBA_MULT)
    if len(_VIGNETTE_CACHE) > 12:
        _VIGNETTE_CACHE.clear()
    _VIGNETTE_CACHE[key] = surface
    return surface


def clear_vignette_cache() -> None:
    _VIGNETTE_CACHE.clear()
    global _VIGNETTE_MASK
    _VIGNETTE_MASK = None


def draw_vignette(target: pygame.Surface, strength: float = 0.55) -> None:
    if strength <= 0.01:
        return
    overlay = vignette_surface(target.get_size(), min(1.0, strength))
    target.blit(overlay, (0, 0))


def draw_fullscreen_color(
    target: pygame.Surface, color: RGB, alpha: float
) -> None:
    """Tint the whole screen (additive, used for damage and nuke flashes)."""
    if alpha <= 0.005:
        return
    overlay = pygame.Surface(target.get_size(), pygame.SRCALPHA)
    overlay.fill((*color, int(255 * min(1.0, alpha))))
    target.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)


def draw_border_pulse(
    target: pygame.Surface, color: RGB, alpha: float, width: int = 6
) -> None:
    """A coloured frame used for the low-health warning."""
    if alpha <= 0.01:
        return
    rect = target.get_rect()
    rect = rect.inflate(-width, -width)
    pygame.draw.rect(target, with_alpha(color, alpha), rect, width=width, border_radius=8)


def draw_scanlines(target: pygame.Surface, alpha: int = 18, offset: int = 0) -> None:
    """Subtle CRT scanlines — a light retro touch."""
    if alpha <= 0:
        return
    width, height = target.get_size()
    color = with_alpha((0, 0, 0), alpha / 255.0)
    step = 3
    for y in range(offset % step, height, step):
        pygame.draw.line(target, color, (0, y), (width, y))


__all__ = [
    "draw_particles",
    "FloatingText",
    "FloatingTextManager",
    "vignette_surface",
    "draw_vignette",
    "draw_fullscreen_color",
    "draw_border_pulse",
    "draw_scanlines",
]
