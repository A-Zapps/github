/**
 * Global application state store for active repository and analysis ID.
 */

class AppState {
  constructor() {
    this.currentAnalysisId = null;
    this.currentRepo = null;
    this.currentHeadSha = null;
    this.rateLimit = { remaining: 5000, limit: 5000, reset: 0 };
    this.subscribers = new Set();

    // Restore analysis ID from URL search param if present (?a=12)
    const params = new URLSearchParams(window.location.search);
    const a = params.get("a");
    if (a && !isNaN(Number(a))) {
      this.currentAnalysisId = Number(a);
    }
  }

  get activeAnalysisId() {
    return this.currentAnalysisId;
  }

  set activeAnalysisId(val) {
    this.currentAnalysisId = val;
  }

  get(key) {
    if (key === "analysisId" || key === "activeAnalysisId") return this.currentAnalysisId;
    if (key === "repo" || key === "activeRepo") return this.currentRepo;
    if (key === "headSha" || key === "activeHeadSha") return this.currentHeadSha;
    return this[key] ?? null;
  }

  get activeRepo() {
    return this.currentRepo;
  }

  set activeRepo(val) {
    this.currentRepo = val;
  }

  setAnalysis(analysisId, repo = null, headSha = null) {
    this.currentAnalysisId = analysisId;
    if (repo) this.currentRepo = repo;
    if (headSha) this.currentHeadSha = headSha;

    // Persist to URL search param without reload
    const url = new URL(window.location.href);
    if (analysisId) {
      url.searchParams.set("a", String(analysisId));
    } else {
      url.searchParams.delete("a");
    }
    window.history.replaceState({}, "", url.toString());

    this.notify();
  }

  setRateLimit(remaining, limit, reset = 0) {
    this.rateLimit = { remaining, limit, reset };
    this.notify();
  }

  subscribe(callback) {
    this.subscribers.add(callback);
    return () => this.subscribers.delete(callback);
  }

  notify() {
    for (const cb of this.subscribers) {
      try {
        cb(this);
      } catch (err) {
        console.error("State subscriber error:", err);
      }
    }
  }
}

export const state = new AppState();
export const subscribe = (callback) => state.subscribe(callback);
