"""Train documentation section classification model with TF-IDF + MultinomialNB and baselines (RULES D1-D10)."""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

logger = logging.getLogger(__name__)

MODELS_DIR = Path("./models/doc_sections")
SEED = 42

DOC_CLASSES = ["installation", "usage", "contributing", "license", "other"]

# Heading patterns for weak labeling
HEADING_PATTERNS = {
    "installation": re.compile(r"\b(install\w*|setup|getting\s*started|prerequisites|requirements)\b", re.IGNORECASE),
    "usage": re.compile(r"\b(usage|quickstart|examples?|how\s*to\s*use|commands|running|api|features)\b", re.IGNORECASE),
    "contributing": re.compile(r"\b(contribut\w*|development|guidelines|pull\s*requests|dev\s*setup|testing)\b", re.IGNORECASE),
    "license": re.compile(r"\b(licen[sc]e|copyright|authors|credits)\b", re.IGNORECASE),
}


def label_heading(heading_text: str) -> str:
    """Assign weak label based on heading content."""
    clean = heading_text.strip().lower()
    for cat, pat in HEADING_PATTERNS.items():
        if pat.search(clean):
            return cat
    return "other"


def split_readme_sections(readme_text: str) -> List[Tuple[str, str]]:
    """Split markdown text into (weak_label, body_text_without_heading)."""
    # Split by markdown headers (# or ## or ###)
    lines = readme_text.splitlines()
    sections: List[Tuple[str, List[str]]] = []
    current_heading = "intro"
    current_lines: List[str] = []

    for line in lines:
        match = re.match(r"^#{1,6}\s+(.+)$", line.strip())
        if match:
            if current_lines:
                sections.append((current_heading, current_lines))
                current_lines = []
            current_heading = match.group(1).strip()
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_heading, current_lines))

    labeled_sections = []
    for heading, text_lines in sections:
        body = "\n".join(text_lines).strip()
        if len(body) >= 5:  # skip completely empty noise
            cat = label_heading(heading)
            labeled_sections.append((cat, body))

    return labeled_sections


def generate_seed_docs_dataset() -> List[Dict[str, str]]:
    """Generate representative documentation corpus with realistic text."""
    seed_data = [
        # Installation
        ("installation", "pip install mypackage\nRun pip install -r requirements.txt to install all dependencies. Ensure Python 3.10 or higher is installed on your operating system."),
        ("installation", "To build from source, clone the repository and run cargo build --release. Ensure rustup and cargo are available on your system path."),
        ("installation", "npm install @example/sdk\nAdd the package to your package.json dependencies and execute npm install or pnpm install."),
        ("installation", "Docker pull example/server:latest\nRun docker-compose up -d to spin up the local development containers with postgres."),
        ("installation", "Download the latest release binary from the GitHub releases page. Unpack the tar.gz archive and move the binary to /usr/local/bin."),
        ("installation", "Add the following dependency to your pom.xml file or build.gradle script to fetch artifacts from Maven Central."),
        ("installation", "brew install example-cli\nVerify the installation by checking example --version in your command prompt."),
        ("installation", "System requirements: at least 4GB RAM, Linux kernel 5.4+ or macOS 12+. Run ./configure && make && sudo make install."),

        # Usage
        ("usage", "from mypackage import Client\nclient = Client(api_key='...')\nresponse = client.fetch_data(limit=10)\nprint(response.results)"),
        ("usage", "Execute the command line runner: repo-analyzer --url https://github.com/org/repo --output json --verbose to inspect local logs."),
        ("usage", "const sdk = require('sdk');\nconst app = sdk.createApp({ port: 8080 });\napp.start().then(() => console.log('Listening on 8080'));"),
        ("usage", "Querying endpoints:\nGET /api/v1/healthz returns the active server status. Pass Bearer authorization in the HTTP headers."),
        ("usage", "Interactive mode:\nRun the command with the -i flag to step through the guided prompt interface and customize configuration settings."),
        ("usage", "Configuration options:\nSet LOG_LEVEL=debug in your environment or provide a config.yaml file with database connection parameters."),
        ("usage", "Example workflow:\n1. Initialize project with init\n2. Run analyze\n3. Export report to PDF format using export command."),
        ("usage", "Curl request example:\ncurl -X POST http://localhost:8000/api/analyze -H 'Content-Type: application/json' -d '{\"repo\": \"test\"}'"),

        # Contributing
        ("contributing", "We welcome contributions! Please open an issue to discuss proposed changes before opening a pull request."),
        ("contributing", "Development guidelines:\n1. Fork the repo and create your feature branch.\n2. Run pytest to ensure all test suites pass.\n3. Run ruff check . to satisfy linting."),
        ("contributing", "Submitting PRs:\nEnsure all commits follow the Conventional Commits specification (e.g. feat: add new endpoint, fix: resolve null pointer)."),
        ("contributing", "Code style:\nWe use Black for formatting and Flake8 for static analysis. Pre-commit hooks run automatically upon git commit."),
        ("contributing", "Setting up local test suite:\nRun tox or pytest -v --cov=app to verify coverage metrics before submitting code."),
        ("contributing", "Please adhere to our Code of Conduct in all interactions within the issue tracker, discussions, and pull requests."),
        ("contributing", "Bug reports should include operating system version, reproduction steps, minimal reproducible code sample, and full stack trace."),
        ("contributing", "To run integration tests, set up local Redis and Postgres instances before executing make test-integration."),

        # License
        ("license", "Distributed under the MIT License. See LICENSE file in the root directory for more information and full legal text."),
        ("license", "Copyright 2026 The Authors. Licensed under Apache License 2.0. You may obtain a copy of the License at www.apache.org/licenses/LICENSE-2.0."),
        ("license", "This software is open source licensed under the BSD 3-Clause License. See the LICENSE file for exact warranty and disclaimer terms."),
        ("license", "GNU General Public License v3.0 or later. Permissions of this strong copyleft license are conditioned on making available complete source code."),
        ("license", "Dual-licensed under MIT and Apache-2.0 at your option. All third-party notices are cataloged in NOTICE.txt."),
        ("license", "Mozilla Public License Version 2.0. Incompatible with secondary licenses as specified in the license agreement header."),
        ("license", "All trademarks, service marks, and company names are the property of their respective owners."),
        ("license", "Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation."),

        # Other
        ("other", "Architecture overview:\nThe backend consists of an event-driven message queue backed by worker pools and persistent storage."),
        ("other", "Security disclosure:\nIf you discover a security vulnerability, please email security@example.com instead of opening a public issue."),
        ("other", "Changelog and release notes:\nVersion 2.0 introduces breaking changes to the REST contract. Older client versions are deprecated."),
        ("other", "Frequently Asked Questions:\nQ: How does this compare to alternative libraries?\nA: Our engine is designed for zero external dependencies."),
        ("other", "Roadmap:\nUpcoming milestones include GraphQL support, real-time WebSocket subscriptions, and Kubernetes operator deployment."),
        ("other", "Acknowledgments:\nSpecial thanks to all open-source maintainers whose upstream packages made this framework possible."),
        ("other", "Benchmark comparisons:\nThroughput benchmarks show 3x latency reduction under concurrent request load up to 10k RPS."),
        ("other", "Community channels:\nJoin our public Discord server or participate in GitHub Discussions to connect with fellow developers."),
    ]
    return [{"category": cat, "text": text} for cat, text in seed_data]


