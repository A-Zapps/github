"""Git history parser and feature extractor as of a specific cutoff date (RULES D2)."""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from backend.app.core.subprocess_runner import run_tool

# Bug-fix regex pattern defined in ARCHITECTURE 9.5
BUG_FIX_PATTERN = re.compile(
    r"\b(fix|bug|defect|patch|crash|error|regression|leak|overflow|cve)\b",
    re.IGNORECASE,
)
BUG_FIX_EXCLUDE = re.compile(
    r"\b(typo|docs?|readme|ci)\b",
    re.IGNORECASE,
)


def is_bugfix_message(msg: str) -> bool:
    """Return True if message matches bug-fix pattern and is not excluded by documentation/typo filters."""
    if not msg:
        return False
    return bool(BUG_FIX_PATTERN.search(msg)) and not bool(BUG_FIX_EXCLUDE.search(msg))


def parse_git_log_history(
    git_dir: str,
    cutoff_date: Optional[datetime] = None,
    months_window: int = 12,
) -> Dict[str, Any]:
    """Parse git log with numstat and extract commit events strictly up to cutoff_date.

    Any commit with timestamp > cutoff_date is excluded (RULES D2 as-of invariance).
    """
    if cutoff_date is None:
        cutoff_date = datetime.now(timezone.utc)
    elif cutoff_date.tzinfo is None:
        cutoff_date = cutoff_date.replace(tzinfo=timezone.utc)

    # Calculate window start: cutoff_date - (months_window * 30 days)
    window_start_ts = cutoff_date.timestamp() - (months_window * 30 * 86400)

    # Format: COMMIT:<hash>|<author>|<iso_date>|<subject>
    argv = [
        "git",
        "log",
        "--numstat",
        "--date=iso-strict",
        "--pretty=format:COMMIT:%H|%an|%ad|%s",
    ]

    try:
        proc = run_tool(argv, timeout=120.0, cwd=git_dir)
        raw_output = proc.stdout.decode("utf-8", errors="replace")
    except Exception:
        raw_output = ""

    commits: List[Dict[str, Any]] = []
    current_commit: Optional[Dict[str, Any]] = None

    for line in raw_output.splitlines():
        line = line.strip()
        if not line:
            continue

        if line.startswith("COMMIT:"):
            if current_commit:
                commits.append(current_commit)

            header = line[7:]
            parts = header.split("|", 3)
            h = parts[0] if len(parts) > 0 else ""
            author = parts[1] if len(parts) > 1 else ""
            date_str = parts[2] if len(parts) > 2 else ""
            subject = parts[3] if len(parts) > 3 else ""

            try:
                commit_dt = datetime.fromisoformat(date_str)
                if commit_dt.tzinfo is None:
                    commit_dt = commit_dt.replace(tzinfo=timezone.utc)
            except Exception:
                commit_dt = datetime.fromtimestamp(0, tz=timezone.utc)

            current_commit = {
                "hash": h,
                "author": author,
                "datetime": commit_dt,
                "timestamp": commit_dt.timestamp(),
                "subject": subject,
                "is_bugfix": is_bugfix_message(subject),
                "files": [],
            }
        elif current_commit:
            # numstat line: <added> <deleted> <filename>
            parts = line.split("\t")
            if len(parts) >= 3:
                added = int(parts[0]) if parts[0].isdigit() else 0
                deleted = int(parts[1]) if parts[1].isdigit() else 0
                fpath = parts[2].replace("\\", "/")
                current_commit["files"].append({
                    "path": fpath,
                    "added": added,
                    "deleted": deleted,
                })

    if current_commit:
        commits.append(current_commit)

    # Filter strictly to commits <= cutoff_date (guarantees as-of invariance)
    past_commits = [c for c in commits if c["timestamp"] <= cutoff_date.timestamp()]
    # Filter within window [window_start, cutoff_date]
    window_commits = [c for c in past_commits if c["timestamp"] >= window_start_ts]

    # Future commits: (T, T + 6 months] for labeling
    future_window_ts = cutoff_date.timestamp() + (6 * 30 * 86400)
    future_commits = [
        c for c in commits
        if cutoff_date.timestamp() < c["timestamp"] <= future_window_ts
    ]

    return {
        "cutoff_date": cutoff_date.isoformat(),
        "total_commits": len(commits),
        "past_commits_count": len(past_commits),
        "window_commits": window_commits,
        "future_commits": future_commits,
    }


