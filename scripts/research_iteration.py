"""Round three: bounded new signal families and evidence-based simplification."""
import json
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))
from tennis_quant.features import FEATURE_NAMES, build_feature_rows
from tennis_quant.innovation import NAMES as INNOVATION_NAMES
from tennis_quant.research_metadata import NAMES as METADATA_NAMES
from tennis_quant.research_dynamics import BLOCKS, NAMES, dynamics_features
from tennis_quant.research_identity import research_version
from tennis_quant.research_io import write_json
from tennis_quant.model import MODEL_PARAMETERS, _calibrate, _fit_calibrator, _raw_predict
from research_layoff import _fit_and_predict, _metrics, _paired
from research_innovation import simultaneous_intervals

CANDIDATES = {**BLOCKS, "recency_730d": (), "hist_boost": ()}


def main():
    out = ROOT / "artifacts"
    rows = build_feature_rows()
    old = np.load(out / "enrichment_predictions.npz")
    innovation = np.load(out / "innovation_predictions.npz")
    if not np.array_equal(old["match_id"], [r["row"]["id"] for r in rows]):
        raise ValueError("Arquivo mudou; repetir experiências anteriores")
    previous = json.loads((out / "enrichment_research.json").read_text(encoding="utf-8"))
    extra, coverage = dynamics_features(rows)
    years, y = old["years"], old["y"]
    elo = np.array([r["elo_probability"] for r in rows])
    base = np.stack([r["x"] for r in rows])
    full = np.column_stack((base, [r["layoff_feature"] for r in rows], innovation["feature_matrix"],
                            old["metadata_matrix"], base[:, :2] * np.array([(r["row"].get("best_of") or 3)-3 for r in rows])[:, None]))
    names = FEATURE_NAMES + ("layoff_log_365d",) + INNOVATION_NAMES + METADATA_NAMES + ("best_of_elo_global", "best_of_elo_surface")
    days = np.array([r["row"]["event_date"].toordinal() for r in rows])
    predictions = {previous["selected"]: old[previous["selected"]].copy()}
    report = {"dataset_hash": previous["dataset_hash"], "reference": previous["selected"],
              "candidates": CANDIDATES, "coverage": coverage, "new_configurations": len(CANDIDATES),
              "total_new_configurations": 14 + len(CANDIDATES), "results": {},
              "selection": "mean annual Brier 2019-2023; no diagnostic selection",
              "status": "research_only", "note": "All historical diagnostics already consulted; hypotheses remain exploratory"}
    def checkpoint():
        write_json(out / "iteration_research.json", report)
    def run(name, year):
        train, cal, test = years <= year-2, years == year-1, years == year
        X = np.column_stack((full, extra[:, CANDIDATES[name]]))
        if name not in {"recency_730d", "hist_boost"}:
            p, model, calibrator = _fit_and_predict(X, y, elo, train, cal, test)
        else:
            model = (HistGradientBoostingClassifier(max_iter=200, max_leaf_nodes=7, learning_rate=.05,
                                                    l2_regularization=10, early_stopping=False, random_state=20260930)
                     if name == "hist_boost" else XGBClassifier(**MODEL_PARAMETERS["xgboost"], n_jobs=4))
            weight = .5 ** ((days[train].max()-days[train])/730) if name == "recency_730d" else np.ones(int(train.sum()))
            model.fit(np.concatenate((X[train], -X[train])), np.concatenate((y[train], 1-y[train])),
                      sample_weight=np.tile(weight, 2))
            calibrator = _fit_calibrator(_raw_predict("xgboost", model, X[cal], elo[cal]), y[cal])
            p = _calibrate(calibrator, _raw_predict("xgboost", model, X[test], elo[test]))
        return p, model, calibrator
    dev = (years >= 2019) & (years <= 2023)
    for name in CANDIDATES:
        predictions[name] = np.full(len(rows), np.nan)
        result = {"yearly": {}}
        for year in range(2019, 2024):
            test = years == year
            predictions[name][test], _, _ = run(name, year)
            result["yearly"][str(year)] = _metrics(y[test], predictions[name][test])
        result["mean_annual_brier"] = float(np.mean([v["brier"] for v in result["yearly"].values()]))
        report["results"][name] = result
        checkpoint()
        print(name, result["mean_annual_brier"], flush=True)
    scores = {n:v["mean_annual_brier"] for n,v in report["results"].items()}
    scores[previous["selected"]] = previous["all_development_scores"][previous["selected"]]
    winner = min(scores, key=scores.get)
    report["selected"] = winner
    report["scores"] = scores
    combined = {n: old[n].copy() for n in previous["all_development_scores"]}
    combined.update(predictions)
    report["simultaneous_all_rounds"] = simultaneous_intervals(rows, y, combined, dev)
    if winner in CANDIDATES:
        for year in range(2024, 2027):
            test = years == year
            predictions[winner][test], model, calibrator = run(winner, year)
            report["results"][winner]["yearly"][str(year)] = _metrics(y[test], predictions[winner][test])
            if year == 2026:
                version = research_version(f"iteration-{winner}", previous["dataset_hash"], names + tuple(NAMES[k] for k in CANDIDATES[winner]), __file__)
                joblib.dump({"models": {"pooled": {"model": model, "calibrator": calibrator}},
                             "feature_names": names + tuple(NAMES[k] for k in CANDIDATES[winner]),
                             "version": version, "candidate": winner, "status": "research_only"}, out / f"{version}.joblib")
                report["artifact"] = f"{version}.joblib"
            checkpoint()
    else:
        report["artifact"] = previous["artifact"]
    for label, mask in (("development", dev), ("diagnostic", (years >= 2024) & (years <= 2026))):
        report[label] = {}
        for reference in ("v4", "v5_layoff", previous["selected"]):
            baseline = old[reference]
            report[label][reference] = {"baseline": _metrics(y[mask], baseline[mask]),
                "selected": _metrics(y[mask], predictions[winner][mask]),
                "paired": _paired(rows, years, y, baseline, predictions[winner], mask)}
        report[label]["subgroups"] = {}
        for field, values in (("tour", ("ATP", "WTA")), ("surface", ("Hard", "Clay", "Grass"))):
            for value in values:
                sub = mask & np.array([r["row"][field] == value for r in rows])
                report[label]["subgroups"][value] = {"baseline": _metrics(y[sub], old[previous['selected']][sub]),
                                                     "selected": _metrics(y[sub], predictions[winner][sub])}
    np.savez_compressed(out / "iteration_predictions.npz", match_id=old["match_id"], y=y, years=years,
                        dynamics_matrix=extra, **predictions)
    checkpoint()
    print("SELECTED", winner, json.dumps(report["diagnostic"]["v4"]), flush=True)


if __name__ == "__main__":
    main()
