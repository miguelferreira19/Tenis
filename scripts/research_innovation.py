"""Reproducible bounded methodology comparison; never optimizes on 2024+."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))
from tennis_quant.features import FEATURE_NAMES, build_feature_rows
from tennis_quant.innovation import NAMES, research_features
from tennis_quant.research_identity import research_version
from tennis_quant.research_io import write_json
from research_layoff import _fit_and_predict, _metrics, _paired

# Fixed before evaluation; indices refer to innovation.NAMES.
CANDIDATES = {"v4": None, "v5_layoff": (), "dynamic": (0, 1),
              "point_global": (2, 3), "point_surface": (4, 5),
              "margin": (6,), "mechanistic": (7,),
              "point_mechanistic": (4, 5, 7), "all": tuple(range(8))}


def simultaneous_intervals(rows, y, predictions, mask, reference="v5_layoff"):
    """Tournament cluster bootstrap with a simultaneous max-deviation band."""
    names = [n for n in predictions if n != reference]
    idx = np.flatnonzero(mask)
    clusters = {}
    group = []
    for i in idx:
        r = rows[i]["row"]
        key = (r["tour"], r["tournament_id"])
        group.append(clusters.setdefault(key, len(clusters)))
    group = np.array(group)
    counts = np.bincount(group)
    losses = (predictions[reference][idx] - y[idx]) ** 2
    sums = np.stack([np.bincount(group, weights=losses - (predictions[n][idx] - y[idx]) ** 2)
                     for n in names], axis=1)
    means = sums.sum(axis=0) / counts.sum()
    rng = np.random.default_rng(20260930)
    draws = rng.integers(0, len(counts), (2000, len(counts)))
    boot = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)[:, None]
    radius = float(np.quantile(np.max(np.abs(boot - means), axis=1), 0.95))
    return {n: {"brier_improvement": float(means[k]),
                "simultaneous_95": [float(means[k] - radius), float(means[k] + radius)]}
            for k, n in enumerate(names)}


def main():
    out = ROOT / "artifacts"
    out.mkdir(exist_ok=True)
    rows = build_feature_rows()
    base = np.stack([r["x"] for r in rows])
    extra, coverage = research_features(rows)
    layoff = np.array([r["layoff_feature"] for r in rows])
    y = np.array([r["y"] for r in rows])
    elo = np.array([r["elo_probability"] for r in rows])
    years = np.array([r["row"]["event_date"].year for r in rows])
    development = (years >= 2019) & (years <= 2023)
    dataset_hash = hashlib.sha256("".join(sorted({r["row"]["source_sha256"] for r in rows})).encode()).hexdigest()
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "dataset_hash": dataset_hash,
              "n": len(rows), "coverage": coverage, "candidates": CANDIDATES,
              "new_configurations": len(CANDIDATES) - 2, "seed": 20260930,
              "protocol": "train <= Y-2; sigmoid calibration Y-1; evaluate Y",
              "selection": "mean annual Brier 2019-2023", "results": {},
              "status": "research_only_not_betting_approved",
              "limitations": ["2024+ already consulted in prior research",
                              "Dates are tournament starts, not individual match timestamps",
                              "Simultaneous intervals cover this round only; prior searches not corrected"]}
    predictions = {}

    def matrix(name):
        cols = CANDIDATES[name]
        return base if cols is None else np.column_stack((base, layoff, extra[:, cols]))

    def checkpoint():
        write_json(out / "innovation_research.json", report)

    for name in CANDIDATES:
        X = matrix(name)
        p = np.full(len(rows), np.nan)
        result = {"yearly": {}}
        for year in range(2019, 2024):
            test = years == year
            p[test], _, _ = _fit_and_predict(X, y, elo, years <= year - 2, years == year - 1, test)
            result["yearly"][str(year)] = _metrics(y[test], p[test])
        result["mean_annual_brier"] = float(np.mean([v["brier"] for v in result["yearly"].values()]))
        result["pooled"] = _metrics(y[development], p[development])
        predictions[name] = p
        report["results"][name] = result
        checkpoint()
        print(name, result["mean_annual_brier"], flush=True)
    winner = min(report["results"], key=lambda n: report["results"][n]["mean_annual_brier"])
    report["selected"] = winner
    report["development_simultaneous"] = simultaneous_intervals(rows, y, predictions, development)
    checkpoint()
    for name in dict.fromkeys(("v4", "v5_layoff", winner)):
        X = matrix(name)
        for year in range(2024, 2027):
            test = years == year
            if not test.any():
                continue
            predictions[name][test], model, calibrator = _fit_and_predict(
                X, y, elo, years <= year - 2, years == year - 1, test)
            report["results"][name]["yearly"][str(year)] = _metrics(y[test], predictions[name][test])
            if name == winner and year == 2026:
                names = FEATURE_NAMES if CANDIDATES[name] is None else FEATURE_NAMES + ("layoff_log_365d",) + tuple(NAMES[c] for c in CANDIDATES[name])
                version = research_version(f"innovation-{winner}", dataset_hash, names, __file__)
                joblib.dump({"family": "xgboost", "model": model, "calibrator": calibrator,
                             "feature_names": names, "version": version, "candidate": name,
                             "status": "research_only"}, out / f"{version}.joblib")
                report["artifact"] = f"{version}.joblib"
        checkpoint()
    diagnostic = (years >= 2024) & (years <= 2026)
    for period, mask in (("development", development), ("diagnostic", diagnostic)):
        report[period] = {}
        for reference in ("v4", "v5_layoff"):
            report[period][reference] = {"baseline": _metrics(y[mask], predictions[reference][mask]),
                "selected": _metrics(y[mask], predictions[winner][mask]),
                "paired": _paired(rows, years, y, predictions[reference], predictions[winner], mask)}
        report[period]["subgroups"] = {}
        for field, values in (("tour", ("ATP", "WTA")), ("surface", ("Hard", "Clay", "Grass"))):
            for value in values:
                sub = mask & np.array([r["row"][field] == value for r in rows])
                report[period]["subgroups"][value] = {
                    "baseline": _metrics(y[sub], predictions["v5_layoff"][sub]),
                    "selected": _metrics(y[sub], predictions[winner][sub])}
    checkpoint()
    np.savez_compressed(out / "innovation_predictions.npz", y=y, years=years,
                        match_id=np.array([r["row"]["id"] for r in rows]),
                        feature_matrix=extra, **predictions)
    print(json.dumps({"selected": winner, "development": report["development"],
                      "diagnostic": report["diagnostic"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
