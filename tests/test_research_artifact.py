"""Local integration check: deployment vector reproduces stored 2026 forecasts."""
import json
import sys
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pytest

from tennis_quant.features import build_feature_rows
from tennis_quant.model import _calibrate, _raw_predict
from tennis_quant.research_metadata import _valid_number

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from predict_research import feature_vector


def test_metadata_validation():
    assert _valid_number("nan", "age") is None
    assert _valid_number("-1", "rank_points") is None
    assert _valid_number("", "ht") is None
    assert _valid_number("185", "ht") == 185


@pytest.mark.parametrize("report_file,predictions_file", [("enrichment_research.json","enrichment_predictions.npz"),("iteration_research.json","iteration_predictions.npz")])
def test_saved_challenger_vector_matches_rolling_forecast(report_file,predictions_file):
    out = ROOT / "artifacts"
    if not (out / "enrichment_predictions.npz").exists():
        pytest.skip("Requer execução local das duas rondas de investigação")
    report = json.loads((out / report_file).read_text(encoding="utf-8"))
    if report["selected"] not in {"all_metadata_context","recency_730d"}:
        pytest.skip("Este check cobre o candidato selecionado na execução 30-09-2026")
    artifact = joblib.load(out / report["artifact"])
    raw = np.load(out / "innovation_predictions.npz")
    enriched = np.load(out / "enrichment_predictions.npz")
    rows = build_feature_rows()
    assert np.array_equal(raw["match_id"], [r["row"]["id"] for r in rows])
    ids = np.flatnonzero(raw["years"] == 2026)[::25]
    X = np.stack([feature_vector(rows[k], raw["feature_matrix"][k], enriched["metadata_matrix"][k],
                                 rows[k]["row"].get("best_of") or 3, artifact["feature_names"]) for k in ids])
    fitted = artifact["models"]["pooled"]
    p = _calibrate(fitted["calibrator"], _raw_predict("xgboost", fitted["model"], X,
                                                      np.array([rows[k]["elo_probability"] for k in ids])))
    assert np.allclose(p, np.load(out / predictions_file)[report["selected"]][ids], atol=1e-12)
    for path in (out / "forward").glob("*.json"):
        for record in json.loads(path.read_text())["forecasts"]:
            assert datetime.fromisoformat(record["as_of"]) < datetime.fromisoformat(record["start_at"])


def test_forward_settlement_requires_both_players_and_frozen_orientation():
    from analyze_research import settled_result
    item={"as_of":"2026-09-30T10:40:00+00:00","start_at":"2026-09-30T11:00:00+00:00","player_a_id":"ATP:1","player_b_id":"ATP:2"}
    event={"player_a_id":"ATP:1","player_b_id":"ATP:2","player_a":"One","player_b":"Two","tour":"ATP","tournament":"Beijing"}
    result={"start_at":datetime.fromisoformat(item["start_at"]),"player_a":"Two","player_b":"One","winner":"Two","tour":"ATP","tournament":"Beijing"}
    assert settled_result(item,event,result)==0
    assert settled_result(item,event,{**result,"start_at":datetime(2026,9,30,11,5)})==0
    assert settled_result(item,event,{**result,"start_at":datetime(2026,9,30,10,35)}) is None
    assert settled_result(item,event,{**result,"player_a":"Someone else"}) is None
    assert settled_result(item,{**event,"player_a_id":"ATP:2"},result) is None
    assert settled_result(item,event,{**result,"start_at":datetime(2026,9,29,12)}) is None


def test_recent_source_audit_flags_duplicate_and_unmapped_identity():
    from audit_recent_source import audit
    from datetime import date
    row={"tourney_date":"20260901","tourney_id":"new","match_num":"1",
         "winner_id":"external1","loser_id":"external2","winner_name":"One","loser_name":"Two"}
    known={("ATP","one"):["ATP:1"]}
    report=audit([row,row],"ATP",known,date(2026,5,25))
    assert report["duplicate_match_keys"]==1
    assert report["unresolved_names"]==["Two"]
    assert report["name_based_identity_candidates"]=={"ATP:external1":"ATP:1"}
    assert len(audit([{**row,"tourney_date":"invalid"}],"ATP",known,date(2026,5,25))["invalid_rows"])==1
