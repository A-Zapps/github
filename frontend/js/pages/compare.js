/**
 * Repository Comparison Page (F9).
 * Side-by-side metric comparison, best-per-metric highlighting,
 * normalized radar score comparisons, and 2D PCA archetype clustering.
 */

import { api } from "../api.js";
import { state } from "../state.js";
import { h } from "../ui/h.js";
import { icons } from "../ui/icons.js";

const REPO_COLORS = ["#5267D8", "#10B981", "#F59E0B", "#EF4444"];

function renderComparePage() {
  const container = h("div", { className: "page-container" });
  let selectedIds = new Set();
  let availableAnalyses = [];
  let comparisonData = null;

  async function loadInitialData() {
    container.textContent = "";

    container.appendChild(
      h("div", { className: "empty-state" },
        h("div", { className: "spinner", style: { margin: "0 auto var(--space-3) auto" } }),
        h("p", { className: "text-muted" }, "Loading available repository analyses for comparison...")
      )
    );

    try {
      const res = await api.getRecentAnalyses(20);
      const all = res.data || [];
      availableAnalyses = all.filter((a) => a.status === "completed");

      // Auto-select up to 2 analyses initially
      if (state.activeAnalysisId) {
        selectedIds.add(state.activeAnalysisId);
      }
      for (const a of availableAnalyses) {
        if (selectedIds.size >= 2) break;
        selectedIds.add(a.id);
      }

      if (availableAnalyses.length < 2) {
        container.textContent = "";
        container.appendChild(
          h("div", { className: "empty-state" },
            h("div", { className: "empty-icon", style: { color: "var(--color-fg-muted)", marginBottom: "var(--space-3)" } }, icons.compare()),
            h("h3", { style: { fontSize: "var(--text-lg)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-2)" } }, "Insufficient Analyses"),
            h("p", { className: "text-muted", style: { marginBottom: "var(--space-4)" } },
              "Repository comparison requires at least 2 completed analyses. Analyze additional repositories first."
            ),
            h("a", { href: "#/analyzer", className: "btn btn-primary" }, "Go to Repository Analyzer")
          )
        );
        return;
      }

      renderUI();
      if (selectedIds.size >= 2) {
        await executeComparison();
      }
    } catch (err) {
      container.textContent = "";
      container.appendChild(
        h("div", { className: "empty-state" },
          h("div", { className: "empty-icon", style: { color: "var(--color-danger)", marginBottom: "var(--space-3)" } }, icons.alertCircle()),
          h("h3", { style: { fontSize: "var(--text-lg)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-2)" } }, "Failed to load analyses"),
          h("p", { className: "text-muted", style: { marginBottom: "var(--space-4)" } }, err.message || "An unexpected error occurred.")
        )
      );
    }
  }

  function renderUI() {
    container.textContent = "";

    // 1. Header
    const header = h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "var(--space-6)" } },
      h("div", null,
        h("h2", { style: { fontSize: "var(--text-2xl)", fontWeight: "var(--font-bold)", marginBottom: "var(--space-1)" } }, "Repository Comparison"),
        h("p", { className: "text-muted" }, "Side-by-side multi-dimensional benchmarking, best-in-class identification, and cluster positioning.")
      ),
      h("div", null,
        h("span", { className: "badge badge-neutral" }, "Compare 2 to 4 projects")
      )
    );
    container.appendChild(header);

    // 2. Selection Picker Card
    const pickerCard = h("div", { className: "card", style: { marginBottom: "var(--space-6)", padding: "var(--space-5)" } },
      h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" } },
        h("h3", { style: { fontSize: "var(--text-md)", fontWeight: "var(--font-semibold)" } }, "Select Repositories to Compare (Choose 2 to 4)"),
        h("span", { className: "text-muted", style: { fontSize: "var(--text-xs)" } }, `${selectedIds.size} selected`)
      ),
      h("div", { style: { display: "flex", flexWrap: "wrap", gap: "var(--space-2)", marginBottom: "var(--space-4)" } },
        availableAnalyses.map((a) => {
          const isChecked = selectedIds.has(a.id);
          const chip = h("button", {
            className: `btn ${isChecked ? "btn-primary" : "btn-secondary"}`,
            style: { fontSize: "var(--text-xs)", display: "flex", alignItems: "center", gap: "var(--space-2)" },
            onClick: () => {
              if (selectedIds.has(a.id)) {
                if (selectedIds.size > 2) selectedIds.delete(a.id);
              } else {
                if (selectedIds.size < 4) selectedIds.add(a.id);
              }
              renderUI();
              executeComparison();
            },
          },
            h("span", { style: { fontWeight: "var(--font-semibold)" } }, a.repo),
            h("span", { style: { fontFamily: "var(--font-mono)", fontSize: "10px", opacity: "0.8" } }, `#${a.id}`)
          );
          return chip;
        })
      )
    );
    container.appendChild(pickerCard);

    // Results Container Placeholder
    const resultsContainer = h("div", { id: "compare-results" });
    container.appendChild(resultsContainer);

    if (comparisonData) {
      renderComparisonResults(resultsContainer);
    }
  }

  async function executeComparison() {
    const resultsContainer = container.querySelector("#compare-results");
    if (!resultsContainer) return;

    if (selectedIds.size < 2) {
      resultsContainer.replaceChildren(
        h("div", { className: "empty-state", style: { padding: "var(--space-6)" } },
          h("p", { className: "text-muted" }, "Please select at least 2 repositories above to perform comparison.")
        )
      );
      return;
    }

    resultsContainer.replaceChildren(
      h("div", { className: "empty-state", style: { padding: "var(--space-6)" } },
        h("div", { className: "spinner", style: { margin: "0 auto var(--space-3) auto" } }),
        h("p", { className: "text-muted" }, "Calculating cross-repository normalizations and best-per-metric rankings...")
      )
    );

    try {
      const resp = await api.postCompare(Array.from(selectedIds));
      comparisonData = resp.data;
      renderComparisonResults(resultsContainer);
    } catch (err) {
      resultsContainer.replaceChildren(
        h("div", { className: "error-banner", style: { padding: "var(--space-4)" } },
          h("div", { style: { fontWeight: "var(--font-bold)", marginBottom: "var(--space-1)" } }, `Comparison Error (${err.code || "FAILED"})`),
          h("div", { style: { fontSize: "var(--text-sm)" } }, err.message || "Failed to execute comparison.")
        )
      );
    }
  }

  function renderComparisonResults(target) {
    target.textContent = "";
    if (!comparisonData) return;

    const analyses = comparisonData.analyses || [];
    const metricsTable = comparisonData.metrics_table || [];
    const radarData = comparisonData.radar_data || {};
    const clusterPoints = comparisonData.cluster_points || [];

    // 1. Repositories Summary Cards
    const reposRow = h("div", {
      className: "grid",
      style: {
        gridTemplateColumns: `repeat(${analyses.length}, 1fr)`,
        gap: "var(--space-4)",
        marginBottom: "var(--space-6)",
      },
    },
      analyses.map((a, idx) =>
        h("div", { className: "card", style: { borderTop: `4px solid ${REPO_COLORS[idx % REPO_COLORS.length]}`, padding: "var(--space-4)" } },
          h("div", { style: { fontWeight: "var(--font-bold)", fontSize: "var(--text-md)", marginBottom: "var(--space-1)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" } }, a.repo_name),
          h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "var(--text-xs)", color: "var(--color-fg-muted)" } },
            h("span", null, `SHA: ${a.head_sha}`),
            h("span", { className: "badge badge-neutral" }, a.health_class)
          ),
          h("div", { style: { marginTop: "var(--space-3)", display: "flex", justifyContent: "space-between", alignItems: "baseline" } },
            h("div", null,
              h("div", { className: "text-muted", style: { fontSize: "10px", textTransform: "uppercase" } }, "Quality"),
              h("div", { style: { fontSize: "var(--text-xl)", fontWeight: "var(--font-bold)", color: "var(--color-primary)" } }, `${a.quality_score}/100`)
            ),
            h("div", { style: { textAlign: "right" } },
              h("div", { className: "text-muted", style: { fontSize: "10px", textTransform: "uppercase" } }, "Grade"),
              h("div", { style: { fontSize: "var(--text-xl)", fontWeight: "var(--font-bold)" } }, a.quality_grade)
            )
          )
        )
      )
    );
    target.appendChild(reposRow);

    // 2. Comparative Metric Table with Best-Per-Metric Highlighting
    const tableCard = h("div", { className: "card", style: { padding: "0", overflow: "hidden", marginBottom: "var(--space-6)" } },
      h("div", { style: { padding: "var(--space-4)", borderBottom: "1px solid var(--color-border)" } },
        h("h3", { style: { fontSize: "var(--text-md)", fontWeight: "var(--font-semibold)" } }, "Side-by-Side Metric Comparison"),
        h("p", { className: "text-muted", style: { fontSize: "var(--text-xs)", marginTop: "2px" } }, "Best value across repositories is highlighted with a green badge.")
      ),
      h("table", { className: "table" },
        h("thead", null,
          h("tr", null,
            h("th", { style: { width: "280px" } }, "Evaluated Metric"),
            analyses.map((a, idx) =>
              h("th", { style: { textAlign: "right" } },
                h("span", { style: { color: REPO_COLORS[idx % REPO_COLORS.length] } }, a.repo_name)
              )
            )
          )
        ),
        h("tbody", null,
          metricsTable.map((row) =>
            h("tr", null,
              h("td", { style: { fontWeight: "var(--font-semibold)" } }, row.name),
              row.values.map((v) =>
                h("td", { style: { textAlign: "right" } },
                  h("div", { style: { display: "inline-flex", alignItems: "center", gap: "var(--space-2)" } },
                    h("span", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" } }, v.value.toString()),
                    v.is_best
                      ? h("span", { className: "badge badge-success", style: { fontSize: "10px", padding: "1px 6px" } }, "★ Best")
                      : null
                  )
                )
              )
            )
          )
        )
      )
    );
    target.appendChild(tableCard);

    // 3. Normalized Radar / Dimensional Comparison Chart
    const radarCard = h("div", { className: "card", style: { marginBottom: "var(--space-6)", padding: "var(--space-5)" } },
      h("h3", { style: { fontSize: "var(--text-md)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-1)" } }, "Normalized Comparative Profiles (0–100 Scale)"),
      h("p", { className: "text-muted", style: { fontSize: "var(--text-xs)", marginBottom: "var(--space-4)" } },
        "Dimensional scores normalized to 100 for side-by-side profile matching. Numbers directly reflect normalized values from the table."
      ),
      h("div", { style: { display: "flex", flexDirection: "column", gap: "var(--space-3)" } },
        (radarData.categories || []).map((catName, cIdx) =>
          h("div", { style: { backgroundColor: "var(--color-bg-subtle)", padding: "var(--space-3)", borderRadius: "var(--radius-md)" } },
            h("div", { style: { fontSize: "var(--text-xs)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-2)" } }, catName),
            h("div", { style: { display: "flex", flexDirection: "column", gap: "var(--space-2)" } },
              (radarData.series || []).map((s, sIdx) => {
                const score = s.data[cIdx] || 0;
                return h("div", { style: { display: "flex", alignItems: "center", gap: "var(--space-3)", fontSize: "var(--text-xs)" } },
                  h("span", { style: { width: "160px", color: REPO_COLORS[sIdx % REPO_COLORS.length], fontWeight: "var(--font-medium)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" } }, s.name),
                  h("div", { style: { flex: "1", height: "6px", backgroundColor: "var(--color-border)", borderRadius: "var(--radius-full)", overflow: "hidden" } },
                    h("div", { style: { width: `${score}%`, height: "100%", backgroundColor: REPO_COLORS[sIdx % REPO_COLORS.length] } })
                  ),
                  h("span", { style: { fontFamily: "var(--font-mono)", width: "36px", textAlign: "right" } }, `${Math.round(score)}`)
                );
              })
            )
          )
        )
      )
    );
    target.appendChild(radarCard);

    // 4. 2D PCA Cluster Map
    const clusterCard = h("div", { className: "card", style: { padding: "var(--space-5)" } },
      h("h3", { style: { fontSize: "var(--text-md)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-1)" } }, "2D PCA Archetype Positioning"),
      h("p", { className: "text-muted", style: { fontSize: "var(--text-xs)", marginBottom: "var(--space-4)" } },
        "Projection coordinates of compared repositories within the multi-repository corpus feature space."
      ),
      h("div", { className: "grid", style: { gridTemplateColumns: `repeat(${clusterPoints.length}, 1fr)`, gap: "var(--space-4)" } },
        clusterPoints.map((cp, idx) =>
          h("div", { style: { padding: "var(--space-3)", backgroundColor: "var(--color-bg-subtle)", borderRadius: "var(--radius-md)", borderLeft: `3px solid ${REPO_COLORS[idx % REPO_COLORS.length]}` } },
            h("div", { style: { fontWeight: "var(--font-semibold)", fontSize: "var(--text-xs)", color: REPO_COLORS[idx % REPO_COLORS.length] } }, cp.repo_name),
            h("div", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--text-md)", marginTop: "4px" } },
              `[${cp.x}, ${cp.y}]`
            ),
            h("div", { className: "text-muted", style: { fontSize: "10px", marginTop: "2px" } },
              `Cluster Archetype #${cp.cluster_id}`
            )
          )
        )
      )
    );
    target.appendChild(clusterCard);
  }

  loadInitialData();

  return {
    element: container,
    destroy: () => {},
  };
}

const comparePage = {
  title: "Repository Comparison",
  instance: null,
  async mount(ctx) {
    this.instance = renderComparePage();
    ctx.container.replaceChildren(this.instance.element);
  },
  unmount() {
    if (this.instance && typeof this.instance.destroy === "function") {
      this.instance.destroy();
      this.instance = null;
    }
  },
};

export default comparePage;
