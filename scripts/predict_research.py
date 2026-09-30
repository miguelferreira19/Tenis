"""Freeze challenger forecasts before future matches, beside the operational model."""
import argparse
import hashlib
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import joblib
import numpy as np
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from tennis_quant.db import engine, fixtures
from tennis_quant.daily import _forecast, _utc
from tennis_quant.espn_fixtures import refresh_day
from tennis_quant.features import FEATURE_NAMES, build_feature_rows, fixture_feature
from tennis_quant.innovation import NAMES, research_features
from tennis_quant.research_metadata import NAMES as META_NAMES, metadata_features, raw_metadata
from tennis_quant.model import _calibrate, _raw_predict


def feature_vector(feature, innovation, metadata, best_of, names):
    values = dict(zip(FEATURE_NAMES, feature["x"]))
    values.update(zip(NAMES, innovation))
    values.update(zip(META_NAMES, metadata))
    values["layoff_log_365d"] = feature["layoff_feature"]
    values["best_of_elo_global"] = feature["x"][0] * (best_of - 3)
    values["best_of_elo_surface"] = feature["x"][1] * (best_of - 3)
    return np.array([values[name] for name in names])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day", type=date.fromisoformat,
                        default=datetime.now(ZoneInfo("Europe/Lisbon")).date())
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    if args.refresh:
        refresh_day(args.day)
    out = ROOT / "artifacts"
    research = json.loads((out / "enrichment_research.json").read_text(encoding="utf-8"))
    iteration = out / "iteration_research.json"
    if iteration.exists():
        candidate = json.loads(iteration.read_text(encoding="utf-8"))
        if "diagnostic" in candidate and candidate.get("selected") == "recency_730d":
            research = candidate
    artifact_path = out / research["artifact"]
    artifact = joblib.load(artifact_path)
    operational = json.loads((out / "evaluation.json").read_text(encoding="utf-8"))["operational_version"]
    start = datetime.combine(args.day, datetime.min.time(), tzinfo=ZoneInfo("Europe/Lisbon")).astimezone(timezone.utc)
    with engine.connect() as conn:
        events = [dict(r) for r in conn.execute(select(fixtures).where(
            fixtures.c.start_at >= start, fixtures.c.start_at < start + timedelta(days=1))).mappings()]
    historical = build_feature_rows()
    raw = raw_metadata()
    records, skipped = [], []
    for tour in ("ATP", "WTA"):
        candidates = []
        for event in events:
            if event["tour"] != tour:
                continue
            if _utc(event["start_at"]) <= datetime.now(timezone.utc):
                skipped.append({"id": event["id"], "reason": "already_started"})
                continue
            baseline, quality, _ = _forecast(event, operational)
            if baseline is None or quality["surface"] not in {"Hard", "Clay", "Grass"}:
                skipped.append({"id": event["id"], "reason": quality.get("reason", "unknown_surface")})
                continue
            # Current verified China/Japan Open fixtures are best of three.
            if not quality.get("tour_level_verified"):
                skipped.append({"id": event["id"], "reason": "unverified_format"})
                continue
            feature = fixture_feature(event["player_a_id"], event["player_b_id"], args.day, tour, quality["surface"])
            feature["row"].update(id=event["id"], tour=tour, best_of=3, score=None, stats_a=None, stats_b=None)
            candidates.append((event, feature, baseline))
        if not candidates:
            continue
        past = [r for r in historical if r["row"]["tour"] == tour and r["row"]["event_date"] < args.day]
        rows = past + [r for _, r, _ in candidates]
        innovation, _ = research_features(rows)
        metadata, _ = metadata_features(rows, raw)
        for k, (event, feature, baseline) in enumerate(candidates, start=len(past)):
            fitted = artifact["models"].get(tour, artifact["models"].get("pooled")) if "models" in artifact else artifact
            x = feature_vector(feature, innovation[k], metadata[k], 3, artifact["feature_names"])
            p = float(_calibrate(fitted["calibrator"], _raw_predict("xgboost", fitted["model"], x[None, :],
                                                                     np.array([feature["elo_probability"]])))[0])
            as_of = datetime.now(timezone.utc)
            if _utc(event["start_at"]) <= as_of:
                skipped.append({"id": event["id"], "reason": "started_during_computation"})
                continue
            records.append({"fixture_id": event["id"], "tour": tour,
                            "player_a_id": event["player_a_id"], "player_b_id": event["player_b_id"],
                            "start_at": _utc(event["start_at"]).isoformat(), "as_of": as_of.isoformat(),
                            "baseline_probability_a": baseline, "challenger_probability_a": p,
                            "features": dict(zip(artifact["feature_names"], x.tolist()))})
    result = {"day": args.day.isoformat(), "model_version": artifact["version"],
              "model_sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
              "dataset_hash": research["dataset_hash"], "baseline_version": operational,
              "last_archive_event": max(r["row"]["event_date"] for r in historical).isoformat(),
              "status": "research_shadow_not_betting_signal", "forecasts": records, "skipped": skipped}
    folder = out / "forward"
    folder.mkdir(exist_ok=True)
    path = folder / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
    with path.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
    print(json.dumps({"path": str(path), "forecasts": len(records), "skipped": len(skipped)}, indent=2))


if __name__ == "__main__":
    main()
