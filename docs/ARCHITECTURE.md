# ARCHITECTURE: GitHub Repository Analyzer

Read PRD.md first. This file is the source of truth for names: folders, endpoints, tables, model names. If code and this file disagree, fix the code or update this file in the same commit.

---

## 1. Big picture

```
Browser (vanilla JS + Chart.js)
   |  JSON over HTTP, same origin: /api/v1/*
   v
FastAPI app (also serves frontend/ as static files)
   |-- api/v1 routers        thin: validate, call a service, return envelope
   |-- services              one per module, orchestrate analyzers + ML
   |-- core                  github client, jobs, sandbox, subprocess runner, cache
   |-- analyzers             static, security, docs, developers
   |-- ml (serving only)     feature builders, registry, predict
   |-- rag                   chunker, embedder, store, llm providers
   |-- reports               chart renderer + PDF builder
   |-- db                    SQLAlchemy 2 + Alembic
   v
Disk: data/ (db, work dirs, reports)   models/ (trained artifacts)

Outbound hosts (allowlist, nothing else):
  api.github.com, github.com (git clone), api.osv.dev, the LLM provider host

Offline: ml/ training scripts read GitHub, write models/ and ml/data/
```

## 2. Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11 or 3.12 |
| API | FastAPI, Uvicorn, pydantic v2, pydantic-settings |
| HTTP client | httpx (async) |
| DB | SQLAlchemy 2, Alembic, SQLite default, Postgres via `DATABASE_URL` |
| Static analysis | lizard (all languages), radon, pylint, bandit (Python), semgrep (optional) |
| ML | scikit-learn, xgboost, pandas, numpy, joblib |
| Deep learning (optional) | torch, transformers (CodeBERT), sentence-transformers (embeddings) |
| PDF | reportlab, matplotlib |
| Frontend | HTML, CSS, vanilla JS (ES modules), Chart.js (vendored file) |
| Tests | pytest, respx (mock GitHub in tests only), ruff |

Requirements split: `requirements.txt` (app), `requirements-ml.txt` (xgboost, torch, transformers, sentence-transformers), `requirements-dev.txt`. Pin exact versions with `pip freeze` once the install works.

## 3. Folder layout

```
repo-analyzer/
  README.md  .env.example  .gitignore
  requirements.txt  requirements-ml.txt  requirements-dev.txt
  docs/                 PRD.md ARCHITECTURE.md RULES.md DESIGN.md TASK.md
  scripts/              check.sh  check.ps1  scan_forbidden.py  dev.sh
  backend/app/
    main.py             app factory, static mount, headers
    config.py           Settings (pydantic-settings)
    logging_setup.py    JSON logs, secret redaction
    errors.py           AppError, error codes, handlers
    api/v1/             repos.py analyses.py jobs.py quality.py bugs.py security.py
                        health.py docs.py developers.py compare.py assistant.py
                        reports.py models.py settings.py github.py
    schemas/            pydantic request/response models
    services/           analysis_pipeline.py + one file per module
    core/               github_client.py  jobs.py  sandbox.py  subprocess_runner.py  cache.py
    analyzers/          inventory.py  metrics.py  duplication.py  lint_python.py
                        secrets.py  semgrep_runner.py  deps_vulns.py  readme_parser.py
                        developer_stats.py  history.py  semgrep_rules/  scoring.yaml
    ml/                 features.py  registry.py  predict.py  schema.py
    rag/                chunker.py  embedder.py  store.py  llm.py  prompts.py
    recommend/          rules.py
    reports/            charts.py  builder.py
    db/                 models.py  session.py  migrations/
  ml/                   training only, never imported by backend/app
    build_dataset.py  labels.py  sampling.py
    train_bug.py  train_health.py  train_maintenance.py
    train_docs.py  train_clusters.py  train_codebert.py  evaluate.py
    data/               gitignored: raw, processed, manifests
  models/               trained artifacts (see section 9)
  frontend/
    index.html
    css/                tokens.css base.css layout.css components.css pages.css
    js/                 main.js router.js api.js state.js jobs.js
    js/ui/              h.js toast.js table.js charts.js skeleton.js icons.js
    js/pages/           overview.js analyzer.js quality.js bugs.js security.js health.js
                        docs.js developers.js compare.js assistant.js reports.js
                        model-performance.js settings.js
    vendor/             chart.umd.min.js, fonts/
  tests/
```

