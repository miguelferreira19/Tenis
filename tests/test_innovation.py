from collections import defaultdict
from datetime import date

import numpy as np
import pytest

from tennis_quant.features import PlayerState, _feature_record
from tennis_quant.innovation import game_share, hold_probability, match_probability, research_features
from tennis_quant.research_metadata import metadata_features


def test_mechanistic_symmetry_and_causal_block():
    for pa, pb in ((0.64, 0.64), (0.72, 0.59), (0.51, 0.66)):
        for best_of in (3, 5):
            assert match_probability(pa, pb, best_of) == pytest.approx(1 - match_probability(pb, pa, best_of))
    assert hold_probability(0.5) == pytest.approx(0.5)
    assert game_share("6-4 6-3", True) == pytest.approx(12 / 19)
    assert game_share("6-4 6-3", False) == pytest.approx(7 / 19)
    assert game_share("6-4 3-6 [10-8]", True) == pytest.approx(9 / 19)
    states = defaultdict(PlayerState)
    rows = []
    for day in (date(2020, 1, 1), date(2020, 1, 1), date(2020, 1, 8)):
        row = {"tour": "ATP", "event_date": day, "surface": "Hard", "best_of": 3,
               "player_a_id": "ATP:1", "player_b_id": "ATP:2", "winner_id": "ATP:1",
               "score": "6-4 6-3", "stats_a": {"svpt": 60, "1stWon": 30, "2ndWon": 12},
               "stats_b": {"svpt": 60, "1stWon": 20, "2ndWon": 12}}
        rows.append(_feature_record(row, states))
    original, _ = research_features(rows)
    assert np.allclose(original[0], original[1])
    assert original[2, 0] > 0
    rows[2]["y"] = 0
    rows[2]["row"]["stats_a"] = None
    modified, _ = research_features(rows)
    assert np.allclose(original, modified)
    raw = {}
    for k, r in enumerate(rows):
        r["row"]["id"] = str(k)
        raw[str(k)] = {"ATP:1": {"age": 30, "ht": 190, "rank_points": 1000},
                       "ATP:2": {"age": 20, "ht": 180, "rank_points": 300}}
    metadata, _ = metadata_features(rows, raw)
    assert np.allclose(metadata[0], metadata[1])
    assert np.allclose(metadata[0], 0)
    assert metadata[2, 0] == pytest.approx(1)
    raw["2"]["ATP:1"]["age"] = 40
    assert np.allclose(metadata_features(rows, raw)[0], metadata)


def test_dynamics_freeze_same_day_and_current_outcome():
    from tennis_quant.research_dynamics import dynamics_features
    states = defaultdict(PlayerState)
    rows = []
    for day in (date(2020,1,1),date(2020,1,1),date(2020,1,8)):
        row = {"tour":"ATP","event_date":day,"surface":"Hard","best_of":3,
               "player_a_id":"ATP:1","player_b_id":"ATP:2","winner_id":"ATP:1",
               "score":"6-4 6-3","stats_a":{"svpt":60,"1stIn":40,"1stWon":30,"2ndWon":12},
               "stats_b":{"svpt":60,"1stIn":40,"1stWon":20,"2ndWon":10}}
        rows.append(_feature_record(row,states))
    before,_ = dynamics_features(rows)
    assert np.allclose(before[0],before[1])
    assert before[2,0] > 0
    rows[-1]["y"] = 0
    rows[-1]["row"]["stats_a"] = None
    assert np.allclose(before,dynamics_features(rows)[0])


def test_atomic_report_keeps_previous_on_invalid_number(tmp_path):
    from tennis_quant.research_io import write_json
    path=tmp_path / "report.json"
    write_json(path,{"valid":1})
    original=path.read_bytes()
    with pytest.raises(ValueError):
        write_json(path,{"invalid":float("nan")})
    assert path.read_bytes()==original
    assert list(tmp_path.iterdir())==[path]
