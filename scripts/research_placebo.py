"""Three joint feature-shuffle controls for the first-round all-feature candidate."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))
from tennis_quant.features import build_feature_rows
from tennis_quant.research_io import write_json
from research_layoff import _fit_and_predict, _metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enrichment", action="store_true")
    args = parser.parse_args()
    out = ROOT / "artifacts"
    rows = build_feature_rows()
    cache = np.load(out / "innovation_predictions.npz")
    if not np.array_equal(cache["match_id"], [r["row"]["id"] for r in rows]):
        raise ValueError("Arquivo mudou")
    base = np.column_stack((np.stack([r["x"] for r in rows]), [r["layoff_feature"] for r in rows]))
    years, y = cache["years"], cache["y"]
    tours = np.array([r["row"]["tour"] for r in rows])
    elo = np.array([r["elo_probability"] for r in rows])
    metadata = np.load(out / "enrichment_predictions.npz")["metadata_matrix"] if args.enrichment else None
    report = {"controls": {}, "n_controls": 3, "target": "all_metadata_context" if args.enrichment else "all",
              "note": "Joint shuffling within year/tour preserves feature dependence and annual distribution. These are synthetic null controls, not deployable features."}
    for seed in (31, 73, 109):
        extra = np.column_stack((cache["feature_matrix"], metadata)) if args.enrichment else cache["feature_matrix"].copy()
        rng = np.random.default_rng(seed)
        for year in sorted(set(years)):
            for tour in ("ATP", "WTA"):
                ids = np.flatnonzero((years == year) & (tours == tour))
                extra[ids] = extra[rng.permutation(ids)]
        X = np.column_stack((base, extra))
        if args.enrichment:
            # Public match format remains causal; only recovered player information is shuffled.
            X = np.column_stack((X, base[:, :2] * np.array([(r["row"].get("best_of") or 3) - 3 for r in rows])[:, None]))
        annual = {}
        for year in range(2019, 2024):
            test = years == year
            p, _, _ = _fit_and_predict(X, y, elo, years <= year - 2, years == year - 1, test)
            annual[str(year)] = _metrics(y[test], p)
        report["controls"][str(seed)] = {"yearly": annual,
            "mean_annual_brier": float(np.mean([v["brier"] for v in annual.values()]))}
        filename = "enrichment_placebo.json" if args.enrichment else "innovation_placebo.json"
        write_json(out / filename, report)
        print(seed, report["controls"][str(seed)]["mean_annual_brier"], flush=True)


if __name__ == "__main__":
    main()
