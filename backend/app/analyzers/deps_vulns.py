"""Dependency vulnerability analyzer parsing manifests and querying the OSV API (RULES B6)."""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from backend.app.core.github_client import is_host_allowed

logger = logging.getLogger(__name__)
OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"


def parse_requirements_txt(content: str) -> List[Dict[str, str]]:
    """Parse requirements.txt for pinned dependencies (e.g. pkg==1.0.0)."""
    deps: List[Dict[str, str]] = []
    for line in content.splitlines():
        line = line.strip().split("#")[0].strip()
        if not line or line.startswith(("-", "http://", "https://", "git+")):
            continue
        # Match pinned version like flask==2.0.1 or urllib3==1.26.5
        match = re.match(r"^([A-Za-z0-9_.\-]+)==([A-Za-z0-9_.\-+]+)", line)
        if match:
            deps.append({
                "name": match.group(1),
                "version": match.group(2),
                "ecosystem": "PyPI",
            })
    return deps


def parse_package_lock_json(content: str) -> List[Dict[str, str]]:
    """Parse package-lock.json (v1, v2, or v3) for top-level or package dependencies."""
    deps: List[Dict[str, str]] = []
    try:
        data = json.loads(content)
    except Exception:
        return []

    # v2/v3 has "packages"
    packages = data.get("packages", {})
    if packages and isinstance(packages, dict):
        for pkg_key, pkg_val in packages.items():
            if not pkg_key or not isinstance(pkg_val, dict):
                continue
            name = pkg_val.get("name") or pkg_key.replace("node_modules/", "")
            version = pkg_val.get("version")
            if name and version:
                deps.append({
                    "name": name,
                    "version": version,
                    "ecosystem": "npm",
                })
        return deps

    # v1 fallback: "dependencies"
    dependencies = data.get("dependencies", {})
    if isinstance(dependencies, dict):
        for name, info in dependencies.items():
            if isinstance(info, dict) and "version" in info:
                deps.append({
                    "name": name,
                    "version": info["version"],
                    "ecosystem": "npm",
                })
    return deps


def parse_poetry_lock(content: str) -> List[Dict[str, str]]:
    """Parse poetry.lock for packages."""
    deps: List[Dict[str, str]] = []
    current_name: Optional[str] = None
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("name = "):
            current_name = line.split("=")[1].strip().strip('"\'')
        elif line.startswith("version = ") and current_name:
            version = line.split("=")[1].strip().strip('"\'')
            deps.append({
                "name": current_name,
                "version": version,
                "ecosystem": "PyPI",
            })
            current_name = None
    return deps


def parse_cargo_lock(content: str) -> List[Dict[str, str]]:
    """Parse Cargo.lock for crates."""
    deps: List[Dict[str, str]] = []
    current_name: Optional[str] = None
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("name = "):
            current_name = line.split("=")[1].strip().strip('"\'')
        elif line.startswith("version = ") and current_name:
            version = line.split("=")[1].strip().strip('"\'')
            deps.append({
                "name": current_name,
                "version": version,
                "ecosystem": "crates.io",
            })
            current_name = None
    return deps


def parse_go_mod(content: str) -> List[Dict[str, str]]:
    """Parse go.mod for required modules."""
    deps: List[Dict[str, str]] = []
    in_require = False
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("require ("):
            in_require = True
            continue
        if in_require:
            if line.startswith(")"):
                in_require = False
                continue
            parts = line.split()
            if len(parts) >= 2:
                deps.append({
                    "name": parts[0],
                    "version": parts[1].lstrip("v"),
                    "ecosystem": "Go",
                })
        elif line.startswith("require ") and "(" not in line:
            parts = line.replace("require ", "").split()
            if len(parts) >= 2:
                deps.append({
                    "name": parts[0],
                    "version": parts[1].lstrip("v"),
                    "ecosystem": "Go",
                })
    return deps


def extract_manifest_dependencies(source_dir: Path) -> List[Dict[str, str]]:
    """Scan and parse supported dependency manifests in source_dir."""
    all_deps: List[Dict[str, str]] = []

    for path in source_dir.rglob("*"):
        if not path.is_file():
            continue

        fname = path.name.lower()
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        if fname.startswith("requirements") and fname.endswith(".txt"):
            all_deps.extend(parse_requirements_txt(content))
        elif fname == "package-lock.json":
            all_deps.extend(parse_package_lock_json(content))
        elif fname == "poetry.lock":
            all_deps.extend(parse_poetry_lock(content))
        elif fname == "cargo.lock":
            all_deps.extend(parse_cargo_lock(content))
        elif fname == "go.mod":
            all_deps.extend(parse_go_mod(content))

    # Deduplicate dependencies by (ecosystem, name, version)
    seen = set()
    deduped = []
    for d in all_deps:
        key = (d["ecosystem"], d["name"].lower(), d["version"])
        if key not in seen:
            seen.add(key)
            deduped.append(d)

    return deduped


async def query_osv_batch(dependencies: List[Dict[str, str]], client: Optional[httpx.AsyncClient] = None) -> List[Dict[str, Any]]:
    """Query OSV API batch endpoint for vulnerability advisories."""
    if not dependencies:
        return []

    if not is_host_allowed(OSV_BATCH_URL):
        logger.error("OSV batch URL is not in allowed hosts allowlist!")
        return []

    # Prepare batch query (max 1,000 per request per OSV docs)
    queries = [
        {
            "package": {"name": dep["name"], "ecosystem": dep["ecosystem"]},
            "version": dep["version"],
        }
        for dep in dependencies[:1000]
    ]

    payload = {"queries": queries}
    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=30.0)
        close_client = True

    results: List[Dict[str, Any]] = []
    try:
        resp = await client.post(OSV_BATCH_URL, json=payload)
        if resp.status_code == 200:
            data = resp.json()
            raw_results = data.get("results", [])
            for dep, r in zip(dependencies, raw_results):
                vulns = r.get("vulns", [])
                if vulns:
                    advisories = []
                    for v in vulns:
                        advisories.append({
                            "id": v.get("id"),
                            "summary": v.get("summary", ""),
                            "details": v.get("details", "")[:200] if v.get("details") else "",
                            "aliases": v.get("aliases", []),
                        })
                    results.append({
                        "name": dep["name"],
                        "version": dep["version"],
                        "ecosystem": dep["ecosystem"],
                        "advisories_count": len(advisories),
                        "advisories": advisories,
                    })
    except Exception as exc:
        logger.warning("OSV batch query failed: %s", exc)
    finally:
        if close_client:
            await client.aclose()

    return results


async def analyze_dependencies_vulnerabilities(
    source_dir: Path,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """Execute complete dependency manifest parsing and vulnerability scan."""
    deps = extract_manifest_dependencies(source_dir)
    vulnerabilities = await query_osv_batch(deps, client=client)

    return {
        "total_dependencies": len(deps),
        "vulnerable_packages_count": len(vulnerabilities),
        "total_advisories": sum(v["advisories_count"] for v in vulnerabilities),
        "dependencies": deps[:100],  # sample up to 100 for overview
        "vulnerabilities": vulnerabilities,
    }
