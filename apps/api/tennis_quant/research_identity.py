"""Version research artefacts by data, parameters and executable source."""
import hashlib
import json
from pathlib import Path

from .model import MODEL_PARAMETERS


def research_version(prefix, dataset_hash, feature_names, script_path):
    folder = Path(__file__).parent
    paths = [folder / name for name in ("features.py", "model.py", "innovation.py", "research_metadata.py",
                                        "research_dynamics.py", "research_identity.py")]
    paths.append(Path(script_path))
    signature = {"dataset": dataset_hash, "features": list(feature_names),
                 "parameters": MODEL_PARAMETERS["xgboost"], "train_end": 2024, "calibration": 2025,
                 "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    digest = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()[:16]
    return f"{prefix}-{digest}"
