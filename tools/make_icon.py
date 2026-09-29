"""Generate the application icon.

The repository deliberately ships **no binary asset** — the icon is drawn with
pygame from the same palette the game uses and packed into a multi-resolution
``.ico`` by a small pure-Python writer, so the Windows build is reproducible
from source alone.

Usage::

    python tools/make_icon.py [output_dir]

It writes ``icon.ico`` (16/24/32/48/64/128/256 px) and ``icon.png`` (256 px)
into ``output_dir`` (``build_assets`` by default) and prints the paths.
"""

from __future__ import annotations

import math
import struct
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def _palette() -> Dict[str, Tuple[int, ...]]:
    from neon_survivor.ui.theme import Palette

    return {
        "void": tuple(Palette.VOID),
        "player": tuple(Palette.PLAYER),
        "cyan": tuple(Palette.CYAN),
        "red": tuple(Palette.RED),
        "text": tuple(Palette.TEXT),
    }


def render(size: int):
    """Draw the icon at *size* pixels and return an RGBA surface."""
    import pygame

    from neon_survivor.gfx.draw import draw_glow

    colors = _palette()
    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    centre = size / 2.0

    # Dark plate with a soft neon rim.
    pygame.draw.circle(surface, colors["void"], (centre, centre), centre - 0.5)
    draw_glow(
        surface, (centre, centre), centre - 0.5, colors["cyan"], 0.9, 0.75
    )
    pygame.draw.circle(
        surface,
        colors["cyan"],
        (centre, centre),
        centre - 0.5,
        max(1, size // 24),
    )

    # Three orbiting shards, echoing the enemy triangles.
    orbit = centre * 0.58
    for index, angle in enumerate((30.0, 150.0, 270.0)):
        theta = math.radians(angle)
        px = centre + math.cos(theta) * orbit
        py = centre + math.sin(theta) * orbit
        radius = max(1.5, size * 0.12)
        points = [
            (px + radius * 1.15, py),
            (px - radius * 0.85, py - radius),
            (px - radius * 0.85, py + radius),
        ]
        color = colors["red"] if index == 0 else colors["cyan"]
        pygame.draw.polygon(surface, color, points)

    # Player ship in the middle: a clean arrowhead pointing up-right, the
    # same direction the crosshair sits at while the mouse is held.
    dx, dy = math.sqrt(0.5), -math.sqrt(0.5)      # forward
    px, py = -dy, dx                              # perpendicular
    head = centre * 0.70
    half = centre * 0.26
    apex = (centre + dx * head, centre + dy * head)
    neck = (centre - dx * head * 0.34, centre - dy * head * 0.34)
    arrow = [
        apex,
        (neck[0] + px * half, neck[1] + py * half),
        (neck[0] - px * half, neck[1] - py * half),
    ]
    pygame.draw.polygon(surface, colors["player"], arrow)
    pygame.draw.polygon(surface, colors["text"], arrow, max(1, size // 48))
    return surface


def _raw_rgba(surface) -> bytes:
    """Return the raw top-down RGBA bytes of *surface*."""
    import pygame

    # ``pygame.image.tobytes`` avoids depending on numpy (which ``surfarray``
    # would require) and is available since pygame-ce 2.2.
    return pygame.image.tobytes(surface, "RGBA")


def _bmp_entry(surface) -> bytes:
    """Pack an ARGB surface as a 32-bit bottom-up DIB with an AND mask."""
    width, height = surface.get_size()
    raw = _raw_rgba(surface)

    header = struct.pack(
        "<IiiHHIIiiII",
        40,                 # biSize
        width,              # biWidth
        height * 2,         # biHeight: XOR image followed by the AND mask
        1,                  # biPlanes
        32,                 # biBitCount
        0,                  # biCompression = BI_RGB
        width * height * 4,
        0, 0, 0, 0,
    )

    # DIB rows are bottom-up and stored as BGRA.
    xor = bytearray()
    for y in range(height - 1, -1, -1):
        row = raw[y * width * 4:(y + 1) * width * 4]
        for x in range(width):
            r, g, b, a = row[x * 4:x * 4 + 4]
            xor += bytes((b, g, r, a))

    mask_stride = ((width + 31) // 32) * 4
    mask = bytes(mask_stride * height)
    return header + bytes(xor) + mask


def build_ico(path: Path) -> Path:
    """Render every size and write a multi-resolution ``.ico`` file."""
    images: List[Tuple[int, bytes]] = [(size, _bmp_entry(render(size))) for size in ICON_SIZES]

    count = len(images)
    offset = 6 + 16 * count
    directory = bytearray(struct.pack("<HHH", 0, 1, count))
    payload = bytearray()
    for size, data in images:
        directory += struct.pack(
            "<BBBBHHII",
            size if size < 256 else 0,
            size if size < 256 else 0,
            0, 0, 1, 32, len(data), offset,
        )
        payload += data
        offset += len(data)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(directory) + bytes(payload))
    return path


def main(argv: Sequence[str]) -> int:
    out_dir = Path(argv[1]) if len(argv) > 1 else ROOT / "build_assets"
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame

    pygame.init()
    pygame.display.set_mode((8, 8))
    try:
        ico = build_ico(out_dir / "icon.ico")
        out_dir.mkdir(parents=True, exist_ok=True)
        pygame.image.save(render(256), str(out_dir / "icon.png"))
    finally:
        pygame.quit()
    print(f"icon: {ico}")
    print(f"icon: {out_dir / 'icon.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