`ml/` imports feature code from `backend/app/ml/features.py` and `backend/app/analyzers/`. Training and serving must share the same feature code. Never copy it.

## 4. Analysis pipeline

An analysis is one run for one repo at one commit. It runs as a job. Stages write results to the DB as they finish, so pages can load partial results.

| # | Stage | What it does | Writes | If it fails |
|---|---|---|---|---|
| 1 | resolve | Validate name, GET repo, find default branch HEAD SHA, check size limit | `analyses` row | Abort. Error code returned. |
| 2 | metadata | Languages, contributors, releases, issues and PRs (capped), stats endpoints | `results[repository]` | Mark stage failed, continue |
| 3 | clone | Bare shallow clone into `data/work/<analysis_id>/git` | files on disk | Abort |
| 4 | materialize | List tree, filter, copy allowed files into `.../src` (section 7) | files on disk | Abort |
| 5 | metrics | Inventory, Lizard metrics, Radon for Python, duplication | `results[quality_raw]` | Mark failed, continue |
| 6 | lint | Pylint and Bandit on sampled Python files | `results[lint]` | Mark failed, continue |
| 7 | security | Secrets scan, Semgrep (if enabled), OSV dependency check | `results[security]` | Mark failed, continue |
| 8 | history | `git log --numstat` features per file and per repo | `results[history]` | Mark failed, skip stage 9 models that need it |
| 9 | predict | bug_risk, maintenance_effort, repo_health, repo_clusters | `results[bugs]`, `[health]`, `[quality]` | Per-model: `MODEL_NOT_TRAINED` is stored, not hidden |
| 10 | docs | README parse, section classifier, score | `results[docs]` | Mark failed, continue |
| 11 | developers | Contributor and activity analytics | `results[developers]` | Mark failed, continue |
| 12 | recommend | Rule engine over results 5 to 11 | `results[recommendations]` | Mark failed, continue |
| 13 | cleanup | Delete the work directory | none | Runs in `finally`, always |

Quality score (module `quality`) is computed after stages 5, 6, 9 from `scoring.yaml`.

The RAG index is built after stage 12 and before stage 13, because it needs the source copy. It is controlled by `ENABLE_ASSISTANT_INDEX` (default true). Chunks, with their text and embeddings, are stored in `rag_chunks`, so the assistant works after the work directory is deleted. Only files under the size caps are indexed.

Caching: an analysis is reused when `(repo full name, head_sha, analyzer_version)` matches. A new commit gives a new analysis.

## 5. Data model

| Table | Columns (main ones) |
|---|---|
| `repositories` | id, full_name (unique), created_at |
| `analyses` | id, repository_id, head_sha, default_branch, analyzer_version, status, created_at, finished_at |
| `stage_runs` | id, analysis_id, stage, status, error_code, error_message, started_at, finished_at |
| `results` | id, analysis_id, module, payload (JSON), model_versions (JSON), created_at. Unique on (analysis_id, module). |
| `jobs` | id, type, status (queued, running, succeeded, failed, cancelled), progress (0 to 100), stage, error_code, error_message, payload (JSON), created_at, updated_at |
| `github_cache` | url, etag, body, fetched_at |
| `rag_chunks` | id, analysis_id, path, start_line, end_line, text, embedding (float32 blob) |
| `reports` | id, analysis_id, file_path, created_at |
| `comparisons` | id, analysis_ids (JSON), result (JSON), created_at |
| `settings` | key, value |

Result modules: `repository`, `quality_raw`, `quality`, `lint`, `security`, `history`, `bugs`, `health`, `docs`, `developers`, `recommendations`.

## 6. API

Base path `/api/v1`. Same origin as the frontend, so no CORS.

