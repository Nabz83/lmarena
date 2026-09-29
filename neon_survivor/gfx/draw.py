"""Reusable drawing primitives: glow, rounded panels, bars and text.

These wrap the raw pygame calls so the rest of the renderer stays readable
and so the "neon" look is defined in exactly one place.
"""

from __future__ import annotations

import math
from typing import Iterable, Optional, Sequence, Tuple

import pygame

from neon_survivor.gfx import fonts
from neon_survivor.ui.theme import Metrics, Palette

RGB = Tuple[int, int, int]
RGBA = Tuple[int, int, int, int]


# --------------------------------------------------------------------------
# Colour helpers
# --------------------------------------------------------------------------
def scale_color(color: Sequence[int], factor: float) -> RGB:
    """Multiply a colour by *factor*, clamping to 0..255."""
    return (
        max(0, min(255, int(color[0] * factor))),
        max(0, min(255, int(color[1] * factor))),
        max(0, min(255, int(color[2] * factor))),
    )


def mix_color(a: Sequence[int], b: Sequence[int], t: float) -> RGB:
    t = max(0.0, min(1.0, t))
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


# --------------------------------------------------------------------------
# Glow
# --------------------------------------------------------------------------
#: Falloff exponent for the radial mask.  Higher = tighter halo.
GLOW_FALLOFF = 2.4
#: Peak brightness of a full-intensity glow (0..1).
GLOW_PEAK = 0.55
#: Hard cap on the radius of a generated glow surface.  A single
#: ``(2*radius)²`` RGBA surface is 16 bytes per pixel, so an unbounded
#: radius (a nuke wave, a zoomed boss) would allocate hundreds of MB.
GLOW_MAX_RADIUS = 420

_GLOW_CACHE: dict = {}


def _build_glow_mask(size: int) -> pygame.Surface:
    """White radial falloff with the falloff baked into the RGB channels.

    ``BLEND_RGBA_ADD`` adds the source RGB *without* weighting it by alpha,
    so the falloff has to live in the colour channels, not only in alpha.
    """
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    center = (size - 1) / 2.0
    for y in range(size):
        dy = (y - center) / center
        for x in range(size):
            dx = (x - center) / center
            d = math.hypot(dx, dy)
            if d > 1.0:
                continue
            f = (1.0 - d) ** GLOW_FALLOFF
            v = int(255 * f * GLOW_PEAK)
            mask.set_at((x, y), (v, v, v, int(255 * f)))
    return mask


_BASE_MASK_CACHE: dict = {}


def _base_mask() -> pygame.Surface:
    mask = _BASE_MASK_CACHE.get(64)
    if mask is None:
        mask = _build_glow_mask(64)
        _BASE_MASK_CACHE[64] = mask
    return mask


def glow_surface(radius: int, color: Sequence[int]) -> pygame.Surface:
    """Return a cached soft radial glow of the given *radius* in *color*."""
    radius = max(2, min(GLOW_MAX_RADIUS, int(radius)))
    key = (radius, tuple(color[:3]))
    cached = _GLOW_CACHE.get(key)
    if cached is not None:
        return cached

    size = radius * 2
    mask = pygame.transform.smoothscale(_base_mask(), (size, size))
    tint = pygame.Surface((size, size), pygame.SRCALPHA)
    tint.fill((color[0], color[1], color[2], 255))
    mask.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    if len(_GLOW_CACHE) > 192:
        _GLOW_CACHE.clear()
    _GLOW_CACHE[key] = mask
    return mask


def clear_glow_cache() -> None:
    _GLOW_CACHE.clear()
    _BASE_MASK_CACHE.clear()


