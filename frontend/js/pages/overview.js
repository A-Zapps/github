/**
 * Overview dashboard page (F1, v1): quick analyze card, high-level metrics, and recent analyses table.
 */

import { api } from "../api.js";
import { state } from "../state.js";
import { h } from "../ui/h.js";
import { icons } from "../ui/icons.js";

export default {
  title: "Overview",

  async mount(ctx) {
    this.container = ctx.container;
    this.render();
    await this.loadRecentAnalyses();
  },

  unmount() {},

  render() {
    this.container.replaceChildren();

    // 1. Quick Analyze Box
    const input = h("input", {
      type: "text",
      placeholder: "Analyze a repository (e.g. pallets/flask or https://github.com/...)",
      className: "btn-secondary",
      style: { flex: "1", padding: "0 12px", height: "36px", borderRadius: "6px" },
    });
    const analyzeBtn = h("button", { className: "btn btn-primary" }, "Analyze");

    analyzeBtn.addEventListener("click", () => {
      const val = input.value.trim();
      if (!val) return;
      window.location.hash = "#/analyzer";
      // Allow analyzer view to receive the input
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

    const analyzeCard = h("div", { className: "card" },
      h("h3", { className: "card-title" }, "Developer Intelligence Platform"),
      h("p", { style: { color: "var(--text-2)", fontSize: "14px" } },
        "Inspect code quality, security vulnerabilities, repository health, and machine-learning bug risks for any public GitHub repository."
      ),
      h("div", { style: { display: "flex", gap: "8px", marginTop: "4px" } }, input, analyzeBtn)
    );

    // 2. Metric Stat Cards
    const statCards = [
      { label: "Code Quality", value: state.currentAnalysisId ? "Evaluating..." : "--", icon: "quality" },
      { label: "Bug Risk Tiers", value: state.currentAnalysisId ? "Evaluating..." : "--", icon: "bugs" },
      { label: "Repository Health", value: state.currentAnalysisId ? "Evaluating..." : "--", icon: "health" },
      { label: "Security Findings", value: state.currentAnalysisId ? "Evaluating..." : "--", icon: "security" },
    ].map((sc) => h("div", { className: "card", style: { padding: "16px" } },
      h("div", { style: { display: "flex", justifyContent: "space-between", color: "var(--text-2)" } },
        h("span", { className: "text-caption" }, sc.label),
        icons[sc.icon](16)
      ),
      h("span", { style: { fontSize: "24px", fontWeight: "600", marginTop: "8px" } }, sc.value)
    ));

    const statsGrid = h("div", {
      style: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px" }
    }, ...statCards);

    // 3. Recent Analyses Container
    this.recentCard = h("div", { className: "card" },
      h("div", { className: "card-header" },
        h("h3", { className: "card-title" }, "Recent Analyses")
      ),
      h("div", { id: "recent-table-wrapper" },
        h("p", { className: "text-caption", style: { padding: "12px 0" } }, "Loading recent analyses...")
      )
    );

    this.container.appendChild(analyzeCard);
    this.container.appendChild(statsGrid);
    this.container.appendChild(this.recentCard);
  },

  async loadRecentAnalyses() {
    const wrapper = this.container.querySelector("#recent-table-wrapper");
    if (!wrapper) return;

    try {
      const res = await api.getRecentAnalyses(10);
      const analyses = res.data || [];

      if (analyses.length === 0) {
        wrapper.replaceChildren(
          h("div", { className: "empty-state", style: { padding: "32px 0" } },
            h("p", { className: "empty-state-desc" }, "No analyses run yet. Submit a repository above to run your first evaluation.")
          )
        );
        return;
      }

      const table = h("table", { style: { width: "100%", fontSize: "13px", borderCollapse: "collapse" } },
        h("thead", {},
          h("tr", { style: { textAlign: "left", color: "var(--text-2)", borderBottom: "1px solid var(--border)" } },
            h("th", { style: { padding: "8px" } }, "Repository"),
            h("th", { style: { padding: "8px" } }, "Head SHA"),
            h("th", { style: { padding: "8px" } }, "Status"),
            h("th", { style: { padding: "8px" } }, "Date"),
            h("th", { style: { padding: "8px", textAlign: "right" } }, "Action")
          )
        ),
        h("tbody", {},
          ...analyses.map((a) => {
            const viewBtn = h("button", { className: "btn btn-secondary btn-sm" }, "View");
            viewBtn.addEventListener("click", () => {
              state.setAnalysis(a.id, a.repo, a.head_sha);
              window.location.hash = "#/analyzer";
            });

            return h("tr", { style: { borderBottom: "1px solid var(--border)" } },
              h("td", { style: { padding: "8px", fontWeight: "500" } }, a.repo),
              h("td", { style: { padding: "8px", fontFamily: "var(--font-mono)" } }, a.head_sha ? a.head_sha.slice(0, 7) : "---"),
              h("td", { style: { padding: "8px" } },
                h("span", { className: `badge ${a.status === "completed" ? "badge-success" : "badge-neutral"}` }, a.status)
              ),
              h("td", { style: { padding: "8px", color: "var(--text-2)" } }, a.created_at ? new Date(a.created_at).toLocaleDateString() : "---"),
              h("td", { style: { padding: "8px", textAlign: "right" } }, viewBtn)
            );
          })
        )
      );

      wrapper.replaceChildren(table);
    } catch (err) {
      wrapper.replaceChildren(
        h("p", { style: { color: "var(--danger)", fontSize: "13px" } }, "Failed to load recent analyses.")
      );
    }
  },
};