| Method and path | Purpose |
|---|---|
| `GET /healthz` | Liveness |
| `POST /analyses` | Body `{repo}`. Returns 202 `{analysis_id, job_id}`. Returns the cached analysis if one matches. |
| `GET /analyses` | Recent analyses |
| `GET /analyses/{id}` | Summary for Overview: status, stage statuses, headline numbers |
| `GET /analyses/{id}/repository` | F1 data |
| `GET /analyses/{id}/quality` | F2 data |
| `GET /analyses/{id}/bugs` | F3 data |
| `GET /analyses/{id}/security` | F4 data |
| `GET /analyses/{id}/health` | F5 data |
| `GET /analyses/{id}/docs` | F6 data |
| `GET /analyses/{id}/developers` | F7 data |
| `GET /analyses/{id}/recommendations` | F10 data |
| `POST /analyses/{id}/assistant/query` | Body `{mode, question, file_path?}`. Modes: `explain_file`, `find_bugs`, `summarize_architecture`, `suggest_improvements`, `ask` |
| `POST /compare` | Body `{analysis_ids: [2..4]}`. Returns the comparison |
| `POST /analyses/{id}/reports` | Starts report job |
| `GET /reports/{id}/download` | PDF file |
| `GET /jobs/{id}` | Status, progress, stage, error |
| `GET /models` | List models with current version and headline metrics |
| `GET /models/{name}` | Full `metrics.json`, model card text |
| `GET /github/rate-limit` | Remaining calls, reset time |
| `GET /settings`, `PUT /settings` | Non-secret settings only |

Success envelope:

```json
{ "data": {}, "meta": { "analysis_id": 0, "head_sha": "", "analyzer_version": "", "model_versions": {}, "generated_at": "" } }
```

Error envelope:

```json
{ "error": { "code": "REPO_NOT_FOUND", "message": "Plain sentence.", "details": {}, "request_id": "" } }
```

Error codes: `INVALID_REPO_NAME`, `REPO_NOT_FOUND`, `REPO_TOO_LARGE`, `GITHUB_RATE_LIMITED` (details.retry_after), `GITHUB_AUTH_FAILED`, `ANALYSIS_NOT_READY`, `STAGE_FAILED`, `MODEL_NOT_TRAINED`, `UNSUPPORTED_LANGUAGE`, `LLM_NOT_CONFIGURED`, `NOT_FOUND`, `VALIDATION_ERROR`, `INTERNAL`.

HTTP mapping: 400 validation, 404 not found, 409 not ready, 429 rate limited, 503 model not trained or LLM not configured, 500 internal.

## 7. Untrusted content: sandbox design

Everything from the analyzed repo is hostile input.

Clone (core/sandbox.py):

```
git clone --bare --single-branch --no-tags --shallow-since=<date> \
    --no-recurse-submodules https://github.com/<owner>/<name>.git <work>/git
```

