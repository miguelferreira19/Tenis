from __future__ import annotations

import hashlib
import json
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import joblib
import numpy as np
from sqlalchemy import update
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss
from xgboost import XGBClassifier

from .db import DATA_DIR, backtest_runs, engine, init_db, model_versions, predictions
from .features import FEATURE_NAMES, FEATURE_VERSION, build_feature_rows
from .ingest import _insert_ignore

TRAIN_END, CALIBRATION_END, VALIDATION_END = 2021, 2022, 2023
MODEL_PARAMETERS = {
    "elo": {"global_weight": 0.55, "surface_weight": 0.45, "k_global": 32, "k_surface": 24},
    "logistic": {"C": 1.0, "fit_intercept": False, "max_iter": 500},
    "xgboost": {"n_estimators": 200, "max_depth": 3, "learning_rate": 0.05,
                "subsample": 0.8, "colsample_bytree": 0.8, "reg_lambda": 5,
                "objective": "binary:logistic", "tree_method": "hist", "random_state": 20260927},
}


def _split(year: int) -> str:
    if year <= TRAIN_END:
        return "train"
    if year <= CALIBRATION_END:
        return "calibration"
    if year <= VALIDATION_END:
        return "validation"
    return "test_oos"


def _clip(probabilities: np.ndarray) -> np.ndarray:
    return np.clip(np.asarray(probabilities, dtype=float), 1e-5, 1 - 1e-5)


def _raw_predict(family: str, fitted, X: np.ndarray, elo: np.ndarray) -> np.ndarray:
    if family == "elo":
        return elo
    forward = fitted.predict_proba(X)[:, 1]
    reverse = fitted.predict_proba(-X)[:, 1]
    return _clip((forward + 1 - reverse) / 2)


def _fit_calibrator(raw: np.ndarray, y: np.ndarray):
    logits = np.log(_clip(raw) / (1 - _clip(raw)))
    X = np.concatenate([logits, -logits]).reshape(-1, 1)
    labels = np.concatenate([y, 1 - y])
    fitted = LogisticRegression(fit_intercept=False, C=10, max_iter=500)
    fitted.fit(X, labels)
    return fitted


def _calibrate(calibrator, raw: np.ndarray) -> np.ndarray:
    logits = np.log(_clip(raw) / (1 - _clip(raw))).reshape(-1, 1)
    return _clip(calibrator.predict_proba(logits)[:, 1])


def _ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    bucket = np.minimum((p * bins).astype(int), bins - 1)
    return float(sum((bucket == i).mean() * abs(float(y[bucket == i].mean()) -
                                              float(p[bucket == i].mean()))
                     for i in range(bins) if np.any(bucket == i)))


def _metrics(rows: list[dict], p: np.ndarray) -> dict:
    y = np.array([r["y"] for r in rows], dtype=int)
    if not len(y):
        return {"n": 0}
    return {
        "n": len(y), "brier": round(float(brier_score_loss(y, p)), 6),
        "log_loss": round(float(log_loss(y, p, labels=[0, 1])), 6),
        "ece_10": round(_ece(y, p), 6),
        "accuracy": round(float(np.mean((p >= 0.5) == y)), 6),
    }


