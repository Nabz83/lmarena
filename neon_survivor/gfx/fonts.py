"""Font loading and caching.

The game uses the font bundled with pygame (``freesansbold``), which ships
with the library itself — no third-party font file has to be redistributed.
"""

from __future__ import annotations

from typing import Dict, Tuple

import pygame

#: Logical size -> cached pygame font.
_CACHE: Dict[Tuple[int, bool], pygame.font.Font] = {}

#: Named sizes used across the UI so the layout stays consistent.
SIZE_TINY = 13
SIZE_SMALL = 17
SIZE_BODY = 20
SIZE_MEDIUM = 26
SIZE_LARGE = 38
SIZE_HUGE = 62
SIZE_TITLE = 88


def _font_usable(font: "pygame.font.Font | None") -> bool:
    """Cheap validity probe for a cached font.

    ``pygame.quit()`` invalidates every :class:`pygame.font.Font`; using one
    afterwards raises ``Invalid font (font module quit since font created)``.
    ``App.shutdown()`` calls ``pygame.quit()``, so anything that draws later
    in the same process (tests, a second window, a crash handler) would
    otherwise blow up.
    """
    if font is None:
        return False
    try:
        font.get_height()
    except Exception:
        return False
    return True


def get_font(size: int, bold: bool = True) -> pygame.font.Font:
    """Return a cached font of the requested pixel *size*."""
    key = (int(size), bool(bold))
    font = _CACHE.get(key)
    if _font_usable(font):
        return font  # type: ignore[return-value]
    if not pygame.font.get_init():
        # The module is down: restart it and rebuild the cache from scratch.
        _CACHE.clear()
        pygame.font.init()
    font = pygame.font.Font(None, int(size))
    font.set_bold(bool(bold))
    _CACHE[key] = font
    return font


def clear_cache() -> None:
    _CACHE.clear()


def measure(text: str, size: int, bold: bool = True) -> Tuple[int, int]:
    """Width/height of *text* rendered at *size*."""
    font = get_font(size, bold)
    return font.size(text)


__all__ = [
    "get_font",
    "clear_cache",
    "measure",
    "SIZE_TINY",
    "SIZE_SMALL",
    "SIZE_BODY",
    "SIZE_MEDIUM",
    "SIZE_LARGE",
    "SIZE_HUGE",
    "SIZE_TITLE",
]
