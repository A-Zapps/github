# PRD: GitHub Repository Analyzer

Status: draft v1
Owner: Sai
Built by: Antigravity agent, reviewed by Sai
Read next: RULES.md, ARCHITECTURE.md, DESIGN.md, TASK.md

---

## 1. Summary

A web app. You type a GitHub repo name (`owner/name`). It pulls real data from GitHub, runs static analysis on the code, and uses models trained on real repositories to predict two things: which files are likely to get bug fixes, and whether the repo is heading toward being healthy or dead. Results show in a dashboard and export as a PDF.

One rule sits above everything else: every number on screen comes from GitHub, a static analysis tool, or a trained model with saved metrics. Nothing is mocked in the product.

## 2. Who it is for

| User | What they want |
|---|---|
| Student or developer | Judge an open-source repo before using it or contributing |
| Maintainer | Quick health check on their own repo |
| Reviewer or professor | See real ML work with honest evaluation |

## 3. Goals

1. Analyze any public GitHub repo end to end from one input box.
2. Show real data, real static analysis results, real model predictions.
3. Show how good each model actually is, including when it is not good.
4. Never run code from the analyzed repo.
5. Export everything as one PDF.

## 4. Non-goals (v1)

- No login, no multi-user, no accounts.
- No private repo support in the UI (a token can be used server-side for rate limits).
- No running, building, or testing the analyzed repo.
- No auto-fix pull requests.
- No dark mode.
- No claims of state-of-the-art accuracy.
- No languages outside what Lizard can parse (see section 6).

## 5. Features

| ID | Feature | What the user sees | Data source | Phase |
|---|---|---|---|---|
| F1 | Repository analysis | Stars, forks, languages, commits, contributors, issues, PRs, file tree, README | GitHub REST API + git history | 1 |
| F2 | Code quality | Score 0 to 100, grade, complexity charts, worst files, duplication, tech debt estimate | Lizard, Radon, Pylint, own duplicate detector | 2 |
| F3 | Bug prediction | Per-file risk (Low, Medium, High) with probability | Trained model (bug_risk) | 4 |
| F4 | Security analysis | Secrets, injection patterns, XSS, unsafe functions, vulnerable dependencies | Own regex rules, Bandit, Semgrep (optional), OSV.dev | 2 |
| F5 | Repository health | One of: Healthy, Moderately Active, Declining, Inactive, with class probabilities | Trained model (repo_health) | 4 |
| F6 | Documentation analysis | README score, which sections exist, what is missing | Heading rules + trained model (doc_sections) | 5 |
| F7 | Developer analytics | Contributors, commit rhythm, PR merge time, issue close time, bus factor | GitHub API + git history | 5 |
| F8 | AI code assistant | Chat that explains files, spots possible bugs, summarizes architecture, with file and line citations | RAG over the repo + an LLM | 7 |
| F9 | Repository comparison | 2 to 4 repos side by side, radar chart, cluster map | Stored analyses + repo_clusters | 6 |
| F10 | Recommendations | Ranked, concrete actions, each tied to evidence | Rule engine over all results | 6 |
| F11 | PDF reports | Downloadable report with every section and chart | Stored analysis | 8 |
| F12 | Model performance page | Metrics, baselines, confusion matrices, curves, model cards | `metrics.json` written by training | 4 |

Navigation (13 items, fixed order): Overview, Repository Analyzer, Code Quality, Bug Prediction, Security Analysis, Repository Health, Documentation, Developer Analytics, Repository Comparison, AI Assistant, Reports, Model Performance, Settings.

## 6. Where we deviate from the brief, and why

The original brief has a few things that cannot work as written. These are the decisions. If you disagree with one, say so before Phase 2.

