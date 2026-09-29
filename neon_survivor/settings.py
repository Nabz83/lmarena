"""Persistent user data: high score, options and stats.

The save file lives in a per-user data directory (never next to the source
tree) and degrades gracefully to a temporary directory if the profile is not
writable — important for a one-file PyInstaller build running from
``Program Files``.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict

from neon_survivor.config import (
    FULLSCREEN_DEFAULT,
    GAME_SLUG,
    MASTER_VOLUME,
    MUSIC_VOLUME,
    SAVE_FILE_NAME,
    SFX_VOLUME,
    VERSION,
)


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def user_data_dir(app_name: str = GAME_SLUG) -> Path:
    """Return a writable per-user directory, creating it if needed."""
    candidates = []
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        if base:
            candidates.append(Path(base) / app_name)
    elif sys.platform == "darwin":
        candidates.append(Path.home() / "Library" / "Application Support" / app_name)
    else:
        base = os.environ.get("XDG_DATA_HOME")
        candidates.append(
            (Path(base) if base else Path.home() / ".local" / "share") / app_name
        )
    candidates.append(Path(tempfile.gettempdir()) / app_name)

    for path in candidates:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return path
        except OSError:
            continue
    # Last resort: temp dir is virtually always writable.
    fallback = Path(tempfile.gettempdir()) / app_name
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def save_path(app_name: str = GAME_SLUG) -> Path:
    return user_data_dir(app_name) / SAVE_FILE_NAME


@dataclass
class Settings:
    """Everything persisted between two runs of the game."""

    high_score: int = 0
    best_wave: int = 1
    best_time: float = 0.0
    total_kills: int = 0
    total_runs: int = 0
    music_volume: float = MUSIC_VOLUME
    sfx_volume: float = SFX_VOLUME
    master_volume: float = MASTER_VOLUME
    fullscreen: bool = FULLSCREEN_DEFAULT
    show_fps: bool = False
    screen_shake: float = 1.0
    version: str = VERSION
    extra: Dict[str, Any] = field(default_factory=dict)

    # -- serialisation ---------------------------------------------------
    @classmethod
    def field_names(cls) -> tuple:
        return tuple(f.name for f in fields(cls))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Settings":
        known = set(cls.field_names())
        kwargs = {k: v for k, v in data.items() if k in known}
        instance = cls(**kwargs)
        instance.extra = {k: v for k, v in data.items() if k not in known}
        instance.sanitize()
        return instance

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        extra = data.pop("extra", {}) or {}
        data.update(extra)
        return data

    # -- validation ------------------------------------------------------
    def sanitize(self) -> None:
        """Coerce every field to a sane, type-safe value."""
        self.high_score = max(0, _as_int(self.high_score, 0))
        self.best_wave = max(1, _as_int(self.best_wave, 1))
        self.best_time = max(0.0, _as_float(self.best_time, 0.0))
        self.total_kills = max(0, _as_int(self.total_kills, 0))
        self.total_runs = max(0, _as_int(self.total_runs, 0))
        self.music_volume = _as_float(self.music_volume, MUSIC_VOLUME)
        self.sfx_volume = _as_float(self.sfx_volume, SFX_VOLUME)
        self.master_volume = _as_float(self.master_volume, MASTER_VOLUME)
        self.music_volume = min(1.0, max(0.0, self.music_volume))
        self.sfx_volume = min(1.0, max(0.0, self.sfx_volume))
        self.master_volume = min(1.0, max(0.0, self.master_volume))
        self.fullscreen = bool(self.fullscreen)
        self.show_fps = bool(self.show_fps)
        self.screen_shake = min(1.0, max(0.0, _as_float(self.screen_shake, 1.0)))
        if not isinstance(self.extra, dict):
            self.extra = {}

    # -- persistence -----------------------------------------------------
    @classmethod
    def load(cls, path: Path | str | None = None) -> "Settings":
        target = Path(path) if path is not None else save_path()
        try:
            raw = target.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("settings root must be an object")
            return cls.from_dict(data)
        except (OSError, ValueError, TypeError):
            # A missing or corrupted save simply starts a fresh profile.
            return cls()

    def save(self, path: Path | str | None = None) -> bool:
        """Atomically write the settings.  Returns ``True`` on success."""
        target = Path(path) if path is not None else save_path()
        self.sanitize()
        tmp = target.with_suffix(target.suffix + ".tmp")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(
                json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
            )
            os.replace(tmp, target)
            return True
        except OSError:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            return False

    # -- gameplay helpers ------------------------------------------------
    def record_run(self, score: int, wave: int, duration: float, kills: int) -> bool:
        """Store the outcome of a run; returns ``True`` if it is a record."""
        is_record = score > self.high_score
        self.high_score = max(self.high_score, int(score))
        self.best_wave = max(self.best_wave, int(wave))
        self.best_time = max(self.best_time, float(duration))
        self.total_kills = max(0, self.total_kills + int(kills))
        self.total_runs += 1
        return is_record


def _as_int(value: Any, default: int) -> int:
    try:
        if isinstance(value, bool):
            return int(value)
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        if isinstance(value, bool):
            return float(value)
        result = float(value)
        if result != result or result in (float("inf"), float("-inf")):
            return default
        return result
    except (TypeError, ValueError):
        return default


__all__ = ["Settings", "save_path", "user_data_dir"]
