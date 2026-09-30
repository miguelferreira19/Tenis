"""Second round: recover raw metadata and test circuit-specific learning."""
import json
import sys
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))
from tennis_quant.features import FEATURE_NAMES, build_feature_rows
from tennis_quant.innovation import NAMES, sigmoid
from tennis_quant.research_metadata import NAMES as META_NAMES, metadata_features
from tennis_quant.research_identity import research_version
from tennis_quant.research_io import write_json
from tennis_quant.model import _fit_calibrator, _calibrate
from research_layoff import _fit_and_predict, _metrics, _paired
from research_innovation import simultaneous_intervals

CANDIDATES = ("metadata", "all_metadata", "all_by_tour", "all_metadata_by_tour",
              "all_metadata_context", "markov_standalone", "dynamic_standalone")


def main():
    out = ROOT / "artifacts"
    rows = build_feature_rows()
    prior = json.loads((out / "innovation_research.json").read_text(encoding="utf-8"))
    cached = np.load(out / "innovation_predictions.npz")
    if not np.array_equal(cached["match_id"], [r["row"]["id"] for r in rows]):
        raise ValueError("Arquivo mudou; repetir primeira ronda")
    extra, coverage = metadata_features(rows)
    base = np.column_stack((np.stack([r["x"] for r in rows]), [r["layoff_feature"] for r in rows]))
    innovation = cached["feature_matrix"]
    full = np.column_stack((base, innovation))
    rich = np.column_stack((full, extra))
    years, y = cached["years"], cached["y"]
    elo = np.array([r["elo_probability"] for r in rows])
    tours = np.array([r["row"]["tour"] for r in rows])
    context = np.column_stack((rich, full[:, :2] * np.array([(r["row"].get("best_of") or 3) - 3 for r in rows])[:, None]))
    matrices = {"metadata": np.column_stack((base, extra)), "all_metadata": rich,
                "all_by_tour": full, "all_metadata_by_tour": rich, "all_metadata_context": context}
    predictions = {n: cached[n].copy() for n in prior["candidates"]}
    report = {"dataset_hash": prior["dataset_hash"], "candidates": CANDIDATES,
              "coverage": coverage, "results": {}, "selection": "mean annual Brier 2019-2023",
              "new_configurations": len(CANDIDATES), "new_rounds_total": 14,
              "adaptation_note": "Second round after first-round diagnostic inspection; development selection only, all 2024+ descriptive",
              "status": "research_only_forward_confirmation_pending"}
    development = (years >= 2019) & (years <= 2023)
    def checkpoint():
        write_json(out / "enrichment_research.json", report)

    def run(name, year):
        train, cal, test = years <= year - 2, years == year - 1, years == year
        if name.endswith("standalone"):
            index = 7 if name.startswith("markov") else 0
            raw = np.array([sigmoid(x) for x in innovation[:, index]])
            calibrator = _fit_calibrator(raw[cal], y[cal])
            return _calibrate(calibrator, raw[test]), {"calibrator": calibrator, "index": index}
        p = np.full(int(test.sum()), np.nan)
        artifacts = {}
        for tour in (("ATP", "WTA") if name.endswith("by_tour") else ("pooled",)):
            mask = tours == tour if tour != "pooled" else np.ones(len(rows), dtype=bool)
            values, model, calibrator = _fit_and_predict(matrices[name], y, elo, train & mask, cal & mask, test & mask)
            p[mask[test]] = values
            artifacts[tour] = {"model": model, "calibrator": calibrator}
        return p, artifacts

    for name in CANDIDATES:
        predictions[name] = np.full(len(rows), np.nan)
        result = {"yearly": {}}
        for year in range(2019, 2024):
            test = years == year
            predictions[name][test], _ = run(name, year)
            result["yearly"][str(year)] = _metrics(y[test], predictions[name][test])
        result["mean_annual_brier"] = float(np.mean([v["brier"] for v in result["yearly"].values()]))
        report["results"][name] = result
        checkpoint()
        print(name, result["mean_annual_brier"], flush=True)
    scores = {n: v["mean_annual_brier"] for n, v in prior["results"].items()}
    scores.update({n: v["mean_annual_brier"] for n, v in report["results"].items()})
    winner = min(scores, key=scores.get)
    report["selected"] = winner
    report["all_development_scores"] = scores
    report["simultaneous_all_rounds"] = simultaneous_intervals(rows, y, predictions, development)
    if winner in CANDIDATES:
        for year in range(2024, 2027):
            test = years == year
            predictions[winner][test], fitted = run(winner, year)
            report["results"][winner]["yearly"][str(year)] = _metrics(y[test], predictions[winner][test])
            if year == 2026:
                names = FEATURE_NAMES + ("layoff_log_365d",)
                if winner != "metadata":
                    names += NAMES
                if "metadata" in winner:
                    names += META_NAMES
                if winner.endswith("context"):
                    names += ("best_of_elo_global", "best_of_elo_surface")
                version = research_version(f"enrichment-{winner}", prior["dataset_hash"], names, __file__)
                joblib.dump({"models": fitted, "feature_names": names, "version": version,
                             "candidate": winner, "status": "research_only"}, out / f"{version}.joblib")
                report["artifact"] = f"{version}.joblib"
            checkpoint()
    else:
        report["artifact"] = prior["artifact"]
    for label, mask in (("development", development), ("diagnostic", (years >= 2024) & (years <= 2026))):
        report[label] = {}
        for reference in ("v4", "v5_layoff", "all"):
            report[label][reference] = {"baseline": _metrics(y[mask], predictions[reference][mask]),
                "selected": _metrics(y[mask], predictions[winner][mask]),
                "paired": _paired(rows, years, y, predictions[reference], predictions[winner], mask)}
        report[label]["subgroups"] = {}
        for field, values in (("tour", ("ATP", "WTA")), ("surface", ("Hard", "Clay", "Grass"))):
            for value in values:
                sub = mask & np.array([r["row"][field] == value for r in rows])
                report[label]["subgroups"][value] = {"baseline": _metrics(y[sub], predictions["v5_layoff"][sub]),
                    "selected": _metrics(y[sub], predictions[winner][sub])}
    np.savez_compressed(out / "enrichment_predictions.npz", match_id=cached["match_id"],
                        y=y, years=years, metadata_matrix=extra, **predictions)
    checkpoint()
    print("SELECTED", winner, json.dumps(report["diagnostic"]["v4"]), flush=True)


if __name__ == "__main__":
    main()
