"""Feature vector validation against model schemas (RULES D1-D10)."""

import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from backend.app.errors import AppError


def load_feature_schema(schema_path: Path) -> List[Dict[str, Any]]:
    """Load and parse feature_schema.json."""
    if not schema_path.is_file():
        raise AppError(
            code="SCHEMA_NOT_FOUND",
            message=f"Feature schema not found at {schema_path}",
            status_code=500,
        )
    data = json.loads(schema_path.read_text(encoding="utf-8"))
    return data.get("features", [])


def validate_and_align_features(
    features: Any,
    expected_feature_names: List[str],
    fill_value: float = 0.0,
) -> pd.DataFrame:
    """Validate input features, verify required columns, fill missing with fill_value, and align column order."""
    if isinstance(features, dict):
        df = pd.DataFrame([features])
    elif isinstance(features, list):
        df = pd.DataFrame(features)
    elif isinstance(features, pd.DataFrame):
        df = features.copy()
    else:
        raise AppError(
            code="INVALID_FEATURES_INPUT",
            message="Features must be a dictionary, list of dictionaries, or pandas DataFrame.",
            status_code=400,
        )

    # Ensure all expected feature columns are present
    for col in expected_feature_names:
        if col not in df.columns:
            df[col] = fill_value

    # Fill NA values
    df = df[expected_feature_names].fillna(fill_value)

    # Convert numeric types
    for col in expected_feature_names:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(fill_value)

    return df