def draw_glow(
    target: pygame.Surface,
    pos: Tuple[float, float],
    radius: float,
    color: Sequence[int],
    intensity: float = 1.0,
    scale: float = 1.0,
) -> None:
    """Additive radial glow centred on *pos* (screen coordinates).

    *scale* stretches the (circular) glow sprite: values above 1 keep the
    soft falloff while growing the covered area without a bigger surface.
    """
    if intensity <= 0.01 or radius <= 0.5:
        return
    surface = glow_surface(max(2, int(radius)), color)
    if scale != 1.0:
        size = max(2, int(surface.get_width() * max(0.05, scale)))
        try:
            surface = pygame.transform.smoothscale(surface, (size, size))
        except ValueError:
            pass
    if intensity < 0.99:
        k = int(max(0.0, min(1.0, intensity)) * 255)
        surface = surface.copy()
        surface.fill((k, k, k, k), special_flags=pygame.BLEND_RGBA_MULT)
    rect = surface.get_rect(center=(int(pos[0]), int(pos[1])))
    target.blit(surface, rect, special_flags=pygame.BLEND_RGBA_ADD)


# --------------------------------------------------------------------------
# Shapes
# --------------------------------------------------------------------------
def draw_glow_circle(
    target: pygame.Surface,
    pos: Tuple[float, float],
    radius: float,
    color: Sequence[int],
    width: int = 2,
    glow: int = 8,
    glow_intensity: float = 1.0,
) -> None:
    """A neon circle: soft halo, body, bright outline, dark inner outline."""
    if glow > 0:
        draw_glow(target, pos, radius + glow, color, glow_intensity * 0.75)
    pygame.draw.circle(target, color, (int(pos[0]), int(pos[1])), int(radius))
    if width > 0:
        pygame.draw.circle(
            target, scale_color(color, 1.7), (int(pos[0]), int(pos[1])), int(radius), width
        )


def rounded_panel(
    target: pygame.Surface,
    rect: pygame.Rect,
    color: Sequence[int] = Palette.PANEL,
    alpha: int = 235,
    border: Optional[Sequence[int]] = None,
    border_width: int = Metrics.BORDER,
    radius: int = Metrics.RADIUS,
) -> None:
    """Draw a rounded, optionally outlined panel."""
    surface = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(surface, (*color[:3], alpha), surface.get_rect(), border_radius=radius)
    target.blit(surface, rect)
    if border is not None and border_width > 0:
        pygame.draw.rect(
            target, border, rect, width=border_width, border_radius=radius
        )


def gradient_bar(
    target: pygame.Surface,
    rect: pygame.Rect,
    ratio: float,
    colors: Sequence[RGB],
    background: RGB = (30, 34, 58),
    border: Optional[RGB] = None,
    radius: Optional[int] = None,
    horizontal: bool = True,
) -> None:
    """A smooth multi-stop gradient progress bar."""
    ratio = max(0.0, min(1.0, ratio))
    radius = rect.height // 2 if radius is None else radius
    pygame.draw.rect(target, background, rect, border_radius=radius)
    if ratio > 0.0:
        size = (int(rect.width * ratio), rect.height) if horizontal else (rect.width, int(rect.height * ratio))
        if size[0] > 0 and size[1] > 0:
            bar = pygame.Surface(size, pygame.SRCALPHA)
            steps = max(2, size[0] if horizontal else size[1])
            for i in range(steps):
                t = i / max(1, steps - 1)
                color = _sample(colors, t)
                if horizontal:
                    pygame.draw.line(bar, color, (i, 0), (i, size[1]))
                else:
                    pygame.draw.line(bar, color, (0, i), (size[0], i))
            target.blit(bar, rect.topleft)
    if border is not None:
        pygame.draw.rect(target, border, rect, width=2, border_radius=radius)


def _sample(colors: Sequence[RGB], t: float) -> RGB:
    if len(colors) == 1:
        return tuple(colors[0])
    scaled = t * (len(colors) - 1)
    index = int(scaled)
    if index >= len(colors) - 1:
        return tuple(colors[-1])
    return mix_color(colors[index], colors[index + 1], scaled - index)


