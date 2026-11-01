"""Tests for repo health model training and artifacts (RULES D1, D5, D7, D10)."""

import json
from pathlib import Path

import joblib
import numpy as np

from backend.app.ml.train_health import HEALTH_FEATURES, train_health_models


def test_train_health_artifacts(tmp_path: Path):
    """Verify train_health_models produces all required artifacts and reports baselines."""
    out_dir = tmp_path / "repo_health"
    metrics = train_health_models(output_dir=out_dir)

    # 1. Verify all 5 artifact files exist
    assert (out_dir / "model.joblib").is_file()
    assert (out_dir / "metrics.json").is_file()
    assert (out_dir / "model_card.md").is_file()
    assert (out_dir / "training_manifest.json").is_file()
    assert (out_dir / "feature_schema.json").is_file()

    # 2. Verify metrics.json reports both models and the baseline
    metrics_data = json.loads((out_dir / "metrics.json").read_text(encoding="utf-8"))
    assert "MajorityClassBaseline" in metrics_data["models"]
    assert "LogisticRegression" in metrics_data["models"]
    assert "XGBoost" in metrics_data["models"]
    assert "macro_f1" in metrics_data["models"]["MajorityClassBaseline"]
    assert "macro_f1" in metrics_data["models"]["XGBoost"]

    # 3. Verify feature_schema.json matches HEALTH_FEATURES
    schema_data = json.loads((out_dir / "feature_schema.json").read_text(encoding="utf-8"))
    schema_names = [f["name"] for f in schema_data["features"]]
    assert schema_names == HEALTH_FEATURES

    # 4. Verify model loading and inference
    loaded_model = joblib.load(out_dir / "model.joblib")
    sample_vec = np.zeros((1, len(HEALTH_FEATURES)))
    pred = loaded_model.predict(sample_vec)
    assert pred[0] in (0, 1, 2, 3)