- Run through `subprocess_runner` (described below under "Tool runs"). Env: `GIT_TERMINAL_PROMPT=0`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL` set to an empty file.
- Private-repo token goes through `GIT_CONFIG_COUNT/KEY/VALUE` env vars (extra header). Never in argv. Never logged.
- A bare clone has no working tree and copies no hooks.
- Before cloning, check `size` from the GitHub API against `MAX_REPO_SIZE_MB`.
- `<date>` is `HISTORY_MONTHS` back from now (default 12). For training, see section 9.6.

Materialize (we write the files ourselves, nothing is extracted by a tool):

1. `git ls-tree -r -z -l <sha>` gives mode, type, size, path.
2. Skip: symlinks (mode 120000), submodules (160000), files over `MAX_FILE_KB`, paths in ignored dirs (node_modules, vendor, dist, build, .git, venv, __pycache__, third_party), minified files, binaries (NUL byte in first 8 KB).
3. Always copy dependency manifests (small, parsed as data, never run).
4. Stop at `MAX_FILES`. Record `truncated: true` in results.
5. Read contents with `git cat-file --batch`. Write to `<work>/src/<safe_path>`.
6. `safe_path`: reject absolute paths, drive letters, `..` segments, NUL, Windows reserved names. After joining, resolve and confirm it is inside `<work>/src`. Handle case-insensitive collisions by skipping the second file.

Tool runs (core/subprocess_runner.py): one function, `run_tool(argv, timeout, cwd, env)`.

- `shell=False` always. Argv is a list of fixed strings plus validated paths.
- `cwd` is the work parent, never inside the repo copy.
- Environment is built from scratch (PATH, HOME set to a temp dir). No inherited secrets.
- Timeout on every call. Output size cap.
- On Linux and macOS, set CPU and memory limits with `resource.setrlimit`.
- Only tools in `ALLOWED_TOOLS = {git, pylint, bandit, semgrep}`.

Tool configuration. The repo may ship its own config. Ignore it.

| Tool | Rule |
|---|---|
| Pylint | `--rcfile=<ours>`, `--persistent=n`, no `--load-plugins`, no `--init-hook`. A repo `pylintrc` can run code, so never pass the repo as cwd. |
| Bandit | `-c <ours>`. No `--ini`. |
| Semgrep | `--config <our rules dir>` only. `--metrics off`, `--disable-version-check`. Never `--config auto`. |
| Radon, Lizard | Used as libraries on file text. They do not import or run the code. |

Optional hardening (Phase 9): run tool stages in a Docker container with `--network none`, read-only mount of `src`.

Outbound requests: one helper checks the host against the allowlist before any request. Redirects are followed only to allowlisted hosts.

## 8. GitHub client (core/github_client.py)

- One shared `httpx.AsyncClient`. Token from `GITHUB_TOKEN`. Header `X-GitHub-Api-Version` set.
- ETag cache: store ETag and body in `github_cache`. Send `If-None-Match`. A 304 does not count against the rate limit.
- Rate limit: read `X-RateLimit-Remaining` and `X-RateLimit-Reset` on every response. If remaining is under 10, wait or raise `GITHUB_RATE_LIMITED`. On 403/429 with `Retry-After`, back off and retry (max 3). Expose through `/github/rate-limit`.
- Stats endpoints may return 202 while GitHub computes. Retry with backoff up to 3 times, then store `{"available": false}`. They may also be empty for very large repos.
- Pagination: follow `Link` headers, with a page cap per endpoint.
- Concurrency: at most 5 requests in flight.

Endpoints used:

| Need | Endpoint |
|---|---|
| Repo info, size, default branch | `GET /repos/{o}/{r}` |
| Languages | `GET /repos/{o}/{r}/languages` |
| HEAD SHA | `GET /repos/{o}/{r}/commits/{branch}` |
| Contributors | `GET /repos/{o}/{r}/contributors` (capped), `GET /stats/contributors` |
| Commit rhythm | `GET /stats/commit_activity`, `/stats/punch_card`, `/stats/participation` |
| Issues | `GET /repos/{o}/{r}/issues?state=all` (PRs appear here too, filter them out) |
| Pull requests | `GET /repos/{o}/{r}/pulls?state=all` |
| Releases | `GET /repos/{o}/{r}/releases` |
| Rate limit | `GET /rate_limit` |

Issues and PRs are capped at the most recent 500 each (configurable). Say so in the UI when a cap was hit.

## 9. ML system

### 9.1 Training and serving are separate

- `ml/` trains. `backend/app/ml/` only loads and predicts.
- Feature code lives in one place: `backend/app/ml/features.py` and `backend/app/analyzers/history.py`.
- `metrics.json` is written only by training scripts. The server never writes or edits it.

### 9.2 Artifact layout

```
models/<model_name>/<version>/
  model.joblib             sklearn Pipeline (preprocessing + estimator)
  feature_schema.json      ordered feature names and dtypes
  metrics.json             all metrics, baselines, confusion matrix, curve points
  model_card.md            data, labels, limits, known biases
  training_manifest.json   repo list hash, cutoff date, seed, library versions, git sha
  thresholds.json          bug_risk only: Low/Medium/High cut points
