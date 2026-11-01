# Model Card: Repository Clustering & Corpus Reference

## Model Details
- **Model Name:** Repository Archetype Clusterer & 2D PCA Embedder
- **Algorithm:** StandardScaler + KMeans (k=4) + PCA(2 components)
- **Version:** 1.0.0
- **Random Seed:** 42

## Intended Use
Groups software repositories into structural and operational archetypes and projects them into a 2D space for comparative visual analytics.

## Metrics
- **Optimal Clusters (k):** 4
- **Silhouette Score:** 0.5111
- **Davies-Bouldin Score:** 0.6998
- **PCA Explained Variance:** [0.5985, 0.2396] (Total: 0.8381)

## Features Used
total_files, total_loc, avg_maintainability, duplication_pct, test_ratio, commits_per_month_mean, distinct_authors, bus_factor
