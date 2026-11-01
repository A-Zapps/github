/**
 * Model Performance Page (T4.5).
 * Inspects all 5 machine learning models, compares metrics against honest baselines,
 * shows training manifests, and renders model cards (RULES D5, D6, D11).
 */

import { api } from "../api.js";
import { h } from "../ui/h.js";
import { icons } from "../ui/icons.js";

function renderModelPerformancePage() {
  const container = h("div", { className: "page-container" });
  let expandedCard = null; // model name of currently viewed model card

  async function loadData() {
    container.textContent = "";

    // Loading state
    container.appendChild(
      h("div", { className: "empty-state" },
        h("div", { className: "spinner", style: { margin: "0 auto var(--space-3) auto" } }),
        h("p", { className: "text-muted" }, "Loading machine learning model registry and validation metrics...")
      )
    );

    try {
      const resp = await api.getModels();
      const models = resp.data || [];
      container.textContent = "";

      // 1. Header
      const header = h("div", { style: { marginBottom: "var(--space-6)" } },
        h("h2", { style: { fontSize: "var(--text-2xl)", fontWeight: "var(--font-bold)", marginBottom: "var(--space-1)" } }, "Model Performance"),
        h("p", { className: "text-muted" }, "Honest evaluation metrics reported alongside naive and heuristic baselines on held-out evaluation splits.")
      );
      container.appendChild(header);

      if (models.length === 0) {
        container.appendChild(
          h("div", { className: "empty-state" },
            h("p", { className: "text-muted" }, "No models registered.")
          )
        );
        return;
      }

      // 2. Render each model card
      const listContainer = h("div", { style: { display: "flex", flexDirection: "column", gap: "var(--space-6)" } });

      for (const m of models) {
        const isTrained = m.trained && m.status === "ready";
        const metrics = m.metrics || {};
        const manifest = m.manifest || {};
        const cardMd = m.model_card || "";

        const card = h("div", { className: "card", style: { padding: "var(--space-6)" } });

        // Card Header
        const cardHeader = h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "var(--space-4)" } },
          h("div", null,
            h("div", { style: { display: "flex", alignItems: "center", gap: "var(--space-2)" } },
              h("h3", { style: { fontSize: "var(--text-lg)", fontWeight: "var(--font-bold)" } }, m.name),
              isTrained
                ? h("span", { className: "badge badge-success" }, "TRAINED")
                : h("span", { className: "badge badge-warning" }, "NOT TRAINED")
            ),
            h("p", { className: "text-muted", style: { fontSize: "var(--text-xs)", marginTop: "var(--space-1)" } },
              metrics.task ? `Task: ${metrics.task}` : "Model artifact details"
            )
          ),
          h("div", { style: { textAlign: "right" } },
            isTrained && metrics.best_model
              ? h("span", { className: "badge badge-neutral" }, `Best: ${metrics.best_model}`)
              : null
          )
        );
        card.appendChild(cardHeader);

        if (!isTrained) {
          // Untrained State Card
          const runCmd = `python backend/app/ml/train_${m.name.replace("_effort", "").replace("_sections", "").replace("repo_", "")}.py`;
          card.appendChild(
            h("div", { style: { backgroundColor: "var(--color-bg-subtle)", padding: "var(--space-4)", borderRadius: "var(--radius-md)" } },
              h("p", { style: { fontSize: "var(--text-sm)", marginBottom: "var(--space-2)" } },
                "This model has not been trained yet. Execute the offline pipeline to build dataset and fit models:"
              ),
              h("code", { style: { display: "block", padding: "var(--space-2)", backgroundColor: "var(--color-bg-canvas)", borderRadius: "var(--radius-sm)", fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" } },
                runCmd
              )
            )
          );
        } else {
          // Trained Metrics Display
          const statsRow = h("div", { className: "grid grid-3", style: { gap: "var(--space-3)", marginBottom: "var(--space-4)" } },
            h("div", { style: { backgroundColor: "var(--color-bg-subtle)", padding: "var(--space-3)", borderRadius: "var(--radius-md)" } },
              h("div", { className: "text-muted", style: { fontSize: "10px", textTransform: "uppercase" } }, "Training Samples"),
              h("div", { style: { fontSize: "var(--text-md)", fontWeight: "var(--font-semibold)", marginTop: "2px" } }, (metrics.training_rows || metrics.n_samples || 0).toString())
            ),
            h("div", { style: { backgroundColor: "var(--color-bg-subtle)", padding: "var(--space-3)", borderRadius: "var(--radius-md)" } },
              h("div", { className: "text-muted", style: { fontSize: "10px", textTransform: "uppercase" } }, "Held-out Test Rows"),
              h("div", { style: { fontSize: "var(--text-md)", fontWeight: "var(--font-semibold)", marginTop: "2px" } }, (metrics.held_out_test_rows || "N/A").toString())
            ),
            h("div", { style: { backgroundColor: "var(--color-bg-subtle)", padding: "var(--space-3)", borderRadius: "var(--radius-md)" } },
              h("div", { className: "text-muted", style: { fontSize: "10px", textTransform: "uppercase" } }, "Random Seed"),
              h("div", { style: { fontSize: "var(--text-md)", fontWeight: "var(--font-semibold)", marginTop: "2px", fontFamily: "var(--font-mono)" } }, (manifest.seed || 42).toString())
            )
          );
          card.appendChild(statsRow);

          // Metrics comparison vs baselines
          if (metrics.models || metrics.baselines) {
            const table = h("table", { className: "table", style: { marginBottom: "var(--space-4)" } },
              h("thead", null,
                h("tr", null,
                  h("th", null, "Model / Baseline"),
                  h("th", { style: { width: "120px" } }, "Type"),
                  h("th", { style: { width: "160px" } }, "Primary Metric"),
                  h("th", null, "Notes")
                )
              ),
              h("tbody", null,
                // Baselines first
                Object.entries(metrics.baselines || {}).map(([bName, bData]) =>
                  h("tr", { style: { backgroundColor: "var(--color-bg-subtle)" } },
                    h("td", { style: { fontWeight: "var(--font-semibold)" } }, bName),
                    h("td", null, h("span", { className: "badge badge-neutral" }, "BASELINE")),
                    h("td", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" } },
                      bData.pr_auc !== undefined ? `PR-AUC: ${bData.pr_auc}` : bData.macro_f1 !== undefined ? `F1: ${bData.macro_f1}` : JSON.stringify(bData)
                    ),
                    h("td", { className: "text-muted", style: { fontSize: "var(--text-xs)" } }, bData.rule || bData.note || "Deterministic baseline")
                  )
                ),
                // Models
                Object.entries(metrics.models || {}).map(([modName, modData]) => {
                  const isBaseline = modName.toLowerCase().includes("baseline");
                  const isBest = modName === metrics.best_model;
                  return h("tr", null,
                    h("td", { style: { fontWeight: isBest ? "var(--font-bold)" : "var(--font-normal)" } },
                      modName + (isBest ? " ★ (Selected)" : "")
                    ),
                    h("td", null,
                      isBaseline
                        ? h("span", { className: "badge badge-neutral" }, "BASELINE")
                        : isBest
                        ? h("span", { className: "badge badge-success" }, "CHAMPION")
                        : h("span", { className: "badge badge-neutral" }, "CANDIDATE")
                    ),
                    h("td", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" } },
                      modData.pr_auc !== undefined ? `PR-AUC: ${modData.pr_auc}` :
                      modData.macro_f1 !== undefined ? `F1: ${modData.macro_f1}` :
                      modData.mae !== undefined ? `MAE: ${modData.mae}` :
                      modData.accuracy !== undefined ? `Acc: ${modData.accuracy}` : JSON.stringify(modData)
                    ),
                    h("td", { className: "text-muted", style: { fontSize: "var(--text-xs)" } },
                      modData.note || (modData.roc_auc !== undefined ? `ROC-AUC: ${modData.roc_auc}` : "")
                    )
                  );
                })
              )
            );
            card.appendChild(table);
          }

          // Toggle Model Card Button
          if (cardMd) {
            const isExpanded = expandedCard === m.name;
            const toggleBtn = h("button", {
              className: "btn btn-secondary",
              style: { fontSize: "var(--text-xs)", marginBottom: "var(--space-2)" },
              onClick: () => {
                expandedCard = isExpanded ? null : m.name;
                loadData();
              },
            }, isExpanded ? "Hide Model Card ▲" : "View Model Card & Documentation ▼");
            card.appendChild(toggleBtn);

            if (isExpanded) {
              const cardBox = h("pre", {
                style: {
                  backgroundColor: "var(--color-bg-subtle)",
                  padding: "var(--space-4)",
                  borderRadius: "var(--radius-md)",
                  fontFamily: "var(--font-mono)",
                  fontSize: "var(--text-xs)",
                  whiteSpace: "pre-wrap",
                  lineHeight: "1.5",
                  marginTop: "var(--space-2)",
                },
              }, cardMd);
              card.appendChild(cardBox);
            }
          }
        }

        listContainer.appendChild(card);
      }

      container.appendChild(listContainer);

    } catch (err) {
      container.textContent = "";
      container.appendChild(
        h("div", { className: "empty-state" },
          h("div", { className: "empty-icon", style: { color: "var(--color-danger)", marginBottom: "var(--space-3)" } }, icons.alertCircle()),
          h("h3", { style: { fontSize: "var(--text-lg)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-2)" } }, "Failed to load model registry"),
          h("p", { className: "text-muted", style: { marginBottom: "var(--space-4)" } }, err.message || "An unexpected error occurred."),
          h("button", { className: "btn btn-secondary", onClick: loadData }, "Retry")
        )
      );
    }
  }

  loadData();

  return {
    element: container,
    destroy: () => {},
  };
}

const modelPerformancePage = {
  title: "Model Performance",
  instance: null,
  async mount(ctx) {
    this.instance = renderModelPerformancePage();
    ctx.container.replaceChildren(this.instance.element);
  },
  unmount() {
    if (this.instance && typeof this.instance.destroy === "function") {
      this.instance.destroy();
      this.instance = null;
    }
  },
};

export default modelPerformancePage;