def train_docs_model(
    output_dir: Path = MODELS_DIR,
) -> Dict[str, Any]:
    """Train README documentation section classification model and save artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset = generate_seed_docs_dataset()

    texts = [row["text"] for row in dataset]
    labels = [row["category"] for row in dataset]

    # Hold out 20% stratified test split
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.20, random_state=SEED, stratify=labels
    )

    # 1. Baseline: Majority Class Classifier
    majority_clf = DummyClassifier(strategy="most_frequent")
    majority_clf.fit(X_train, y_train)
    y_pred_base = majority_clf.predict(X_test)
    base_acc = round(float(accuracy_score(y_test, y_pred_base)), 4)
    base_macro_f1 = round(float(f1_score(y_test, y_pred_base, average="macro", zero_division=0)), 4)

    # 2. Model: TF-IDF + MultinomialNB Pipeline
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=3000, stop_words="english")),
        ("clf", MultinomialNB(alpha=0.5)),
    ])
    pipeline.fit(X_train, y_train)
    y_pred_nb = pipeline.predict(X_test)
    nb_acc = round(float(accuracy_score(y_test, y_pred_nb)), 4)
    nb_macro_f1 = round(float(f1_score(y_test, y_pred_nb, average="macro", zero_division=0)), 4)

    # Save artifacts
    # a. model.joblib
    joblib.dump(pipeline, output_dir / "model.joblib")

    # b. metrics.json
    metrics_payload = {
        "task": "doc_sections",
        "best_model": "MultinomialNB",
        "classes": DOC_CLASSES,
        "models": {
            "MajorityClassBaseline": {
                "accuracy": base_acc,
                "macro_f1": base_macro_f1,
                "note": "Predicts most frequent training class",
            },
            "MultinomialNB": {
                "accuracy": nb_acc,
                "macro_f1": nb_macro_f1,
            },
        },
        "held_out_test_rows": len(y_test),
        "training_rows": len(y_train),
    }
    (output_dir / "metrics.json").write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")

    # c. feature_schema.json
    schema_payload = {
        "input_type": "text",
        "features": [
            {"name": "text", "type": "string", "description": "Markdown section body text (headings excluded)"}
        ],
        "output_classes": DOC_CLASSES,
    }
    (output_dir / "feature_schema.json").write_text(json.dumps(schema_payload, indent=2), encoding="utf-8")

    # d. training_manifest.json
    manifest_payload = {
        "seed": SEED,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "classes": DOC_CLASSES,
        "libraries": {
            "scikit-learn": "1.4+",
        },
    }
    (output_dir / "training_manifest.json").write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")

    # e. model_card.md
    model_card = f"""# Model Card: Documentation Section Classifier

## Model Details
- **Model Name:** README Section Classifier
- **Model Type:** TF-IDF + MultinomialNB
- **Version:** 1.0.0
- **Random Seed:** {SEED}

## Intended Use
Classifies README markdown body sections into functional categories: `installation`, `usage`, `contributing`, `license`, `other`.
Headings are intentionally stripped from the text the model observes to prevent trivial shortcut learning.

## Metrics & Baseline Comparison
- **Majority Class Baseline:** Accuracy = {base_acc}, Macro F1 = {base_macro_f1}
- **MultinomialNB:** Accuracy = {nb_acc}, Macro F1 = {nb_macro_f1}

## Limitations
- Very short one-liner sections (<20 characters) may have insufficient vocabulary signal.
"""
    (output_dir / "model_card.md").write_text(model_card, encoding="utf-8")

    return metrics_payload


if __name__ == "__main__":
    train_docs_model()
