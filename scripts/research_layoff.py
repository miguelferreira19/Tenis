"""Audit a single research challenger with annual rolling-origin forecasts.

The 2024+ period has already been consulted in this project. Its metrics are
diagnostic, never a pristine holdout or a betting-strategy approval.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import brier_score_loss, log_loss
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from tennis_quant.db import engine, model_versions
from tennis_quant.features import FEATURE_NAMES, FEATURE_VERSION, build_feature_rows
from tennis_quant.ingest import _insert_ignore
from tennis_quant.model import MODEL_PARAMETERS, _calibrate, _fit_calibrator, _raw_predict

FEATURE_NAME = "layoff_log_365d"
YEARS = range(2019, 2027)


def _fit_and_predict(X, y, elo, train, calibration, test):
    model = XGBClassifier(**MODEL_PARAMETERS["xgboost"], n_jobs=4)
    model.fit(np.concatenate((X[train], -X[train])),
              np.concatenate((y[train], 1 - y[train])))
    calibrator = _fit_calibrator(_raw_predict("xgboost", model, X[calibration], elo[calibration]),
                                 y[calibration])
    p = _calibrate(calibrator, _raw_predict("xgboost", model, X[test], elo[test]))
    return p, model, calibrator


def _metrics(y, p):
    return {"n": int(len(y)), "brier": float(brier_score_loss(y, p)),
            "log_loss": float(log_loss(y, p, labels=[0, 1]))}


def _paired(rows, years, y, baseline, challenger, mask):
    clusters = defaultdict(list)
    for i in np.flatnonzero(mask):
        row = rows[i]["row"]
        clusters[(int(years[i]), row["tour"], row["tournament_id"])].append(
            (baseline[i] - y[i]) ** 2 - (challenger[i] - y[i]) ** 2)
    counts = np.array([len(values) for values in clusters.values()])
    sums = np.array([sum(values) for values in clusters.values()])
    rng = np.random.default_rng(20260927)
    draws = rng.integers(0, len(counts), size=(2000, len(counts)))
    samples = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)
    return {"improvement": float(sums.sum() / counts.sum()),
            "bootstrap_95": [float(x) for x in np.quantile(samples, (0.025, 0.975))],
            "n_tournaments": len(counts), "resamples": 2000}


def main():
    rows = build_feature_rows()
    base = np.stack([r["x"] for r in rows])
    layoff = np.array([r["layoff_feature"] for r in rows])
    candidate = np.column_stack((base, layoff))
    y = np.array([r["y"] for r in rows], dtype=int)
    elo = np.array([r["elo_probability"] for r in rows])
    years = np.array([r["row"]["event_date"].year for r in rows])
    baseline_p = np.full(len(rows), np.nan)
    challenger_p = np.full(len(rows), np.nan)
    report = {"feature": FEATURE_NAME, "baseline_feature_version": FEATURE_VERSION,
              "model": "xgboost", "parameter_source": "MODEL_PARAMETERS.xgboost",
              "split_rule": "train <= year-2; calibrate year-1; evaluate year",
              "yearly": {}, "status": "research_only_forward_confirmation_pending"}
    for year in YEARS:
        train, cal, test = years <= year - 2, years == year - 1, years == year
        if not test.any():
            continue
        baseline_p[test], _, _ = _fit_and_predict(base, y, elo, train, cal, test)
        challenger_p[test], fitted, calibrator = _fit_and_predict(candidate, y, elo, train, cal, test)
        report["yearly"][str(year)] = {"baseline": _metrics(y[test], baseline_p[test]),
            "challenger": _metrics(y[test], challenger_p[test])}
        if year == 2026:
            operational_model, operational_calibrator = fitted, calibrator
    for label, mask in (("development_2019_2023", (years >= 2019) & (years <= 2023)),
                        ("diagnostic_2024_2026", (years >= 2024) & (years <= 2026))):
        if not mask.any():
            continue
        comparison = {"baseline": _metrics(y[mask], baseline_p[mask]),
                      "challenger": _metrics(y[mask], challenger_p[mask]),
                      "paired": _paired(rows, years, y, baseline_p, challenger_p, mask)}
        for field, values in (("tour", ("ATP", "WTA")),
                              ("surface", ("Hard", "Clay", "Grass"))):
            comparison[f"by_{field}"] = {}
            for value in values:
                subset = mask & np.array([r["row"][field] == value for r in rows])
                if subset.any():
                    comparison[f"by_{field}"][value] = {"n": int(subset.sum()),
                        "brier_improvement": float(np.mean((baseline_p[subset] - y[subset]) ** 2 -
                                                           (challenger_p[subset] - y[subset]) ** 2))}
        report[label] = comparison
    evaluation = json.loads((ROOT / "artifacts" / "evaluation.json").read_text(encoding="utf-8"))
    signature = hashlib.sha256(json.dumps({"dataset": evaluation["dataset_hash"],
        "feature": FEATURE_NAME, "parameters": MODEL_PARAMETERS["xgboost"],
        "train_end": 2024, "calibration": 2025}, sort_keys=True).encode()).hexdigest()[:12]
    version = f"xgboost-prematch-v5-layoff-{signature}"
    report["version"] = version
    report["active_model_unchanged"] = evaluation.get("operational_version")
    report["limitations"] = ["Anos 2024+ já consultados; confirmação prospectiva em falta.",
        "Dados históricos usam início do torneio, não hora exata de cada jogo.",
        "Sem odds históricas temporizadas: ROI, CLV e gates de apostas não calculáveis."]
    artifact_dir = ROOT / "artifacts"
    artifact_dir.mkdir(exist_ok=True)
    if "operational_model" in locals():
        joblib.dump({"family": "xgboost", "model": operational_model,
                     "calibrator": operational_calibrator,
                     "feature_names": FEATURE_NAMES + (FEATURE_NAME,), "version": version,
                     "status": "research_only_challenger"}, artifact_dir / f"{version}.joblib")
        with engine.begin() as conn:
            _insert_ignore(conn, model_versions, [{"id": version, "family": "xgboost",
                "trained_at": datetime.now(timezone.utc), "train_end": datetime(2024, 12, 31).date(),
                "validation_end": datetime(2025, 12, 31).date(),
                "dataset_hash": evaluation["dataset_hash"], "feature_version": "prematch-v5-layoff",
                "parameters": {**MODEL_PARAMETERS["xgboost"], "extra_feature": FEATURE_NAME},
                "status": "research_only_challenger"}])
    (artifact_dir / "layoff_research.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"version": version, "development": report.get("development_2019_2023"),
                      "diagnostic": report.get("diagnostic_2024_2026")}, indent=2))


if __name__ == "__main__":
    main()
