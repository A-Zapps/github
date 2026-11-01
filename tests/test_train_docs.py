"""Tests for documentation section classifier training and artifacts (T3.8)."""


import joblib

from backend.app.ml.train_docs import (
    DOC_CLASSES,
    split_readme_sections,
    train_docs_model,
)


def test_split_readme_sections_and_labeling():
    sample_readme = """# My Project
A cool open source project that does great things.

## Installation
Run pip install myproject to install it from PyPI.

## Usage
Import it and run main().

## Contributing
Please send PRs to the main branch.

## License
MIT License.
"""
    sections = split_readme_sections(sample_readme)
    assert len(sections) >= 4
    categories = [cat for cat, _ in sections]
    assert "installation" in categories
    assert "usage" in categories
    assert "contributing" in categories
    assert "license" in categories

    # Ensure heading text is not in body
    for cat, body in sections:
        assert not body.startswith("## ")


def test_train_docs_artifacts(tmp_path):
    metrics = train_docs_model(output_dir=tmp_path)

    assert "MultinomialNB" in metrics["models"]
    assert "MajorityClassBaseline" in metrics["models"]
    assert "accuracy" in metrics["models"]["MultinomialNB"]

    # Verify artifacts
    assert (tmp_path / "model.joblib").is_file()
    assert (tmp_path / "metrics.json").is_file()
    assert (tmp_path / "feature_schema.json").is_file()
    assert (tmp_path / "training_manifest.json").is_file()
    assert (tmp_path / "model_card.md").is_file()

    # Verify model prediction
    model = joblib.load(tmp_path / "model.joblib")
    test_text = ["pip install -r requirements.txt and configure your virtual environment"]
    preds = model.predict(test_text)
    assert len(preds) == 1
    assert preds[0] in DOC_CLASSES
