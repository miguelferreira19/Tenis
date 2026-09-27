from __future__ import annotations

from collections import defaultdict
from datetime import date

import numpy as np
import pytest

from tennis_quant.features import PlayerState, _feature_record, _service_points_won, _update, eligible_for_model
from tennis_quant.model import _calibrate, _fit_calibrator


def sample_match(match_id: str, day: date, winner: str = "ATP:1") -> dict:
    return {
        "id": match_id, "event_date": day, "surface": "Hard",
        "player_a_id": "ATP:1", "player_b_id": "ATP:2", "winner_id": winner,
        "rank_a": 20, "rank_b": 30,
        "stats_a": {"svpt": 60, "1stWon": 30, "2ndWon": 12},
        "stats_b": {"svpt": 60, "1stWon": 24, "2ndWon": 12},
    }


def test_feature_snapshot_is_before_event_result():
    states = defaultdict(PlayerState)
    row = sample_match("one", date(2024, 1, 1))
    first = _feature_record(row, states)
    assert first["details"]["matches_a"] == 0
    assert first["details"]["rank_a"] is None
    assert first["elo_probability"] == pytest.approx(0.5)
    _update(row, states)
    next_event = _feature_record(sample_match("two", date(2024, 1, 8)), states)
    assert next_event["details"]["matches_a"] == 1
    assert next_event["details"]["rank_a"] == 20
    assert next_event["details"]["serve_a"] == pytest.approx(0.7)
    assert next_event["details"]["elo_a"] > next_event["details"]["elo_b"]
    assert next_event["elo_probability"] > 0.5


def test_invalid_or_missing_service_stats_do_not_create_features():
    assert _service_points_won({"svpt": None, "1stWon": 2, "2ndWon": 1}) is None
    assert _service_points_won({"svpt": 4, "1stWon": 4, "2ndWon": 2}) is None


def test_calibration_preserves_player_swap_symmetry():
    raw = np.array([0.2, 0.4, 0.6, 0.8])
    y = np.array([0, 0, 1, 1])
    calibrator = _fit_calibrator(raw, y)
    calibrated = _calibrate(calibrator, raw)
    assert np.allclose(calibrated, 1 - _calibrate(calibrator, 1 - raw))


def test_incomplete_matches_are_excluded_from_model():
    assert eligible_for_model({"score": "6-4 6-3"})
    assert not eligible_for_model({"score": "W/O"})
    assert not eligible_for_model({"score": "6-2 1-0 RET"})
    assert not eligible_for_model({"score": None})

