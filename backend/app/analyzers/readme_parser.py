"""README parser and documentation completeness analyzer (T5.1, RULES A1-A8, D1-D10)."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.app.ml.registry import get_model_registry

# Heading patterns for weak labeling
HEADING_PATTERNS = {
    "installation": re.compile(r"\b(install\w*|setup|getting\s*started|prerequisites|requirements)\b", re.IGNORECASE),
    "usage": re.compile(r"\b(usage|quickstart|examples?|how\s*to\s*use|commands|running|api|features)\b", re.IGNORECASE),
    "contributing": re.compile(r"\b(contribut\w*|development|guidelines|pull\s*requests|dev\s*setup|testing)\b", re.IGNORECASE),
    "license": re.compile(r"\b(licen[sc]e|copyright|authors|credits)\b", re.IGNORECASE),
}


def label_heading(heading_text: str) -> str:
    """Assign weak label based on heading content."""
    clean = heading_text.strip().lower()
    for cat, pat in HEADING_PATTERNS.items():
        if pat.search(clean):
            return cat
    return "other"


def split_readme_sections(readme_text: str) -> List[Tuple[str, str]]:
    """Split markdown text into (weak_label, body_text_without_heading)."""
    lines = readme_text.splitlines()
    sections: List[Tuple[str, List[str]]] = []
    current_heading = "intro"
    current_lines: List[str] = []

    for line in lines:
        match = re.match(r"^#{1,6}\s+(.+)$", line.strip())
        if match:
            if current_lines:
                sections.append((current_heading, current_lines))
                current_lines = []
            current_heading = match.group(1).strip()
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_heading, current_lines))

    result = []
    for heading, blines in sections:
        body = "\n".join(blines).strip()
        weak_label = label_heading(heading)
        result.append((weak_label, body))

    return result

DOC_CLASSES = ["installation", "usage", "contributing", "license", "other"]

EXPECTED_SECTIONS = {
    "installation": {
        "weight": 30,
        "title": "Installation & Setup",
        "suggestion": "Add an 'Installation' or 'Getting Started' section explaining prerequisites, package manager commands, and initial configuration.",
    },
    "usage": {
        "weight": 30,
        "title": "Usage & Examples",
        "suggestion": "Add a 'Usage' or 'Quickstart' section with minimal reproducible code examples, command line invocations, or API request snippets.",
    },
    "contributing": {
        "weight": 20,
        "title": "Contributing Guidelines",
        "suggestion": "Add a 'Contributing' section describing development prerequisites, how to run tests, and pull request guidelines.",
    },
    "license": {
        "weight": 20,
        "title": "License & Terms",
        "suggestion": "Add a 'License' section stating the open-source license terms (e.g. MIT, Apache-2.0) and link to the LICENSE file.",
    },
}

README_FILENAMES = ["README.md", "readme.md", "README.rst", "readme.rst", "README.txt", "readme.txt", "README", "readme"]


def find_readme_file(repo_dir: Path) -> Optional[Path]:
    """Find primary README file in repository root."""
    for fname in README_FILENAMES:
        p = repo_dir / fname
        if p.is_file():
            return p
    return None


def parse_and_score_readme(repo_dir: Path) -> Dict[str, Any]:
    """Parse repository README, classify sections with heading rules + ML model, and score completeness."""
    readme_path = find_readme_file(repo_dir)
    if not readme_path:
        return {
            "has_readme": False,
            "filename": None,
            "overall_score": 0,
            "grade": "F",
            "sections": [],
            "checklist": {
                sec: {
                    "status": "missing",
                    "title": meta["title"],
                    "weight": meta["weight"],
                    "suggestion": meta["suggestion"],
                }
                for sec, meta in EXPECTED_SECTIONS.items()
            },
            "suggestions": [
                "No README found in repository root. Create a README.md file covering project overview, installation, usage, and license."
            ],
        }

    try:
        content = readme_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        content = ""

    raw_sections = split_readme_sections(content)
    registry = get_model_registry()
    has_ml_model = registry.is_model_trained("doc_sections")

    detected_sections: List[Dict[str, Any]] = []
    category_bodies: Dict[str, List[str]] = {k: [] for k in EXPECTED_SECTIONS}

    for rule_cat, body in raw_sections:
        final_cat = rule_cat
        # If heading was ambiguous ("other"), only refine using ML model if body exhibits strong commands/terms
        if final_cat == "other" and has_ml_model and len(body) >= 40:
            body_lower = body.lower()
            install_cues = ("pip install", "npm install", "cargo build", "brew install", "docker run", "yarn add", "go get")
            usage_cues = ("import ", "curl ", "example:", "usage:", "```python", "```bash", "```javascript")
            if any(cue in body_lower for cue in install_cues) or any(cue in body_lower for cue in usage_cues):
                try:
                    preds = registry.predict_doc_sections([body])
                    if preds and preds[0] in ("installation", "usage"):
                        final_cat = preds[0]
                except Exception:
                    pass

        if final_cat in category_bodies:
            category_bodies[final_cat].append(body)

        detected_sections.append({
            "category": final_cat,
            "length": len(body),
            "preview": body[:120].strip() + ("..." if len(body) > 120 else ""),
        })

    # Evaluate completeness checklist
    total_score = 0
    checklist: Dict[str, Any] = {}
    suggestions: List[str] = []

    for sec, meta in EXPECTED_SECTIONS.items():
        bodies = category_bodies.get(sec, [])
        total_len = sum(len(b) for b in bodies)

        if not bodies:
            status = "missing"
            earned = 0
            suggestions.append(meta["suggestion"])
        elif total_len < 60:
            status = "weak"
            earned = meta["weight"] // 2
            suggestions.append(f"The '{meta['title']}' section is very brief ({total_len} chars). Expand it with more detailed instructions.")
        else:
            status = "found"
            earned = meta["weight"]

        total_score += earned
        checklist[sec] = {
            "status": status,
            "title": meta["title"],
            "weight": meta["weight"],
            "earned": earned,
            "char_count": total_len,
            "suggestion": meta["suggestion"] if status != "found" else None,
        }

    # Grade assignment
    if total_score >= 90:
        grade = "A"
    elif total_score >= 75:
        grade = "B"
    elif total_score >= 60:
        grade = "C"
    elif total_score >= 40:
        grade = "D"
    else:
        grade = "F"

    return {
        "has_readme": True,
        "filename": readme_path.name,
        "overall_score": total_score,
        "grade": grade,
        "sections": detected_sections,
        "checklist": checklist,
        "suggestions": suggestions,
    }
