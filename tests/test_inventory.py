"""Unit tests for repository file inventory, language classification, and test detection."""

import os
import shutil
import tempfile

from backend.app.analyzers.inventory import (
    detect_language,
    is_test_file,
    scan_inventory,
)


def test_language_detection_by_extension():
    """Verify language detection across standard languages and extensions."""
    assert detect_language("app.py") == "Python"
    assert detect_language("server.js") == "JavaScript"
    assert detect_language("component.tsx") == "TypeScript"
    assert detect_language("Main.java") == "Java"
    assert detect_language("lib.rs") == "Rust"
    assert detect_language("main.go") == "Go"
    assert detect_language("styles.css") == "CSS"
    assert detect_language("README.md") == "Markdown"
    assert detect_language("binary.unknown") == "Other"


def test_test_file_identification():
    """Verify test file detection across directory patterns and filename conventions."""
    assert is_test_file("tests/test_app.py") is True
    assert is_test_file("test/unit/calculator_test.py") is True
    assert is_test_file("src/__tests__/Button.test.js") is True
    assert is_test_file("src/components/Modal.spec.ts") is True
    assert is_test_file("src/test/java/UserTest.java") is True
    assert is_test_file("pkg/math/calc_test.go") is True

    # Non-test files
    assert is_test_file("src/app.py") is False
    assert is_test_file("src/components/Button.jsx") is False
    assert is_test_file("lib/test_utils/helpers.py") is True  # In test directory
    assert is_test_file("contest_results.py") is False


def test_scan_inventory_fixture_repo():
    """Verify inventory scan on a fixture directory returns exact counts."""
    tmp_dir = tempfile.mkdtemp()
    try:
        # 1. Python source
        os.makedirs(os.path.join(tmp_dir, "src"))
        with open(os.path.join(tmp_dir, "src", "main.py"), "w") as f:
            f.write("import sys\nprint('hello')\nexit(0)\n")  # 3 lines

        # 2. JavaScript source
        with open(os.path.join(tmp_dir, "src", "app.js"), "w") as f:
            f.write("const x = 1;\nconsole.log(x);\n")  # 2 lines

        # 3. Python test
        os.makedirs(os.path.join(tmp_dir, "tests"))
        with open(os.path.join(tmp_dir, "tests", "test_main.py"), "w") as f:
            f.write("def test_ok():\n    assert True\n")  # 2 lines

        # 4. JavaScript test
        with open(os.path.join(tmp_dir, "tests", "app.test.js"), "w") as f:
            f.write("test('it works', () => expect(1).toBe(1));\n")  # 1 line

        inventory = scan_inventory(tmp_dir)

        assert inventory["total_files"] == 4
        assert inventory["total_lines"] == 8
        assert inventory["source_files_count"] == 2
        assert inventory["test_files_count"] == 2
        assert inventory["test_to_source_ratio"] == 1.0

        assert inventory["languages"]["Python"]["files"] == 2
        assert inventory["languages"]["Python"]["lines"] == 5

        assert inventory["languages"]["JavaScript"]["files"] == 2
        assert inventory["languages"]["JavaScript"]["lines"] == 3

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
