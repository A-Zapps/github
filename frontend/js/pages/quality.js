/**
 * Code Quality Page (F2).
 * Displays overall score gauge, letter grade, technical debt estimate,
 * component score breakdown with weights, and worst 10 files with table/chart toggle.
 */

import { api } from "../api.js";
import { state, subscribe } from "../state.js";
import { createHorizontalBarChart, makeChartContainer } from "../ui/charts.js";
import { h } from "../ui/h.js";
import { icons } from "../ui/icons.js";

function getGradeColor(grade) {
  switch (grade) {
    case "A": return "#16803C";
    case "B": return "#5267D8";
    case "C": return "#B25E09";
    case "D": return "#D97706";
    default: return "#CF3A3A";
  }
}

export default function renderQualityPage() {
  const container = h("div", { className: "page-container" });

  let chartInstance = null;

  function cleanup() {
    if (chartInstance) {
      chartInstance.destroy();
      chartInstance = null;
    }
  }

  async function loadData() {
    cleanup();
    container.textContent = "";

    const analysisId = state.activeAnalysisId;
    if (!analysisId) {
      container.appendChild(
        h("div", { className: "empty-state" },
          h("div", { className: "empty-icon", style: { color: "var(--color-fg-muted)", marginBottom: "var(--space-3)" } }, icons.info()),
          h("h3", { style: { fontSize: "var(--text-lg)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-2)" } }, "No analysis selected"),
          h("p", { className: "text-muted", style: { marginBottom: "var(--space-4)" } }, "Analyze a GitHub repository first to view comprehensive code quality metrics."),
          h("a", { href: "#/analyzer", className: "btn btn-primary" }, "Go to Repository Analyzer")
        )
      );
      return;
    }

    // Loading state
    container.appendChild(
      h("div", { className: "empty-state" },
        h("div", { className: "spinner", style: { margin: "0 auto var(--space-3) auto" } }),
        h("p", { className: "text-muted" }, "Loading code quality metrics...")
      )
    );

    try {
      const resp = await api.getQualityData(analysisId);
      const data = resp.data;
      container.textContent = "";

      // 1. Header
      const header = h("div", { style: { marginBottom: "var(--space-6)" } },
        h("div", { style: { display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "var(--space-3)" } },
          h("div", {},
            h("h2", { style: { fontSize: "var(--text-2xl)", fontWeight: "var(--font-bold)", color: "var(--color-fg-default)" } }, "Code Quality"),
            h("p", { className: "text-muted", style: { fontSize: "var(--text-sm)" } }, `Repository: ${state.activeRepo || "Active Repository"} (Analysis #${analysisId})`)
          ),
          h("div", { className: "badge badge-neutral" }, `Generated: ${new Date(resp.meta.generated_at).toLocaleTimeString()}`)
        )
      );
      container.appendChild(header);

      // 2. Overview Stats Row: Score Gauge, Tech Debt, Outliers
      const gradeColor = getGradeColor(data.grade);
      const statsGrid = h("div", { className: "grid grid-cols-3", style: { gap: "var(--space-4)", marginBottom: "var(--space-6)" } },
        // Quality Score Card
        h("div", { className: "card", style: { display: "flex", alignItems: "center", gap: "var(--space-4)", padding: "var(--space-5)" } },
          h("div", {
            style: {
              width: "64px",
              height: "64px",
              borderRadius: "50%",
              backgroundColor: `${gradeColor}15`,
              color: gradeColor,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "var(--text-2xl)",
              fontWeight: "var(--font-bold)",
              border: `3px solid ${gradeColor}`,
              flexShrink: 0,
            }
          }, data.grade),
          h("div", {},
            h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: "var(--font-semibold)" } }, "Quality Score"),
            h("div", { style: { fontSize: "var(--text-3xl)", fontWeight: "var(--font-bold)", color: "var(--color-fg-default)" } }, `${data.overall_score}/100`),
            h("div", { style: { fontSize: "var(--text-xs)", color: "var(--color-fg-muted)" } }, `Grade ${data.grade} Rating`)
          )
        ),

        // Tech Debt Card
        h("div", { className: "card", style: { padding: "var(--space-5)" } },
          h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "var(--space-1)" } },
            h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: "var(--font-semibold)" } }, "Technical Debt"),
            h("span", { className: "badge badge-neutral", style: { fontSize: "10px" } }, "estimate from fixed rules, not measured")
          ),
          h("div", { style: { fontSize: "var(--text-2xl)", fontWeight: "var(--font-bold)", color: "var(--color-fg-default)", marginBottom: "var(--space-1)" } },
            `${data.tech_debt.days} days`
          ),
          h("div", { style: { fontSize: "var(--text-xs)", color: "var(--color-fg-muted)" } },
            `${data.tech_debt.hours} hours (${data.tech_debt.minutes} mins) • ${data.tech_debt.label}`
          )
        ),

        // Complexity & Duplication Snapshot
        h("div", { className: "card", style: { padding: "var(--space-5)" } },
          h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-2)" } }, "Key Signals"),
          h("div", { style: { display: "flex", flexDirection: "column", gap: "var(--space-2)", fontSize: "var(--text-xs)" } },
            h("div", { style: { display: "flex", justifyContent: "space-between" } },
              h("span", { className: "text-muted" }, "Complexity (CCN > 10):"),
              h("span", { style: { fontWeight: "var(--font-semibold)" } }, data.components.complexity ? data.components.complexity.metric_value : "N/A")
            ),
            h("div", { style: { display: "flex", justifyContent: "space-between" } },
              h("span", { className: "text-muted" }, "Code Duplication:"),
              h("span", { style: { fontWeight: "var(--font-semibold)" } }, data.components.duplication ? data.components.duplication.metric_value : "N/A")
            ),
            h("div", { style: { display: "flex", justifyContent: "space-between" } },
              h("span", { className: "text-muted" }, "Test Ratio:"),
              h("span", { style: { fontWeight: "var(--font-semibold)" } }, data.components.test_ratio ? data.components.test_ratio.metric_value : "N/A")
            )
          )
        )
      );
      container.appendChild(statsGrid);

      // Corpus Percentiles & Maintenance Effort (RULES D8 & T4.6)
      const corpusPercentiles = data.corpus_percentiles || {};
      const maintEffort = data.maintenance_effort || {};

      if (Object.keys(corpusPercentiles).length > 0 || maintEffort.status === "ready") {
        const mlInsightsRow = h("div", { className: "grid grid-2", style: { gap: "var(--space-4)", marginBottom: "var(--space-6)" } },
          // Percentile vs Corpus Card
          h("div", { className: "card", style: { padding: "var(--space-5)" } },
            h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "var(--space-2)" } },
              h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: "var(--font-semibold)" } }, "Percentile vs Corpus Reference"),
              h("span", { className: "badge badge-neutral", style: { fontSize: "10px" } }, "corpus_reference")
            ),
            h("p", { className: "text-muted", style: { fontSize: "var(--text-xs)", marginBottom: "var(--space-3)" } },
              "Relative standing against multi-repository open source benchmark distribution (higher is better for maintainability/tests; lower is better for duplication)."
            ),
            h("div", { style: { display: "flex", flexDirection: "column", gap: "var(--space-2)" } },
              [
                { label: "Maintainability Index", key: "avg_maintainability" },
                { label: "Code Scale (LOC)", key: "total_loc" },
                { label: "Duplication Inversion", key: "duplication_pct" },
                { label: "Testing Coverage Ratio", key: "test_ratio" },
              ].map((item) => {
                const pVal = corpusPercentiles[item.key] !== undefined ? Math.round(corpusPercentiles[item.key]) : 50;
                return h("div", { style: { display: "flex", alignItems: "center", gap: "var(--space-3)", fontSize: "var(--text-xs)" } },
                  h("span", { style: { width: "160px", color: "var(--color-fg-muted)" } }, item.label),
                  h("div", { style: { flex: "1", height: "6px", backgroundColor: "var(--color-bg-subtle)", borderRadius: "var(--radius-full)", overflow: "hidden" } },
                    h("div", { style: { width: `${pVal}%`, height: "100%", backgroundColor: "var(--color-primary)" } })
                  ),
                  h("span", { style: { fontFamily: "var(--font-mono)", fontWeight: "var(--font-semibold)", width: "40px", textAlign: "right" } }, `${pVal}th`)
                );
              })
            )
          ),

          // Maintenance Effort Prediction Card
          h("div", { className: "card", style: { padding: "var(--space-5)" } },
            h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "var(--space-2)" } },
              h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: "var(--font-semibold)" } }, "Predicted Maintenance Effort"),
              h("span", { className: "badge badge-neutral", style: { fontSize: "10px" } }, maintEffort.model_version ? `v${maintEffort.model_version}` : "RandomForestRegressor")
            ),
            h("div", { style: { fontSize: "var(--text-2xl)", fontWeight: "var(--font-bold)", color: "var(--color-fg-default)", marginTop: "var(--space-1)", marginBottom: "var(--space-1)" } },
              maintEffort.predicted_total_churn_lines_6m !== undefined
                ? `~${Math.round(maintEffort.predicted_total_churn_lines_6m).toLocaleString()} lines`
                : "Awaiting analysis"
            ),
            h("div", { style: { fontSize: "var(--text-xs)", color: "var(--color-fg-muted)", marginBottom: "var(--space-3)" } },
              "Predicted total code churn (lines added + deleted) over the upcoming 6-month development window."
            ),
            h("div", { style: { fontSize: "var(--text-xs)", backgroundColor: "var(--color-bg-subtle)", padding: "var(--space-2)", borderRadius: "var(--radius-sm)" } },
              "Trained on historical commits, cyclomatic complexity distributions, and author ownership metrics."
            )
          )
        );
        container.appendChild(mlInsightsRow);
      }

      // 3. Component Scores Breakdown
      const componentsCard = h("div", { className: "card", style: { marginBottom: "var(--space-6)" } },
        h("div", { className: "card-header" },
          h("h3", { className: "card-title" }, "Component Scores & Formula Weights")
        ),
        h("div", { style: { padding: "var(--space-4)" } },
          h("div", { style: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "var(--space-5)" } },
            ...Object.entries(data.components).map(([key, comp]) => {
              const weightPct = Math.round(comp.weight * 100);
              const score = comp.score;
              const barColor = score >= 80 ? "var(--color-primary)" : score >= 60 ? "#D97706" : "#CF3A3A";

              return h("div", {},
                h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-1)" } },
                  h("span", { style: { fontWeight: "var(--font-semibold)", fontSize: "var(--text-sm)", textTransform: "capitalize" } }, key.replace(/_/g, " ")),
                  h("span", { style: { fontSize: "var(--text-xs)", color: "var(--color-fg-muted)" } }, `Weight: ${weightPct}%`)
                ),
                h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "var(--text-xs)", color: "var(--color-fg-muted)", marginBottom: "var(--space-2)" } },
                  h("span", {}, comp.metric_value),
                  h("span", { style: { fontWeight: "var(--font-bold)", color: "var(--color-fg-default)" } }, `${score}/100`)
                ),
                h("div", { style: { height: "6px", backgroundColor: "var(--color-bg-subtle)", borderRadius: "var(--radius-full)", overflow: "hidden" } },
                  h("div", { style: { height: "100%", width: `${score}%`, backgroundColor: barColor, borderRadius: "var(--radius-full)" } })
                )
              );
            })
          )
        )
      );
      container.appendChild(componentsCard);

      // 4. Worst 10 Files Section (Table & Chart Toggle)
      const worstFiles = data.worst_files || [];

      // Build Table Node
      const tableRows = worstFiles.map((f, i) =>
        h("tr", {},
          h("td", { style: { color: "var(--color-fg-muted)", width: "32px" } }, `${i + 1}`),
          h("td", { className: "font-mono", style: { fontSize: "var(--text-xs)", maxWidth: "340px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" } }, f.path),
          h("td", { style: { textAlign: "right" } }, `${f.loc}`),
          h("td", { style: { textAlign: "right", fontWeight: "var(--font-bold)", color: f.ccn_max > 10 ? "#CF3A3A" : "inherit" } }, `${f.ccn_max}`),
          h("td", { style: { textAlign: "right" } }, `${f.ccn_mean}`),
          h("td", { style: { textAlign: "right" } },
            `${f.maintainability_index}`,
            f.is_proxy ? h("span", { className: "badge badge-neutral", style: { marginLeft: "var(--space-2)", fontSize: "9px" } }, "proxy") : ""
          )
        )
      );

      const tableNode = h("table", { className: "table", style: { width: "100%", fontSize: "var(--text-xs)" } },
        h("thead", {},
          h("tr", {},
            h("th", { style: { width: "32px" } }, "#"),
            h("th", {}, "File Path"),
            h("th", { style: { textAlign: "right" } }, "LOC"),
            h("th", { style: { textAlign: "right" } }, "Max CCN"),
            h("th", { style: { textAlign: "right" } }, "Mean CCN"),
            h("th", { style: { textAlign: "right" } }, "Maintainability")
          )
        ),
        h("tbody", {}, ...tableRows)
      );

      // Build Chart Canvas
      const chartCanvas = h("canvas");
      const worstCard = makeChartContainer("Highest Complexity Files (Worst 10)", chartCanvas, tableNode);
      container.appendChild(worstCard);

      // Render chart
      const chartLabels = worstFiles.map(f => f.path.split("/").pop());
      const chartData = worstFiles.map(f => f.ccn_max);
      chartInstance = createHorizontalBarChart(chartCanvas, chartLabels, chartData, "Max CCN");

    } catch (err) {
      container.textContent = "";
      container.appendChild(
        h("div", { className: "error-banner", style: { padding: "var(--space-4)" } },
          h("div", { style: { fontWeight: "var(--font-bold)", marginBottom: "var(--space-1)" } }, `Error loading quality metrics (${err.code || "FAILED"})`),
          h("div", { style: { fontSize: "var(--text-sm)" } }, err.message || "Failed to load quality metrics.")
        )
      );
    }
  }

  // Subscribe to state updates when activeAnalysisId changes
  const unsubscribe = subscribe((key) => {
    if (key === "activeAnalysisId" || key === "activeRepo") {
      loadData();
    }
  });

  loadData();

  return container;
}
