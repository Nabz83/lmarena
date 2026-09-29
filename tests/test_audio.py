"""Tests for the procedural audio layer.

The synthesis is pure Python, so it is fully testable without a mixer.
"""

from __future__ import annotations


import pytest

from neon_survivor.audio import music as music_mod
from neon_survivor.audio import sfx as sfx_mod
from neon_survivor.audio import synth


class TestNoteNames:
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("A4", 440.0),
            ("C4", 261.63),
            ("E2", 82.41),
            ("C#3", 138.59),
            ("Bb4", 466.16),
            ("G5", 783.99),
            ("C1", 32.70),
        ],
    )
    def test_named_notes(self, name, expected):
        assert synth.note_to_freq(name) == pytest.approx(expected, rel=0.01)

    def test_midi_numbers(self):
        assert synth.note_to_freq(69) == pytest.approx(440.0, abs=0.01)
        assert synth.note_to_freq(60) == pytest.approx(261.63, abs=0.01)
        assert synth.midi_to_freq(69) == pytest.approx(440.0, abs=0.01)

    def test_garbage_input_is_safe(self):
        assert synth.note_to_freq("") == 0.0
        assert synth.note_to_freq("H#9") == 0.0  # unknown letter
        assert synth.note_to_freq(-1) == 0.0

    def test_default_octave_is_four(self):
        assert synth.note_to_freq("A") == pytest.approx(440.0)


class TestWaveTables:
    @pytest.mark.parametrize("wave", ["sine", "square", "saw", "triangle", "noise"])
    def test_table_length_and_range(self, wave):
        table = synth.wave_table(wave)
        assert len(table) == synth.TABLE_SIZE
        assert all(-1.01 <= v <= 1.01 for v in table)

    def test_tables_are_cached(self):
        assert synth.wave_table("sine") is synth.wave_table("sine")

    def test_pulse_duty_changes_the_shape(self):
        narrow = synth.wave_table("pulse", 0.25)
        wide = synth.wave_table("pulse", 0.75)
        assert narrow != wide


class TestEnvelopes:
    def test_adsr_bounds(self):
        env = synth.adsr(1000, 0.1, 0.2, 0.5, 0.3)
        assert len(env) == 1000
        assert all(0.0 <= v <= 1.0 for v in env)
        assert env[0] == pytest.approx(0.0, abs=0.05)
        assert max(env) <= 1.0

    def test_adsr_decreases_to_zero(self):
        env = synth.adsr(1000, 0.05, 0.1, 0.6, 0.5)
        assert env[-1] < 0.02

    def test_exp_decay(self):
        env = synth.exp_decay(100, 5.0)
        assert env[0] == pytest.approx(1.0)
        assert env[-1] < env[0]


class TestRendering:
    def test_tone_length_matches_duration(self):
        buffer = synth.render_tone(440.0, 0.25, sample_rate=8000)
        assert len(buffer) == 2000

    def test_tone_is_bounded(self):
        buffer = synth.render_tone(440.0, 0.1, amplitude=0.5, sample_rate=8000)
        assert all(-0.51 <= v <= 0.51 for v in buffer)

    def test_decay_reduces_the_tail(self):
        rate = 8000
        flat = synth.render_tone(440.0, 0.2, decay=0.0, sample_rate=rate)
        faded = synth.render_tone(440.0, 0.2, decay=8.0, sample_rate=rate)
        tail = len(flat) // 4
        rms_flat = sum(v * v for v in flat[-tail:]) / tail
        rms_faded = sum(v * v for v in faded[-tail:]) / tail
        assert rms_faded < rms_flat * 0.05

    def test_sweep_moves_towards_the_target(self):
        buffer = synth.render_sweep(100.0, 800.0, 0.2, sample_rate=8000)
        head = sum(abs(v) for v in buffer[:200]) / 200
        tail = sum(abs(v) for v in buffer[-200:]) / 200
        assert tail < head

    def test_noise_is_randomised(self):
        a = synth.render_noise(0.1, seed=1)
        b = synth.render_noise(0.1, seed=2)
        assert a != b

    def test_noise_is_deterministic_per_seed(self):
        assert synth.render_noise(0.1, seed=3) == synth.render_noise(0.1, seed=3)


