"""Reusable UI widgets: menu lists, sliders, banners and buttons."""

from __future__ import annotations

import math
from typing import Callable, List, Optional, Sequence, Tuple

import pygame

from neon_survivor.gfx import draw, fonts
from neon_survivor.ui.theme import Metrics, Palette, with_alpha

RGB = Tuple[int, int, int]


class MenuItem:
    """One selectable row of a vertical menu."""

    def __init__(
        self,
        label: str,
        action: str = "",
        enabled: bool = True,
        value_provider: Optional[Callable[[], str]] = None,
        hint: str = "",
        danger: bool = False,
        bar_provider: Optional[Callable[[], float]] = None,
    ) -> None:
        self.label = label
        self.action = action or label.lower().replace(" ", "_")
        self.enabled = enabled
        self.value_provider = value_provider
        self.hint = hint
        self.danger = danger
        #: When set, a horizontal gauge is drawn after the label.
        self.bar_provider = bar_provider
        self.selected = False
        self.hover_t = 0.0

    @property
    def text(self) -> str:
        if self.value_provider is not None:
            try:
                value = self.value_provider()
            except Exception:
                value = ""
            return f"{self.label}   {value}"
        return self.label


class Menu:
    """Keyboard/mouse driven vertical menu."""

    def __init__(self, items: Sequence[MenuItem], on_change=None, on_activate=None) -> None:
        self.items: List[MenuItem] = list(items)
        self.index = 0
        self.time = 0.0
        self.on_change = on_change
        self.on_activate = on_activate
        self._rows: List[pygame.Rect] = []
        self._ensure_selection()

    # -- model -----------------------------------------------------------
    def _ensure_selection(self) -> None:
        if not self.items:
            return
        if not self.items[self.index].enabled:
            for i, item in enumerate(self.items):
                if item.enabled:
                    self.index = i
                    return

    def set_items(self, items: Sequence[MenuItem]) -> None:
        self.items = list(items)
        self.index = min(self.index, max(0, len(self.items) - 1))
        self._ensure_selection()

    def _move(self, delta: int) -> None:
        if not self.items:
            return
        for _ in range(len(self.items)):
            self.index = (self.index + delta) % len(self.items)
            if self.items[self.index].enabled:
                self._changed()
                return

    def _changed(self) -> None:
        for i, item in enumerate(self.items):
            item.selected = i == self.index
        if self.on_change is not None:
            self.on_change(self.items[self.index])

    def move_up(self) -> None:
        self._move(-1)

    def move_down(self) -> None:
        self._move(1)

    def activate(self) -> Optional[MenuItem]:
        if not self.items:
            return None
        item = self.items[self.index]
        if not item.enabled:
            return None
        if self.on_activate is not None:
            self.on_activate(item)
        return item

    def adjust(self, direction: int) -> Optional[MenuItem]:
        """Notify the owner that the selected slider moved."""
        item = self.items[self.index] if self.items else None
        if item is not None and self.on_change is not None:
            self.on_change(item)
        return item

    @property
    def current(self) -> Optional[MenuItem]:
        return self.items[self.index] if self.items else None

    # -- input -----------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> Optional[MenuItem]:
        if event.type == pygame.MOUSEMOTION and self._rows:
            for i, row in enumerate(self._rows):
                if row.collidepoint(event.pos) and self.items[i].enabled:
                    if self.index != i:
                        self.index = i
                        self._changed()
                    return self.items[i]
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self._rows:
            for i, row in enumerate(self._rows):
                if row.collidepoint(event.pos):
                    if self.items[i].enabled:
                        self.index = i
                        self._changed()
                        return self.items[i]
        return None

    # -- drawing ---------------------------------------------------------
    def draw(
        self,
        target: pygame.Surface,
        center_x: float,
        center_y: float,
        width: float,
        row_height: int = 46,
        size: int = fonts.SIZE_MEDIUM,
    ) -> None:
        self.time += 1 / 60.0
        self._rows.clear()
        count = len(self.items)
        if count == 0:
            return
        total = count * row_height
        top = center_y - total / 2.0
        for i, item in enumerate(self.items):
            y = top + i * row_height
            row = pygame.Rect(int(center_x - width / 2), int(y), int(width), int(row_height - 6))
            self._rows.append(row)
            target_hover = 1.0 if item.selected else 0.0
            item.hover_t += (target_hover - item.hover_t) * 0.25
            self._draw_row(target, item, row, size)

    def _draw_row(self, target: pygame.Surface, item: MenuItem, row: pygame.Rect, size: int) -> None:
        t = item.hover_t
        if t > 0.02:
            glow = draw.mix_color(Palette.PANEL, Palette.PURPLE, t * 0.7)
            draw.rounded_panel(
                target, row, glow, alpha=int(200 + 40 * t),
                border=draw.mix_color(Palette.PANEL_LIGHT, Palette.CYAN, t),
                border_width=2, radius=Metrics.RADIUS,
            )
            # Selection marker.
            slide = (1.0 - t) * 14.0
            draw.text(
                target, ">", (row.left + 14 - slide, row.centery),
                size, Palette.CYAN, align="left", valign="center",
            )

        base = Palette.TEXT if item.enabled else Palette.TEXT_FAINT
        if item.danger and item.enabled:
            base = draw.mix_color(Palette.TEXT, Palette.RED, 0.45)
        if item.selected and item.enabled:
            base = draw.mix_color(base, Palette.TEXT, t)

        if item.bar_provider is not None:
            try:
                ratio = float(item.bar_provider())
            except Exception:
                ratio = 0.0
            label = item.label
            draw.text(
                target, label, (row.left + 20, row.centery), size, base,
                align="left", valign="center",
            )
            bar = pygame.Rect(0, 0, int(row.width * 0.30), 8)
            bar.midleft = (int(row.centerx - row.width * 0.12), row.centery)
            gauge_color = Palette.CYAN if item.enabled else Palette.TEXT_FAINT
            draw_slider(target, bar, ratio, gauge_color)
            if item.value_provider is not None:
                draw.text(
                    target, item.value_provider(), (row.right - 20, row.centery),
                    size, base, align="right", valign="center",
                )
        else:
            draw.text(
                target, item.text, (row.centerx, row.centery), size, base,
                align="center", valign="center",
            )
        if item.hint and item.selected:
            draw.text(
                target, item.hint, (row.centerx, row.bottom + 16), fonts.SIZE_TINY,
                Palette.TEXT_DIM, align="center",
            )