def compute_file_history_features(
    history_data: Dict[str, Any],
    cutoff_date: datetime,
) -> Dict[str, Dict[str, Any]]:
    """Compute file-level history features strictly in the window before cutoff_date."""
    window_commits = history_data.get("window_commits", [])
    cutoff_ts = cutoff_date.timestamp()

    file_stats: Dict[str, Dict[str, Any]] = {}

    for commit in window_commits:
        author = commit["author"]
        ts = commit["timestamp"]
        is_bug = commit["is_bugfix"]

        for f in commit["files"]:
            path = f["path"]
            if path not in file_stats:
                file_stats[path] = {
                    "commits_12m": 0,
                    "authors": set(),
                    "lines_added_12m": 0,
                    "lines_deleted_12m": 0,
                    "bugfix_commits_12m": 0,
                    "timestamps": [],
                }

            st = file_stats[path]
            st["commits_12m"] += 1
            st["authors"].add(author)
            st["lines_added_12m"] += f["added"]
            st["lines_deleted_12m"] += f["deleted"]
            if is_bug:
                st["bugfix_commits_12m"] += 1
            st["timestamps"].append(ts)

    result: Dict[str, Dict[str, Any]] = {}
    for path, st in file_stats.items():
        added = st["lines_added_12m"]
        deleted = st["lines_deleted_12m"]
        churn_ratio = round((added + deleted) / max(1, added), 3)

        timestamps = sorted(st["timestamps"])
        last_ts = timestamps[-1]
        first_ts = timestamps[0]

        days_since_last_change = round(max(0.0, (cutoff_ts - last_ts) / 86400.0), 1)
        age_days_capped = round(min(365.0, max(0.0, (cutoff_ts - first_ts) / 86400.0)), 1)

        result[path] = {
            "commits_12m": st["commits_12m"],
            "authors_12m": len(st["authors"]),
            "lines_added_12m": added,
            "lines_deleted_12m": deleted,
            "churn_ratio": churn_ratio,
            "days_since_last_change": days_since_last_change,
            "bugfix_commits_12m": st["bugfix_commits_12m"],
            "age_days_capped": age_days_capped,
        }

    return result


def compute_repo_history_features(
    history_data: Dict[str, Any],
    cutoff_date: datetime,
) -> Dict[str, Any]:
    """Compute repo-level history features strictly in the window before cutoff_date."""
    window_commits = history_data.get("window_commits", [])
    cutoff_ts = cutoff_date.timestamp()

    if not window_commits:
        return {
            "commits_per_month_mean": 0.0,
            "commits_per_month_slope": 0.0,
            "last3m_to_prior9m_ratio": 0.0,
            "distinct_authors": 0,
            "new_authors_3m": 0,
            "days_since_last_commit": 365.0,
            "bus_factor": 0,
        }

    # Monthly buckets (12 buckets of 30 days, 0 is most recent month)
    monthly_counts = [0] * 12
    author_counts: Dict[str, int] = {}
    authors_prior_9m: Set[str] = set()
    authors_last_3m: Set[str] = set()

    three_months_ts = cutoff_ts - (90 * 86400)
    timestamps: List[float] = []

    for commit in window_commits:
        ts = commit["timestamp"]
        author = commit["author"]
        timestamps.append(ts)
        author_counts[author] = author_counts.get(author, 0) + 1

        days_ago = max(0.0, (cutoff_ts - ts) / 86400.0)
        bucket_idx = min(11, int(days_ago // 30))
        monthly_counts[bucket_idx] += 1

        if ts >= three_months_ts:
            authors_last_3m.add(author)
        else:
            authors_prior_9m.add(author)

    # 1. Mean monthly commits
    commits_mean = round(sum(monthly_counts) / 12.0, 2)

    # 2. Linear slope over 12 months (month 11 is oldest, month 0 is newest)
    # y = monthly_counts reversed: [oldest -> newest]
    y = list(reversed(monthly_counts))
    n = 12
    x_mean = 5.5
    y_mean = sum(y) / 12.0
    numer = sum((i - x_mean) * (y[i] - y_mean) for i in range(n))
    denom = sum((i - x_mean) ** 2 for i in range(n)) or 1.0
    slope = round(numer / denom, 3)

    # 3. last-3-months over prior-9-months ratio
    c_last_3m = sum(monthly_counts[:3])
    c_prior_9m = sum(monthly_counts[3:])
    rate_last_3m = c_last_3m / 3.0
    rate_prior_9m = c_prior_9m / 9.0
    ratio_3m_9m = round(rate_last_3m / max(0.1, rate_prior_9m), 2)

    # 4. Authors metrics
    distinct_authors = len(author_counts)
    new_authors_3m = len(authors_last_3m - authors_prior_9m)

    # 5. Days since last commit
    last_commit_ts = max(timestamps) if timestamps else cutoff_ts
    days_since_last = round(max(0.0, (cutoff_ts - last_commit_ts) / 86400.0), 1)

    # 6. Bus factor: minimum authors generating > 50% of commits
    sorted_author_commits = sorted(author_counts.values(), reverse=True)
    total_commits = sum(sorted_author_commits)
    threshold = total_commits * 0.50
    cum = 0
    bus_factor = 0
    for count in sorted_author_commits:
        cum += count
        bus_factor += 1
        if cum > threshold:
            break

    return {
        "commits_per_month_mean": commits_mean,
        "commits_per_month_slope": slope,
        "last3m_to_prior9m_ratio": ratio_3m_9m,
        "distinct_authors": distinct_authors,
        "new_authors_3m": new_authors_3m,
        "days_since_last_commit": days_since_last,
        "bus_factor": bus_factor,
    }
