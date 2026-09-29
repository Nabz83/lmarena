"""Command line entry point: ``python -m neon_survivor``."""

from __future__ import annotations

import argparse
import os
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neon-survivor",
        description="Neon Survivor — a 2D action/survival game.",
    )
    parser.add_argument(
        "--fullscreen", action="store_true", help="start in fullscreen mode"
    )
    parser.add_argument(
        "--windowed", action="store_true", help="force a windowed start"
    )
    parser.add_argument(
        "--no-sound", action="store_true", help="disable all audio output"
    )
    parser.add_argument(
        "--fps", action="store_true", help="show the frame counter in game"
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=None,
        metavar="N",
        help="quit after N frames (used by the smoke tests)",
    )
    parser.add_argument(
        "--version", action="store_true", help="print the version and exit"
    )
    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)

    if args.version:
        from neon_survivor.config import GAME_TITLE, VERSION

        # A windowed (console-less) frozen build has ``sys.stdout is None``.
        if sys.stdout is not None:
            print(f"{GAME_TITLE} {VERSION}")
        return 0

    # Import late so ``--version`` works even without a display.
    from neon_survivor.app import App
    from neon_survivor.settings import Settings

    settings = Settings.load()
    if args.fullscreen:
        settings.fullscreen = True
    if args.windowed:
        settings.fullscreen = False
    if args.fps:
        settings.show_fps = True

    if args.no_sound:
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    app = App(settings)
    if args.no_sound:
        app.audio.set_muted(True)

    app.run(max_frames=args.frames)
    return 0


if __name__ == "__main__":
    sys.exit(main())
