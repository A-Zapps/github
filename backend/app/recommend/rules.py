"""Recommendation rule engine evaluating cross-stage analysis results (T6.1, RULES A1-A8).

Every recommendation is backed by concrete evidence (file, line, or measured metric).
No recommendation appears without evidence.
"""

from typing import Any, Dict, List


class RecommendationRule:
    """Base definition for a deterministic recommendation rule with evidence validation."""

    def __init__(
        self,
        rule_id: str,
        category: str,
        title: str,
        priority: str,  # CRITICAL, HIGH, MEDIUM, LOW
        effort: str,    # QUICK, MODERATE, SIGNIFICANT
        target_page: str,
    ):
        self.rule_id = rule_id
        self.category = category
        self.title = title
        self.priority = priority
        self.effort = effort
        self.target_page = target_page

    def evaluate(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Evaluate rule against results dictionary and return list of evidence-backed recommendations."""
        raise NotImplementedError


class SecretExposureRule(RecommendationRule):
    """Rule SEC-SECRET: Flags exposed secrets and credentials."""

    def __init__(self):
        super().__init__(
            rule_id="SEC-SECRET",
            category="security",
            title="Revoke and rotate exposed credentials",
            priority="CRITICAL",
            effort="QUICK",
            target_page="#/security",
        )

    def evaluate(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        recs = []
        sec = results.get("security", {})
        secrets_list = sec.get("secrets", {}).get("findings", [])
        for s in secrets_list[:5]:
            recs.append({
                "id": f"{self.rule_id}-{len(recs)+1}",
                "rule_id": self.rule_id,
                "category": self.category,
                "title": f"Revoke exposed {s.get('rule_id', 'credential')} in {s.get('file')}",
                "description": f"Found exposed secret ({s.get('masked')}) at line {s.get('line')}. Invalidate the token immediately and store it in an environment secret manager.",
                "priority": self.priority,
                "effort": self.effort,
                "target_page": self.target_page,
                "evidence": {
                    "file": s.get("file"),
                    "line": s.get("line"),
                    "masked_secret": s.get("masked"),
                    "rule": s.get("rule_id"),
                },
            })
        return recs


class VulnerableDependencyRule(RecommendationRule):
    """Rule SEC-DEP: Flags dependencies with known public CVE advisories."""

    def __init__(self):
        super().__init__(
            rule_id="SEC-DEP",
            category="security",
            title="Upgrade vulnerable package dependency",
            priority="HIGH",
            effort="QUICK",
            target_page="#/security",
        )

    def evaluate(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        recs = []
        sec = results.get("security", {})
        vulns = sec.get("dependencies", {}).get("vulnerabilities", [])
        for v in vulns[:5]:
            advisories = v.get("advisories", [])
            adv_id = advisories[0].get("id") if advisories else "CVE"
            recs.append({
                "id": f"{self.rule_id}-{len(recs)+1}",
                "rule_id": self.rule_id,
                "category": self.category,
                "title": f"Upgrade {v.get('package')} (v{v.get('version')}) to patch {adv_id}",
                "description": f"Dependency {v.get('package')} v{v.get('version')} has {len(advisories)} known security advisory(s) listed in OSV database.",
                "priority": self.priority,
                "effort": self.effort,
                "target_page": self.target_page,
                "evidence": {
                    "package": v.get("package"),
                    "version": v.get("version"),
                    "advisory_id": adv_id,
                    "advisory_count": len(advisories),
                },
            })
        return recs


class HighBugRiskRule(RecommendationRule):
    """Rule BUG-HIGH: Flags source files predicted with high defect risk."""

    def __init__(self):
        super().__init__(
            rule_id="BUG-HIGH",
            category="bug_risk",
            title="Refactor and test defect-prone source file",
            priority="HIGH",
            effort="MODERATE",
            target_page="#/bugs",
        )

    def evaluate(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        recs = []
        bugs = results.get("bugs", {})
        files = bugs.get("files", [])
        for f in files:
            if f.get("risk_tier") == "high":
                pct = int(f.get("probability", 0.0) * 100)
                drivers_str = ", ".join(f.get("drivers", []))
                recs.append({
                    "id": f"{self.rule_id}-{len(recs)+1}",
                    "rule_id": self.rule_id,
                    "category": self.category,
                    "title": f"Reduce defect risk in {f.get('file')} ({pct}% risk)",
                    "description": f"File {f.get('file')} is predicted with {pct}% defect probability due to: {drivers_str}. Add unit test coverage and break up complex methods.",
                    "priority": self.priority,
                    "effort": self.effort,
                    "target_page": self.target_page,
                    "evidence": {
                        "file": f.get("file"),
                        "probability": f.get("probability"),
                        "ccn_max": f.get("ccn_max"),
                        "loc": f.get("loc"),
                        "drivers": f.get("drivers"),
                    },
                })
                if len(recs) >= 3:
                    break
        return recs


class LowMaintainabilityRule(RecommendationRule):
    """Rule QUAL-MI: Flags files with poor maintainability index (<50)."""

    def __init__(self):
        super().__init__(
            rule_id="QUAL-MI",
            category="quality",
            title="Decompose complex unmaintainable module",
            priority="MEDIUM",
            effort="MODERATE",
            target_page="#/quality",
        )

    def evaluate(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        recs = []
        qual = results.get("quality", {})
        worst_files = qual.get("worst_files", [])
        for f in worst_files:
            mi = f.get("mi", 100.0)
            if mi < 50.0:
                recs.append({
                    "id": f"{self.rule_id}-{len(recs)+1}",
                    "rule_id": self.rule_id,
                    "category": self.category,
                    "title": f"Refactor low maintainability in {f.get('path')} (MI: {mi})",
                    "description": f"File {f.get('path')} has maintainability index of {mi}/100 and {f.get('loc')} LOC with max cyclomatic complexity {f.get('ccn_max')}.",
                    "priority": self.priority,
                    "effort": self.effort,
                    "target_page": self.target_page,
                    "evidence": {
                        "file": f.get("path"),
                        "maintainability_index": mi,
                        "ccn_max": f.get("ccn_max"),
                        "loc": f.get("loc"),
                    },
                })
                if len(recs) >= 3:
                    break
        return recs


class CodeDuplicationRule(RecommendationRule):
    """Rule QUAL-DUP: Flags excessive code duplication (>5%)."""

    def __init__(self):
        super().__init__(
            rule_id="QUAL-DUP",
            category="quality",
            title="Consolidate duplicate code blocks into shared utilities",
            priority="MEDIUM",
            effort="MODERATE",
            target_page="#/quality",
        )

    def evaluate(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        qual = results.get("quality", {})
        dup_comp = qual.get("components", {}).get("duplication", {})
        dup_val = dup_comp.get("metric_value", "0%")
        # Try extracting float from 'X%'
        try:
            val_pct = float(str(dup_val).replace("%", "").strip())
        except Exception:
            val_pct = 0.0

        if val_pct > 5.0:
            return [{
                "id": f"{self.rule_id}-1",
                "rule_id": self.rule_id,
                "category": self.category,
                "title": f"Extract duplicated logic to reduce {val_pct}% code duplication",
                "description": f"Measured code duplication is {val_pct}%, which exceeds the 5% target benchmark. Extract repeated 6-line blocks into reusable helper functions.",
                "priority": self.priority,
                "effort": self.effort,
                "target_page": self.target_page,
                "evidence": {
                    "duplication_percentage": val_pct,
                    "target_benchmark": 5.0,
                },
            }]
        return []


class DocumentationMissingRule(RecommendationRule):
    """Rule DOC-MISSING: Flags missing core README documentation sections."""

    def __init__(self):
        super().__init__(
            rule_id="DOC-MISSING",
            category="docs",
            title="Add missing project documentation",
            priority="MEDIUM",
            effort="QUICK",
            target_page="#/docs",
        )

    def evaluate(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        recs = []
        docs = results.get("docs", {})
        checklist = docs.get("checklist", {})
        for sec_name, sec_data in checklist.items():
            if sec_data.get("status") == "missing":
                recs.append({
                    "id": f"{self.rule_id}-{len(recs)+1}",
                    "rule_id": self.rule_id,
                    "category": self.category,
                    "title": f"Add {sec_data.get('title')} section to README",
                    "description": sec_data.get("suggestion") or f"Document {sec_name} to help users onboard and adopt the project.",
                    "priority": self.priority,
                    "effort": self.effort,
                    "target_page": self.target_page,
                    "evidence": {
                        "section": sec_name,
                        "title": sec_data.get("title"),
                        "status": "missing",
                    },
                })
        return recs


class BusFactorRiskRule(RecommendationRule):
    """Rule DEV-BUS: Flags single-contributor ownership vulnerability."""

    def __init__(self):
        super().__init__(
            rule_id="DEV-BUS",
            category="developers",
            title="Distribute repository knowledge and review responsibilities",
            priority="HIGH",
            effort="SIGNIFICANT",
            target_page="#/developers",
        )

    def evaluate(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        devs = results.get("developers", {})
        bus_factor = devs.get("bus_factor", 2)
        total_commits = devs.get("total_commits", 0)
        contributors = devs.get("contributors", [])

        if bus_factor <= 1 and total_commits >= 5 and contributors:
            top_author = contributors[0]
            pct = top_author.get("percentage", 0.0)
            return [{
                "id": f"{self.rule_id}-1",
                "rule_id": self.rule_id,
                "category": self.category,
                "title": f"Mitigate single-maintainer bus factor risk ({pct}% by {top_author.get('author')})",
                "description": f"A single contributor ({top_author.get('author')}) accounts for {pct}% of all commits. Introduce branch protection rules and pair programming to share project ownership.",
                "priority": self.priority,
                "effort": self.effort,
                "target_page": self.target_page,
                "evidence": {
                    "bus_factor": bus_factor,
                    "top_contributor": top_author.get("author"),
                    "top_contributor_share": pct,
                    "total_commits": total_commits,
                },
            }]
        return []


# Standard rule collection
ALL_RULES: List[RecommendationRule] = [
    SecretExposureRule(),
    VulnerableDependencyRule(),
    HighBugRiskRule(),
    LowMaintainabilityRule(),
    CodeDuplicationRule(),
    DocumentationMissingRule(),
    BusFactorRiskRule(),
]

PRIORITY_WEIGHT = {
    "CRITICAL": 1,
    "HIGH": 2,
    "MEDIUM": 3,
    "LOW": 4,
}


def generate_recommendations(results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate and rank all evidence-backed recommendations across analysis results.

    Enforces that NO recommendation is emitted without concrete evidence (RULES A1-A8).
    """
    all_recs: List[Dict[str, Any]] = []

    for rule in ALL_RULES:
        try:
            recs = rule.evaluate(results)
            for r in recs:
                # Strict verification: evidence must be present and non-empty
                if "evidence" in r and r["evidence"]:
                    all_recs.append(r)
        except Exception:
            pass

    # Sort by priority (CRITICAL first), then by effort (QUICK first)
    all_recs.sort(key=lambda r: (PRIORITY_WEIGHT.get(r.get("priority", "LOW"), 5), r.get("effort") != "QUICK"))

    return all_recs