def train_and_evaluate() -> dict:
    init_db()
    rows = build_feature_rows()
    if not rows:
        raise ValueError("Sem jogos. Execute primeiro a importação histórica.")
    partitions = {name: [r for r in rows if _split(r["row"]["event_date"].year) == name]
                  for name in ("train", "calibration", "validation", "test_oos")}
    if any(len(partitions[k]) < 100 for k in ("train", "calibration", "validation", "test_oos")):
        raise ValueError("Amostra insuficiente para treino, calibração, seleção e teste OOS separados.")
    manifest = DATA_DIR / "manifest.json"
    if not manifest.exists():
        raise ValueError("Manifesto de dados em falta.")
    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    with engine.connect() as conn:
        from .db import raw_ingestions
        digests = sorted((r for r in conn.execute(raw_ingestions.select()).mappings()
                          if "/raw/results/" in r["local_path"].replace("\\", "/")),
                         key=lambda r: r["id"])
    dataset_hash = hashlib.sha256("".join(r["sha256"] for r in digests).encode()).hexdigest()
    X_train = np.stack([r["x"] for r in partitions["train"]])
    y_train = np.array([r["y"] for r in partitions["train"]], dtype=int)
    X_aug = np.concatenate([X_train, -X_train])
    y_aug = np.concatenate([y_train, 1 - y_train])
    models = {
        "elo": None,
        "logistic": LogisticRegression(**MODEL_PARAMETERS["logistic"]),
        "xgboost": XGBClassifier(**MODEL_PARAMETERS["xgboost"], n_jobs=4),
    }
    models["logistic"].fit(X_aug, y_aug)
    models["xgboost"].fit(X_aug, y_aug)
    now = datetime.now(timezone.utc)
    artifact_dir = DATA_DIR.parent / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, dict] = {}
    all_prediction_rows = []
    version_rows = []
    run_rows = []
    for family, fitted in models.items():
        signature = hashlib.sha256(json.dumps({"dataset": dataset_hash, "family": family,
            "features": FEATURE_VERSION, "parameters": MODEL_PARAMETERS[family]}, sort_keys=True).encode()).hexdigest()[:12]
        version = f"{family}-{FEATURE_VERSION}-{signature}"
        X_cal = np.stack([r["x"] for r in partitions["calibration"]])
        elo_cal = np.array([r["elo_probability"] for r in partitions["calibration"]])
        raw_cal = _raw_predict(family, fitted, X_cal, elo_cal)
        calibrator = _fit_calibrator(raw_cal, np.array([r["y"] for r in partitions["calibration"]]))
        joblib.dump({"family": family, "model": fitted, "calibrator": calibrator,
                     "feature_names": FEATURE_NAMES, "version": version}, artifact_dir / f"{version}.joblib")
        family_summary = {}
        for split in ("calibration", "validation", "test_oos"):
            part = partitions[split]
            X = np.stack([r["x"] for r in part])
            elo = np.array([r["elo_probability"] for r in part])
            p = _calibrate(calibrator, _raw_predict(family, fitted, X, elo))
            family_summary[split] = _metrics(part, p)
            for circuit in ("ATP", "WTA"):
                mask = np.array([r["row"]["tour"] == circuit for r in part])
                family_summary[f"{split}_{circuit}"] = _metrics([r for r, keep in zip(part, mask) if keep], p[mask])
            for surface in ("Hard", "Clay", "Grass"):
                mask = np.array([r["row"]["surface"] == surface for r in part])
                family_summary[f"{split}_{surface.lower()}"] = _metrics([r for r, keep in zip(part, mask) if keep], p[mask])
            for record, probability in zip(part, p):
                match = record["row"]
                as_of = datetime.combine(match["event_date"] - timedelta(days=1),
                                         time(23, 59, 59), tzinfo=timezone.utc)
                all_prediction_rows.append({
                    "id": f"{match['id']}:{version}", "match_id": match["id"],
                    "model_version": version, "feature_version": FEATURE_VERSION,
                    "as_of": as_of, "probability_a": float(probability),
                    "fair_odds_a": float(1 / probability),
                    "fair_odds_b": float(1 / (1 - probability)),
                    "split": split,
                    "features": {"vector": dict(zip(FEATURE_NAMES, record["x"].tolist())),
                                 "players": record["details"]},
                    "quality": record["quality"],
                })
        version_rows.append({
            "id": version, "family": family, "trained_at": now,
            "train_end": datetime(TRAIN_END, 12, 31).date(),
            "validation_end": datetime(VALIDATION_END, 12, 31).date(),
            "dataset_hash": dataset_hash, "feature_version": FEATURE_VERSION,
            "parameters": MODEL_PARAMETERS[family], "status": "research_only",
        })
        for split in ("validation", "test_oos"):
            run_rows.append({"id": f"{version}:{split}", "model_version": version,
                "created_at": now, "split": split, "metrics": family_summary[split],
                "status": "prediction_only_no_odds"})
        summary[family] = {"version": version, **family_summary}
    selected = min(summary, key=lambda family: summary[family]["validation"]["brier"])
    summary["selected_by_validation"] = selected
    summary["dataset_hash"] = dataset_hash
    summary["data_source"] = manifest_data["source"]
    summary["splits"] = {k: len(v) for k, v in partitions.items()}
    summary["betting_backtest"] = "blocked_no_timestamped_odds"
    with engine.begin() as conn:
        conn.execute(update(model_versions).where(model_versions.c.feature_version != FEATURE_VERSION)
                     .values(status="superseded_temporal_audit"))
        _insert_ignore(conn, model_versions, version_rows)
        _insert_ignore(conn, predictions, all_prediction_rows)
        _insert_ignore(conn, backtest_runs, run_rows)
    (artifact_dir / "evaluation.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary

