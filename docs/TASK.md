# TASK: GitHub Repository Analyzer

Tick a box only when its "Done when" line is true and you ran it.
`[YOU]` means Sai does it. The agent stops and asks.
Time numbers are guesses for agent work. Write the real time next to each phase when it ends.

---

## How to run this with Antigravity

1. Put the five files in repo-analyzer/docs/.
2. Paste the kickoff prompt below.
3. After each phase, check the "You will see" line. If it is not true, do not start the next phase.

Kickoff prompt:

```
Read docs/RULES.md, docs/ARCHITECTURE.md, docs/DESIGN.md, docs/PRD.md, in that order.
Then open docs/TASK.md and do Phase 0 only, one task at a time.
After each task: run scripts/check, tick the box, commit, and tell me what I can now see or run.
Stop at the end of Phase 0 and wait for me.
```

Next-phase prompt:

```
Continue with Phase N from docs/TASK.md. Same rules. Stop at the end of the phase.
```

---

## Phase 0: Foundation (about 1 h)

- [x] T0.1 Create the folder layout from ARCHITECTURE section 3, `.gitignore`, `.env.example`, and the three requirements files. Done when: `pip install -r requirements.txt` works in a fresh venv.
- [x] T0.2 `config.py` (pydantic-settings), JSON logging with secret redaction, `AppError` and the error envelope handlers. Done when: a test shows a token string never appears in a log line, and an unknown route returns the error envelope.
- [x] T0.3 SQLAlchemy models and the first Alembic migration for every table in ARCHITECTURE section 5. Done when: `alembic upgrade head` creates all tables in a new SQLite file.
- [x] T0.4 App factory, `GET /api/v1/healthz`, static mount for `frontend/`, security headers (RULES B9). Done when: `http://localhost:8000` serves the shell and a test checks the four headers.
- [x] T0.5 Frontend shell: `tokens.css` exactly as in DESIGN section 1, layout, collapsible sidebar with the 13 routes, hash router, each page shows an empty state saying "Not built yet". Done when: all 13 links navigate, the sidebar collapses, and the layout works at 375 px.
- [x] T0.6 `scripts/check` (ruff, pytest, `scan_forbidden.py`) and first tests. Done when: it exits 0, and adding `import random` to `backend/app` makes it fail.

You will see: the empty dashboard in the final design, all pages reachable.

## Phase 1: Real GitHub data (about 3 h)

- [x] T1.0 [YOU] Create a GitHub personal access token with read-only public access. Put it in `.env` as `GITHUB_TOKEN`. Done when: `GET /github/rate-limit` (after T1.1) shows a limit of 5,000. Time: 5 min.
- [x] T1.1 `github_client.py`: shared async client, ETag cache, rate-limit handling, 202 retry, pagination caps, host allowlist. Tests with respx. Done when: tests cover 304, 403 with Retry-After, 202 then 200, and a blocked host.
- [x] T1.2 Repo name validation, `POST /analyses`, job runner (process pool, startup cleanup), `GET /jobs/{id}`. Done when: posting `pallets/flask` returns 202 and the job moves from queued to succeeded, and `../etc` returns `INVALID_REPO_NAME`.
- [x] T1.3 Stages 1 and 2 (resolve, metadata): repo info, languages, contributors, releases, capped issues and PRs, stats endpoints. Stored in `results[repository]`. Done when: `GET /analyses/{id}/repository` returns real numbers matching the GitHub page.
- [x] T1.4 `sandbox.py`: bare shallow clone and materialize (ARCHITECTURE section 7), plus `subprocess_runner.py`. Tests: `..` path, absolute path, symlink, oversize file, case collision, cleanup after failure. Done when: all those tests pass and a run leaves no work directory behind.
- [x] T1.5 Repository Analyzer page: input, stage stepper, results (stats row, languages donut, commits per week bar, README as plain text, file tree summary). Done when: analyzing `pallets/flask` fills the page with real data, and a bad name shows the error state.
- [x] T1.6 Overview page v1 (analyze box, recent analyses) and Settings page v1 (token set or not, rate limit, cache TTL). Done when: the rate-limit meter in the topbar shows live numbers.

