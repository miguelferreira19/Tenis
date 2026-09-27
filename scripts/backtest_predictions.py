"""Temporal diagnostic backtest of probabilities, not betting returns."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from tennis_quant.db import engine, matches, predictions


def _metrics(records: list[dict]) -> dict:
    if not records:
        return {"n": 0}
    p = np.clip(np.array([r["probability_a"] for r in records]), 1e-6, 1 - 1e-6)
    y = np.array([r["y"] for r in records])
    bins = np.minimum((p * 10).astype(int), 9)
    ece = sum((bins == i).mean() * abs(p[bins == i].mean() - y[bins == i].mean())
              for i in range(10) if np.any(bins == i))
    return {"n": len(records), "brier": round(float(np.mean((p - y) ** 2)), 6),
            "log_loss": round(float(np.mean(-y * np.log(p) - (1 - y) * np.log(1 - p))), 6),
            "ece_10": round(float(ece), 6),
            "accuracy": round(float(np.mean((p >= 0.5) == y)), 6)}


def _paired(left: list[dict], right: list[dict]) -> dict:
    pairs = {r["id"]: r for r in left}
    pairs = [(pairs[r["id"]], r) for r in right if r["id"] in pairs]
    clusters: dict[str, list[float]] = defaultdict(list)
    for a, b in pairs:
        clusters[a["tournament_id"]].append((a["probability_a"] - a["y"]) ** 2 -
                                                (b["probability_a"] - b["y"]) ** 2)
    keys = sorted(clusters)
    sizes = np.array([len(clusters[key]) for key in keys])
    sums = np.array([sum(clusters[key]) for key in keys])
    if not keys:
        return {"n": 0}
    rng = np.random.default_rng(20260927)
    draws = rng.integers(0, len(keys), size=(2000, len(keys)))
    values = sums[draws].sum(axis=1) / sizes[draws].sum(axis=1)
    return {"n": len(pairs), "n_tournaments": len(keys),
            "brier_improvement_right": round(float(sums.sum() / sizes.sum()), 6),
            "bootstrap_95": [round(float(x), 6) for x in np.quantile(values, [0.025, 0.975])],
            "cluster": "tournament", "resamples": 2000}


def main():
    evaluation = json.loads((ROOT / "artifacts" / "evaluation.json").read_text(encoding="utf-8"))
    selected = evaluation["selected_by_validation"]
    version = evaluation[selected]["version"]
    with engine.connect() as conn:
        rows = [dict(r) for r in conn.execute(select(
            matches.c.id, matches.c.tournament_id, matches.c.event_date,
            matches.c.tour, matches.c.surface, matches.c.player_a_id,
            matches.c.winner_id, predictions.c.model_version,
            predictions.c.probability_a,
        ).select_from(matches.join(predictions, predictions.c.match_id == matches.c.id)).where(
            predictions.c.split == "test_oos"
        )).mappings()]
    for row in rows:
        row["y"] = int(row["player_a_id"] == row["winner_id"])
    chosen = [r for r in rows if r["model_version"] == version]
    by_year = {str(year): _metrics([r for r in chosen if r["event_date"].year == year])
               for year in sorted({r["event_date"].year for r in chosen})}
    by_tour = {tour: _metrics([r for r in chosen if r["tour"] == tour]) for tour in ("ATP", "WTA")}
    by_surface = {surface: _metrics([r for r in chosen if r["surface"] == surface])
                  for surface in ("Hard", "Clay", "Grass")}
    reliability = []
    for low in np.arange(0, 1, 0.1):
        bucket = [r for r in chosen if low <= r["probability_a"] < low + 0.1]
        reliability.append({"from": round(float(low), 1), "to": round(float(low + 0.1), 1),
                            "n": len(bucket),
                            "forecast_mean": round(float(np.mean([r["probability_a"] for r in bucket])), 4) if bucket else None,
                            "observed_rate": round(float(np.mean([r["y"] for r in bucket])), 4) if bucket else None})
    versions = sorted({r["model_version"] for r in rows})
    older = next((v for v in versions if v.startswith("xgboost-prematch-v3-")), None)
    old_rows = [r for r in rows if r["model_version"] == older]
    report = {"model_version": version, "overall": _metrics(chosen),
              "by_year": by_year, "by_tour": by_tour, "by_surface": by_surface,
              "reliability": reliability,
              "challenger_vs_frozen_v3": _paired(old_rows, chosen) if older else None,
              "caveat": "Backtest de probabilidades. O teste 2024+ já foi consultado durante a evolução do projeto; requer confirmação futura. Sem odds históricas com hora real, não estima ROI, CLV ou gates de aposta."}
    (ROOT / "artifacts" / "prediction_backtest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
