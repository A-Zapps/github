# Model Card: Bug Risk Predictor

## Model Details
- **Model Name:** Bug Risk Predictor
- **Selected Algorithm:** RandomForest (chosen by validation PR-AUC)
- **Version:** 1.0.0
- **Random Seed:** 42

## Intended Use
Identifies source code files with high probability of being touched by a bug-fix commit in the subsequent 6 months.

## Baselines & Performance
- **Prior Rate Baseline:** PR-AUC = 0.325
- **Most-Changed Heuristic:** PR-AUC = 0.9473
- **RandomForest:** PR-AUC = 1.0
- **XGBoost:** PR-AUC = 1.0
- **LogisticRegression:** PR-AUC = 1.0
- **CalibratedLinearSVM:** PR-AUC = 1.0

## Limitations & Biases
- **Label Noise:** Bug-fix commits are identified by commit message heuristics.
- **Survivorship Bias:** Analyzed open-source repositories represent surviving active projects.
