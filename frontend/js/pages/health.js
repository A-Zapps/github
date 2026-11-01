/**
 * Repository Health Page (F5).
 * 4-class lifecycle tier prediction, class probabilities, signals table, and archetype clusters.
 */

import { api } from "../api.js";
import { state, subscribe } from "../state.js";
import { h } from "../ui/h.js";
import { icons } from "../ui/icons.js";

function getHealthClassBadge(cls) {
  const c = (cls || "Moderately Active").toLowerCase();
  if (c.includes("healthy")) {
    return h("span", { className: "badge badge-success", style: { fontSize: "var(--text-md)", padding: "var(--space-2) var(--space-4)" } }, "HEALTHY");
  }
  if (c.includes("moderate")) {
    return h("span", { className: "badge badge-neutral", style: { fontSize: "var(--text-md)", padding: "var(--space-2) var(--space-4)", backgroundColor: "var(--color-primary-light)", color: "var(--color-primary)" } }, "MODERATELY ACTIVE");
  }
  if (c.includes("declin")) {
    return h("span", { className: "badge badge-warning", style: { fontSize: "var(--text-md)", padding: "var(--space-2) var(--space-4)" } }, "DECLINING");
  }
  return h("span", { className: "badge badge-danger", style: { fontSize: "var(--text-md)", padding: "var(--space-2) var(--space-4)" } }, "INACTIVE");
}