def ring(
    target: pygame.Surface,
    center: Tuple[float, float],
    radius: float,
    color: Sequence[int],
    start_deg: float,
    end_deg: float,
    width: int = 2,
) -> None:
    """Draw an arc; ``start_deg``/``end_deg`` are degrees, 0 = east."""
    if abs(end_deg - start_deg) < 0.4:
        return
    steps = max(3, int(abs(end_deg - start_deg) / 4))
    points = []
    for i in range(steps + 1):
        t = i / steps
        angle = math.radians(start_deg + (end_deg - start_deg) * t)
        points.append(
            (center[0] + math.cos(angle) * radius, center[1] + math.sin(angle) * radius)
        )
    if len(points) >= 2:
        pygame.draw.lines(target, color, False, [(int(x), int(y)) for x, y in points], width)


def polyline(
    target: pygame.Surface,
    points: Iterable[Tuple[float, float]],
    color: Sequence[int],
    width: int = 1,
) -> None:
    pts = [(int(x), int(y)) for x, y in points]
    if len(pts) >= 2:
        pygame.draw.lines(target, color, False, pts, width)


# --------------------------------------------------------------------------
# Text
# --------------------------------------------------------------------------
def text(
    target: pygame.Surface,
    content: str,
    pos: Tuple[float, float],
    size: int = fonts.SIZE_BODY,
    color: RGB = Palette.TEXT,
    align: str = "left",
    valign: str = "top",
    bold: bool = True,
    shadow: bool = True,
    shadow_offset: int = 2,
) -> pygame.Rect:
    """Blit text and return its rect.  ``pos`` is a world/screen point."""
    font = fonts.get_font(size, bold)
    surface = font.render(str(content), True, color)
    rect = surface.get_rect()
    if align == "center":
        rect.centerx = int(pos[0])
    elif align == "right":
        rect.right = int(pos[0])
    else:
        rect.left = int(pos[0])
    if valign == "center":
        rect.centery = int(pos[1])
    elif valign == "bottom":
        rect.bottom = int(pos[1])
    else:
        rect.top = int(pos[1])

    if shadow:
        shade = font.render(str(content), True, Palette.VOID)
        target.blit(shade, rect.move(shadow_offset, shadow_offset + 1))
    target.blit(surface, rect)
    return rect


def text_outlined(
    target: pygame.Surface,
    content: str,
    pos: Tuple[float, float],
    size: int = fonts.SIZE_BODY,
    color: RGB = Palette.TEXT,
    border_color: RGB = Palette.VOID,
    align: str = "center",
    valign: str = "center",
    bold: bool = True,
    border_width: int = 2,
) -> pygame.Rect:
    """Text with a contrasting outline — used for titles and banners."""
    font = fonts.get_font(size, bold)
    base = font.render(str(content), True, color)
    rect = base.get_rect()
    if align == "center":
        rect.centerx = int(pos[0])
    elif align == "right":
        rect.right = int(pos[0])
    else:
        rect.left = int(pos[0])
    if valign == "center":
        rect.centery = int(pos[1])
    elif valign == "bottom":
        rect.bottom = int(pos[1])
    else:
        rect.top = int(pos[1])

    outlined = font.render(str(content), True, border_color, border_width)
    target.blit(outlined, rect)
    target.blit(base, rect)
    return rect


def format_number(value: int) -> str:
    """``1234567`` -> ``1 234 567`` (thin spaces keep it readable)."""
    return f"{int(value):,}".replace(",", " ")


def format_time(seconds: float) -> str:
    total = max(0.0, float(seconds))
    minutes = int(total // 60)
    secs = int(total % 60)
    return f"{minutes:02d}:{secs:02d}"


__all__ = [
    "scale_color",
    "mix_color",
    "glow_surface",
    "draw_glow",
    "draw_glow_circle",
    "rounded_panel",
    "gradient_bar",
    "ring",
    "polyline",
    "text",
    "text_outlined",
    "format_number",
    "format_time",
]