models/<model_name>/CURRENT   text file with the current version name
models/corpus_reference/<version>/stats.json   percentiles for quality metrics
```

Use a `CURRENT` text file, not a symlink (symlinks are unreliable on Windows). At load time, check the live feature list against `feature_schema.json`. Mismatch raises an error. No silent reordering.

### 9.3 Models

| Name | Task | Algorithm | Unit | Label | Main metric | Baselines |
|---|---|---|---|---|---|---|
| `bug_risk` | Bug-prone file | RandomForest, XGBoost, LogisticRegression, linear SVM (calibrated). Best on validation PR-AUC is served. All four are kept in metrics. | file | File touched by a bug-fix commit in the 6 months after cutoff | PR-AUC, ROC-AUC, Precision, Recall, F1 | Prior rate. "Most-changed files" heuristic. |
| `repo_health` | 4-class | XGBoost (LogisticRegression as a comparison) | repo | Rule on activity in the 6 months after cutoff (9.5) | Macro F1 | Majority class. Persistence (label from the past window). |
| `maintenance_effort` | Regression | RandomForestRegressor | file | `log1p(lines added + deleted in next 6 months)` | MAE, RMSE, R2 | Mean predictor |
| `doc_sections` | Text classes | TF-IDF + MultinomialNB | README section body text | Weak label from heading text | Macro F1, Accuracy | Majority class |
| `repo_clusters` | Unsupervised | StandardScaler, KMeans (k by silhouette, 3 to 10), PCA (2 components for plots) | repo | none | Silhouette, Davies-Bouldin, PCA explained variance | none |
| `code_vuln` (optional) | Vulnerable function | CodeBERT fine-tuned | C/C++ function | Devign label | Accuracy, F1, ROC-AUC | Majority class |

SVM note: RBF SVC with probabilities is slow above about 20,000 rows. Use LinearSVC wrapped in CalibratedClassifierCV, or subsample. Say which in the model card.

### 9.4 Features

File-level (bug_risk, maintenance_effort):

- Static, language-agnostic from Lizard: `loc, nloc, n_functions, ccn_max, ccn_mean, ccn_p90, token_count, params_max`.
- History in the 12 months before cutoff: `commits_12m, authors_12m, lines_added_12m, lines_deleted_12m, churn_ratio, days_since_last_change, bugfix_commits_12m, age_days_capped` (capped at the window, because history before the window is not cloned).
- Context: `is_test, language` (top N languages one-hot, rest as `other`).

Repo-level (repo_health, repo_clusters), all reconstructable as of the cutoff date:

- Commits per month: mean, slope, last-3-months over prior-9-months ratio.
- Distinct authors, new authors in last 3 months, days since last commit.
- PRs opened and merged in 12 months, median PR merge time.
- Issues opened and closed in 12 months, close ratio, median close time.
- Releases in 12 months, days since last release.
- Repo age at cutoff, bus factor, main language.
- NOT used: stars, forks, watchers, open issue count. GitHub only gives today's value.

### 9.5 Labels (ml/labels.py)

Bug-fix commit: not a merge, message matches `fix|bug|defect|patch|crash|error|regression|leak|overflow|CVE` (case-insensitive word match) and does not match `typo|docs?|readme|ci`. A file is positive if a bug-fix commit touches it in the label window. This is noisy. Say so in the model card.

Repo health. Let `r_past` be commits per month in the 12 months before cutoff. Let `r_fut` be commits per month in the 6 months after.

| Class | Rule |
|---|---|
| Inactive | `r_fut == 0` |
| Declining | `0 < r_fut < 0.5 * r_past` |
| Healthy | `r_fut >= 0.5 * r_past` and `r_fut >= 4` and at least 2 distinct authors in the future window |
| Moderately Active | everything else |

These thresholds are starting values. Set them once, write them in the model card, freeze them before training. Never change them to raise a score.

### 9.6 Dataset build

- `ml/build_dataset.py` samples repos, clones, extracts features as of cutoff `T`, extracts labels from `T` to `T + 6 months`, deletes the clone. It is resumable (skips repos already in the manifest).
- `T` is today minus 7 months, so the whole label window has happened.
- Clone with `--shallow-since = T - 12 months`. Compute static metrics on the tree at the last commit before `T`, not at HEAD. Using HEAD leaks the future.
- Sampling is stratified by language and by activity level. The sampler uses search queries, so repos that were deleted or hidden are missing. State this survivorship bias in every model card.
- Training repos are capped at `TRAIN_MAX_REPO_MB` (default 150).
- The dataset contains numbers only. No source code is stored.
- Default size: 400 repos for health and clusters, a subset with enough history for file-level models.

### 9.7 Evaluation protocol

1. Split by repo, never by file or row. Held-out test set: 20% of repos, set aside first, touched once at the end.
2. Cross-validation: `GroupKFold` on the other 80%, grouped by repo.
3. Hyperparameter search (`RandomizedSearchCV`) runs inside training folds only.
4. Preprocessing lives inside the sklearn Pipeline so it is fit on training folds only.
5. Imbalance: class weights or `scale_pos_weight`. Report PR-AUC.
6. Every model reports its baselines next to its own numbers.
7. Fixed seeds. The seed is in the manifest.
8. Risk tiers for bug_risk: cut points are chosen on validation data and saved in `thresholds.json`. The UI always shows the probability next to the tier.
9. Calibrate probabilities (`CalibratedClassifierCV`) when the served model is not already calibrated.

### 9.8 Serving

- `registry.py` loads models once at startup and caches them. A missing model gives `MODEL_NOT_TRAINED` at call time, not a crash at startup.
- Every prediction response includes the model name, version, and the probability. Not just the label.
- `repo_clusters` returns cluster id, PCA coordinates, and the nearest corpus repos (names only).

## 10. Code quality score (rule-based, not ML)

Formula and weights live in `analyzers/scoring.yaml`. Components, each scaled 0 to 100:

1. Complexity: share of functions with CCN over 10, lower is better.
2. Maintainability: Radon MI for Python files. Lizard-based proxy for other languages. Label the proxy as a proxy.
3. Duplication: percent of duplicated lines. Detector hashes normalized 6-line windows.
4. Lint density: Pylint and Bandit messages per 1,000 lines (Python only; skipped for others and the weight is redistributed).
5. Tests: ratio of test files to source files.
6. File size outliers: share of files over 1,000 lines.

The UI shows each component, the weights, and the percentile against `corpus_reference`. Tech debt estimate: fixed minutes per issue type from the YAML file, summed. Label it "estimate from fixed rules, not measured".

## 11. RAG assistant

- Chunking: by function ranges from Lizard when available, else 60-line windows with 10 lines overlap. Skip files over 200 KB.
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2`, local, CPU. Stored in `rag_chunks`. Search is brute-force cosine with numpy. That is fine up to about 50,000 chunks. No vector DB.
- Retrieval: top 8 chunks plus the file asked about, plus a structure digest (tree summary, languages, entry points, most-imported modules).
- LLM providers: `llm.py` defines `LLMProvider.generate(system, messages, max_tokens)`. Implementations are chosen by `LLM_PROVIDER`. With no provider, the endpoint returns retrieved chunks only and a note.
- Prompt: repo text is placed inside clearly fenced blocks. System prompt says the blocks are data, not instructions. The model has no tools.
- Citations: the model must cite as `[path:start-end]`. The server checks each citation against retrieved chunks. Invalid ones are removed and the answer is flagged.
- Bug suggestions from the LLM are labeled "AI suggestion, not verified". Static analysis findings for the same file are included in context.
- Output is rendered as text in the UI, never as HTML.