export default function renderHealthPage() {
  const container = h("div", { className: "page-container" });

  async function loadData() {
    container.textContent = "";

    const analysisId = state.activeAnalysisId;
    if (!analysisId) {
      container.appendChild(
        h("div", { className: "empty-state" },
          h("div", { className: "empty-icon", style: { color: "var(--color-fg-muted)", marginBottom: "var(--space-3)" } }, icons.heart()),
          h("h3", { style: { fontSize: "var(--text-lg)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-2)" } }, "No analysis selected"),
          h("p", { className: "text-muted", style: { marginBottom: "var(--space-4)" } }, "Select or analyze a GitHub repository first to view lifecycle health diagnostics."),
          h("a", { href: "#/analyzer", className: "btn btn-primary" }, "Go to Repository Analyzer")
        )
      );
      return;
    }

    container.appendChild(
      h("div", { className: "empty-state" },
        h("div", { className: "spinner", style: { margin: "0 auto var(--space-3) auto" } }),
        h("p", { className: "text-muted" }, "Assessing repository lifecycle health and activity dynamics...")
      )
    );

    try {
      const resp = await api.getHealthData(analysisId);
      const data = resp.data;
      container.textContent = "";

      const health = data.health || {};
      const signals = data.signals || {};
      const clusters = data.clusters || {};
      const healthClass = health.health_class || "Moderately Active";
      const probs = health.probabilities || { "Healthy": 0.25, "Moderately Active": 0.25, "Declining": 0.25, "Inactive": 0.25 };
      const modelVer = health.model_version || "1.0.0";

      // 1. Header with Model Badge
      const header = h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "var(--space-6)" } },
        h("div", null,
          h("h2", { style: { fontSize: "var(--text-2xl)", fontWeight: "var(--font-bold)", marginBottom: "var(--space-1)" } }, "Repository Health"),
          h("p", { className: "text-muted" }, "Lifecycle classification evaluating sustained participation, commit velocity, and bus factor risks.")
        ),
        h("div", { style: { display: "flex", alignItems: "center", gap: "var(--space-2)" } },
          h("span", { className: "badge badge-neutral" }, "Model: repo_health"),
          h("span", { className: "badge badge-neutral" }, `v${modelVer}`)
        )
      );
      container.appendChild(header);

      // 2. Main Lifecycle Classification Hero Card
      const heroCard = h("div", { className: "card", style: { marginBottom: "var(--space-6)", padding: "var(--space-6)" } },
        h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-4)" } },
          h("div", null,
            h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase", marginBottom: "var(--space-1)" } }, "Lifecycle Classification"),
            getHealthClassBadge(healthClass)
          ),
          h("div", { style: { textAlign: "right" } },
            h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase" } }, "Confidence"),
            h("div", { style: { fontSize: "var(--text-2xl)", fontWeight: "var(--font-bold)", color: "var(--color-primary)" } },
              `${Math.round((probs[healthClass] || 0.5) * 100)}%`
            )
          )
        ),
        // Class Probabilities Breakdown Bars
        h("div", { style: { marginTop: "var(--space-4)" } },
          h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase", marginBottom: "var(--space-2)" } }, "Class Probabilities (Sums to 100%)"),
          h("div", { className: "grid grid-4", style: { gap: "var(--space-3)" } },
            Object.entries(probs).map(([cName, pVal]) => {
              const pct = Math.round(pVal * 100);
              return h("div", { style: { backgroundColor: "var(--color-bg-subtle)", padding: "var(--space-3)", borderRadius: "var(--radius-md)" } },
                h("div", { style: { display: "flex", justifyContent: "space-between", fontSize: "var(--text-xs)", marginBottom: "var(--space-1)" } },
                  h("span", { style: { fontWeight: cName === healthClass ? "var(--font-bold)" : "var(--font-normal)" } }, cName),
                  h("span", { style: { fontFamily: "var(--font-mono)" } }, `${pct}%`)
                ),
                h("div", { style: { height: "6px", backgroundColor: "var(--color-border)", borderRadius: "var(--radius-full)", overflow: "hidden" } },
                  h("div", {
                    style: {
                      width: `${pct}%`,
                      height: "100%",
                      backgroundColor: cName === healthClass ? "var(--color-primary)" : "var(--color-fg-muted)",
                    },
                  })
                )
              );
            })
          )
        )
      );
      container.appendChild(heroCard);

      // 3. Signals Table
      const signalsList = [
        {
          name: "Monthly Commit Velocity",
          value: `${signals.commits_per_month_mean || 0} commits / mo`,
          meaning: (signals.commits_per_month_mean || 0) >= 4 ? "Sustained active engineering velocity" : "Low development frequency",
        },
        {
          name: "Commit Velocity Momentum (Slope)",
          value: `${signals.commits_per_month_slope || 0}`,
          meaning: (signals.commits_per_month_slope || 0) >= 0 ? "Commit momentum is stable or accelerating" : "Declining activity trend over the recent 12 months",
        },
        {
          name: "Recent 3m vs Prior 9m Ratio",
          value: `${signals.last3m_to_prior9m_ratio || 0}`,
          meaning: (signals.last3m_to_prior9m_ratio || 0) >= 0.5 ? "Recent activity is on pace with annual baseline" : "Recent activity drop-off detected (< 50% baseline)",
        },
        {
          name: "Distinct Active Authors (12m)",
          value: `${signals.distinct_authors || 0} contributors`,
          meaning: (signals.distinct_authors || 0) >= 3 ? "Collaborative team development" : "Single-maintainer or low participation risk",
        },
        {
          name: "New Contributors Joined (3m)",
          value: `${signals.new_authors_3m || 0} new contributors`,
          meaning: (signals.new_authors_3m || 0) > 0 ? "Growing maintainer base" : "No new onboarding in the last quarter",
        },
        {
          name: "Days Since Last Commit",
          value: `${signals.days_since_last_commit || 0} days ago`,
          meaning: (signals.days_since_last_commit || 0) <= 30 ? "Actively maintained in the past month" : "Long period of silence (> 30 days)",
        },
        {
          name: "Project Bus Factor",
          value: `${signals.bus_factor || 1}`,
          meaning: (signals.bus_factor || 1) >= 3 ? "Resilient to individual contributor departure" : "Vulnerable: 1-2 authors make up > 50% of recent code changes",
        },
      ];

      const signalsCard = h("div", { className: "card", style: { padding: "0", overflow: "hidden", marginBottom: "var(--space-6)" } },
        h("div", { style: { padding: "var(--space-4)", borderBottom: "1px solid var(--color-border)" } },
          h("h3", { style: { fontSize: "var(--text-md)", fontWeight: "var(--font-semibold)" } }, "Lifecycle Activity Signals")
        ),
        h("table", { className: "table" },
          h("thead", null,
            h("tr", null,
              h("th", { style: { width: "260px" } }, "Signal"),
              h("th", { style: { width: "200px" } }, "Measured Value"),
              h("th", null, "Operational Interpretation")
            )
          ),
          h("tbody", null,
            signalsList.map((sig) =>
              h("tr", null,
                h("td", { style: { fontWeight: "var(--font-semibold)" } }, sig.name),
                h("td", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" } }, sig.value),
                h("td", { className: "text-muted" }, sig.meaning)
              )
            )
          )
        )
      );
      container.appendChild(signalsCard);

      // 4. Archetype Clustering & PCA Card
      if (clusters.cluster_id !== undefined) {
        const clusterNames = [
          "Small Utility / Script",
          "Rapidly Growing Project",
          "Large Mature Enterprise",
          "Legacy Maintenance",
        ];
        const archetypeName = clusterNames[clusters.cluster_id % 4] || `Archetype ${clusters.cluster_id}`;
        const pca = clusters.pca_coordinates || [0, 0];

        const clusterCard = h("div", { className: "card" },
          h("h3", { style: { fontSize: "var(--text-md)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-3)" } }, "Corpus Archetype & 2D Projection"),
          h("div", { className: "grid grid-2", style: { gap: "var(--space-4)" } },
            h("div", null,
              h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase" } }, "Assigned Cluster"),
              h("div", { style: { fontSize: "var(--text-lg)", fontWeight: "var(--font-bold)", marginTop: "var(--space-1)" } }, archetypeName),
              h("p", { className: "text-muted", style: { marginTop: "var(--space-2)", fontSize: "var(--text-xs)" } },
                "Unsupervised KMeans archetype assignment based on code scale, velocity, author distribution, and test coverage."
              )
            ),
            h("div", null,
              h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase" } }, "2D PCA Coordinates"),
              h("div", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--text-lg)", marginTop: "var(--space-1)" } },
                `[PC1: ${pca[0]}, PC2: ${pca[1]}]`
              ),
              h("p", { className: "text-muted", style: { marginTop: "var(--space-2)", fontSize: "var(--text-xs)" } },
                "Dimensionality reduction mapping this repository relative to the multi-repo corpus."
              )
            )
          )
        );
        container.appendChild(clusterCard);
      }

    } catch (err) {
      container.textContent = "";
      if (err.code === "MODEL_NOT_TRAINED" || err.status === 503) {
        container.appendChild(
          h("div", { className: "empty-state" },
            h("div", { className: "empty-icon", style: { color: "var(--color-warning)", marginBottom: "var(--space-3)" } }, icons.alertCircle()),
            h("h3", { style: { fontSize: "var(--text-lg)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-2)" } }, "Repo Health Model Not Trained"),
            h("p", { className: "text-muted", style: { marginBottom: "var(--space-4)" } }, "The repository health model artifact is not available. Run the offline training command:"),
            h("code", { style: { display: "block", padding: "var(--space-3)", backgroundColor: "var(--color-bg-subtle)", borderRadius: "var(--radius-md)", fontFamily: "var(--font-mono)", marginBottom: "var(--space-4)" } }, "python backend/app/ml/train_health.py"),
            h("a", { href: "#/models", className: "btn btn-secondary" }, "View Model Performance")
          )
        );
      } else {
        container.appendChild(
          h("div", { className: "empty-state" },
            h("div", { className: "empty-icon", style: { color: "var(--color-danger)", marginBottom: "var(--space-3)" } }, icons.alertCircle()),
            h("h3", { style: { fontSize: "var(--text-lg)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-2)" } }, "Failed to load repository health"),
            h("p", { className: "text-muted", style: { marginBottom: "var(--space-4)" } }, err.message || "An unexpected error occurred."),
            h("button", { className: "btn btn-secondary", onClick: loadData }, "Retry")
          )
        );
      }
    }
  }

  const unsubscribe = subscribe(loadData);
  loadData();

const healthPage = {
  title: "Repository Health",
  instance: null,
  async mount(ctx) {
    this.instance = renderHealthPage();
    ctx.container.replaceChildren(this.instance.element);
  },
  unmount() {
    if (this.instance && typeof this.instance.destroy === "function") {
      this.instance.destroy();
      this.instance = null;
    }
  },
};

export default healthPage;
