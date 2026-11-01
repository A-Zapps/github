/**
 * Developer Analytics Page (F7).
 * Displays contributor workload, bus factor risks, 7x24 commit rhythm heatmap,
 * and PR/issue closure velocity.
 */

import { api } from "../api.js";
import { state, subscribe } from "../state.js";
import { h } from "../ui/h.js";
import { icons } from "../ui/icons.js";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function renderDevelopersPage() {
  const container = h("div", { className: "page-container" });

  async function loadData() {
    container.textContent = "";

    const analysisId = state.activeAnalysisId;
    if (!analysisId) {
      container.appendChild(
        h("div", { className: "empty-state" },
          h("div", { className: "empty-icon", style: { color: "var(--color-fg-muted)", marginBottom: "var(--space-3)" } }, icons.users()),
          h("h3", { style: { fontSize: "var(--text-lg)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-2)" } }, "No analysis selected"),
          h("p", { className: "text-muted", style: { marginBottom: "var(--space-4)" } }, "Select or analyze a GitHub repository first to view developer collaboration analytics."),
          h("a", { href: "#/analyzer", className: "btn btn-primary" }, "Go to Repository Analyzer")
        )
      );
      return;
    }

    container.appendChild(
      h("div", { className: "empty-state" },
        h("div", { className: "spinner", style: { margin: "0 auto var(--space-3) auto" } }),
        h("p", { className: "text-muted" }, "Aggregating contributor distributions and commit rhythms...")
      )
    );

    try {
      const resp = await api.getDeveloperData(analysisId);
      const data = resp.data || {};
      container.textContent = "";

      const totalCommits = data.total_commits || 0;
      const contributors = data.contributors || [];
      const busFactor = data.bus_factor || 1;
      const busFactorLabel = data.bus_factor_label || "";
      const heatmap = data.commit_rhythm_heatmap || [];
      const prStats = data.pr_merge_time || { available: false };
      const issueStats = data.issue_close_time || { available: false };

      // 1. Header
      const header = h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "var(--space-6)" } },
        h("div", null,
          h("h2", { style: { fontSize: "var(--text-2xl)", fontWeight: "var(--font-bold)", marginBottom: "var(--space-1)" } }, "Developer Analytics"),
          h("p", { className: "text-muted" }, "Contributor workload concentration, bus factor resilience, commit rhythm, and turnaround velocity.")
        ),
        h("div", { style: { display: "flex", alignItems: "center", gap: "var(--space-2)" } },
          h("span", { className: "badge badge-neutral" }, `${data.distinct_contributors || 0} Authors`),
          h("span", { className: "badge badge-neutral" }, `${totalCommits} Commits Analyzed`)
        )
      );
      container.appendChild(header);

      // 2. Headline Stats Row
      const statsRow = h("div", { className: "grid grid-4", style: { gap: "var(--space-4)", marginBottom: "var(--space-6)" } },
        h("div", { className: "card" },
          h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase" } }, "Total Commits"),
          h("div", { style: { fontSize: "var(--text-3xl)", fontWeight: "var(--font-bold)", marginTop: "var(--space-1)" } }, totalCommits.toString())
        ),
        h("div", { className: "card" },
          h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase" } }, "Active Contributors"),
          h("div", { style: { fontSize: "var(--text-3xl)", fontWeight: "var(--font-bold)", marginTop: "var(--space-1)" } }, (data.distinct_contributors || 0).toString())
        ),
        h("div", { className: "card", style: { borderLeft: `4px solid ${busFactor <= 1 ? "var(--color-danger)" : busFactor === 2 ? "var(--color-warning)" : "var(--color-success)"}` } },
          h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase" } }, "Project Bus Factor"),
          h("div", { style: { fontSize: "var(--text-3xl)", fontWeight: "var(--font-bold)", marginTop: "var(--space-1)", color: busFactor <= 1 ? "var(--color-danger)" : "var(--color-fg-default)" } },
            `${busFactor}`
          ),
          h("div", { style: { fontSize: "10px", color: "var(--color-fg-muted)", marginTop: "2px" } },
            busFactor <= 1 ? "High Vulnerability" : busFactor === 2 ? "Moderate Resilience" : "Healthy Redundancy"
          )
        ),
        h("div", { className: "card" },
          h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase" } }, "Top Contributor Share"),
          h("div", { style: { fontSize: "var(--text-3xl)", fontWeight: "var(--font-bold)", marginTop: "var(--space-1)" } },
            contributors.length > 0 ? `${contributors[0].percentage}%` : "0%"
          )
        )
      );
      container.appendChild(statsRow);

      // 3. Bus Factor Risk Card
      const busCard = h("div", { className: "card", style: { marginBottom: "var(--space-6)", padding: "var(--space-4) var(--space-5)" } },
        h("div", { style: { display: "flex", alignItems: "center", gap: "var(--space-3)" } },
          h("div", { style: { color: busFactor <= 1 ? "var(--color-danger)" : "var(--color-primary)" } }, icons.shield(24)),
          h("div", null,
            h("div", { style: { fontWeight: "var(--font-semibold)", fontSize: "var(--text-sm)" } }, "Bus Factor Assessment"),
            h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", marginTop: "2px" } }, busFactorLabel)
          )
        )
      );
      container.appendChild(busCard);

      // 4. Commit Rhythm Heatmap (7 weekdays x 24 hours)
      // Find max cell value for color scaling
      let maxCell = 1;
      for (const row of heatmap) {
        for (const val of row) {
          if (val > maxCell) maxCell = val;
        }
      }

      const heatmapCard = h("div", { className: "card", style: { marginBottom: "var(--space-6)", padding: "var(--space-5)" } },
        h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-4)" } },
          h("div", null,
            h("h3", { style: { fontSize: "var(--text-md)", fontWeight: "var(--font-semibold)" } }, "Commit Rhythm (Weekday × Hour)"),
            h("p", { className: "text-muted", style: { fontSize: "var(--text-xs)", marginTop: "2px" } },
              `Heatmap distribution of ${totalCommits} commits across hours of day and days of week.`
            )
          ),
          h("div", { style: { display: "flex", alignItems: "center", gap: "var(--space-2)", fontSize: "var(--text-xs)", color: "var(--color-fg-muted)" } },
            h("span", null, "Less"),
            h("div", { style: { width: "12px", height: "12px", backgroundColor: "var(--color-bg-subtle)", borderRadius: "2px" } }),
            h("div", { style: { width: "12px", height: "12px", backgroundColor: "rgba(82, 103, 216, 0.3)", borderRadius: "2px" } }),
            h("div", { style: { width: "12px", height: "12px", backgroundColor: "rgba(82, 103, 216, 0.7)", borderRadius: "2px" } }),
            h("div", { style: { width: "12px", height: "12px", backgroundColor: "var(--color-primary)", borderRadius: "2px" } }),
            h("span", null, "More")
          )
        ),
        // Heatmap Grid
        h("div", { style: { overflowX: "auto" } },
          h("div", { style: { minWidth: "680px" } },
            // Hour header row (0 to 23)
            h("div", { style: { display: "flex", marginLeft: "44px", marginBottom: "4px", fontSize: "10px", color: "var(--color-fg-muted)" } },
              Array.from({ length: 24 }).map((_, hIdx) =>
                h("div", { style: { width: "24px", textAlign: "center" } }, hIdx % 3 === 0 ? `${hIdx}h` : "")
              )
            ),
            // Weekday rows
            heatmap.map((row, wIdx) =>
              h("div", { style: { display: "flex", alignItems: "center", marginBottom: "4px" } },
                h("div", { style: { width: "40px", fontSize: "var(--text-xs)", color: "var(--color-fg-muted)", marginRight: "4px" } }, WEEKDAYS[wIdx]),
                h("div", { style: { display: "flex", gap: "3px" } },
                  row.map((count, hIdx) => {
                    const ratio = count / maxCell;
                    const bg = count === 0
                      ? "var(--color-bg-subtle)"
                      : ratio < 0.25
                      ? "rgba(82, 103, 216, 0.25)"
                      : ratio < 0.6
                      ? "rgba(82, 103, 216, 0.55)"
                      : ratio < 0.85
                      ? "rgba(82, 103, 216, 0.8)"
                      : "var(--color-primary)";
                    return h("div", {
                      title: `${WEEKDAYS[wIdx]} ${hIdx}:00 - ${count} commits`,
                      style: {
                        width: "21px",
                        height: "21px",
                        backgroundColor: bg,
                        borderRadius: "3px",
                        cursor: "pointer",
                      },
                    });
                  })
                )
              )
            )
          )
        )
      );
      container.appendChild(heatmapCard);

      // 5. Turnaround Velocity Cards: PR Merge Time & Issue Close Time
      const velocityRow = h("div", { className: "grid grid-2", style: { gap: "var(--space-4)", marginBottom: "var(--space-6)" } },
        // PR Merge Time Card
        h("div", { className: "card", style: { padding: "var(--space-5)" } },
          h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-1)" } }, "Pull Request Merge Velocity"),
          prStats.available
            ? h("div", null,
                h("div", { style: { fontSize: "var(--text-3xl)", fontWeight: "var(--font-bold)", marginTop: "var(--space-2)", color: "var(--color-fg-default)" } },
                  `${prStats.median_hours} hours`
                ),
                h("div", { style: { fontSize: "var(--text-xs)", color: "var(--color-fg-muted)", marginTop: "2px" } },
                  `Median turnaround (P90: ${prStats.p90_hours} hrs across ${prStats.count} merged PRs)`
                )
              )
            : h("div", { style: { marginTop: "var(--space-3)", color: "var(--color-fg-muted)", fontSize: "var(--text-xs)" } },
                h("span", { className: "badge badge-neutral", style: { marginBottom: "var(--space-2)" } }, "available: false"),
                h("p", null, prStats.reason || "Insufficient PR history")
              )
        ),
        // Issue Close Time Card
        h("div", { className: "card", style: { padding: "var(--space-5)" } },
          h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-1)" } }, "Issue Resolution Velocity"),
          issueStats.available
            ? h("div", null,
                h("div", { style: { fontSize: "var(--text-3xl)", fontWeight: "var(--font-bold)", marginTop: "var(--space-2)", color: "var(--color-fg-default)" } },
                  `${issueStats.median_hours} hours`
                ),
                h("div", { style: { fontSize: "var(--text-xs)", color: "var(--color-fg-muted)", marginTop: "2px" } },
                  `Median resolution (P90: ${issueStats.p90_hours} hrs across ${issueStats.count} closed issues)`
                )
              )
            : h("div", { style: { marginTop: "var(--space-3)", color: "var(--color-fg-muted)", fontSize: "var(--text-xs)" } },
                h("span", { className: "badge badge-neutral", style: { marginBottom: "var(--space-2)" } }, "available: false"),
                h("p", null, issueStats.reason || "Insufficient issue history")
              )
        )
      );
      container.appendChild(velocityRow);

      // 6. Top Contributors Table
      const contributorsCard = h("div", { className: "card", style: { padding: "0", overflow: "hidden" } },
        h("div", { style: { padding: "var(--space-4)", borderBottom: "1px solid var(--color-border)" } },
          h("h3", { style: { fontSize: "var(--text-md)", fontWeight: "var(--font-semibold)" } }, "Top Contributors Breakdown")
        ),
        h("table", { className: "table" },
          h("thead", null,
            h("tr", null,
              h("th", { style: { width: "40px" } }, "#"),
              h("th", null, "Author"),
              h("th", { style: { width: "120px" } }, "Commits"),
              h("th", { style: { width: "160px" } }, "Share"),
              h("th", { style: { width: "120px" } }, "Lines Added"),
              h("th", { style: { width: "120px" } }, "Lines Deleted")
            )
          ),
          h("tbody", null,
            contributors.map((c, idx) =>
              h("tr", null,
                h("td", { style: { color: "var(--color-fg-muted)" } }, `${idx + 1}`),
                h("td", { style: { fontWeight: "var(--font-semibold)" } }, c.author),
                h("td", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" } }, c.commits.toString()),
                h("td", null,
                  h("div", { style: { display: "flex", alignItems: "center", gap: "var(--space-2)" } },
                    h("span", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", width: "36px" } }, `${c.percentage}%`),
                    h("div", { style: { flex: "1", height: "6px", backgroundColor: "var(--color-bg-subtle)", borderRadius: "var(--radius-full)", overflow: "hidden" } },
                      h("div", { style: { width: `${c.percentage}%`, height: "100%", backgroundColor: "var(--color-primary)" } })
                    )
                  )
                ),
                h("td", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--color-success)" } }, `+${c.lines_added}`),
                h("td", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--color-danger)" } }, `-${c.lines_deleted}`)
              )
            )
          )
        )
      );
      container.appendChild(contributorsCard);

    } catch (err) {
      container.textContent = "";
      container.appendChild(
        h("div", { className: "empty-state" },
          h("div", { className: "empty-icon", style: { color: "var(--color-danger)", marginBottom: "var(--space-3)" } }, icons.alertCircle()),
          h("h3", { style: { fontSize: "var(--text-lg)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-2)" } }, "Failed to load developer analytics"),
          h("p", { className: "text-muted", style: { marginBottom: "var(--space-4)" } }, err.message || "An unexpected error occurred."),
          h("button", { className: "btn btn-secondary", onClick: loadData }, "Retry")
        )
      );
    }
  }

  const unsubscribe = subscribe(loadData);
  loadData();

  return {
    element: container,
    destroy: () => unsubscribe(),
  };
}

const developersPage = {
  title: "Developer Analytics",
  instance: null,
  async mount(ctx) {
    this.instance = renderDevelopersPage();
    ctx.container.replaceChildren(this.instance.element);
  },
  unmount() {
    if (this.instance && typeof this.instance.destroy === "function") {
      this.instance.destroy();
      this.instance = null;
    }
  },
};

export default developersPage;
