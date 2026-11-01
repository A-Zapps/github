"""Tests for 6-line window code duplication detection."""

from pathlib import Path

from backend.app.analyzers.duplication import detect_duplication


def test_duplication_detection(tmp_path: Path):
    """Test duplicate detection between two files with shared block."""
    shared_block = """line one = 1
line two = 2
line three = 3
line four = 4
line five = 5
line six = 6
"""
    f1 = tmp_path / "module_a.py"
    f1.write_text(f"header_a = 'hello'\n{shared_block}footer_a = 'bye'\n", encoding="utf-8")

    f2 = tmp_path / "module_b.py"
    f2.write_text(f"header_b = 'welcome'\n{shared_block}footer_b = 'goodbye'\n", encoding="utf-8")

    f3 = tmp_path / "unique.py"
    f3.write_text("x = 10\ny = 20\nz = 30\n", encoding="utf-8")

    res = detect_duplication(tmp_path, ["module_a.py", "module_b.py", "unique.py"])
    assert res["duplicate_blocks_count"] >= 1
    assert res["duplicate_lines"] >= 12  # At least 6 lines in module_a and 6 in module_b
    assert res["duplication_percentage"] > 0
    assert res["files"]["module_a.py"]["duplicate_lines"] == 6
    assert res["files"]["module_b.py"]["duplicate_lines"] == 6
    assert res["files"]["unique.py"]["duplicate_lines"] == 0


def test_no_duplication(tmp_path: Path):
    """Test when no duplicate blocks exist."""
    f1 = tmp_path / "file1.txt"
    f1.write_text("a\nb\nc\nd\ne\n", encoding="utf-8")

    f2 = tmp_path / "file2.txt"
    f2.write_text("v\nw\nx\ny\nz\n", encoding="utf-8")

    res = detect_duplication(tmp_path, ["file1.txt", "file2.txt"])
    assert res["duplicate_blocks_count"] == 0
    assert res["duplicate_lines"] == 0
    assert res["duplication_percentage"] == 0.0
