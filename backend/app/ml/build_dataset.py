"""Dataset builder pipeline: clones, extracts as-of features and labels, deletes clone, writes parquet (RULES D1, D2, D9)."""

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from backend.app.analyzers.history import (
    compute_file_history_features,
    compute_repo_history_features,
    parse_git_log_history,
)
from backend.app.analyzers.inventory import scan_inventory
from backend.app.analyzers.metrics import analyze_repository_metrics
from backend.app.config import get_settings
from backend.app.core.sandbox import (
    cleanup_work_dir,
    clone_bare_repo,
    materialize_tree,
)
from backend.app.core.subprocess_runner import run_tool
from backend.app.ml.labels import (
    compute_file_bug_labels,
    compute_file_maintenance_labels,
    compute_repo_health_label,
)
from backend.app.ml.sampling import sample_repositories

logger = logging.getLogger(__name__)

DEFAULT_DATASET_DIR = Path("./data/dataset")


def load_manifest(manifest_path: Path) -> Dict[str, Any]:
    """Load existing dataset manifest to allow resuming without re-processing."""
    if manifest_path.is_file():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seed": 42,
        "processed_repos": [],
        "file_rows_count": 0,
        "repo_rows_count": 0,
    }


def save_manifest(manifest_path: Path, manifest: Dict[str, Any]) -> None:
    """Save updated manifest."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def get_commit_sha_as_of(git_dir: str, cutoff_date: datetime) -> Optional[str]:
    """Find the latest commit SHA strictly at or before cutoff_date, or fallback to oldest in clone."""
    argv = [
        "git", "log", "-1",
        f"--until={cutoff_date.isoformat()}",
        "--pretty=format:%H",
    ]
    try:
        proc = run_tool(argv, timeout=30.0, cwd=git_dir)
        sha = proc.stdout.decode("utf-8", errors="replace").strip()
        if sha:
            return sha
        # Fallback to earliest commit in clone if all commits are after cutoff
        proc_rev = run_tool(["git", "log", "-1", "--reverse", "--pretty=format:%H"], timeout=30.0, cwd=git_dir)
        return proc_rev.stdout.decode("utf-8", errors="replace").strip() or None
    except Exception:
        return None


def extract_repo_features_and_labels(
    repo_name: str,
    work_base_dir: Path,
    cutoff_date: datetime,
    token: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Clone, extract features & labels strictly as of cutoff_date, and delete the clone."""
    work_dir = work_base_dir / f"build_{hashlib.md5(repo_name.encode()).hexdigest()[:8]}"
    git_dir = work_dir / "git"
    src_dir = work_dir / "src"

    try:
        # Shallow clone with history window
        clone_bare_repo(repo_name, str(git_dir), months=19, token=token)

        # Find head commit as of cutoff date T
        sha_as_of = get_commit_sha_as_of(str(git_dir), cutoff_date)
        if not sha_as_of:
            logger.warning("No commits found before cutoff date for %s", repo_name)
            return None

        # Materialize source tree at commit T
        materialize_tree(str(git_dir), str(src_dir), head_sha=sha_as_of, max_files=2000, max_file_kb=500)

        # Parse git history
        history_data = parse_git_log_history(str(git_dir), cutoff_date=cutoff_date, months_window=12)
        window_commits = history_data.get("window_commits", [])
        future_commits = history_data.get("future_commits", [])

        # Run static metrics as of T
        inventory = scan_inventory(str(src_dir))
        active_files = [f["path"] for f in inventory.get("files", [])]
        static_metrics = analyze_repository_metrics(src_dir, active_files)

        # 1. Repo level features & labels
        repo_features = compute_repo_history_features(history_data, cutoff_date)
        repo_health_label = compute_repo_health_label(window_commits, future_commits)

        repo_record = {
            "repo": repo_name,
            "cutoff_date": cutoff_date.isoformat(),
            **repo_features,
            "total_files": static_metrics.get("total_files", 0),
            "total_loc": static_metrics.get("total_loc", 0),
            "avg_maintainability": static_metrics.get("avg_maintainability_index", 100.0),
            "label_health": repo_health_label.get("label"),
            "label_health_class": repo_health_label.get("class_id"),
        }

        # 2. File level features & labels
        file_history_features = compute_file_history_features(history_data, cutoff_date)
        file_bug_labels = compute_file_bug_labels(future_commits, active_files)
        file_maint_labels = compute_file_maintenance_labels(future_commits, active_files)

        file_records: List[Dict[str, Any]] = []
        for fpath in active_files:
            fm = static_metrics.get("files", {}).get(fpath, {})
            fh = file_history_features.get(fpath, {
                "commits_12m": 0,
                "authors_12m": 0,
                "lines_added_12m": 0,
                "lines_deleted_12m": 0,
                "churn_ratio": 0.0,
                "days_since_last_change": 365.0,
                "bugfix_commits_12m": 0,
                "age_days_capped": 0.0,
            })

            file_records.append({
                "repo": repo_name,
                "file": fpath,
                "loc": fm.get("loc", 0),
                "nloc": fm.get("nloc", 0),
                "n_functions": fm.get("n_functions", 0),
                "ccn_max": fm.get("ccn_max", 0),
                "ccn_mean": fm.get("ccn_mean", 0.0),
                "ccn_p90": fm.get("ccn_p90", 0.0),
                "token_count": fm.get("token_count", 0),
                "params_max": fm.get("params_max", 0),
                **fh,
                "is_test": 1 if any(t in fpath.lower() for t in ("test", "spec")) else 0,
                "label_bug_risk": file_bug_labels.get(fpath, 0),
                "label_maintenance_effort": file_maint_labels.get(fpath, 0.0),
            })

        return {
            "repo_record": repo_record,
            "file_records": file_records,
        }

    except Exception as exc:
        logger.warning("Failed processing repo %s: %s", repo_name, exc)
        return None
    finally:
        # Guarantee clone and work directories are deleted (RULES B12)
        cleanup_work_dir(str(work_dir))


