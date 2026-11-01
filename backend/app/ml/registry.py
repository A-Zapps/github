"""Central ML Model Registry for loading, serving, and monitoring model artifacts (RULES D1-D12)."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np

from backend.app.errors import AppError
from backend.app.ml.schema import validate_and_align_features

logger = logging.getLogger(__name__)

DEFAULT_MODELS_BASE = Path("./models")


class ModelRegistry:
    """Registry managing model artifact lifecycles, graceful 503 handling, and unified predictions."""

    def __init__(self, base_dir: Path = DEFAULT_MODELS_BASE):
        self.base_dir = base_dir
        self._cache: Dict[str, Any] = {}

    def get_model_path(self, model_name: str) -> Path:
        return self.base_dir / model_name

    def is_model_trained(self, model_name: str) -> bool:
        """Check if model directory and primary artifact exist."""
        p = self.get_model_path(model_name)
        if not p.is_dir():
            return False
        if model_name == "repo_clusters":
            return (p / "kmeans.joblib").is_file() and (p / "scaler.joblib").is_file()
        return (p / "model.joblib").is_file()

    def get_model_metadata(self, model_name: str) -> Dict[str, Any]:
        """Fetch metrics, schema, manifest, and model card if available."""
        p = self.get_model_path(model_name)
        trained = self.is_model_trained(model_name)
        if not trained:
            return {
                "name": model_name,
                "status": "MODEL_NOT_TRAINED",
                "trained": False,
                "metrics": None,
                "model_card": None,
                "manifest": None,
            }

        metrics = {}
        if (p / "metrics.json").is_file():
            try:
                metrics = json.loads((p / "metrics.json").read_text(encoding="utf-8"))
            except Exception:
                pass

        card = ""
        if (p / "model_card.md").is_file():
            try:
                card = (p / "model_card.md").read_text(encoding="utf-8")
            except Exception:
                pass

        manifest = {}
        if (p / "training_manifest.json").is_file():
            try:
                manifest = json.loads((p / "training_manifest.json").read_text(encoding="utf-8"))
            except Exception:
                pass

        return {
            "name": model_name,
            "status": "ready",
            "trained": True,
            "metrics": metrics,
            "model_card": card,
            "manifest": manifest,
        }

    def list_models(self) -> List[Dict[str, Any]]:
        """List all supported models and their live training status."""
        known = ["bug_risk", "repo_health", "maintenance_effort", "doc_sections", "repo_clusters"]
        return [self.get_model_metadata(name) for name in known]

    def _require_model(self, model_name: str) -> Path:
        """Validate model exists or raise 503 AppError."""
        p = self.get_model_path(model_name)
        if not self.is_model_trained(model_name):
            raise AppError(
                code="MODEL_NOT_TRAINED",
                message=f"Model '{model_name}' has not been trained or its artifacts are missing.",
                status_code=503,
            )
        return p

    def get_bug_risk_model(self) -> Tuple[Any, List[str], Dict[str, float]]:
        """Load bug risk pipeline, feature names, and thresholds."""
        p = self._require_model("bug_risk")
        if "bug_risk" not in self._cache:
            model = joblib.load(p / "model.joblib")
            schema = json.loads((p / "feature_schema.json").read_text(encoding="utf-8"))
            feature_names = [f["name"] for f in schema.get("features", [])]
            thresholds = {}
            if (p / "thresholds.json").is_file():
                thresholds = json.loads((p / "thresholds.json").read_text(encoding="utf-8"))
            self._cache["bug_risk"] = (model, feature_names, thresholds)
        return self._cache["bug_risk"]

    def predict_bug_risk(self, features: Any) -> List[Dict[str, Any]]:
        """Predict bug risk probabilities and risk tiers for files."""
        model, feature_names, thresholds = self.get_bug_risk_model()
        df = validate_and_align_features(features, feature_names)

        probs = model.predict_proba(df)[:, 1]
        med_th = thresholds.get("medium_risk_threshold", 0.35)
        high_th = thresholds.get("high_risk_threshold", 0.65)

        results = []
        for i, p in enumerate(probs):
            prob = round(float(p), 4)
            if prob >= high_th:
                tier = "high"
            elif prob >= med_th:
                tier = "medium"
            else:
                tier = "low"

            results.append({
                "probability": prob,
                "risk_tier": tier,
                "model_version": "1.0.0",
            })
        return results

    def get_repo_health_model(self) -> Tuple[Any, List[str], List[str]]:
        """Load repo health pipeline, feature names, and classes."""
        p = self._require_model("repo_health")
        if "repo_health" not in self._cache:
            model = joblib.load(p / "model.joblib")
            schema = json.loads((p / "feature_schema.json").read_text(encoding="utf-8"))
            feature_names = [f["name"] for f in schema.get("features", [])]
            metrics = json.loads((p / "metrics.json").read_text(encoding="utf-8"))
            classes = metrics.get("classes", ["Inactive", "Declining", "Moderately Active", "Healthy"])
            self._cache["repo_health"] = (model, feature_names, classes)
        return self._cache["repo_health"]

    def predict_repo_health(self, features: Any) -> Dict[str, Any]:
        """Predict repository health class and class probabilities."""
        model, feature_names, class_names = self.get_repo_health_model()
        df = validate_and_align_features(features, feature_names)

        probs = model.predict_proba(df)[0]
        pred_idx = int(np.argmax(probs))

        prob_dict = {
            class_names[i] if i < len(class_names) else f"Class_{i}": round(float(probs[i]), 4)
            for i in range(len(probs))
        }

        return {
            "health_class": class_names[pred_idx] if pred_idx < len(class_names) else "Unknown",
            "probabilities": prob_dict,
            "model_version": "1.0.0",
        }

    def get_maintenance_model(self) -> Tuple[Any, List[str]]:
        """Load maintenance effort regression model."""
        p = self._require_model("maintenance_effort")
        if "maintenance_effort" not in self._cache:
            model = joblib.load(p / "model.joblib")
            schema = json.loads((p / "feature_schema.json").read_text(encoding="utf-8"))
            feature_names = [f["name"] for f in schema.get("features", [])]
            self._cache["maintenance_effort"] = (model, feature_names)
        return self._cache["maintenance_effort"]

    def predict_maintenance_effort(self, features: Any) -> List[Dict[str, Any]]:
        """Predict expected maintenance churn (log1p) for files."""
        model, feature_names = self.get_maintenance_model()
        df = validate_and_align_features(features, feature_names)

        preds = model.predict(df)
        return [
            {
                "predicted_effort_log": round(float(p), 4),
                "predicted_churn_lines": round(float(np.expm1(p)), 1),
                "model_version": "1.0.0",
            }
            for p in preds
        ]

    def get_doc_sections_model(self) -> Any:
        """Load README section text classification pipeline."""
        p = self._require_model("doc_sections")
        if "doc_sections" not in self._cache:
            model = joblib.load(p / "model.joblib")
            self._cache["doc_sections"] = model
        return self._cache["doc_sections"]

    def predict_doc_sections(self, texts: List[str]) -> List[str]:
        """Classify README sections into functional classes."""
        if not texts:
            return []
        model = self.get_doc_sections_model()
        return list(model.predict(texts))

    def get_repo_clusters_model(self) -> Tuple[Any, Any, Any, List[str], Dict[str, Any]]:
        """Load KMeans, Scaler, PCA, and Corpus Reference stats."""
        p = self._require_model("repo_clusters")
        if "repo_clusters" not in self._cache:
            kmeans = joblib.load(p / "kmeans.joblib")
            scaler = joblib.load(p / "scaler.joblib")
            pca = joblib.load(p / "pca.joblib")
            schema = json.loads((p / "feature_schema.json").read_text(encoding="utf-8"))
            feature_names = [f["name"] for f in schema.get("features", [])]
            stats = {}
            stats_file = p / "corpus_reference" / "stats.json"
            if stats_file.is_file():
                stats = json.loads(stats_file.read_text(encoding="utf-8"))
            self._cache["repo_clusters"] = (kmeans, scaler, pca, feature_names, stats)
        return self._cache["repo_clusters"]

    def predict_repo_clusters(self, features: Any) -> Dict[str, Any]:
        """Predict cluster index, 2D PCA projection coordinates, and corpus percentile ranking."""
        kmeans, scaler, pca, feature_names, stats = self.get_repo_clusters_model()
        df = validate_and_align_features(features, feature_names)

        scaled = scaler.transform(df)
        cluster_id = int(kmeans.predict(scaled)[0])
        pca_coords = pca.transform(scaled)[0]

        # Calculate percentile estimates vs corpus for features present in stats
        percentiles: Dict[str, float] = {}
        row = df.iloc[0]
        for col in feature_names:
            val = float(row[col])
            col_stats = stats.get(col, {})
            # Approximate percentile using p10, p25, p50, p75, p90
            p10 = col_stats.get("p10", 0.0)
            p50 = col_stats.get("p50", 1.0)
            p90 = col_stats.get("p90", 2.0)
            if val <= p10:
                est = 10.0 * (val / max(0.001, p10))
            elif val <= p50:
                est = 10.0 + 40.0 * ((val - p10) / max(0.001, (p50 - p10)))
            elif val <= p90:
                est = 50.0 + 40.0 * ((val - p50) / max(0.001, (p90 - p50)))
            else:
                est = min(99.0, 90.0 + 9.0 * ((val - p90) / max(0.001, p90)))
            percentiles[col] = round(float(max(1.0, min(99.0, est))), 1)

        return {
            "cluster_id": cluster_id,
            "pca_coordinates": [round(float(pca_coords[0]), 3), round(float(pca_coords[1]), 3)],
            "corpus_percentiles": percentiles,
            "model_version": "1.0.0",
        }


# Singleton registry instance
_default_registry = ModelRegistry()


def get_model_registry() -> ModelRegistry:
    return _default_registry
