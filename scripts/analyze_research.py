"""Independent scoring pass over saved predictions, without training or selection."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))
from tennis_quant.features import build_feature_rows
from tennis_quant.db import engine, fixtures, recent_results
from tennis_quant.daily import _utc
from tennis_quant.research_io import write_json
from tennis_quant.model import _ece



def settled_result(item, event, completed):
    if not completed:
        return None
    actual, scheduled = _utc(completed["start_at"]), datetime.fromisoformat(item["start_at"])
    # ESPN replaces scheduled time with actual start. Bound delays before scoring;
    # never accept a forecast made after either start timestamp.
    if abs((actual-scheduled).total_seconds()) > 12*3600 or datetime.fromisoformat(item["as_of"]) >= min(actual,scheduled):
        return None
    if completed.get("tour") != event.get("tour") or completed.get("tournament") != event.get("tournament"):
        return None
    if event.get("player_a_id") != item["player_a_id"] or event.get("player_b_id") != item["player_b_id"]:
        return None
    names = {event.get("player_a"),event.get("player_b")}
    if None in names or len(names) != 2 or names != {completed.get("player_a"),completed.get("player_b")}:
        return None
    if completed.get("winner") not in names:
        return None
    return int(completed["winner"] == event["player_a"])


def main():
    out = ROOT / "artifacts"
    first = json.loads((out / "innovation_research.json").read_text(encoding="utf-8"))
    enrichment = json.loads((out / "enrichment_research.json").read_text(encoding="utf-8"))
    iteration = json.loads((out / "iteration_research.json").read_text(encoding="utf-8")) if (out / "iteration_research.json").exists() else None
    if iteration and "diagnostic" not in iteration:
        iteration = None
    selected = iteration["selected"] if iteration else enrichment["selected"]
    earlier = np.load(out / "enrichment_predictions.npz")
    arrays = np.load(out / "iteration_predictions.npz") if iteration else earlier
    rows = build_feature_rows()
    if not np.array_equal(arrays["match_id"], [r["row"]["id"] for r in rows]):
        raise ValueError("Predições não correspondem ao arquivo atual")
    y, years = arrays["y"], arrays["years"]
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "selected": selected,
              "artifact": (iteration or enrichment)["artifact"], "dataset_hash": enrichment["dataset_hash"],
              "status": "exploratory_retrospective", "new_configurations": 14 + (iteration["new_configurations"] if iteration else 0),
              "shuffle_controls": 6, "yearly": {}, "periods": {}, "candidates": [],
              "source_note": "Scores independently recomputed from saved forecasts, without refit. Reviewer is this session; no external independent evaluator.",
              "limitations": ["2024+ já consultado; sem holdout histórico intocado", "Arquivo termina em maio de 2026",
                              "Sem odds temporizadas nem evidência de rentabilidade"]}
    for name, score in enrichment["all_development_scores"].items():
        report["candidates"].append({"name": name, "mean_annual_brier": score, "round": 1 if name in first["candidates"] else 2})
    if iteration:
        for name, result in iteration["results"].items():
            report["candidates"].append({"name": name, "mean_annual_brier": result["mean_annual_brier"], "round": 3})
    def scored(mask, predictions):
        target,p = y[mask],predictions[mask]
        if not len(p) or not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
            raise ValueError("Predições inválidas no scoring independente")
        clipped = np.clip(p,1e-12,1-1e-12)
        metrics = {"n":len(p), "brier":float(np.mean((target-p)**2)),
                   "log_loss":float(-np.mean(target*np.log(clipped)+(1-target)*np.log1p(-clipped)))}
        metrics.update(accuracy=float(np.mean((predictions[mask] >= .5) == y[mask])),
                       ece_10=_ece(y[mask], predictions[mask]))
        return metrics
    for year in range(2019, 2027):
        mask = years == year
        report["yearly"][str(year)] = {"baseline": scored(mask, earlier["v4"]), "selected": scored(mask, arrays[selected])}
    for label, mask in (("development", (years >= 2019) & (years <= 2023)),
                        ("diagnostic", (years >= 2024) & (years <= 2026))):
        report["periods"][label] = {"baseline": scored(mask, earlier["v4"]), "selected": scored(mask, arrays[selected]),
            "paired": (iteration or enrichment)[label]["v4"]["paired"], "subgroups": {}, "reliability": []}
        for field, values in (("tour", ("ATP", "WTA")), ("surface", ("Hard", "Clay", "Grass"))):
            for value in values:
                sub = mask & np.array([r["row"][field] == value for r in rows])
                report["periods"][label]["subgroups"][value] = {"baseline": scored(sub, earlier["v4"]), "selected": scored(sub, arrays[selected])}
        p = arrays[selected][mask]
        target = y[mask]
        confidence = np.maximum(p, 1-p)
        correct = ((p >= .5) == target).astype(int)
        for low, high in ((.5, .6), (.6, .7), (.7, .8), (.8, .9), (.9, 1.01)):
            sub = (confidence >= low) & (confidence < high)
            report["periods"][label]["reliability"].append({"from": low, "to": min(high, 1), "n": int(sub.sum()),
                "predicted": float(np.mean(confidence[sub])) if sub.any() else None,
                "observed": float(np.mean(correct[sub])) if sub.any() else None})
    report["simultaneous"] = (iteration or enrichment)["simultaneous_all_rounds"][selected]
    if iteration:
        report["incremental_vs_previous"] = iteration["diagnostic"][enrichment["selected"]]["paired"]
    with engine.connect() as conn:
        events = {r["id"]: dict(r) for r in conn.execute(select(fixtures)).mappings()}
        results = {r["id"]: dict(r) for r in conn.execute(select(recent_results)).mappings()}
    frozen = {}
    rejected = 0
    for path in sorted((out / "forward").glob("*.json")):
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        for item in snapshot["forecasts"]:
            key = (snapshot["model_version"], item["fixture_id"])
            # First prediction wins; duplicates cannot improve the sample retroactively.
            if key in frozen:
                continue
            if datetime.fromisoformat(item["as_of"]) >= datetime.fromisoformat(item["start_at"]):
                rejected += 1
                continue
            event = events.get(item["fixture_id"], {})
            completed = results.get(item["fixture_id"])
            result_a = settled_result(item,event,completed)
            settled = result_a is not None
            frozen[key] = {"fixture_id": item["fixture_id"], "version": snapshot["model_version"],
                "player_a": event.get("player_a", item["player_a_id"]), "player_b": event.get("player_b", item["player_b_id"]),
                "start_at": item["start_at"], "as_of": item["as_of"], "baseline": item["baseline_probability_a"],
                "selected": item["challenger_probability_a"], "settled": settled,
                "result_a": result_a,
                "actual_start_at": _utc(completed["start_at"]).isoformat() if settled else None}
    report["forward"] = {"forecasts": list(frozen.values()), "n": len(frozen), "n_matches": len({item["fixture_id"] for item in frozen.values()}),
                         "settled": sum(item["settled"] for item in frozen.values()), "invalid_excluded": rejected,
                         "settlement_rule":"Same competition ID, both player identities and names, tour and tournament; forecast before scheduled and actual start; delay bounded to 12 hours",
                         "note": "Resultados públicos provisórios; amostra insuficiente para promoção"}
    by_version = {}
    for version in sorted({item["version"] for item in frozen.values()}):
        group = [item for item in frozen.values() if item["version"] == version]
        resolved = [item for item in group if item["settled"]]
        metrics = {}
        for model in ("baseline","selected"):
            if resolved:
                target = np.array([item["result_a"] for item in resolved])
                p = np.array([item[model] for item in resolved])
                if not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
                    raise ValueError("Probabilidades prospectivas inválidas")
                clipped = np.clip(p,1e-12,1-1e-12)
                metrics[model] = {"n":len(p),"brier":float(np.mean((p-target)**2)),
                                  "log_loss":float(-np.mean(target*np.log(clipped)+(1-target)*np.log1p(-clipped))),
                                  "accuracy":float(np.mean((p >= .5)==target))}
        by_version[version] = {"forecasts":len(group),"settled":len(resolved),"metrics":metrics,
                              "status":"insufficient_prospective_evidence"}
    report["forward"]["by_version"] = by_version
    write_json(out / "research_analysis.json", report)
    print(json.dumps({"selected": selected, "diagnostic": report["periods"]["diagnostic"], "forward": report["forward"]}, indent=2))


if __name__ == "__main__":
    main()
