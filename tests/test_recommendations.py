"""Tests for recommendation rule engine and evidence requirements (T6.1)."""

from backend.app.recommend.rules import (
    BusFactorRiskRule,
    SecretExposureRule,
    generate_recommendations,
)


def test_no_recommendations_when_clean_results():
    clean_results = {
        "security": {"secrets": {"findings": []}, "dependencies": {"vulnerabilities": []}},
        "bugs": {"files": [{"file": "clean.py", "risk_tier": "low", "probability": 0.1}]},
        "quality": {
            "worst_files": [{"path": "clean.py", "mi": 85.0, "ccn_max": 2, "loc": 50}],
            "components": {"duplication": {"metric_value": "1.2%"}},
        },
        "docs": {"checklist": {"installation": {"status": "found"}, "usage": {"status": "found"}}},
        "developers": {"bus_factor": 4, "total_commits": 100, "contributors": [{"author": "A", "percentage": 25.0}]},
    }

    recs = generate_recommendations(clean_results)
    assert len(recs) == 0


def test_every_recommendation_must_contain_evidence():
    """Verify that every generated recommendation has a non-empty evidence dictionary."""
    problematic_results = {
        "security": {
            "secrets": {"findings": [{"file": "config.py", "line": 15, "masked": "AKIA****", "rule_id": "aws_key"}]},
            "dependencies": {"vulnerabilities": [{"package": "requests", "version": "2.18.0", "advisories": [{"id": "CVE-2018-18074"}]}]},
        },
        "bugs": {
            "files": [{"file": "engine.py", "risk_tier": "high", "probability": 0.82, "drivers": ["High CCN (18.0)"], "ccn_max": 18, "loc": 400}],
        },
        "quality": {
            "worst_files": [{"path": "legacy.py", "mi": 32.0, "ccn_max": 24, "loc": 900}],
            "components": {"duplication": {"metric_value": "12.5%"}},
        },
        "docs": {
            "checklist": {
                "installation": {"status": "missing", "title": "Installation"},
            },
        },
        "developers": {
            "bus_factor": 1,
            "total_commits": 50,
            "contributors": [{"author": "SoloDev", "percentage": 85.0}],
        },
    }

    recs = generate_recommendations(problematic_results)
    assert len(recs) >= 6

    # Acceptance criterion: No recommendation appears without evidence
    for r in recs:
        assert "evidence" in r, f"Recommendation {r['id']} missing evidence field"
        assert isinstance(r["evidence"], dict), f"Evidence in {r['id']} must be a dict"
        assert len(r["evidence"]) > 0, f"Evidence in {r['id']} cannot be empty"
        assert "target_page" in r
        assert r["target_page"].startswith("#/")


def test_secret_rule_evidence():
    rule = SecretExposureRule()
    results = {
        "security": {"secrets": {"findings": [{"file": "env.py", "line": 4, "masked": "ghp_****", "rule_id": "gh_token"}]}}
    }
    recs = rule.evaluate(results)
    assert len(recs) == 1
    assert recs[0]["priority"] == "CRITICAL"
    assert recs[0]["evidence"]["file"] == "env.py"
    assert recs[0]["evidence"]["line"] == 4


def test_bus_factor_rule_evidence():
    rule = BusFactorRiskRule()
    results = {
        "developers": {
            "bus_factor": 1,
            "total_commits": 20,
            "contributors": [{"author": "Alice", "percentage": 90.0}],
        }
    }
    recs = rule.evaluate(results)
    assert len(recs) == 1
    assert recs[0]["evidence"]["bus_factor"] == 1
    assert recs[0]["evidence"]["top_contributor"] == "Alice"
