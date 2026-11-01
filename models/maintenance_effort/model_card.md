# Model Card: Maintenance Effort Predictor

## Model Details
- **Model Name:** Maintenance Effort Predictor
- **Model Type:** RandomForestRegressor (100 trees, max_depth=6)
- **Version:** 1.0.0
- **Random Seed:** 42

## Intended Use
Predicts expected code churn (log1p of total lines added + deleted) over the upcoming 6-month development cycle for individual source files.

## Target
`log1p(churn)` where `churn = lines_added + lines_deleted` in the 6 months after the cutoff date.

## Factors & Feature Inputs
loc, nloc, n_functions, ccn_max, ccn_mean, ccn_p90, token_count, params_max, commits_12m, authors_12m, lines_added_12m, lines_deleted_12m, churn_ratio, days_since_last_change, bugfix_commits_12m, age_days_capped, is_test

## Metrics & Baseline Comparison
- **Mean Predictor Baseline:** MAE = 0.355, RMSE = 0.4583, R2 = -0.0006
- **RandomForestRegressor:** MAE = 0.2174, RMSE = 0.2626, R2 = 0.6715

## Limitations
- Volatile refactorings or mass formatting changes may inflate short-term churn without representing routine maintenance.
