"""Tests for Lizard and Radon metrics analyzer."""

from pathlib import Path

from backend.app.analyzers.metrics import analyze_file_metrics, analyze_repository_metrics


def test_python_metrics(tmp_path: Path):
    """Test Lizard and Radon on a Python file with known structure."""
    py_code = '''def simple_func(x):
    return x + 1

def complex_func(a, b, c):
    if a > 0:
        if b > 0:
            return a + b
        elif c > 0:
            return a + c
    elif b < 0:
        return b
    return 0
'''
    f = tmp_path / "sample.py"
    f.write_text(py_code, encoding="utf-8")

    metrics = analyze_file_metrics(f, "sample.py")
    assert metrics["loc"] == 12
    assert metrics["n_functions"] == 2
    assert metrics["ccn_max"] >= 5  # complex_func has branching
    assert metrics["maintainability_index"] is not None
    assert not metrics["maintainability_index_is_proxy"]
    assert metrics["halstead"] is not None
    assert metrics["radon_cc"] is not None
    assert len(metrics["radon_cc"]) == 2


def test_non_python_metrics(tmp_path: Path):
    """Test Lizard on a JavaScript file with maintainability proxy."""
    js_code = '''function calculateTotal(items) {
    let sum = 0;
    for (let i = 0; i < items.length; i++) {
        if (items[i].active) {
            sum += items[i].price;
        }
    }
    return sum;
}
'''
    f = tmp_path / "cart.js"
    f.write_text(js_code, encoding="utf-8")

    metrics = analyze_file_metrics(f, "cart.js")
    assert metrics["loc"] == 9
    assert metrics["n_functions"] == 1
    assert metrics["functions"][0]["name"] == "calculateTotal"
    assert metrics["maintainability_index_is_proxy"] is True
    assert 0.0 <= metrics["maintainability_index"] <= 100.0


def test_repository_metrics_aggregation(tmp_path: Path):
    """Test repository level aggregation of multiple files."""
    f1 = tmp_path / "a.py"
    f1.write_text("def a():\n    return 1\n", encoding="utf-8")

    f2 = tmp_path / "b.py"
    f2.write_text("def b():\n    if True:\n        pass\n", encoding="utf-8")

    repo_metrics = analyze_repository_metrics(tmp_path, ["a.py", "b.py"])
    assert repo_metrics["total_files"] == 2
    assert repo_metrics["total_functions"] == 2
    assert repo_metrics["ccn_max"] >= 2
    assert "a.py" in repo_metrics["files"]
    assert "b.py" in repo_metrics["files"]
