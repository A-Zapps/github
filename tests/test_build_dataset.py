"""Tests for ML dataset builder, manifest tracking, parquet output, and resumability (RULES D1, D9)."""

from pathlib import Path
from unittest.mock import patch

import pandas as pd

from backend.app.ml.build_dataset import build_dataset
from backend.app.ml.sampling import sample_repositories


def test_sampling_deterministic():
    """Verify sample_repositories returns requested number of repos deterministically."""
    s1 = sample_repositories(target_count=5, seed=42)
    s2 = sample_repositories(target_count=5, seed=42)
    assert len(s1) == 5
    assert s1 == s2


def test_resumable_dry_run(tmp_path: Path):
    """Verify that build_dataset creates manifest and parquet files, and restarting skips completed repos."""
    out_dir = tmp_path / "dataset"
    out_dir.mkdir()

    # Mock extract_repo_features_and_labels to avoid live network cloning during unit test
    def mock_extract(repo_name, work_base_dir, cutoff_date, token):
        return {
            "repo_record": {
                "repo": repo_name,
                "cutoff_date": cutoff_date.isoformat(),
                "commits_per_month_mean": 12.5,
                "commits_per_month_slope": 0.12,
                "last3m_to_prior9m_ratio": 1.1,
                "distinct_authors": 5,
                "new_authors_3m": 1,
                "days_since_last_commit": 2.0,
                "bus_factor": 2,
                "total_files": 10,
                "total_loc": 1000,
                "avg_maintainability": 85.0,
                "label_health": "Healthy",
                "label_health_class": 3,
            },
            "file_records": [
                {
                    "repo": repo_name,
                    "file": f"mod_{i}.py",
                    "loc": 100,
                    "nloc": 80,
                    "n_functions": 4,
                    "ccn_max": 3,
                    "ccn_mean": 2.0,
                    "ccn_p90": 2.5,
                    "token_count": 200,
                    "params_max": 2,
                    "commits_12m": 3,
                    "authors_12m": 2,
                    "lines_added_12m": 120,
                    "lines_deleted_12m": 20,
                    "churn_ratio": 1.16,
                    "days_since_last_change": 5.0,
                    "bugfix_commits_12m": 1,
                    "age_days_capped": 100.0,
                    "is_test": 0,
                    "label_bug_risk": 1 if i == 0 else 0,
                    "label_maintenance_effort": 2.5,
                }
                for i in range(3)
            ],
        }

    repos = ["test/repo1", "test/repo2", "test/repo3", "test/repo4", "test/repo5"]

    with patch("backend.app.ml.build_dataset.extract_repo_features_and_labels", side_effect=mock_extract):
        # 1. First run: processes all 5 repos
        res1 = build_dataset(output_dir=out_dir, custom_repos=repos)
        assert res1["new_processed"] == 5
        assert res1["total_repos"] == 5
        assert res1["total_files"] == 15

        # Verify parquet files exist and are valid
        repo_df = pd.read_parquet(out_dir / "repo_features.parquet")
        file_df = pd.read_parquet(out_dir / "file_features.parquet")
        assert len(repo_df) == 5
        assert len(file_df) == 15

        # RULES D9: Verify dataset holds numbers and metadata only, NO raw source code
        for col in file_df.columns:
            assert col not in ("source", "code", "content", "raw_code"), f"Forbidden code column {col} in dataset!"

        # 2. Restart simulation: killing and restarting must skip all finished repos
        res2 = build_dataset(output_dir=out_dir, custom_repos=repos)
        assert res2["new_processed"] == 0, "Restart did not skip already processed repos!"
        assert res2["total_repos"] == 5