You will see: type `pallets/flask`, watch the stages tick, get real stats and charts.

## Phase 2: Code quality and security (about 4 h)

- [x] T2.1 `inventory.py`: language detection by extension, test-file detection, ignore rules. Done when: a fixture repo gives the expected counts.
- [x] T2.2 `metrics.py`: Lizard for all files, Radon (CC, MI, Halstead) for Python. Done when: results for a fixture file match values worked out by hand.
- [x] T2.3 `duplication.py`: 6-line normalized window hashing. Done when: a fixture with a known copied block reports it and the percent is right.
- [x] T2.4 `lint_python.py`: Pylint and Bandit through `run_tool`, our configs, sampled files, timeouts. Done when: a fixture repo containing a hostile `pylintrc` with an `init-hook` does not execute it (test writes a marker file and asserts it does not exist).
- [x] T2.5 `scoring.yaml` and the quality score, component scores, tech debt estimate. Done when: `GET /analyses/{id}/quality` returns the score, components, weights, and the label "estimate from fixed rules".
- [x] T2.6 Code Quality page (gauge, component bars, histograms, worst files). Done when: all numbers match the API and the chart table toggles work.
- [x] T2.7 `secrets.py`: regex rules plus entropy check, masking. Done when: tests find fixture secrets, never return more than 4 characters, and skip obvious placeholders like `YOUR_KEY_HERE`.
- [x] T2.8 Own Semgrep rules (SQL string building, `innerHTML`, `eval` and `exec`, `shell=True`, pickle and unsafe YAML load, weak hashes) and `semgrep_runner.py`, behind `ENABLE_SEMGREP`. Done when: with Semgrep off the stage reports "skipped: disabled", not an error.
- [x] T2.9 `deps_vulns.py`: parse `requirements*.txt`, `package-lock.json`, `poetry.lock`, `go.mod`, `Cargo.lock`, query OSV batch endpoint. Done when: a fixture with a known-vulnerable pinned version returns an advisory id.
- [x] T2.10 Security page (severity bar, tabs for code, secrets, dependencies). Done when: findings link to file and line, and no secret shows more than 4 characters.

You will see: Code Quality and Security pages with real findings for a real repo.

## Phase 3: Dataset and training (about 5 h agent time, plus unattended dataset build)

- [x] T3.1 `analyzers/history.py` and `ml/features.py`: file and repo features as of a cutoff date. Done when: the as-of invariance test passes (add commits after the cutoff, features do not change).
- [ ] T3.2 `ml/labels.py`: bug-fix commit rule and the repo health rule from ARCHITECTURE 9.5. Done when: unit tests on hand-made commit lists give the expected labels. Thresholds frozen.
- [ ] T3.3 `ml/build_dataset.py` and `sampling.py`: stratified sampler, resumable, per-repo timeout, clone deleted after features are saved, parquet output, manifest. Done when: a 5-repo dry run produces files and the manifest, and killing and restarting skips finished repos.
- [ ] T3.4 [YOU] Run the dataset build for 400 repos. Leave it running. Time: 6 to 12 h unattended (guess, depends on network and rate limit). Done when: the manifest lists at least 300 repos with features and labels.
- [ ] T3.5 `train_bug.py`: RF, XGBoost, LogReg, calibrated linear SVM. GroupKFold, randomized search, held-out repos, baselines, thresholds, artifacts, model card. Done when: `models/bug_risk/<v>/` has all files and `metrics.json` lists all four models plus baselines.
- [ ] T3.6 `train_health.py`: XGBoost and LogReg, baselines (majority, persistence), confusion matrix. Done when: `models/repo_health/<v>/` complete.
- [ ] T3.7 `train_maintenance.py`: RandomForestRegressor, MAE, RMSE, R2, mean baseline. Done when: `models/maintenance_effort/<v>/` complete.
- [ ] T3.8 `train_docs.py`: split READMEs into sections, weak labels from headings, remove headings from the text the model sees, TF-IDF + MultinomialNB. Done when: `models/doc_sections/<v>/` complete.
- [ ] T3.9 `train_clusters.py`: scaler, KMeans (k by silhouette), PCA, plus `corpus_reference/stats.json`. Done when: silhouette and PCA variance are in `metrics.json`.
- [ ] T3.10 `backend/app/ml/registry.py` and `schema.py`: load models, check feature schema, `MODEL_NOT_TRAINED` handling. Done when: deleting a model folder makes the matching endpoint return 503, not crash the server.

