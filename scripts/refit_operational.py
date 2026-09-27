"""Refit the frozen model family on recent data for exploratory future fixtures."""
from __future__ import annotations

import hashlib
import json
import sys
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


def main():
    report_path = ROOT / "artifacts" / "evaluation.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    # The family is frozen by the original 2023 validation, not reselected in 2026.
    family = report["selected_by_validation"]
    if family != "xgboost":
        raise ValueError("O refit atual espera a família XGBoost validada em 2023")
    rows = build_feature_rows()
    train = [r for r in rows if r["row"]["event_date"].year <= 2024]
    cal = [r for r in rows if r["row"]["event_date"].year == 2025]
    check = [r for r in rows if r["row"]["event_date"].year == 2026]
    if min(len(train), len(cal), len(check)) < 500:
        raise ValueError("Amostra insuficiente para refit e verificação temporal")
    X = np.stack([r["x"] for r in train])
    y = np.array([r["y"] for r in train])
    fitted = XGBClassifier(**MODEL_PARAMETERS[family], n_jobs=4)
    fitted.fit(np.concatenate([X, -X]), np.concatenate([y, 1 - y]))
    def forecast(part):
        features = np.stack([r["x"] for r in part])
        elo = np.array([r["elo_probability"] for r in part])
        return _raw_predict(family, fitted, features, elo)
    calibrator = _fit_calibrator(forecast(cal), np.array([r["y"] for r in cal]))
    p = _calibrate(calibrator, forecast(check))
    observed = np.array([r["y"] for r in check])
    signature = hashlib.sha256(json.dumps({"dataset": report["dataset_hash"],
        "family": family, "feature_version": FEATURE_VERSION, "train_end": 2024,
        "calibration": 2025, "parameters": MODEL_PARAMETERS[family]}, sort_keys=True).encode()).hexdigest()[:12]
    version = f"{family}-operational-{FEATURE_VERSION}-{signature}"
    joblib.dump({"family": family, "model": fitted, "calibrator": calibrator,
                 "feature_names": FEATURE_NAMES, "version": version},
                ROOT / "artifacts" / f"{version}.joblib")
    operational = {"version": version, "family": family, "feature_version": FEATURE_VERSION,
        "train_end": "2024-12-31", "calibration_year": 2025,
        "diagnostic_2026": {"n": len(check),
                            "brier": round(float(brier_score_loss(observed, p)), 6),
                            "log_loss": round(float(log_loss(observed, p)), 6)},
        "last_archive_event": max(r["row"]["event_date"] for r in rows).isoformat(),
        "status": "research_only_forward_confirmation_pending",
        "note": "Refit para jogos futuros. 2026 é diagnóstico consultado, não holdout intocado; sem validação de ROI/CLV."}
    with engine.begin() as conn:
        _insert_ignore(conn, model_versions, [{"id": version, "family": family,
            "trained_at": datetime.now(timezone.utc), "train_end": datetime(2024, 12, 31).date(),
            "validation_end": datetime(2025, 12, 31).date(), "dataset_hash": report["dataset_hash"],
            "feature_version": FEATURE_VERSION, "parameters": MODEL_PARAMETERS[family],
            "status": "research_only"}])
    (ROOT / "artifacts" / "operational.json").write_text(json.dumps(operational, indent=2), encoding="utf-8")
    report["operational_version"] = version
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(operational, indent=2))


if __name__ == "__main__":
    main()
