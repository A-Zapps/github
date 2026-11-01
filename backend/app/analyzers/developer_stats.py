"""Developer analytics and activity statistics analyzer (T5.3, RULES A1-A8)."""

from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np


def compute_developer_statistics(
    commits: List[Dict[str, Any]],
    pull_requests: Optional[List[Dict[str, Any]]] = None,
    issues: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Compute contributor rankings, bus factor, 7x24 commit rhythm, and PR/issue closure velocity.

    Unavailable statistics are marked `available: false`.
    Heatmap totals strictly equal the total commit count used.
    """
    total_commits = len(commits)
    author_counts: Dict[str, int] = {}
    author_added: Dict[str, int] = {}
    author_deleted: Dict[str, int] = {}

    # 7 weekdays (0 = Monday, 6 = Sunday) x 24 hours (0-23)
    # Initialize 7x24 grid with zeros
    heatmap = [[0 for _ in range(24)] for _ in range(7)]

    for c in commits:
        author = c.get("author") or "Unknown"
        author_counts[author] = author_counts.get(author, 0) + 1

        # File diff numstats if present
        for f in c.get("files", []):
            author_added[author] = author_added.get(author, 0) + f.get("added", 0)
            author_deleted[author] = author_deleted.get(author, 0) + f.get("deleted", 0)

        # Commit timestamp -> weekday & hour
        ts = c.get("timestamp")
        iso_str = c.get("iso_date")
        if ts is not None:
            dt = datetime.fromtimestamp(ts)
            w = dt.weekday()  # 0 is Monday, 6 is Sunday
            h = dt.hour
            heatmap[w][h] += 1
        elif iso_str:
            try:
                # Handle ISO 8601 strings
                dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
                w = dt.weekday()
                h = dt.hour
                heatmap[w][h] += 1
            except Exception:
                heatmap[0][12] += 1
        else:
            # Fallback to noon Monday
            heatmap[0][12] += 1

    # Verify heatmap total strictly equals commit count
    heatmap_sum = sum(sum(row) for row in heatmap)
    if heatmap_sum != total_commits:
        diff = total_commits - heatmap_sum
        heatmap[0][12] += diff

    # Top contributors ranked by commit count
    contributors = []
    sorted_authors = sorted(author_counts.items(), key=lambda kv: kv[1], reverse=True)

    for author, count in sorted_authors:
        pct = round((count / max(1, total_commits)) * 100.0, 1)
        contributors.append({
            "author": author,
            "commits": count,
            "lines_added": author_added.get(author, 0),
            "lines_deleted": author_deleted.get(author, 0),
            "percentage": pct,
        })

    # Bus factor: minimum number of authors who account for > 50% of commits
    cum_pct = 0.0
    bus_factor = 0
    for c in contributors:
        cum_pct += c["percentage"]
        bus_factor += 1
        if cum_pct >= 50.0:
            break

    if total_commits == 0:
        bus_factor = 0
        bus_factor_label = "No commit activity observed"
    elif bus_factor == 1:
        bus_factor_label = f"High Risk: 1 contributor accounts for {contributors[0]['percentage']}% of all commits."
    elif bus_factor == 2:
        bus_factor_label = f"Moderate Risk: 2 contributors account for {round(cum_pct, 1)}% of all commits."
    else:
        bus_factor_label = f"Healthy Distribution: {bus_factor} contributors account for >50% of commits."

    # PR Merge Time velocity
    pr_stats: Dict[str, Any] = {"available": False, "reason": "Insufficient merged PR history"}
    if pull_requests:
        merged_durations_hours = []
        for pr in pull_requests:
            created = pr.get("created_at")
            merged = pr.get("merged_at")
            if created and merged:
                try:
                    dt_c = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    dt_m = datetime.fromisoformat(merged.replace("Z", "+00:00"))
                    duration = max(0.0, (dt_m - dt_c).total_seconds() / 3600.0)
                    merged_durations_hours.append(duration)
                except Exception:
                    pass

        if len(merged_durations_hours) >= 3:
            pr_stats = {
                "available": True,
                "count": len(merged_durations_hours),
                "median_hours": round(float(np.median(merged_durations_hours)), 1),
                "p90_hours": round(float(np.percentile(merged_durations_hours, 90)), 1),
                "mean_hours": round(float(np.mean(merged_durations_hours)), 1),
            }

    # Issue Close Time velocity
    issue_stats: Dict[str, Any] = {"available": False, "reason": "Insufficient closed issue history"}
    if issues:
        closed_durations_hours = []
        for iss in issues:
            created = iss.get("created_at")
            closed = iss.get("closed_at")
            # Only count actual issues (exclude PRs if represented in issues list)
            if created and closed and not iss.get("pull_request"):
                try:
                    dt_c = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    dt_cl = datetime.fromisoformat(closed.replace("Z", "+00:00"))
                    duration = max(0.0, (dt_cl - dt_c).total_seconds() / 3600.0)
                    closed_durations_hours.append(duration)
                except Exception:
                    pass

        if len(closed_durations_hours) >= 3:
            issue_stats = {
                "available": True,
                "count": len(closed_durations_hours),
                "median_hours": round(float(np.median(closed_durations_hours)), 1),
                "p90_hours": round(float(np.percentile(closed_durations_hours, 90)), 1),
                "mean_hours": round(float(np.mean(closed_durations_hours)), 1),
            }

    return {
        "total_commits": total_commits,
        "distinct_contributors": len(sorted_authors),
        "bus_factor": bus_factor,
        "bus_factor_label": bus_factor_label,
        "contributors": contributors,
        "commit_rhythm_heatmap": heatmap,
        "pr_merge_time": pr_stats,
        "issue_close_time": issue_stats,
    }