You will see: `models/*/CURRENT` and `metrics.json` files, and a printed table of model vs baseline numbers.

If a model does not beat its baseline, keep the result and move on. Report it as it is.

## Phase 4: Predictions in the app (about 3 h)

- [ ] T4.1 Pipeline stages 8 and 9: history features for the repo, then bug_risk, maintenance_effort, repo_health, repo_clusters. Done when: a fresh analysis stores `results[bugs]` and `results[health]` with model versions.
- [ ] T4.2 Endpoints `/bugs`, `/health`, `/models`, `/models/{name}`. Done when: responses include probability, tier, model name and version, and the not-trained case returns the right code.
- [ ] T4.3 Bug Prediction page. Done when: file table sorts and filters, drivers show for each file, and the scatter chart matches the table.
- [ ] T4.4 Repository Health page. Done when: class probabilities sum to 100% and the signals table shows the real inputs.
- [ ] T4.5 Model Performance page: all models, baselines next to metrics, confusion matrices, curves, feature importance, model card link, not-trained cards. Done when: every number traces to a `metrics.json` file.
- [ ] T4.6 Add percentile vs corpus and maintenance effort to the Code Quality page. Done when: the percentile comes from `corpus_reference` and is labeled.

You will see: predictions on a real repo, and an honest Model Performance page.

## Phase 5: Documentation and developers (about 2 h)

- [ ] T5.1 `readme_parser.py`, heading rules, `doc_sections` model, completeness score in `scoring.yaml`. Done when: fixtures with and without install and usage sections score differently and for the right reason.
- [ ] T5.2 `/docs` endpoint and Documentation page. Done when: missing sections show as missing with a suggestion.
- [ ] T5.3 `developer_stats.py`: contributors, commit rhythm, bus factor, PR merge time, issue close time. Done when: fixture history gives hand-checked values, and unavailable stats are marked `available: false`.
- [ ] T5.4 `/developers` endpoint and Developer Analytics page (bar, heatmap, histograms). Done when: the heatmap totals equal the commit count used.

You will see: Documentation and Developer Analytics pages with real data.

## Phase 6: Recommendations and comparison (about 2 h)

- [ ] T6.1 `recommend/rules.py`: each rule has an id, a condition on results, priority, effort, and evidence (file and line or metric). Tests per rule. Done when: no recommendation appears without evidence.
- [ ] T6.2 `/recommendations` endpoint and Overview panel (top 5, link to the rest). Done when: each item links to the page that shows its evidence.
- [ ] T6.3 `POST /compare` for 2 to 4 analyses, normalization, best-per-metric. Done when: comparing the same analysis twice is rejected.
- [ ] T6.4 Repository Comparison page: metric table, radar, PCA scatter with corpus points. Done when: the radar values match the table.

You will see: a ranked action list and a side-by-side comparison.

## Phase 7: AI assistant (about 3 h)

