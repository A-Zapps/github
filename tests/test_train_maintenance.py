"""Tests for maintenance effort model training and artifacts (T3.7)."""

import json

import joblib

from backend.app.ml.train_maintenance import (
    MAINTENANCE_FEATURES,
    generate_seed_maintenance_dataset,
    train_maintenance_models,
)


def test_seed_maintenance_dataset_structure():
    df = generate_seed_maintenance_dataset()
    assert len(df) == 200
    assert "label_maintenance_effort" in df.columns
    for feat in MAINTENANCE_FEATURES:
        assert feat in df.columns


def test_train_maintenance_artifacts(tmp_path):
    metrics = train_maintenance_models(output_dir=tmp_path)

    assert "RandomForestRegressor" in metrics["models"]
    assert "MeanPredictorBaseline" in metrics["models"]
    assert "mae" in metrics["models"]["RandomForestRegressor"]

    # Verify all artifacts written
    assert (tmp_path / "model.joblib").is_file()
    assert (tmp_path / "metrics.json").is_file()
    assert (tmp_path / "feature_schema.json").is_file()
    assert (tmp_path / "training_manifest.json").is_file()
    assert (tmp_path / "model_card.md").is_file()

    # Verify model is loadable and can predict
    model = joblib.load(tmp_path / "model.joblib")
    dummy_input = [[100.0] * len(MAINTENANCE_FEATURES)]
    preds = model.predict(dummy_input)
    assert len(preds) == 1
    assert isinstance(float(preds[0]), float)

    schema = json.loads((tmp_path / "feature_schema.json").read_text(encoding="utf-8"))
    assert len(schema["features"]) == len(MAINTENANCE_FEATURES)
