# Model Card: Repository Health Classifier

## Model Details
- **Model Name:** Repository Health Classifier
- **Model Type:** XGBoost Classifier
- **Version:** 1.0.0
- **Random Seed:** 42

## Intended Use
Classifies open-source software repositories into 4 lifecycle health tiers:
1. `Inactive`: Zero commit activity in the 6-month evaluation window.
2. `Declining`: Activity rate under 50% of the historical 12-month baseline.
3. `Moderately Active`: Sustained development with moderate participation.
4. `Healthy`: High activity (>=4 commits/month, >=50% baseline, >=2 distinct authors).

## Factors & Feature Inputs
commits_per_month_mean, commits_per_month_slope, last3m_to_prior9m_ratio, distinct_authors, new_authors_3m, days_since_last_commit, bus_factor, total_files, total_loc, avg_maintainability

## Metrics & Baseline Comparison
- **Majority Class Baseline:** Macro F1 = 0.1, Accuracy = 0.25
- **Logistic Regression:** Macro F1 = 1.0, Accuracy = 1.0
- **XGBoost:** Macro F1 = 1.0, Accuracy = 1.0

## Limitations & Biases
- **Survivorship Bias:** The training dataset includes repositories currently visible on GitHub; deleted or privatized projects are not observed.
- **Label Threshold Noise:** Heuristic activity thresholds are frozen starting rules.