- [ ] T7.1 `chunker.py`, `embedder.py`, `store.py`: function-aware chunks, local embeddings, numpy search. Done when: asking for a known function returns its chunk first.
- [ ] T7.2 `llm.py` provider interface, one provider implemented (the one Sai names in Q1), `prompts.py` with fenced untrusted blocks. Done when: with no key set, the endpoint returns retrieved chunks and `LLM_NOT_CONFIGURED` in the note.
- [ ] T7.3 `/assistant/query` with the five modes and citation validation. Done when: a test with a fake provider that cites a non-existent file gets that citation removed and the answer flagged.
- [ ] T7.4 AI Assistant page: modes, file picker, thread, citation chips, code panel, warning banner. Done when: output renders as text only (test with `<img onerror>` in a fixture file).

You will see: ask about a file and get an answer with working citations.

## Phase 8: Reports (about 2 h)

- [ ] T8.1 `charts.py` (matplotlib, DESIGN palette). Done when: each chart uses the same data as the API.
- [ ] T8.2 `builder.py` (ReportLab): all sections plus appendix with head SHA, versions, date, limits. Done when: a test with `<b>` and `&` in a repo-derived string produces a valid PDF.
- [ ] T8.3 Report job, download endpoint, Reports page. Done when: the downloaded PDF opens and numbers match the screen.

You will see: a PDF you can send to someone.

## Phase 9: Hardening and release (about 3 h)

- [ ] T9.1 Large repo run: limits hit, `truncated` shown in UI, partial results, no crash. Done when: a repo above `MAX_FILES` finishes with a visible banner.
- [ ] T9.2 Rate limit run with low remaining calls. Done when: the UI shows when it can retry.
- [ ] T9.3 Security test pass: every item in ARCHITECTURE section 17 "Sandbox" and "Security" rows has a test and passes. Done when: `scripts/check` runs them all.
- [ ] T9.4 Responsive and keyboard pass at 375, 768, 1280 px. Done when: the checklist in DESIGN section 9 is ticked by hand.
- [ ] T9.5 Measure real run times and put them in the README. Done when: the success criteria 1 numbers are replaced with measured ones.
- [ ] T9.6 README: what it is, requirements (Python, git), install for Windows (WSL2 note), macOS, Linux, `.env` setup, run, train models, run tests, known limits, honest notes on model quality. Done when: a fresh clone follows it and works.
- [ ] T9.7 Optional: `Dockerfile` and `docker-compose.yml`, tool stages in a container with no network. Done when: `docker compose up` serves the app.

You will see: a project you can demo and hand to someone else.

## Phase 10: Optional CodeBERT

- [ ] T10.1 [YOU] Get a GPU (Colab free tier works) and download the Devign defect dataset. Check it is available and check its license first. Time: 30 min.
- [ ] T10.2 `ml/train_codebert.py`: fine-tune, evaluate on the dataset test split, save to `models/code_vuln/`. Done when: `metrics.json` has accuracy, F1, ROC-AUC and the majority baseline. Report whatever it gets.
- [ ] T10.3 Serving for C and C++ functions only, behind `ENABLE_CODEBERT`. Other languages return `UNSUPPORTED_LANGUAGE`. Done when: the Security page shows a "not applicable" badge for non-C files, never a score.

---

## Final checklist

- [ ] All 13 pages load real data and have four states.
- [ ] Every model has `metrics.json`, `model_card.md`, `training_manifest.json`.
- [ ] Model Performance page shows baselines next to every model.
- [ ] No mock data outside `tests/` (scan passes).
- [ ] Security tests pass.
- [ ] PDF matches screen.
- [ ] README works on a fresh clone.

## Time log

| Phase | Guess | Actual |
|---|---|---|
| 0 | 1 h | |
| 1 | 3 h | |
| 2 | 4 h | |
| 3 | 5 h + build | |
| 4 | 3 h | |
| 5 | 2 h | |
| 6 | 2 h | |
| 7 | 3 h | |
| 8 | 2 h | |
| 9 | 3 h | |
| 10 | 4 h + GPU | |
