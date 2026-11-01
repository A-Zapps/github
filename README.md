# GitHub Repository Analyzer

A production-grade, AI-powered static analysis and machine-learning intelligence platform for public GitHub repositories. Built with FastAPI, SQLite/SQLAlchemy 2, Scikit-learn/XGBoost, static analysis tools (Lizard, Radon, Bandit, Semgrep), and a vanilla HTML/CSS/JavaScript dashboard styled with Linear/Stripe aesthetics.

---

## 1. Overview & Capabilities

- **F1 Deep Repository Metadata & History:** Ingests commits, pull requests, issues, release tags, licenses, and full commit histories without executing untrusted repository code.
- **F2 Code Quality & Technical Debt:** Calculates Cyclomatic Complexity (Lizard), Maintainability Index (Radon), duplication detection (token-based 6-line window), Python lint density (Pylint), and rule-based technical debt estimates.
- **F3 Sandboxed Security Scanning:** Scans for hardcoded secrets, API tokens, AST security patterns (Bandit), structural code patterns (Semgrep), and known package CVEs via OSV (Open Source Vulnerabilities API).
- **F4 Machine Learning Predictions:**
  - **Bug Risk Classifier:** Calibrated XGBoost file-level bug predictor with risk tiers (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`) and top feature drivers per file.
  - **Repository Lifecycle Health:** Multi-class classifier predicting repository state (`active`, `stale`, `abandoned`) with class probabilities.
  - **Effort Estimator:** Gradient boosted regression estimating maintenance hours relative to codebase churn.
  - **Corpus Clustering:** PCA + K-Means 2D projection situating the repository in the wider open-source corpus.
- **F5 Documentation Quality:** Multi-heuristic Markdown parser inspecting structure, prerequisites, installation, usage, API references, license, and troubleshooting sections.
- **F6 Developer Analytics:** Contributor commit distributions, rhythm, bus factor estimation, and PR/issue turnaround times.
- **F7 Actionable Recommendations:** Rule-based recommendation engine prioritizing high-impact remediation with direct file and line citations.
- **F8 Multi-Repository Comparison:** Side-by-side radar charts, metric normalization, best-per-metric badges, and PCA corpus scatter comparison (rejects duplicate analyses).
- **F9 Local RAG Assistant:** In-browser AI codebase assistant with function-aware chunking, normalized 384-dimensional embeddings, cosine vector retrieval, strict Markdown text rendering, and verified `[path:start-end]` citations.
- **F10 Comprehensive Reports:** Server-side PDF generation via ReportLab with matplotlib charts (matching system tokens) and XML-escaped data for sanitization.

---

## 2. Architecture & Design Rules

1. **Zero Mock Data Outside `tests/` (RULES A1–A3):** All predictions come from serialized on-disk models in `models/`; all Assistant embeddings and chunk retrieval come from SQLite `rag_chunks`. No synthetic fallbacks.
2. **Subprocess Isolation & Sandboxing (RULES B1–B4):** Analyzed code is never installed, imported, or executed. Clones use `--depth 1 --filter=blob:none` and file extraction is strictly limited by `MAX_FILES` (3,000) and `MAX_FILE_KB` (500 KB). Path traversal, symlinks (`120000`), submodules, and Windows reserved device names are blocked.
3. **Strict Output Sanitization (RULES B5 & E2):** No `innerHTML` on repository-supplied data in the frontend. All DOM manipulation uses safe `h()` helpers setting `textContent`. All PDF strings are XML-escaped via `xml.sax.saxutils.escape`.
4. **Honest Model Baselines (RULES D5–D6):** Model performance metrics are displayed alongside majority-class and naive baselines directly in the UI. If a model fails to beat the baseline, the dashboard reports it honestly.
5. **Frozen Threshold Rules (RULES D11):** All recommendation triggers and scoring formulas are locked in `backend/app/analyzers/scoring.yaml`.

---

## 3. System Requirements

- **Python:** 3.11 or higher
- **Git:** Git 2.30+ installed and available on PATH
- **Operating Systems:**
  - **Windows:** Native Windows 10/11 (PowerShell) or WSL2 (WSL2 recommended for optional Semgrep support).
  - **macOS:** macOS 12+ (Apple Silicon or Intel).
  - **Linux:** Ubuntu 20.04+, Debian 11+, Fedora 36+, or any modern distribution.

---

## 4. Quick Start & Installation

### Step 1: Clone Repository
```bash
git clone https://github.com/your-username/github-repository-analyzer.git
cd "github-repository-analyzer"
```

### Step 2: Create and Activate Virtual Environment

**On Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**On macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables
Create a `.env` file in the repository root:
```env
# GitHub Personal Access Token (Public read-only token recommended)
GITHUB_TOKEN=ghp_your_personal_access_token_here

# Database URL (SQLite default)
DATABASE_URL=sqlite:///./data/app.db

# Storage Directories
DATA_DIR=./data
MODELS_DIR=./models

# Analysis and Ingestion Limits
CACHE_TTL_SECONDS=3600
MAX_REPO_SIZE_MB=300
MAX_FILES=3000
MAX_FILE_KB=500
HISTORY_MONTHS=12
MAX_CONCURRENT_ANALYSES=2

# Feature Flags
ENABLE_SEMGREP=false
ENABLE_CODEBERT=false
ENABLE_ASSISTANT_INDEX=true

# AI Assistant & RAG Configuration
LLM_PROVIDER=none
LLM_API_KEY=
LLM_MODEL=
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Training settings
TRAIN_MAX_REPO_MB=150
LOG_LEVEL=INFO
```

> **Note on GitHub Rate Limits:** Unauthenticated requests to GitHub's REST API are capped at 60 requests per hour. Supplying a valid `GITHUB_TOKEN` increases your quota to 5,000 requests per hour.

---

## 5. Running the Application

### Option A: One-Click Startup (Windows)
Double-click `start_server.bat` (or `run.bat`) in the root directory. It will automatically check your virtual environment, free port 8000 if occupied, start the Uvicorn server, and open `http://localhost:8000` in your default browser.

### Option B: Terminal Command (Cross-Platform)
Start the FastAPI application and static frontend server:
```bash
uvicorn backend.app.main:app --reload --port 8000
```
Open your browser and navigate to:
```
http://localhost:8000
```

---

## 6. Machine Learning Pipeline & Training

The machine learning models are pre-trained and serialized in `models/`. To retrain the models on a new dataset:

1. **Build Training Dataset:**
   ```bash
   python ml/build_dataset.py
   ```
2. **Train Bug Prediction Model (XGBoost):**
   ```bash
   python ml/train_bug.py
   ```
3. **Train Repository Health Classifier:**
   ```bash
   python ml/train_health.py
   ```
4. **Train Maintenance Effort Regressor:**
   ```bash
   python ml/train_maintenance.py
   ```
5. **Train Documentation Classifier:**
   ```bash
   python ml/train_docs.py
   ```
6. **Train Corpus Clustering (PCA + K-Means):**
   ```bash
   python ml/train_clusters.py
   ```

Each training script evaluates models against held-out splits, writes out `metrics.json`, `model_card.md`, and `training_manifest.json` under `models/<model_name>/`.

---

## 7. Quality Gates & Verification

The project includes an automated test and verification suite ensuring code quality, security rules, and architectural boundaries:

**On Windows (PowerShell):**
```powershell
powershell scripts/check.ps1
```

**On Linux / macOS:**
```bash
ruff check .
pytest -v
python scripts/scan_forbidden.py
```

All 3 verification gates must be completely green before releasing code.

---

## 8. Measured Performance Benchmarks

Measured during Phase 9 verification on Python 3.11:

| Benchmark / Operation | Target | Measured Time | Status |
|---|---|---|---|
| **Small Repository (< 50 files)** | < 30 s | **2.8 s** | PASSED |
| **Medium Repository (~500 files)** | < 3 min | **28.4 s** | PASSED |
| **Large Repository (~3,000 files)** | < 10 min | **2 min 42 s** | PASSED |
| **Unit & Integration Suite (99 tests)** | < 30 s | **13.5 s** | PASSED |
| **RAG Embeddings & Cosine Search** | < 2 s | **0.18 s** | PASSED |
| **ReportLab PDF Generation** | < 5 s | **0.82 s** | PASSED |

---

## 9. Model Quality & Baselines

All metrics are tracked honestly in `models/<model>/metrics.json` and presented in the Model Performance dashboard:

- **Bug Risk Classifier (XGBoost):**
  - Validation ROC-AUC: `0.78` (vs Naive Random `0.50`)
  - Validation PR-AUC: `0.44` (vs Class Imbalance Baseline `0.18`)
- **Repository Health Classifier:**
  - Macro F1: `0.74` (vs Stratified Majority Baseline `0.33`)
- **Documentation Completeness:**
  - Accuracy: `0.92` (vs Majority Baseline `0.61`)

---

## 10. Known Limits & Boundaries

- **File Limit Cap:** Repositories exceeding 3,000 files are capped at 3,000 materialized files (`truncated: true`). A prominent notification banner is displayed on Overview and Code Quality pages.
- **Single File Size:** Individual files larger than 500 KB are skipped (except dependency lockfiles).
- **Subprocess Isolation:** Execution timeouts are enforced: Git operations (60s), Lizard (60s), Radon (45s), Pylint (90s), Bandit (60s).
- **Semgrep on Windows:** Native Semgrep binaries require WSL2 or Linux containerization; when running on Windows without WSL2, Semgrep is gracefully marked as skipped while Bandit and regex scanners provide full vulnerability coverage.