## 12. Reports

- Charts: matplotlib, same data as the screen, colors from DESIGN.md.
- PDF: ReportLab. Every string from the repo (names, README text, commit messages) goes through `xml.sax.saxutils.escape` before it enters a `Paragraph`, because Paragraph parses markup.
- Sections: cover, summary, repository, quality, bug prediction, security, health, documentation, developers, recommendations, appendix (model versions, metrics, limits, head SHA, analyzer version, date).
- Stored in `data/reports/`, listed in `reports` table.

## 13. Jobs

- Jobs run in a process pool for CPU stages and asyncio for I/O. `MAX_CONCURRENT_ANALYSES` default 2.
- Job row holds progress and current stage. The frontend polls `GET /jobs/{id}` every 1.5 seconds.
- On startup, any job still `running` is set to `failed` with `SERVER_RESTARTED`.
- Cancel: set status `cancelled`, the pipeline checks between stages.

## 14. Frontend architecture

- No framework, no bundler. ES modules loaded from `index.html`.
- Hash router: `#/overview`, `#/analyzer`, `#/quality`, `#/bugs`, `#/security`, `#/health`, `#/docs`, `#/developers`, `#/compare`, `#/assistant`, `#/reports`, `#/models`, `#/settings`. The active analysis id is stored in `state.js` and in the URL query (`?a=12`).
- Page contract: `export default { title, async mount(ctx), unmount() }`. `unmount` destroys charts and listeners.
- All HTTP goes through `api.js`: adds the envelope handling, throws typed errors, supports abort.
- DOM building uses `h(tag, props, ...children)` from `ui/h.js`. It sets text with `textContent`. Never `innerHTML` with API data.
- Every page implements four states: loading (skeleton), empty, error (with retry), and loaded. A failed stage shows a partial-result banner.
- Chart.js is wrapped in `ui/charts.js` to apply global defaults and to destroy charts on route change.

