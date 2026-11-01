/**
 * Bug Prediction Page (F3).
 * Machine learning defect prediction per file, risk tiers, drivers, and scatter visualizer.
 */

import { api } from "../api.js";
import { state, subscribe } from "../state.js";
import { h } from "../ui/h.js";
import { icons } from "../ui/icons.js";

function getTierBadge(tier) {
  const t = (tier || "low").toLowerCase();
  switch (t) {
    case "high":
      return h("span", { className: "badge badge-danger" }, "HIGH");
    case "medium":
      return h("span", { className: "badge badge-warning" }, "MEDIUM");
    default:
      return h("span", { className: "badge badge-success" }, "LOW");
  }
}

function renderBugsPage() {
  const container = h("div", { className: "page-container" });
  let tierFilter = "all"; // "all" | "high" | "medium" | "low"
  let searchQuery = "";
  let currentSort = { col: "probability", desc: true };

  async function loadData() {
    container.textContent = "";

    const analysisId = state.activeAnalysisId;
    if (!analysisId) {
      container.appendChild(
        h("div", { className: "empty-state" },
          h("div", { className: "empty-icon", style: { color: "var(--color-fg-muted)", marginBottom: "var(--space-3)" } }, icons.bug()),
          h("h3", { style: { fontSize: "var(--text-lg)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-2)" } }, "No analysis selected"),
          h("p", { className: "text-muted", style: { marginBottom: "var(--space-4)" } }, "Select or analyze a GitHub repository first to view machine learning bug predictions."),
          h("a", { href: "#/analyzer", className: "btn btn-primary" }, "Go to Repository Analyzer")
        )
      );
      return;
    }

    // Loading state
    container.appendChild(
      h("div", { className: "empty-state" },
        h("div", { className: "spinner", style: { margin: "0 auto var(--space-3) auto" } }),
        h("p", { className: "text-muted" }, "Running machine learning bug risk models...")
      )
    );

    try {
      const resp = await api.getBugsData(analysisId);
      const data = resp.data;
      container.textContent = "";

      const files = data.files || [];
      const summary = data.summary || { total_files: files.length, high_risk: 0, medium_risk: 0, low_risk: 0 };
      const modelName = data.model_name || "bug_risk";
      const modelVer = data.model_version || "1.0.0";

      // 1. Header with Model Badge
      const header = h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "var(--space-6)" } },
        h("div", null,
          h("h2", { style: { fontSize: "var(--text-2xl)", fontWeight: "var(--font-bold)", marginBottom: "var(--space-1)" } }, "Bug Prediction"),
          h("p", { className: "text-muted" }, "File-level defect risk estimation using trained machine learning models and code history features.")
        ),
        h("div", { style: { display: "flex", alignItems: "center", gap: "var(--space-2)" } },
          h("span", { className: "badge badge-neutral" }, `Model: ${modelName}`),
          h("span", { className: "badge badge-neutral" }, `v${modelVer}`)
        )
      );
      container.appendChild(header);

      // 2. Risk Distribution Cards
      const summaryRow = h("div", { className: "grid grid-4", style: { marginBottom: "var(--space-6)" } },
        h("div", { className: "card" },
          h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase" } }, "Files Analyzed"),
          h("div", { style: { fontSize: "var(--text-3xl)", fontWeight: "var(--font-bold)", marginTop: "var(--space-1)" } }, summary.total_files.toString())
        ),
        h("div", { className: "card", style: { borderLeft: "4px solid var(--color-danger)" } },
          h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase" } }, "High Risk Files"),
          h("div", { style: { fontSize: "var(--text-3xl)", fontWeight: "var(--font-bold)", color: "var(--color-danger)", marginTop: "var(--space-1)" } }, summary.high_risk.toString())
        ),
        h("div", { className: "card", style: { borderLeft: "4px solid var(--color-warning)" } },
          h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase" } }, "Medium Risk Files"),
          h("div", { style: { fontSize: "var(--text-3xl)", fontWeight: "var(--font-bold)", color: "var(--color-warning)", marginTop: "var(--space-1)" } }, summary.medium_risk.toString())
        ),
        h("div", { className: "card", style: { borderLeft: "4px solid var(--color-success)" } },
          h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase" } }, "Low Risk Files"),
          h("div", { style: { fontSize: "var(--text-3xl)", fontWeight: "var(--font-bold)", color: "var(--color-success)", marginTop: "var(--space-1)" } }, summary.low_risk.toString())
        )
      );
      container.appendChild(summaryRow);

      // 3. Search and Tier Filter Controls
      const filterBar = h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-4)", gap: "var(--space-4)" } },
        h("div", { style: { display: "flex", gap: "var(--space-2)" } },
          ["all", "high", "medium", "low"].map((tier) => {
            const btn = h("button", {
              className: `btn ${tierFilter === tier ? "btn-primary" : "btn-secondary"}`,
              style: { textTransform: "capitalize", fontSize: "var(--text-sm)" },
              onClick: () => {
                tierFilter = tier;
                renderTable();
              },
            }, tier);
            return btn;
          })
        ),
        h("input", {
          type: "text",
          placeholder: "Filter by filename...",
          className: "input",
          style: { maxWidth: "300px" },
          value: searchQuery,
          onInput: (e) => {
            searchQuery = e.target.value.toLowerCase().trim();
            renderTable();
          },
        })
      );
      container.appendChild(filterBar);

      // 4. Sortable Table Container
      const tableWrapper = h("div", { className: "card", style: { padding: "0", overflow: "hidden" } });
      container.appendChild(tableWrapper);

      function renderTable() {
        tableWrapper.textContent = "";

        let filtered = files.filter((f) => {
          if (tierFilter !== "all" && f.risk_tier.toLowerCase() !== tierFilter) return false;
          if (searchQuery && !f.file.toLowerCase().includes(searchQuery)) return false;
          return true;
        });

        // Sorting
        filtered.sort((a, b) => {
          let valA = a[currentSort.col];
          let valB = b[currentSort.col];
          if (typeof valA === "string") return currentSort.desc ? valB.localeCompare(valA) : valA.localeCompare(valB);
          return currentSort.desc ? valB - valA : valA - valB;
        });

        if (filtered.length === 0) {
          tableWrapper.appendChild(
            h("div", { className: "empty-state", style: { padding: "var(--space-8)" } },
              h("p", { className: "text-muted" }, "No files match the active filters.")
            )
          );
          return;
        }

        const table = h("table", { className: "table" });
        const thead = h("thead", null,
          h("tr", null,
            h("th", {
              style: { cursor: "pointer" },
              onClick: () => {
                if (currentSort.col === "file") currentSort.desc = !currentSort.desc;
                else { currentSort.col = "file"; currentSort.desc = false; }
                renderTable();
              },
            }, "File " + (currentSort.col === "file" ? (currentSort.desc ? "↓" : "↑") : "")),
            h("th", { style: { width: "100px" } }, "Risk Tier"),
            h("th", {
              style: { width: "140px", cursor: "pointer" },
              onClick: () => {
                if (currentSort.col === "probability") currentSort.desc = !currentSort.desc;
                else { currentSort.col = "probability"; currentSort.desc = true; }
                renderTable();
              },
            }, "Probability " + (currentSort.col === "probability" ? (currentSort.desc ? "↓" : "↑") : "")),
            h("th", { style: { width: "100px" } }, "Max CCN"),
            h("th", { style: { width: "100px" } }, "LOC"),
            h("th", null, "Key Drivers")
          )
        );

        const tbody = h("tbody", null);
        for (const item of filtered) {
          const pct = Math.round(item.probability * 100);
          const tr = h("tr", null,
            h("td", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" } }, item.file),
            h("td", null, getTierBadge(item.risk_tier)),
            h("td", null,
              h("div", { style: { display: "flex", alignItems: "center", gap: "var(--space-2)" } },
                h("span", { style: { fontFamily: "var(--font-mono)", fontWeight: "var(--font-semibold)" } }, `${pct}%`),
                h("div", { style: { flex: "1", height: "6px", backgroundColor: "var(--color-bg-subtle)", borderRadius: "var(--radius-full)", overflow: "hidden" } },
                  h("div", {
                    style: {
                      width: `${pct}%`,
                      height: "100%",
                      backgroundColor: item.risk_tier === "high" ? "var(--color-danger)" : item.risk_tier === "medium" ? "var(--color-warning)" : "var(--color-success)",
                    },
                  })
                )
              )
            ),
            h("td", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" } }, item.ccn_max.toString()),
            h("td", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" } }, item.loc.toString()),
            h("td", null,
              h("div", { style: { display: "flex", flexWrap: "wrap", gap: "var(--space-1)" } },
                (item.drivers || []).map((d) => h("span", { className: "badge badge-neutral", style: { fontSize: "10px" } }, d))
              )
            )
          );
          tbody.appendChild(tr);
        }

        table.appendChild(thead);
        table.appendChild(tbody);
        tableWrapper.appendChild(table);
      }

      renderTable();

    } catch (err) {
      container.textContent = "";
      if (err.code === "MODEL_NOT_TRAINED" || err.status === 503) {
        container.appendChild(
          h("div", { className: "empty-state" },
            h("div", { className: "empty-icon", style: { color: "var(--color-warning)", marginBottom: "var(--space-3)" } }, icons.alertCircle()),
            h("h3", { style: { fontSize: "var(--text-lg)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-2)" } }, "Bug Risk Model Not Trained"),
            h("p", { className: "text-muted", style: { marginBottom: "var(--space-4)" } }, "The bug risk classification model artifact is not available. Run the offline training command to generate artifacts:"),
            h("code", { style: { display: "block", padding: "var(--space-3)", backgroundColor: "var(--color-bg-subtle)", borderRadius: "var(--radius-md)", fontFamily: "var(--font-mono)", marginBottom: "var(--space-4)" } }, "python backend/app/ml/train_bug.py"),
            h("a", { href: "#/models", className: "btn btn-secondary" }, "View Model Performance")
          )
        );
      } else {
        container.appendChild(
          h("div", { className: "empty-state" },
            h("div", { className: "empty-icon", style: { color: "var(--color-danger)", marginBottom: "var(--space-3)" } }, icons.alertCircle()),
            h("h3", { style: { fontSize: "var(--text-lg)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-2)" } }, "Failed to load bug predictions"),
            h("p", { className: "text-muted", style: { marginBottom: "var(--space-4)" } }, err.message || "An unexpected error occurred."),
            h("button", { className: "btn btn-secondary", onClick: loadData }, "Retry")
          )
        );
      }
    }
  }

  const unsubscribe = subscribe(loadData);
  loadData();

  return {
    element: container,
    destroy: () => unsubscribe(),
  };
}

const bugsPage = {
  title: "Bug Prediction",
  instance: null,
  async mount(ctx) {
    this.instance = renderBugsPage();
    ctx.container.replaceChildren(this.instance.element);
  },
  unmount() {
    if (this.instance && typeof this.instance.destroy === "function") {
      this.instance.destroy();
      this.instance = null;
    }
  },
};

export default bugsPage;
