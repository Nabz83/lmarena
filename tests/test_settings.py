"""Tests for the persistent settings profile."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from neon_survivor.settings import Settings, save_path, user_data_dir


class TestRoundTrip:
    def test_save_and_load(self, tmp_path: Path):
        path = tmp_path / "settings.json"
        settings = Settings()
        settings.high_score = 12345
        settings.best_wave = 7
        settings.music_volume = 0.42
        assert settings.save(path)
        loaded = Settings.load(path)
        assert loaded.high_score == 12345
        assert loaded.best_wave == 7
        assert loaded.music_volume == pytest.approx(0.42)

    def test_missing_file_returns_defaults(self, tmp_path: Path):
        loaded = Settings.load(tmp_path / "nope.json")
        assert loaded.high_score == 0
        assert loaded.version

    def test_corrupted_file_returns_defaults(self, tmp_path: Path):
        path = tmp_path / "settings.json"
        path.write_text("{ this is not json", encoding="utf-8")
        assert Settings.load(path).high_score == 0

    def test_non_object_root_returns_defaults(self, tmp_path: Path):
        path = tmp_path / "settings.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        assert Settings.load(path).high_score == 0

    def test_unknown_keys_are_preserved(self, tmp_path: Path):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps({"high_score": 5, "future_option": "x"}), encoding="utf-8")
        loaded = Settings.load(path)
        assert loaded.high_score == 5
        assert loaded.extra.get("future_option") == "x"
        assert Settings.load(path).extra.get("future_option") == "x"

    def test_save_is_atomic_and_valid_json(self, tmp_path: Path):
        path = tmp_path / "settings.json"
        Settings().save(path)
        json.loads(path.read_text(encoding="utf-8"))
        assert not path.with_suffix(".json.tmp").exists()


class TestSanitisation:
    @pytest.mark.parametrize(
        "value,expected",
        [(-5, 0), ("abc", 0), (None, 0), (12.7, 12), (True, 1)],
    )
    def test_high_score_is_coerced(self, value, expected):
        settings = Settings(high_score=value)
        settings.sanitize()
        assert settings.high_score == expected

    def test_volumes_are_clamped(self):
        settings = Settings(music_volume=5.0, sfx_volume=-2.0, master_volume=0.5)
        settings.sanitize()
        assert settings.music_volume == 1.0
        assert settings.sfx_volume == 0.0
        assert settings.master_volume == 0.5

    def test_nan_is_rejected(self):
        settings = Settings(master_volume=float("nan"))
        settings.sanitize()
        assert 0.0 <= settings.master_volume <= 1.0

    def test_infinity_is_rejected(self):
        settings = Settings(best_time=float("inf"))
        settings.sanitize()
        assert settings.best_time == 0.0

    def test_best_wave_is_at_least_one(self):
        settings = Settings(best_wave=-3)
        settings.sanitize()
        assert settings.best_wave == 1

    def test_extra_is_always_a_dict(self):
        settings = Settings(extra="oops")
        settings.sanitize()
        assert settings.extra == {}


class TestRunRecording:
    def test_record_run_reports_a_record(self):
        settings = Settings()
        assert settings.record_run(1000, 3, 60.0, 10)
        assert settings.high_score == 1000
        assert settings.total_kills == 10
        assert settings.total_runs == 1

    def test_a_worse_run_is_not_a_record(self):
        settings = Settings(high_score=5000)
        assert not settings.record_run(100, 2, 30.0, 5)
        assert settings.high_score == 5000
        assert settings.best_wave == 2  # the wave is still tracked
        assert settings.total_runs == 1

    def test_best_fields_never_regress(self):
        settings = Settings()
        settings.record_run(100, 5, 120.0, 10)
        settings.record_run(50, 2, 10.0, 1)
        assert settings.high_score == 100
        assert settings.best_wave == 5
        assert settings.best_time == pytest.approx(120.0)

    def test_kills_accumulate_across_runs(self):
        settings = Settings()
        settings.record_run(100, 1, 10.0, 7)
        settings.record_run(200, 1, 10.0, 3)
        assert settings.total_kills == 10


class TestPaths:
    def test_user_data_dir_is_writable(self):
        path = user_data_dir("neon_survivor_test")
        assert path.exists()
        probe = path / "probe.txt"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()

    def test_save_path_is_a_file(self):
        assert save_path().name == "settings.json"

    def test_save_to_unwritable_location_returns_false(self, tmp_path: Path):
        blocker = tmp_path / "blocker"
        blocker.write_text("i am a file", encoding="utf-8")
        settings = Settings()
        assert not settings.save(blocker / "nested" / "settings.json")