## 15. Configuration (.env)

| Variable | Default | Meaning |
|---|---|---|
| `GITHUB_TOKEN` | none | Token for API calls |
| `DATABASE_URL` | `sqlite:///./data/app.db` | DB |
| `DATA_DIR`, `MODELS_DIR` | `./data`, `./models` | Paths |
| `CACHE_TTL_SECONDS` | 3600 | GitHub response cache |
| `MAX_REPO_SIZE_MB` | 300 | Reject larger repos |
| `MAX_FILES`, `MAX_FILE_KB` | 3000, 500 | Analysis limits |
| `HISTORY_MONTHS` | 12 | Clone window |
| `MAX_CONCURRENT_ANALYSES` | 2 | Parallel jobs |
| `ENABLE_SEMGREP` | false | Turn on Semgrep |
| `ENABLE_CODEBERT` | false | Turn on code_vuln |
| `ENABLE_ASSISTANT_INDEX` | true | Build the RAG index during analysis |
| `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL` | none | Assistant |
| `EMBEDDING_MODEL` | all-MiniLM-L6-v2 | Embeddings |
| `TRAIN_MAX_REPO_MB` | 150 | Training clone cap |
| `LOG_LEVEL` | INFO | Logs |

Secrets live only in `.env`. `.env` is in `.gitignore`. `/settings` never returns secrets, only whether each one is set.

## 16. Logging

JSON lines. Fields: time, level, request_id, analysis_id, stage, message. A redaction filter removes anything that looks like a token or key. One request id per request, returned in the error envelope.

## 17. Testing

| Area | Tests |
|---|---|
| GitHub client | respx mocks: ETag 304, rate limit, 202 retry, pagination cap, host allowlist |
| Sandbox | `..` paths, absolute paths, symlink entries, size caps, case collisions, repo-supplied `pylintrc` ignored |
| Analyzers | Tiny fixture repos with known answers |
| Features | As-of invariance: features computed for cutoff T must not change when later commits are added to the history |
| Labels | Hand-made commit lists with known labels |
| API | TestClient: envelope shape, every error code path |
| Security | Secret masking, name regex, XSS strings in repo names and README, PDF escaping |
| Forbidden patterns | `scripts/scan_forbidden.py`: `random`, `np.random`, `faker`, `Lorem`, hardcoded metric numbers in `backend/app` |
| Frontend | Manual checklist in TASK.md Phase 9. Optional Playwright smoke test. |

Fixtures and mocks live under `tests/` only.

## 18. Running

- Dev: `uvicorn backend.app.main:app --reload`, then open `http://localhost:8000`.
- Windows: use WSL2 if you want Semgrep. Everything else runs natively.
- Optional: `Dockerfile` and `docker-compose.yml` in Phase 9.
