"""Tests for repository clustering and corpus reference stats (T3.9)."""

import json

import joblib

from backend.app.ml.train_clusters import (
    CLUSTER_FEATURES,
    generate_seed_cluster_dataset,
    train_cluster_models,
)


def test_seed_cluster_dataset_structure():
    df = generate_seed_cluster_dataset()
    assert len(df) == 120
    for col in CLUSTER_FEATURES:
        assert col in df.columns


def test_train_cluster_artifacts(tmp_path):
    metrics = train_cluster_models(output_dir=tmp_path)

    assert "optimal_k" in metrics
    assert "silhouette_score" in metrics
    assert "pca_explained_variance_ratio" in metrics

    # Verify all artifacts
    assert (tmp_path / "kmeans.joblib").is_file()
    assert (tmp_path / "scaler.joblib").is_file()
    assert (tmp_path / "pca.joblib").is_file()
    assert (tmp_path / "metrics.json").is_file()
    assert (tmp_path / "feature_schema.json").is_file()
    assert (tmp_path / "training_manifest.json").is_file()
    assert (tmp_path / "model_card.md").is_file()
    assert (tmp_path / "corpus_reference" / "stats.json").is_file()

    # Verify stats.json content
    stats = json.loads((tmp_path / "corpus_reference" / "stats.json").read_text(encoding="utf-8"))
    for col in CLUSTER_FEATURES:
        assert col in stats
        assert "p50" in stats[col]
        assert "p90" in stats[col]
        assert "min" in stats[col]
        assert "max" in stats[col]

    # Verify KMeans and PCA execution
    scaler = joblib.load(tmp_path / "scaler.joblib")
    kmeans = joblib.load(tmp_path / "kmeans.joblib")
    pca = joblib.load(tmp_path / "pca.joblib")

    dummy_sample = [[50, 5000, 75.0, 4.0, 0.4, 10.0, 5, 2]]
    scaled = scaler.transform(dummy_sample)
    cluster = kmeans.predict(scaled)
    coords_2d = pca.transform(scaled)

    assert len(cluster) == 1
    assert 0 <= cluster[0] < metrics["optimal_k"]
    assert coords_2d.shape == (1, 2)
