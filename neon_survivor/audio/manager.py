"""Audio manager: owns the mixer, caches sounds and drives the music.

The manager is fully defensive: if the machine has no audio device (CI
containers, headless servers, RDP without audio redirection) every call
becomes a no-op instead of raising.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional, Tuple

from neon_survivor.audio import music as music_mod
from neon_survivor.audio import sfx as sfx_mod
from neon_survivor.audio import synth
from neon_survivor.config import (
    AUDIO_BUFFER,
    AUDIO_CHANNELS,
    AUDIO_SAMPLE_RATE,
    MASTER_VOLUME,
    MUSIC_VOLUME,
    SFX_VOLUME,
    VOICE_LIMIT,
)


class AudioManager:
    """Lazily builds and plays every sound the game needs."""

    def __init__(
        self,
        master_volume: float = MASTER_VOLUME,
        music_volume: float = MUSIC_VOLUME,
        sfx_volume: float = SFX_VOLUME,
    ) -> None:
        self.available = False
        self.error: Optional[str] = None
        self.master_volume = master_volume
        self.music_volume = music_volume
        self.sfx_volume = sfx_volume
        self.muted = False

        self._sounds: Dict[str, object] = {}
        self._music: Dict[str, object] = {}
        self._music_threads: Dict[str, threading.Thread] = {}
        self._current_channel = None
        self._current_music_key: Optional[str] = None
        self._pending_music: Optional[str] = None
        self._active_sounds: List = []
        self._enabled = True
        self._init_mixer()

    # -- setup -----------------------------------------------------------
    def _init_mixer(self) -> None:
        try:
            import pygame

            pygame.mixer.init(
                frequency=AUDIO_SAMPLE_RATE,
                size=-16,
                channels=AUDIO_CHANNELS,
                buffer=AUDIO_BUFFER,
            )
            pygame.mixer.set_num_channels(max(8, VOICE_LIMIT))
            self.available = True
        except Exception as exc:  # pragma: no cover - depends on the machine
            self.available = False
            self.error = str(exc)

    # -- volumes ---------------------------------------------------------
    def set_master_volume(self, value: float) -> None:
        self.master_volume = max(0.0, min(1.0, value))
        self._apply_music_volume()

    def set_music_volume(self, value: float) -> None:
        self.music_volume = max(0.0, min(1.0, value))
        self._apply_music_volume()

    def set_sfx_volume(self, value: float) -> None:
        self.sfx_volume = max(0.0, min(1.0, value))

    def set_muted(self, muted: bool) -> None:
        self.muted = bool(muted)
        self._apply_music_volume()

    def _apply_music_volume(self) -> None:
        if self._current_channel is not None:
            try:
                volume = 0.0 if self.muted else self.music_volume * self.master_volume
                self._current_channel.set_volume(volume)
            except Exception:
                pass

    # -- building --------------------------------------------------------
    def _make_sound(self, buffer: List[float]):
        import pygame

        data = synth.to_pcm16(buffer) if AUDIO_CHANNELS == 1 else synth.to_stereo(buffer)
        return pygame.mixer.Sound(buffer=data)

    def preload_sfx(self, names: Optional[List[str]] = None) -> int:
        """Build the requested effects up-front; returns how many are ready."""
        if not self.available:
            return 0
        built = 0
        for name in names or sfx_mod.available_sounds():
            if name in self._sounds:
                built += 1
                continue
            builder, _ = sfx_mod.SFX_RECIPES[name]
            try:
                self._sounds[name] = self._make_sound(builder())
                built += 1
            except Exception:
                continue
        return built

    def preload_music(self, key: str, blocking: bool = True) -> bool:
        """Render a music track into the cache.

        Rendering a track takes well over a second of pure Python, which is
        far too long to block the first frame of the title screen, so
        ``blocking=False`` hands the work to a daemon thread and returns
        immediately.  :meth:`play_music` uses that path and starts the track
        as soon as it lands in the cache.
        """
        if not self.available or key not in music_mod.TRACKS:
            return False
        if key in self._music:
            return True
        if not blocking:
            self._render_music_async(key)
            return key in self._music or self._music_threads.get(key) is not None
        return self._render_music_sync(key)

    def _render_music_sync(self, key: str) -> bool:
        try:
            buffer = music_mod.render_track(music_mod.TRACKS[key])
            self._music[key] = self._make_sound(buffer)
            return True
        except Exception:
            return False

    def _render_music_async(self, key: str) -> bool:
        """Start (once) a daemon thread that renders *key* in the background."""
        thread = self._music_threads.get(key)
        if thread is not None and thread.is_alive():
            return True
        if key in self._music:
            return True

        def worker() -> None:
            built = self._render_music_sync(key)
            if built and self._pending_music == key and not self.muted:
                # The track we were still waiting for has arrived: start it.
                self._start_music(key, fade_ms=0)

        thread = threading.Thread(target=worker, name=f"music-{key}", daemon=True)
        self._music_threads[key] = thread
        thread.start()
        return True

    # -- playback --------------------------------------------------------
    def play(
        self,
        name: str,
        volume: float = 1.0,
        pitch: float = 1.0,
    ) -> bool:
        """Play a one-shot effect.  Returns ``True`` if it was started."""
        if not self.available or self.muted or not self._enabled:
            return False
        sound = self._sounds.get(name)
        if sound is None:
            if name not in sfx_mod.SFX_RECIPES:
                return False
            builder, _ = sfx_mod.SFX_RECIPES[name]
            try:
                sound = self._make_sound(builder())
            except Exception:
                return False
            self._sounds[name] = sound

        try:
            if pitch != 1.0:
                sound = sound.copy()
                sound.set_pitch(max(0.1, min(3.0, pitch)))
            channel = sound.play()
            if channel is None:
                return False
            channel.set_volume(
                max(0.0, min(1.0, volume * self.sfx_volume * self.master_volume))
            )
            # Keep the list from growing forever on long sessions.
            if len(self._active_sounds) > 64:
                self._active_sounds = [c for c in self._active_sounds if c and c.get_busy()]
            self._active_sounds.append(channel)
            return True
        except Exception:
            return False

    def play_random(self, names: List[str], volume: float = 1.0, pitch_jitter: float = 0.08) -> bool:
        """Play one of *names* at a slightly randomised pitch."""
        if not names:
            return False
        import random

        name = random.choice(names)
        jitter = 1.0 + random.uniform(-pitch_jitter, pitch_jitter)
        return self.play(name, volume=volume, pitch=jitter)

    # -- music -----------------------------------------------------------
    def play_music(self, key: str, fade_ms: int = 900) -> bool:
        """Start (or switch to) a looping track without blocking the frame."""
        if not self.available or key not in music_mod.TRACKS:
            return False
        if self._current_music_key == key and self._current_channel is not None:
            if self._current_channel.get_busy():
                self._pending_music = None
                return True
        self._pending_music = key
        if key in self._music:
            return self._start_music(key, fade_ms)
        # Still rendering: a daemon thread will start it when it is ready.
        self._render_music_async(key)
        return True

    def _start_music(self, key: str, fade_ms: int = 900) -> bool:
        sound = self._music.get(key)
        if sound is None:
            return False
        try:
            if self._current_channel is not None:
                self._current_channel.fadeout(max(0, fade_ms))
            self._current_channel = sound.play(loops=-1)
            self._current_music_key = key
            self._pending_music = None
            self._apply_music_volume()
            return True
        except Exception:
            self._current_channel = None
            self._current_music_key = None
            return False

    def stop_music(self, fade_ms: int = 600) -> None:
        self._pending_music = None
        if self._current_channel is not None:
            try:
                self._current_channel.fadeout(max(0, fade_ms))
            except Exception:
                pass
        self._current_channel = None
        self._current_music_key = None

    def pause_music(self) -> None:
        if self._current_channel is not None:
            try:
                self._current_channel.pause()
            except Exception:
                pass

    def unpause_music(self) -> None:
        if self._current_channel is not None:
            try:
                self._current_channel.unpause()
            except Exception:
                pass

    @property
    def current_music(self) -> Optional[str]:
        return self._current_music_key

    # -- housekeeping ----------------------------------------------------
    def preload_core(self) -> int:
        """Build the effects needed on the very first frames."""
        core = [
            "shoot", "shoot_heavy", "hit", "enemy_die", "player_hurt",
            "pickup", "pickup_health", "pickup_power", "ui_move",
            "ui_select", "ui_back", "wave_start", "game_over",
        ]
        return self.preload_sfx(core)

    def shutdown(self) -> None:
        self.stop_music(0)
        self._sounds.clear()
        self._music.clear()

    def status(self) -> Tuple[bool, Optional[str], Optional[str]]:
        return (self.available, self.error, self._current_music_key)


__all__ = ["AudioManager"]
