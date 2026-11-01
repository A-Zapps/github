"""Tests for dependency vulnerability scanner and OSV batch querying."""

from pathlib import Path

import httpx
import pytest
import respx

from backend.app.analyzers.deps_vulns import (
    analyze_dependencies_vulnerabilities,
    parse_cargo_lock,
    parse_go_mod,
    parse_package_lock_json,
    parse_poetry_lock,
    parse_requirements_txt,
)


def test_manifest_parsers():
    """Verify parsers extract package names, versions, and ecosystems correctly."""
    # requirements.txt
    req_txt = "flask==2.0.1\nrequests==2.25.1\n# comment\n-e .\n"
    py_deps = parse_requirements_txt(req_txt)
    assert len(py_deps) == 2
    assert py_deps[0] == {"name": "flask", "version": "2.0.1", "ecosystem": "PyPI"}

    # package-lock.json
    pkg_json = '{"packages": {"node_modules/lodash": {"version": "4.17.20"}}}'
    npm_deps = parse_package_lock_json(pkg_json)
    assert len(npm_deps) == 1
    assert npm_deps[0]["name"] == "lodash"
    assert npm_deps[0]["version"] == "4.17.20"

    # poetry.lock
    poetry_txt = '[[package]]\nname = "pydantic"\nversion = "1.8.2"\n'
    poetry_deps = parse_poetry_lock(poetry_txt)
    assert len(poetry_deps) == 1
    assert poetry_deps[0]["name"] == "pydantic"

    # Cargo.lock
    cargo_txt = '[[package]]\nname = "serde"\nversion = "1.0.130"\n'
    cargo_deps = parse_cargo_lock(cargo_txt)
    assert len(cargo_deps) == 1
    assert cargo_deps[0]["name"] == "serde"

    # go.mod
    go_txt = "module example.com/app\n\nrequire (\n\tgithub.com/gin-gonic/gin v1.7.0\n)\n"
    go_deps = parse_go_mod(go_txt)
    assert len(go_deps) == 1
    assert go_deps[0]["name"] == "github.com/gin-gonic/gin"
    assert go_deps[0]["version"] == "1.7.0"


@pytest.mark.asyncio
@respx.mock
async def test_osv_batch_vulnerability_detection(tmp_path: Path):
    """Verify a fixture with a known-vulnerable pinned version returns an advisory ID."""
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("requests==2.20.0\n", encoding="utf-8")

    # Mock OSV batch API response
    respx.post("https://api.osv.dev/v1/querybatch").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "vulns": [
                            {
                                "id": "GHSA-j8r2-6x86-q33q",
                                "summary": "Unintended leak of Proxy-Authorization header in requests",
                                "aliases": ["CVE-2018-18074"],
                            }
                        ]
                    }
                ]
            },
        )
    )

    async with httpx.AsyncClient() as client:
        res = await analyze_dependencies_vulnerabilities(tmp_path, client=client)

    assert res["total_dependencies"] == 1
    assert res["vulnerable_packages_count"] == 1
    assert res["total_advisories"] == 1
    assert res["vulnerabilities"][0]["name"] == "requests"
    assert res["vulnerabilities"][0]["advisories"][0]["id"] == "GHSA-j8r2-6x86-q33q"
