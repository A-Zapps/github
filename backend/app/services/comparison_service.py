"""Repository comparison service (T6.3, RULES A1-A8).

Performs side-by-side metric normalization, best-per-metric tagging,
and 2D PCA cluster positioning across 2 to 4 analyses.
Rejects duplicate analysis IDs.
"""

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from backend.app.db.models import Analysis, Result
from backend.app.errors import AppError


def compare_analyses(analysis_ids: List[int], db: Session) -> Dict[str, Any]:
    """Compare 2 to 4 repository analyses with metric normalization and best-per-metric marking.

    Rejects duplicate analysis IDs or invalid counts.
    """
    if len(analysis_ids) < 2 or len(analysis_ids) > 4:
        raise AppError(
            code="INVALID_COMPARE_REQUEST",
            message="Comparison requires between 2 and 4 repository analyses.",
            status_code=400,
        )

    # Reject duplicate IDs (Acceptance criterion T6.3)
    if len(set(analysis_ids)) != len(analysis_ids):
        raise AppError(
            code="DUPLICATE_ANALYSIS_ID",
            message="Comparing the same analysis twice is not permitted.",
            status_code=400,
        )

    analyses = []
    for a_id in analysis_ids:
        a = db.query(Analysis).filter(Analysis.id == a_id).first()
        if not a:
            raise AppError("NOT_FOUND", f"Analysis {a_id} not found.", status_code=404)
        if a.status != "completed":
            raise AppError("ANALYSIS_NOT_READY", f"Analysis {a_id} is not completed (status: {a.status}).", status_code=409)

        # Load all results for this analysis
        results = db.query(Result).filter(Result.analysis_id == a_id).all()
        res_map = {r.module: r.payload for r in results}

        repo_name = a.repository.full_name if a.repository else f"Analysis #{a.id}"
        qual = res_map.get("quality", {})
        bugs = res_map.get("bugs", {})
        sec = res_map.get("security", {})
        docs = res_map.get("docs", {})
        devs = res_map.get("developers", {})
        health = res_map.get("health", {})

        # Extract numeric duplication
        dup_val_str = str(qual.get("components", {}).get("duplication", {}).get("metric_value", "0%"))
        try:
            dup_pct = float(dup_val_str.replace("%", "").strip())
        except Exception:
            dup_pct = 0.0

        analyses.append({
            "analysis_id": a.id,
            "repo_name": repo_name,
            "head_sha": a.head_sha[:7] if a.head_sha else "---",
            "quality_score": float(qual.get("overall_score", 0)),
            "quality_grade": qual.get("grade", "F"),
            "tech_debt_hours": float(qual.get("tech_debt", {}).get("hours", 0.0)),
            "duplication_pct": dup_pct,
            "high_bug_risk_files": int(bugs.get("summary", {}).get("high_risk", 0)),
            "total_security_issues": int(sec.get("total_issues", 0)),
            "docs_score": float(docs.get("overall_score", 0)),
            "bus_factor": int(devs.get("bus_factor", 1)),
            "total_commits": int(devs.get("total_commits", 0)),
            "health_class": health.get("health", {}).get("health_class", "Unknown"),
            "cluster_id": health.get("clusters", {}).get("cluster_id", 0),
            "pca_coords": health.get("clusters", {}).get("pca_coordinates", [0.0, 0.0]),
        })

    # Definitions of metrics to compare
    # higher_is_better: True if larger number is superior
    metric_specs = [
        {"key": "quality_score", "name": "Quality Score (0-100)", "higher_is_better": True},
        {"key": "docs_score", "name": "Documentation Completeness (0-100)", "higher_is_better": True},
        {"key": "bus_factor", "name": "Bus Factor Resilience", "higher_is_better": True},
        {"key": "duplication_pct", "name": "Code Duplication (%)", "higher_is_better": False},
        {"key": "high_bug_risk_files", "name": "High Bug-Risk Files", "higher_is_better": False},
        {"key": "total_security_issues", "name": "Security Vulnerabilities", "higher_is_better": False},
        {"key": "tech_debt_hours", "name": "Technical Debt (Hours)", "higher_is_better": False},
    ]

    metrics_table = []
    radar_metrics = []

    for spec in metric_specs:
        k = spec["key"]
        higher_better = spec["higher_is_better"]
        vals = [a[k] for a in analyses]

        if higher_better:
            best_val = max(vals)
        else:
            best_val = min(vals)

        row_entries = []
        normalized_row = []

        max_in_row = max(vals)
        min_in_row = min(vals)

        for a in analyses:
            val = a[k]
            is_best = (val == best_val)
            row_entries.append({
                "analysis_id": a["analysis_id"],
                "value": val,
                "is_best": is_best,
            })

            # Normalization (0 to 100 scale for radar chart)
            if higher_better:
                norm = round((val / max(0.001, max_in_row)) * 100.0, 1)
            else:
                norm = round((max(0.001, min_in_row) / max(0.001, val)) * 100.0, 1) if val > 0 else 100.0
            normalized_row.append(min(100.0, max(10.0, norm)))

        metrics_table.append({
            "key": k,
            "name": spec["name"],
            "higher_is_better": higher_better,
            "values": row_entries,
        })

        radar_metrics.append({
            "name": spec["name"].split(" (")[0],
            "scores": normalized_row,
        })

    # Corpus PCA scatter points
    cluster_points = [
        {
            "analysis_id": a["analysis_id"],
            "repo_name": a["repo_name"],
            "x": a["pca_coords"][0] if len(a["pca_coords"]) > 0 else 0.0,
            "y": a["pca_coords"][1] if len(a["pca_coords"]) > 1 else 0.0,
            "cluster_id": a["cluster_id"],
        }
        for a in analyses
    ]

    return {
        "analyses": analyses,
        "metrics_table": metrics_table,
        "radar_data": {
            "categories": [rm["name"] for rm in radar_metrics],
            "series": [
                {
                    "name": a["repo_name"],
                    "data": [radar_metrics[i]["scores"][idx] for i in range(len(radar_metrics))],
                }
                for idx, a in enumerate(analyses)
            ],
        },
        "cluster_points": cluster_points,
    }