class TestBufferMaths:
    def test_mix_pads_to_the_longest(self):
        mixed = synth.mix([1.0, 1.0], [0.5])
        assert mixed == [1.5, 1.0]

    def test_overlay_offsets(self):
        base = [0.0] * 4
        synth.overlay(base, [1.0, 1.0], 2)
        assert base == [0.0, 0.0, 1.0, 1.0]

    def test_overlay_clips_at_the_edges(self):
        base = [0.0] * 2
        synth.overlay(base, [1.0, 1.0, 1.0], 1)
        assert base == [0.0, 1.0]

    def test_overlay_with_gain(self):
        base = [0.0] * 2
        synth.overlay(base, [1.0], 0, gain=0.25)
        assert base[0] == pytest.approx(0.25)

    def test_normalize_scales_to_peak(self):
        out = synth.normalize([0.5, -1.0, 0.25], peak=1.0)
        assert max(abs(v) for v in out) == pytest.approx(1.0)

    def test_normalize_of_silence_is_safe(self):
        assert synth.normalize([0.0, 0.0]) == [0.0, 0.0]

    def test_soft_clip_never_exceeds_one(self):
        out = synth.soft_clip([5.0, -5.0, 0.5], drive=2.0)
        assert all(-1.0 <= v <= 1.0 for v in out)

    def test_fade_edges(self):
        buffer = [1.0] * 100
        synth.fade_edges(buffer, 20)
        assert buffer[0] == pytest.approx(0.0, abs=0.06)
        assert buffer[50] == 1.0

    def test_pcm16_length(self):
        pcm = synth.to_pcm16([0.0, 1.0, -1.0])
        assert len(pcm) == 6

    def test_pcm16_clamps(self):
        pcm = synth.to_pcm16([5.0, -5.0])
        assert len(pcm) == 4  # no crash on out-of-range input

    def test_stereo_duplicates_channels(self):
        pcm = synth.to_stereo([0.0, 1.0])
        assert len(pcm) == 8


class TestSoundEffects:
    def test_registry_is_populated(self):
        names = sfx_mod.available_sounds()
        assert len(names) >= 15
        for name in names:
            assert name in sfx_mod.SFX_RECIPES

    @pytest.mark.parametrize("name", sfx_mod.available_sounds())
    def test_each_effect_renders_a_valid_buffer(self, name):
        builder, volume = sfx_mod.SFX_RECIPES[name]
        buffer = builder()
        assert len(buffer) > 0
        assert 0.0 < volume <= 1.0
        peak = max(abs(v) for v in buffer)
        assert 0.05 < peak <= 1.0, f"{name} peak={peak}"

    def test_effects_are_short_enough_for_one_shots(self):
        from neon_survivor.config import AUDIO_SAMPLE_RATE

        for name in sfx_mod.available_sounds():
            builder, _ = sfx_mod.SFX_RECIPES[name]
            duration = len(builder()) / AUDIO_SAMPLE_RATE
            assert duration < 2.0, f"{name} is {duration:.2f}s long"

    def test_arpeggio_length(self):
        buffer = sfx_mod.arpeggio(("C4", "E4", "G4"), note_len=0.1, gap=0.05)
        assert len(buffer) > 0.1 * 22050


class TestMusic:
    def test_tracks_are_declared(self):
        assert set(music_mod.available_tracks()) == {"calm", "action", "boss"}

    def test_boss_is_the_fastest(self):
        assert music_mod.BOSS.bpm > music_mod.ACTION.bpm > music_mod.CALM.bpm

    def test_every_track_renders(self):
        for key, spec in music_mod.TRACKS.items():
            buffer = music_mod.render_track(spec, sample_rate=11025)
            assert len(buffer) > 0, key
            peak = max(abs(v) for v in buffer)
            assert 0.2 < peak <= 1.0, f"{key} peak={peak}"

    def test_render_matches_the_declared_length(self):
        for key, spec in music_mod.TRACKS.items():
            buffer = music_mod.render_track(spec, sample_rate=11025)
            expected = music_mod.track_length(spec, 11025)
            actual = len(buffer) / 11025
            # The seamless cross-fade removes a small tail.
            assert abs(actual - expected) < 0.6, key

    def test_loop_is_seamless_at_the_edges(self):
        buffer = music_mod.render_track(music_mod.CALM, sample_rate=11025)
        # The head starts near silence thanks to the cross-fade.
        head = sum(abs(v) for v in buffer[:200]) / 200
        assert head < 0.25