| Brief says | We do | Why |
|---|---|---|
| Radon, Bandit, Pylint for code analysis | Use them for Python only. Add Lizard for every other language. Models use Lizard metrics so they work across languages. | Radon, Bandit and Pylint only read Python. |
| Random Forest for "code quality" | Quality score is a transparent rule-based formula (weights in `scoring.yaml`). The UI also shows a percentile against the training corpus. | There is no ground-truth "quality" label to train on. A model trained on a made-up label would be fake accuracy. |
| Random Forest Regressor for "maintainability" | It predicts maintenance effort per file: log of lines changed in the next 6 months. | Radon's maintainability index is a formula of the same inputs. Predicting it from those inputs proves nothing. Future change effort is a measurable target. |
| TF-IDF + Naive Bayes for "documentation classification" | It classifies README sections (install, usage, API, contributing, license, testing, other) from their body text. | Quality has no label. Section type does (from headings), and the classifier can then find sections that have odd headings. |
| XGBoost for repo health | Labels come from what happens in the 6 months after a cutoff date. Features come only from before it. | Labels computed from the same features would just be a rule dressed as a model. |
| CodeBERT for vulnerability classification | Optional phase 10. Trained on the Devign dataset (C/C++ functions). Only applied to C/C++ functions. | That is the labeled data that exists. Applying it to other languages would be guessing. Needs a GPU to train (Colab works). |
| Semgrep | Optional. Own rule files only. Windows users run in WSL2 or skip it. | Semgrep does not run natively on Windows. |
| PyTorch | Only needed for CodeBERT and sentence embeddings. | Keeps the base install light. |
| SQLite/PostgreSQL | SQLite by default. Postgres works by changing `DATABASE_URL`. | Zero setup for local work. |
| "Background processing" | In-process job runner with a jobs table. No Celery, no Redis. | One less thing to install. Cost: running jobs are marked failed if the server restarts. |
| Chart.js in PDF | PDF charts are drawn with matplotlib using the same data. | Chart.js needs a browser. |
| Not in the brief, but a common choice: stars and forks as model inputs | Not used as model inputs. They still show on the Repository page. | GitHub only gives today's counts. Using them to predict from a past cutoff leaks the future. |

## 7. Success criteria

Each one is a check you can run.

1. Analyzing a public repo under 300 MB finishes without a crash and shows live progress. Target: under 3 minutes for a repo with under 500 files, under 10 minutes for under 3,000 files. These are targets, measured in Phase 9.
2. Every API response carries `head_sha`, `analyzer_version`, and `model_versions` in `meta`.
3. Each trained model has `metrics.json`, `model_card.md`, and `training_manifest.json`. One command retrains it.
4. Each model is compared to a baseline on held-out repos. If a model does not beat its baseline, the Model Performance page says so. That counts as a pass.
5. If a model file is missing, the endpoint returns `MODEL_NOT_TRAINED` and the page says "not trained". No fallback numbers.
6. Tests prove the analyzed code is never executed: path traversal, symlinks, repo-supplied config files, hooks.
7. All 13 pages work with real data and have loading, empty, and error states.
8. The PDF has every section and its charts match the screen.
9. A fresh clone plus README steps runs in under 30 minutes, not counting model training.
10. `scripts/check` passes: lint, tests, forbidden-pattern scan.

## 8. Open questions

Defaults are what the agent assumes unless you change them.

| # | Question | Default |
|---|---|---|
| Q1 | Which LLM for the assistant, and do you have an API key? | Provider is set by `LLM_PROVIDER`. Without a key, the assistant shows retrieved code only. |
| Q2 | What OS do you develop on? | Windows with WSL2 assumed. Semgrep runs only inside WSL2 or Linux. |
| Q3 | GPU access for CodeBERT? | None. Phase 10 stays optional. |
| Q4 | How long can the dataset build run? | 400 repos, resumable, runs unattended. |
| Q5 | Public repos only? | Yes. |

## 9. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| GitHub rate limits (60 per hour without a token, 5,000 with) | Slow or failed analyses | Token required in practice. ETag caching. Read rate-limit headers. Show the meter in the UI. |
| Bug labels come from commit messages | Label noise lowers accuracy | State it in the model card. Report PR-AUC, not just accuracy. |
| Small training corpus | Wide uncertainty in metrics | Report corpus size. Split by repo, never by file. |
| Hostile repo content | Code execution, XSS, prompt injection | RULES.md section B. Tests in Phase 9. |
| LLM invents code or file references | Wrong answers shown as fact | Citations are checked against retrieved chunks. Unverified output is labeled. |
| Scope is large | Project stalls | Vertical slices. Each phase ends with something you can see. |
| Heavy installs (torch, xgboost) | Slow setup | Split requirements files. |

## 10. Phases

See TASK.md for tasks and done-when checks.

| Phase | Result you can see | Agent time (guess) |
|---|---|---|
| 0 | Empty dashboard shell in final design | 1 h |
| 1 | Type `pallets/flask`, see real stats and charts | 3 h |
| 2 | Code Quality and Security pages with real findings | 4 h |
| 3 | Trained models and metrics files on disk | 5 h, plus 6 to 12 h unattended dataset build |
| 4 | Bug Prediction, Health, Model Performance pages | 3 h |
| 5 | Documentation and Developer Analytics pages | 2 h |
| 6 | Recommendations and Comparison | 2 h |
| 7 | AI Assistant | 3 h |
| 8 | PDF reports | 2 h |
| 9 | Hardening, tests, README | 3 h |
| 10 | Optional: CodeBERT | 4 h plus GPU |

The time guesses are for agent work. Add your review time. Track actuals in TASK.md.