# --------------------------------------------------------------------------
# Banner
# --------------------------------------------------------------------------
class Banner:
    """The big centred "WAVE 3" / "BOSS INCOMING" announcement."""

    def __init__(self) -> None:
        self.text = ""
        self.subtitle = ""
        self.color = Palette.CYAN
        self.time = 0.0
        self.duration = 0.0
        self.active = False

    def show(self, text: str, subtitle: str = "", color: RGB = Palette.CYAN, duration: float = 2.6) -> None:
        self.text = text
        self.subtitle = subtitle
        self.color = color
        self.duration = duration
        self.time = duration
        self.active = True

    def hide(self) -> None:
        self.active = False
        self.time = 0.0

    def update(self, dt: float) -> None:
        if self.active:
            self.time = max(0.0, self.time - dt)
            if self.time <= 0.0:
                self.active = False

    @property
    def progress(self) -> float:
        if self.duration <= 0:
            return 0.0
        return max(0.0, min(1.0, self.time / self.duration))

    def draw(self, target: pygame.Surface) -> None:
        if not self.active or not self.text:
            return
        width, height = target.get_size()
        t = self.progress
        # Slide in, hold, fade out.
        appear = min(1.0, (1.0 - t) * 6.0)
        offset = (1.0 - appear) * 40.0
        alpha = min(1.0, t * 4.0) * appear

        y = height * 0.28 + offset
        # Backdrop band.
        band_h = 86 if self.subtitle else 66
        band = pygame.Rect(0, int(y - band_h / 2), width, band_h)
        overlay = pygame.Surface(band.size, pygame.SRCALPHA)
        pygame.draw.rect(overlay, (0, 0, 0, int(120 * alpha)), overlay.get_rect())
        target.blit(overlay, band.topleft)
        pygame.draw.line(
            target, with_alpha(self.color, alpha),
            (0, band.top), (width, band.top), 2,
        )
        pygame.draw.line(
            target, with_alpha(self.color, alpha * 0.6),
            (0, band.bottom - 1), (width, band.bottom - 1), 2,
        )

        title_color = draw.mix_color(self.color, (255, 255, 255), 0.35)
        font = fonts.get_font(fonts.SIZE_HUGE, True)
        surface = font.render(self.text, True, title_color)
        surface = surface.copy()
        surface.set_alpha(int(255 * alpha))
        target.blit(surface, surface.get_rect(center=(width // 2, int(y - (10 if self.subtitle else 0)))))

        if self.subtitle:
            draw.text(
                target, self.subtitle, (width // 2, int(y + 26)),
                fonts.SIZE_BODY, with_alpha(Palette.TEXT_DIM, alpha),
                align="center", valign="center",
            )


# --------------------------------------------------------------------------
# Volume slider
# --------------------------------------------------------------------------
def draw_slider(
    target: pygame.Surface,
    rect: pygame.Rect,
    ratio: float,
    color: RGB = Palette.CYAN,
) -> None:
    ratio = max(0.0, min(1.0, ratio))
    draw.rounded_panel(target, rect, Palette.VOID, alpha=210, border=Palette.GRID, border_width=1, radius=6)
    inner = rect.inflate(-6, -6)
    if ratio > 0.0:
        fill = pygame.Rect(inner.left, inner.top, int(inner.width * ratio), inner.height)
        draw.gradient_bar(target, fill, 1.0, (color, draw.mix_color(color, (255, 255, 255), 0.5)))
    knob_x = inner.left + int(inner.width * ratio)
    pygame.draw.circle(target, Palette.TEXT, (knob_x, rect.centery), 7)
    pygame.draw.circle(target, color, (knob_x, rect.centery), 4)


# --------------------------------------------------------------------------
# Logo
# --------------------------------------------------------------------------
def draw_logo(target: pygame.Surface, cx: float, cy: float, time: float, scale: float = 1.0) -> None:
    """The animated title logo."""
    width, _ = target.get_size()
    size = int(fonts.SIZE_TITLE * scale)
    font = fonts.get_font(size, True)
    title = "NEON SURVIVOR"
    surface = font.render(title, True, Palette.TEXT)
    outline = font.render(title, True, Palette.MAGENTA, 4)
    rect = surface.get_rect(center=(int(cx), int(cy)))

    draw.draw_glow(target, (cx, cy), rect.width * 0.62, Palette.MAGENTA, 0.45 + 0.12 * math.sin(time * 1.6))
    target.blit(outline, rect)
    target.blit(surface, rect)

    # Underline sweep.
    y = rect.bottom + 14
    grad_w = int(rect.width * 1.05)
    for i in range(grad_w):
        t = i / max(1, grad_w - 1)
        color = draw.mix_color(Palette.CYAN, Palette.MAGENTA, t)
        pygame.draw.line(
            target, color,
            (rect.centerx - grad_w // 2 + i, y),
            (rect.centerx - grad_w // 2 + i, y + 3),
        )
    return None


__all__ = ["MenuItem", "Menu", "Banner", "draw_slider", "draw_logo"]
