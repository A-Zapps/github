/**
 * Overview dashboard page (F1, F10): Quick analyze card, active analysis summary,
 * top 5 evidence-backed recommendations panel, and recent analyses table.
 */

import { api } from "../api.js";
import { state, subscribe } from "../state.js";
import { h } from "../ui/h.js";
import { icons } from "../ui/icons.js";

function getPriorityBadge(priority) {
  const p = (priority || "LOW").toUpperCase();
  switch (p) {
    case "CRITICAL":
      return h("span", { className: "badge badge-danger", style: { fontWeight: "var(--font-bold)" } }, "CRITICAL");
    case "HIGH":
      return h("span", { className: "badge badge-danger" }, "HIGH");
    case "MEDIUM":
      return h("span", { className: "badge badge-warning" }, "MEDIUM");
    default:
      return h("span", { className: "badge badge-neutral" }, "LOW");
  }
}

export default {
  title: "Overview",

  async mount(ctx) {
    this.container = ctx.container;
    this.showAllRecs = false;
    this.render();
    await this.loadData();
    this.unsubscribe = subscribe(() => this.loadData());
  },

  unmount() {
    if (typeof this.unsubscribe === "function") {
      this.unsubscribe();
    }
  },

  render() {
    this.container.textContent = "";

    // 1. Quick Analyze Box
    const input = h("input", {
      type: "text",
      placeholder: "Analyze a repository (e.g. pallets/flask or https://github.com/...)",
      className: "input",
      style: { flex: "1" },
    });
    const analyzeBtn = h("button", { className: "btn btn-primary" }, "Analyze");

    analyzeBtn.addEventListener("click", () => {
      const val = input.value.trim();
      if (!val) return;
      window.location.hash = "#/analyzer";
      setTimeout(() => {
        const targetInput = document.querySelector("#content input[type='text']");
        if (targetInput) {
          targetInput.value = val;
          const targetBtn = document.querySelector("#content button.btn-primary");
          if (targetBtn) targetBtn.click();
        }
      }, 100);
    });

    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") analyzeBtn.click();
    });

    const analyzeCard = h("div", { className: "card", style: { marginBottom: "var(--space-6)" } },
      h("h3", { style: { fontSize: "var(--text-lg)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-1)" } }, "Analyze a GitHub Repository"),
      h("p", { className: "text-muted", style: { fontSize: "var(--text-sm)", marginBottom: "var(--space-3)" } },
        "Inspect code quality, security vulnerabilities, machine-learning bug risks, repository lifecycle health, and actionable recommendations."
      ),
      h("div", { style: { display: "flex", gap: "var(--space-2)" } }, input, analyzeBtn)
    );

    // 2. Active Analysis Overview Grid Placeholder
    this.activeGrid = h("div", { className: "grid grid-4", style: { gap: "var(--space-4)", marginBottom: "var(--space-6)" } });

    // 3. Top 5 Recommendations Container
    this.recsContainer = h("div", { style: { marginBottom: "var(--space-6)" } });

    // 4. Recent Analyses Container
    this.recentCard = h("div", { className: "card", style: { padding: "0", overflow: "hidden" } },
      h("div", { style: { padding: "var(--space-4)", borderBottom: "1px solid var(--color-border)" } },
        h("h3", { style: { fontSize: "var(--text-md)", fontWeight: "var(--font-semibold)" } }, "Recent Analyses")
      ),
      h("div", { id: "recent-table-wrapper" },
        h("p", { className: "text-muted", style: { padding: "var(--space-4)", fontSize: "var(--text-xs)" } }, "Loading recent evaluations...")
      )
    );

    this.container.appendChild(analyzeCard);
    this.container.appendChild(this.activeGrid);
    this.container.appendChild(this.recsContainer);
    this.container.appendChild(this.recentCard);
  },

  async loadData() {
    await Promise.all([
      this.loadActiveMetrics(),
      this.loadRecommendations(),
      this.loadRecentAnalyses(),
    ]);
  },

  async loadActiveMetrics() {
    const analysisId = state.activeAnalysisId || state.currentAnalysisId;
    this.activeGrid.textContent = "";

    if (!analysisId) {
      const cards = [
        { label: "Code Quality", val: "--", sub: "Analyze a repo", route: "#/quality" },
        { label: "Bug Risk Tiers", val: "--", sub: "Analyze a repo", route: "#/bugs" },
        { label: "Security Findings", val: "--", sub: "Analyze a repo", route: "#/security" },
        { label: "Repository Health", val: "--", sub: "Analyze a repo", route: "#/health" },
      ].map((item) =>
        h("div", { className: "card", style: { padding: "var(--space-4)" } },
          h("div", { className: "text-muted", style: { fontSize: "10px", textTransform: "uppercase" } }, item.label),
          h("div", { style: { fontSize: "var(--text-2xl)", fontWeight: "var(--font-bold)", marginTop: "4px" } }, item.val),
          h("div", { className: "text-muted", style: { fontSize: "10px", marginTop: "2px" } }, item.sub)
        )
      );
      this.activeGrid.append(...cards);
      return;
    }

    try {
      const [qRes, bRes, sRes, hRes] = await Promise.allSettled([
        api.getQualityData(analysisId),
        api.getBugsData(analysisId),
        api.getSecurityData(analysisId),
        api.getHealthData(analysisId),
      ]);

      const qData = qRes.status === "fulfilled" ? qRes.value.data : null;
      const bData = bRes.status === "fulfilled" ? bRes.value.data : null;
      const sData = sRes.status === "fulfilled" ? sRes.value.data : null;
      const hData = hRes.status === "fulfilled" ? hRes.value.data : null;

      // Status banner if active analysis is failed
      const existingFail = this.container.querySelector(".analysis-failed-banner");
      if (existingFail) existingFail.remove();

      if (!qData && !bData && !sData && !hData) {
        try {
          const sumRes = await api.getAnalysisSummary(analysisId);
          if (sumRes && sumRes.data && sumRes.data.status === "failed") {
            const failBanner = h("div", {
              className: "badge badge-danger analysis-failed-banner",
              style: {
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "var(--space-3) var(--space-4)",
                marginBottom: "var(--space-4)",
                borderRadius: "var(--radius-md)",
                fontSize: "var(--text-sm)",
                width: "100%",
              }
            },
              h("span", {}, `Notice: Analysis #${analysisId} (${sumRes.data.repo}) failed. Evaluation metrics are unavailable.`),
              h("div", { style: { display: "flex", gap: "var(--space-2)" } },
                h("a", { href: "#/analyzer", className: "btn btn-secondary", style: { fontSize: "var(--text-xs)" } }, "View in Analyzer"),
                h("button", {
                  className: "btn btn-secondary",
                  style: { fontSize: "var(--text-xs)" },
                  onClick: async () => {
                    const rec = await api.getRecentAnalyses(5);
                    const compl = (rec.data || []).find((a) => a.status === "completed");
                    if (compl) {
                      state.setAnalysis(compl.id, compl.repo, compl.head_sha);
                    }
                  }
                }, "Switch to Completed")
              )
            );
            this.container.insertBefore(failBanner, this.activeGrid);
          }
        } catch (e) {}
      }

      // Truncation banner for large repositories (T9.1)
      const existingTrunc = this.container.querySelector(".truncation-banner");
      if (existingTrunc) existingTrunc.remove();
      if (qData && qData.truncated) {
        const truncBanner = h("div", {
          className: "badge badge-warning truncation-banner",
          style: {
            display: "flex",
            alignItems: "center",
            padding: "var(--space-3) var(--space-4)",
            marginBottom: "var(--space-4)",
            borderRadius: "var(--radius-md)",
            fontSize: "var(--text-sm)",
            width: "100%",
          }
        },
        "Notice: Repository exceeds file cap (3,000 files). Analysis was performed on the materialized sample; results are partial."
        );
        this.container.insertBefore(truncBanner, this.activeGrid);
      }

      const cards = [
        h("a", { href: "#/quality", className: "card", style: { padding: "var(--space-4)", textDecoration: "none", color: "inherit" } },
          h("div", { className: "text-muted", style: { fontSize: "10px", textTransform: "uppercase" } }, "Code Quality"),
          h("div", { style: { fontSize: "var(--text-2xl)", fontWeight: "var(--font-bold)", marginTop: "4px", color: "var(--color-primary)" } },
            qData ? `${qData.overall_score}/100` : "--"
          ),
          h("div", { className: "text-muted", style: { fontSize: "10px", marginTop: "2px" } },
            qData ? `Grade ${qData.grade} Rating` : "Pending"
          )
        ),
        h("a", { href: "#/bugs", className: "card", style: { padding: "var(--space-4)", textDecoration: "none", color: "inherit" } },
          h("div", { className: "text-muted", style: { fontSize: "10px", textTransform: "uppercase" } }, "Bug Predictions"),
          h("div", { style: { fontSize: "var(--text-2xl)", fontWeight: "var(--font-bold)", marginTop: "4px", color: bData && bData.summary?.high_risk > 0 ? "var(--color-danger)" : "var(--color-fg-default)" } },
            bData && bData.summary ? `${bData.summary.high_risk} High Risk` : "--"
          ),
          h("div", { className: "text-muted", style: { fontSize: "10px", marginTop: "2px" } },
            bData && bData.summary ? `${bData.summary.total_files} files analyzed` : "Pending"
          )
        ),
        h("a", { href: "#/security", className: "card", style: { padding: "var(--space-4)", textDecoration: "none", color: "inherit" } },
          h("div", { className: "text-muted", style: { fontSize: "10px", textTransform: "uppercase" } }, "Security Analysis"),
          h("div", { style: { fontSize: "var(--text-2xl)", fontWeight: "var(--font-bold)", marginTop: "4px", color: sData && sData.total_issues > 0 ? "var(--color-danger)" : "var(--color-success)" } },
            sData ? `${sData.total_issues} Issues` : "--"
          ),
          h("div", { className: "text-muted", style: { fontSize: "10px", marginTop: "2px" } },
            sData ? `${sData.severity_summary?.HIGH || 0} High / Critical` : "Pending"
          )
        ),
        h("a", { href: "#/health", className: "card", style: { padding: "var(--space-4)", textDecoration: "none", color: "inherit" } },
          h("div", { className: "text-muted", style: { fontSize: "10px", textTransform: "uppercase" } }, "Repository Health"),
          h("div", { style: { fontSize: "var(--text-2xl)", fontWeight: "var(--font-bold)", marginTop: "4px", color: "var(--color-primary)" } },
            hData && hData.health ? hData.health.health_class : "--"
          ),
          h("div", { className: "text-muted", style: { fontSize: "10px", marginTop: "2px" } },
            hData && hData.signals ? `${hData.signals.commits_per_month_mean || 0} commits / mo` : "Pending"
          )
        ),
      ];

      this.activeGrid.append(...cards);
    } catch (e) {
      // Ignore fallback
    }
  },

  async loadRecommendations() {
    const analysisId = state.activeAnalysisId || state.currentAnalysisId;
    this.recsContainer.textContent = "";
    if (!analysisId) return;

    try {
      const resp = await api.getRecommendations(analysisId);
      const recs = resp.data?.recommendations || [];

      if (recs.length === 0) return;

      const topRecs = this.showAllRecs ? recs : recs.slice(0, 5);

      const panel = h("div", { className: "card", style: { padding: "var(--space-5)" } },
        h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-4)" } },
          h("div", null,
            h("h3", { style: { fontSize: "var(--text-md)", fontWeight: "var(--font-semibold)" } }, "Actionable Recommendations"),
            h("p", { className: "text-muted", style: { fontSize: "var(--text-xs)", marginTop: "2px" } },
              `Ranked priority actions with direct evidence from quality, security, and ML models.`
            )
          ),
          h("span", { className: "badge badge-neutral" }, `${recs.length} total`)
        ),
        // List of recommendations
        h("div", { style: { display: "flex", flexDirection: "column", gap: "var(--space-3)" } },
          topRecs.map((r) => {
            const ev = r.evidence || {};
            const evString = ev.file
              ? `${ev.file}${ev.line ? `:${ev.line}` : ""}`
              : ev.package
              ? `${ev.package} (${ev.advisory_id || "vulnerability"})`
              : ev.duplication_percentage
              ? `${ev.duplication_percentage}% duplicated`
              : ev.section
              ? `Missing section: ${ev.title}`
              : Object.keys(ev).length > 0
              ? JSON.stringify(ev)
              : "Measured signal";

            return h("div", {
              style: {
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "var(--space-3)",
                backgroundColor: "var(--color-bg-subtle)",
                borderRadius: "var(--radius-md)",
                gap: "var(--space-3)",
              },
            },
              h("div", { style: { flex: "1" } },
                h("div", { style: { display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "4px" } },
                  getPriorityBadge(r.priority),
                  h("span", { style: { fontWeight: "var(--font-semibold)", fontSize: "var(--text-sm)" } }, r.title),
                  h("span", { className: "badge badge-neutral", style: { fontSize: "10px" } }, `Effort: ${r.effort}`)
                ),
                h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", marginBottom: "4px" } }, r.description),
                h("div", { style: { display: "flex", alignItems: "center", gap: "var(--space-2)" } },
                  h("span", { style: { fontSize: "10px", color: "var(--color-fg-muted)", textTransform: "uppercase" } }, "Evidence:"),
                  h("code", { style: { fontSize: "10px", fontFamily: "var(--font-mono)", backgroundColor: "var(--color-bg-canvas)", padding: "1px 4px", borderRadius: "3px" } }, evString)
                )
              ),
              h("a", {
                href: r.target_page,
                className: "btn btn-secondary",
                style: { fontSize: "var(--text-xs)", whiteSpace: "nowrap" },
              }, "View Evidence →")
            );
          })
        ),
        // Toggle view all
        recs.length > 5
          ? h("div", { style: { marginTop: "var(--space-3)", textAlign: "center" } },
              h("button", {
                className: "btn btn-secondary",
                style: { fontSize: "var(--text-xs)" },
                onClick: () => {
                  this.showAllRecs = !this.showAllRecs;
                  this.loadRecommendations();
                },
              }, this.showAllRecs ? "Show Top 5 Only ▲" : `View All ${recs.length} Recommendations ▼`)
            )
          : null
      );

      this.recsContainer.appendChild(panel);
    } catch (e) {
      // Ignore
    }
  },

  async loadRecentAnalyses() {
    const wrapper = this.container.querySelector("#recent-table-wrapper");
    if (!wrapper) return;

    try {
      const res = await api.getRecentAnalyses(10);
      const analyses = res.data || [];

      if (analyses.length === 0) {
        wrapper.replaceChildren(
          h("div", { className: "empty-state", style: { padding: "var(--space-8)" } },
            h("p", { className: "text-muted" }, "No analyses run yet. Submit a repository above to run your first evaluation.")
          )
        );
        return;
      }

      const table = h("table", { className: "table" },
        h("thead", null,
          h("tr", null,
            h("th", null, "Repository"),
            h("th", { style: { width: "120px" } }, "Head SHA"),
            h("th", { style: { width: "120px" } }, "Status"),
            h("th", { style: { width: "140px" } }, "Date"),
            h("th", { style: { width: "100px", textAlign: "right" } }, "Action")
          )
        ),
        h("tbody", null,
          analyses.map((a) => {
            const viewBtn = h("button", { className: "btn btn-secondary", style: { fontSize: "var(--text-xs)" } }, "Inspect");
            viewBtn.addEventListener("click", () => {
              if (state.setAnalysis) state.setAnalysis(a.id, a.repo, a.head_sha);
              if (a.status === "completed") {
                this.loadActiveMetrics();
                this.loadRecommendations();
                window.scrollTo({ top: 0, behavior: "smooth" });
              } else {
                window.location.hash = "#/analyzer";
              }
            });

            return h("tr", null,
              h("td", { style: { fontWeight: "var(--font-semibold)" } }, a.repo),
              h("td", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" } }, a.head_sha ? a.head_sha.slice(0, 7) : "---"),
              h("td", null,
                h("span", { className: `badge ${a.status === "completed" ? "badge-success" : "badge-neutral"}` }, a.status)
              ),
              h("td", { className: "text-muted", style: { fontSize: "var(--text-xs)" } }, a.created_at ? new Date(a.created_at).toLocaleDateString() : "---"),
              h("td", { style: { textAlign: "right" } }, viewBtn)
            );
          })
        )
      );

      wrapper.replaceChildren(table);
    } catch (err) {
      wrapper.replaceChildren(
        h("p", { className: "text-muted", style: { padding: "var(--space-4)" } }, "Failed to load recent analyses.")
      );
    }
  },
};
