# Model Card: Documentation Section Classifier

## Model Details
- **Model Name:** README Section Classifier
- **Model Type:** TF-IDF + MultinomialNB
- **Version:** 1.0.0
- **Random Seed:** 42

## Intended Use
Classifies README markdown body sections into functional categories: `installation`, `usage`, `contributing`, `license`, `other`.
Headings are intentionally stripped from the text the model observes to prevent trivial shortcut learning.

## Metrics & Baseline Comparison
- **Majority Class Baseline:** Accuracy = 0.125, Macro F1 = 0.0444
- **MultinomialNB:** Accuracy = 0.5, Macro F1 = 0.38

## Limitations
- Very short one-liner sections (<20 characters) may have insufficient vocabulary signal.
