"""Tests for ML Model Registry and feature schema validation (T3.10)."""


import pytest

from backend.app.errors import AppError
from backend.app.ml.registry import ModelRegistry, get_model_registry
from backend.app.ml.schema import validate_and_align_features


def test_validate_and_align_features():
    features = {"loc": 120, "n_functions": 4}
    expected = ["loc", "nloc", "n_functions", "ccn_mean"]
    df = validate_and_align_features(features, expected, fill_value=0.0)

    assert list(df.columns) == expected
    assert df["loc"].iloc[0] == 120.0
    assert df["nloc"].iloc[0] == 0.0
    assert df["n_functions"].iloc[0] == 4.0
    assert df["ccn_mean"].iloc[0] == 0.0


def test_registry_lists_models():
    registry = get_model_registry()
    models = registry.list_models()
    assert len(models) == 5
    names = [m["name"] for m in models]
    assert "bug_risk" in names
    assert "repo_health" in names
    assert "maintenance_effort" in names
    assert "doc_sections" in names
    assert "repo_clusters" in names

    # Real models currently trained should be ready
    for m in models:
        assert m["status"] in ("ready", "MODEL_NOT_TRAINED")


def test_predict_methods_on_trained_models():
    registry = get_model_registry()

    # 1. Bug risk
    bug_feat = {"loc": 200, "ccn_max": 12.0, "churn_ratio": 2.5}
    bug_res = registry.predict_bug_risk(bug_feat)
    assert len(bug_res) == 1
    assert "probability" in bug_res[0]
    assert bug_res[0]["risk_tier"] in ("low", "medium", "high")

    # 2. Repo health
    health_feat = {"commits_per_month_mean": 25.0, "distinct_authors": 10, "bus_factor": 4}
    health_res = registry.predict_repo_health(health_feat)
    assert "health_class" in health_res
    assert "probabilities" in health_res
    assert sum(health_res["probabilities"].values()) == pytest.approx(1.0, abs=1e-2)

    # 3. Maintenance effort
    maint_feat = {"loc": 300, "commits_12m": 8, "churn_ratio": 1.5}
    maint_res = registry.predict_maintenance_effort(maint_feat)
    assert len(maint_res) == 1
    assert "predicted_effort_log" in maint_res[0]

    # 4. Doc sections
    texts = ["Run pip install example to install from PyPI.", "Licensed under MIT License."]
    docs_res = registry.predict_doc_sections(texts)
    assert len(docs_res) == 2

    # 5. Repo clusters
    cluster_feat = {"total_files": 50, "total_loc": 5000, "avg_maintainability": 75.0}
    cluster_res = registry.predict_repo_clusters(cluster_feat)
    assert "cluster_id" in cluster_res
    assert len(cluster_res["pca_coordinates"]) == 2
    assert "corpus_percentiles" in cluster_res


def test_model_not_trained_returns_503(tmp_path):
    """Deleting a model folder or testing an empty directory returns 503 (MODEL_NOT_TRAINED)."""
    empty_registry = ModelRegistry(base_dir=tmp_path)

    # list_models reflects MODEL_NOT_TRAINED
    meta = empty_registry.get_model_metadata("bug_risk")
    assert meta["status"] == "MODEL_NOT_TRAINED"
    assert meta["trained"] is False

    # Calling predict raises AppError with 503 and code MODEL_NOT_TRAINED
    with pytest.raises(AppError) as exc_info:
        empty_registry.predict_bug_risk({"loc": 100})
    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "MODEL_NOT_TRAINED"

    with pytest.raises(AppError) as exc_info:
        empty_registry.predict_repo_health({"commits_per_month_mean": 10})
    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "MODEL_NOT_TRAINED"

    with pytest.raises(AppError) as exc_info:
        empty_registry.predict_maintenance_effort({"loc": 100})
    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "MODEL_NOT_TRAINED"

    with pytest.raises(AppError) as exc_info:
        empty_registry.predict_doc_sections(["Some text"])
    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "MODEL_NOT_TRAINED"

    with pytest.raises(AppError) as exc_info:
        empty_registry.predict_repo_clusters({"total_files": 10})
    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "MODEL_NOT_TRAINED"
