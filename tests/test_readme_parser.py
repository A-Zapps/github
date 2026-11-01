"""Tests for README documentation completeness and section parsing (T5.1)."""

from pathlib import Path

from backend.app.analyzers.readme_parser import parse_and_score_readme


def test_no_readme_returns_zero(tmp_path: Path):
    res = parse_and_score_readme(tmp_path)
    assert res["has_readme"] is False
    assert res["overall_score"] == 0
    assert res["grade"] == "F"
    assert len(res["suggestions"]) >= 1
    assert res["checklist"]["installation"]["status"] == "missing"
    assert res["checklist"]["usage"]["status"] == "missing"


def test_complete_readme_high_score(tmp_path: Path):
    readme_content = """# Awesome Project
This is an enterprise-grade open source project.

## Installation
Run `pip install awesome-project` from the PyPI repository.
Make sure you have Python 3.10 or higher and an isolated virtual environment created.

## Usage
Import the package and execute the command line runner:
```python
from awesome import run_analysis
results = run_analysis("pallets/flask")
print(results)
```

## Contributing
We welcome pull requests and issue reports!
Please check our contributing guidelines, fork the repository, and run `pytest tests/` before submitting.

## License
Licensed under the Apache License, Version 2.0. See the LICENSE file for more details.
"""
    (tmp_path / "README.md").write_text(readme_content, encoding="utf-8")

    res = parse_and_score_readme(tmp_path)
    assert res["has_readme"] is True
    assert res["overall_score"] == 100
    assert res["grade"] == "A"
    assert res["checklist"]["installation"]["status"] == "found"
    assert res["checklist"]["usage"]["status"] == "found"
    assert res["checklist"]["contributing"]["status"] == "found"
    assert res["checklist"]["license"]["status"] == "found"
    assert len(res["suggestions"]) == 0


def test_missing_install_and_usage_scores_differently_for_right_reason(tmp_path: Path):
    """Verify fixture without install and usage scores significantly lower due to those specific sections."""
    # Complete repo
    dir_complete = tmp_path / "complete"
    dir_complete.mkdir()
    (dir_complete / "README.md").write_text("""# Project
## Installation
Pip install all requirements and libraries from wheels. Ensure gcc is installed.

## Usage
Run python main.py --config config.yaml with all your runtime settings.

## Contributing
Submit pull requests to the master branch.

## License
MIT License.
""", encoding="utf-8")

    # Incomplete repo (lacking install and usage)
    dir_incomplete = tmp_path / "incomplete"
    dir_incomplete.mkdir()
    (dir_incomplete / "README.md").write_text("""# Project
Just a generic description of a tool with no installation or usage commands.

## Contributing
Submit pull requests to the master branch with tests passing.

## License
MIT License.
""", encoding="utf-8")

    res_comp = parse_and_score_readme(dir_complete)
    res_incomp = parse_and_score_readme(dir_incomplete)

    # Must score differently
    assert res_comp["overall_score"] > res_incomp["overall_score"]

    # Exactly for the right reason (missing installation and usage: 30 + 30 = 60 points lower)
    assert res_incomp["checklist"]["installation"]["status"] == "missing"
    assert res_incomp["checklist"]["usage"]["status"] == "missing"
    assert res_incomp["checklist"]["installation"]["earned"] == 0
    assert res_incomp["checklist"]["usage"]["earned"] == 0
    assert res_comp["checklist"]["installation"]["earned"] == 30
    assert res_comp["checklist"]["usage"]["earned"] == 30

    # Ensure suggestions specifically highlight installation and usage
    suggestions_text = " ".join(res_incomp["suggestions"])
    assert "Installation" in suggestions_text
    assert "Usage" in suggestions_text
