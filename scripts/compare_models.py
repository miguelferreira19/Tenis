from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sqlalchemy import and_, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from tennis_quant.db import engine, matches, predictions


def main():
    evaluation = json.loads((ROOT / "artifacts" / "evaluation.json").read_text(encoding="utf-8"))
    versions = {family: evaluation[family]["version"] for family in ("elo", "logistic", "xgboost")}
    p = predictions.alias("p")
    with engine.connect() as conn:
        data = [dict(r) for r in conn.execute(select(
            matches.c.id, matches.c.tournament_id, matches.c.event_date, matches.c.tour,
            matches.c.surface, matches.c.player_a_id, matches.c.winner_id,
            p.c.model_version, p.c.probability_a,
        ).select_from(matches.join(p, p.c.match_id == matches.c.id)).where(and_(
            p.c.split == "test_oos", p.c.model_version.in_(versions.values())))).mappings()]
    by_match = {}
    family_by_version = {version: family for family, version in versions.items()}
    for r in data:
        item = by_match.setdefault(r["id"], {k: r[k] for k in (
            "tournament_id", "event_date", "tour", "surface", "player_a_id", "winner_id")})
        item[family_by_version[r["model_version"]]] = r["probability_a"]
    records = [r for r in by_match.values() if all(f in r for f in versions)]
    y = np.array([int(r["player_a_id"] == r["winner_id"]) for r in records])
    losses = {f: (np.array([r[f] for r in records]) - y) ** 2 for f in versions}
    years = np.array([r["event_date"].year for r in records])
    groups = {}
    for label, mask in [
        *[(str(year), years == year) for year in sorted(set(years))],
        *[(tour, np.array([r["tour"] == tour for r in records])) for tour in ("ATP", "WTA")],
        *[(surface, np.array([r["surface"] == surface for r in records])) for surface in ("Hard", "Clay", "Grass")],
    ]:
        groups[label] = {"n": int(mask.sum()), **{f: float(losses[f][mask].mean()) for f in versions}}
    # Paired tournament-cluster bootstrap: preserves within-tournament dependence.
    cluster_names = sorted(set(r["tournament_id"] for r in records))
    n = np.array([sum(r["tournament_id"] == key for r in records) for key in cluster_names])
    diffs = {}
    rng = np.random.default_rng(20260927)
    draws = rng.integers(0, len(cluster_names), size=(2000, len(cluster_names)))
    for benchmark in ("elo", "logistic"):
        loss_diff = losses[benchmark] - losses["xgboost"]
        sums = np.array([sum(loss_diff[i] for i, r in enumerate(records) if r["tournament_id"] == key)
                         for key in cluster_names])
        bootstrap = sums[draws].sum(axis=1) / n[draws].sum(axis=1)
        diffs[f"xgboost_vs_{benchmark}"] = {
            "brier_improvement": float(loss_diff.mean()),
            "cluster_bootstrap_95": [float(x) for x in np.quantile(bootstrap, [0.025, 0.975])],
            "n_tournaments": len(cluster_names), "resamples": 2000,
        }
    result = {"n": len(records), "by_group": groups, "paired_comparison": diffs,
              "selection_note": "XGBoost escolhido em 2023; teste OOS não usado para seleção."}
    (ROOT / "artifacts" / "model_comparison.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