def build_dataset(
    output_dir: Path = DEFAULT_DATASET_DIR,
    target_count: int = 5,
    cutoff_date: Optional[datetime] = None,
    custom_repos: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Execute resumable dataset build across sampled repositories."""
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "training_manifest.json"
    repo_parquet_path = output_dir / "repo_features.parquet"
    file_parquet_path = output_dir / "file_features.parquet"

    manifest = load_manifest(manifest_path)
    processed_set = set(manifest.get("processed_repos", []))

    if cutoff_date is None:
        # T is today minus 7 months so the full 6-month label window has elapsed
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=210)

    sampled = sample_repositories(target_count=target_count, custom_list=custom_repos)
    settings = get_settings()

    work_base = Path(settings.DATA_DIR) / "dataset_work"
    work_base.mkdir(parents=True, exist_ok=True)

    all_repo_records: List[Dict[str, Any]] = []
    all_file_records: List[Dict[str, Any]] = []

    # If parquet files exist, load them to resume
    if repo_parquet_path.is_file():
        try:
            existing_repo_df = pd.read_parquet(repo_parquet_path)
            all_repo_records = existing_repo_df.to_dict(orient="records")
        except Exception:
            pass

    if file_parquet_path.is_file():
        try:
            existing_file_df = pd.read_parquet(file_parquet_path)
            all_file_records = existing_file_df.to_dict(orient="records")
        except Exception:
            pass

    new_processed = 0
    for item in sampled:
        repo_name = item["repo"]
        if repo_name in processed_set:
            logger.info("Skipping already processed repo: %s", repo_name)
            continue

        logger.info("Extracting features for repo: %s", repo_name)
        extracted = extract_repo_features_and_labels(
            repo_name=repo_name,
            work_base_dir=work_base,
            cutoff_date=cutoff_date,
            token=settings.GITHUB_TOKEN,
        )

        if extracted:
            all_repo_records.append(extracted["repo_record"])
            all_file_records.extend(extracted["file_records"])
            manifest["processed_repos"].append(repo_name)
            processed_set.add(repo_name)
            new_processed += 1

            # Save progress incrementally
            if all_repo_records:
                pd.DataFrame(all_repo_records).to_parquet(repo_parquet_path, index=False)
            if all_file_records:
                pd.DataFrame(all_file_records).to_parquet(file_parquet_path, index=False)

            manifest["repo_rows_count"] = len(all_repo_records)
            manifest["file_rows_count"] = len(all_file_records)
            save_manifest(manifest_path, manifest)

    cleanup_work_dir(str(work_base))

    return {
        "manifest": manifest,
        "new_processed": new_processed,
        "total_repos": len(all_repo_records),
        "total_files": len(all_file_records),
        "repo_parquet": str(repo_parquet_path),
        "file_parquet": str(file_parquet_path),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build training dataset across sampled repositories")
    parser.add_argument("--count", type=int, default=20, help="Target number of repositories to sample")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print(f"Starting dataset build (target: {args.count} repos)...")
    res = build_dataset(target_count=args.count)
    print(f"Build completed! Total repos: {res['total_repos']}, total files: {res['total_files']}.")

