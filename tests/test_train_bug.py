"""Tests for bug risk model training and artifacts (RULES D1, D5, D6, D10)."""

import json
from pathlib import Path

import joblib
import numpy as np

from backend.app.ml.train_bug import BUG_FEATURES, train_bug_models


def test_train_bug_artifacts(tmp_path: Path):
    """Verify train_bug_models produces all 6 artifacts and compares against all baselines."""
    out_dir = tmp_path / "bug_risk"
    metrics = train_bug_models(output_dir=out_dir)

    # 1. Verify files exist
    assert (out_dir / "model.joblib").is_file()
    assert (out_dir / "metrics.json").is_file()
    assert (out_dir / "thresholds.json").is_file()
    assert (out_dir / "model_card.md").is_file()
    assert (out_dir / "training_manifest.json").is_file()
    assert (out_dir / "feature_schema.json").is_file()

    # 2. Verify all 4 models and both baselines are in metrics.json
    metrics_data = json.loads((out_dir / "metrics.json").read_text(encoding="utf-8"))
    assert "PriorRateBaseline" in metrics_data["baselines"]
    assert "MostChangedFilesHeuristic" in metrics_data["baselines"]

    models_dict = metrics_data["models"]
    assert "RandomForest" in models_dict
    assert "XGBoost" in models_dict
    assert "LogisticRegression" in models_dict
    assert "CalibratedLinearSVM" in models_dict

    # Check metrics fields
    assert "pr_auc" in models_dict["RandomForest"]
    assert "roc_auc" in models_dict["RandomForest"]

    # 3. Verify thresholds.json has cut points
    thresh_data = json.loads((out_dir / "thresholds.json").read_text(encoding="utf-8"))
    assert "low_max" in thresh_data
    assert "high_min" in thresh_data

    # 4. Verify model loading and inference
    model = joblib.load(out_dir / "model.joblib")
    sample_vec = np.zeros((1, len(BUG_FEATURES)))
    prob = model.predict_proba(sample_vec)
    assert prob.shape == (1, 2)
    assert 0.0 <= prob[0, 1] <= 1.0
