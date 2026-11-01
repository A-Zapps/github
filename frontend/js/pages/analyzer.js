/**
 * Repository Analyzer view (F1): input, stage stepper, stats, charts, and README.
 */

import { api, ApiError } from "../api.js";
import { state } from "../state.js";
import { createBarChart, createDonutChart, makeChartContainer } from "../ui/charts.js";
import { h } from "../ui/h.js";
import { icons } from "../ui/icons.js";

const STAGES = [
  { id: "resolve", label: "Resolve Repository & Branch" },
  { id: "metadata", label: "Ingest Issues, PRs & Commits" },
  { id: "completed", label: "Analysis Completed" },
];

export default {
  title: "Repository Analyzer",
  charts: [],

  async mount(ctx) {
    this.container = ctx.container;
    this.render();

    // If an analysis ID exists in state, load its data automatically
    if (state.currentAnalysisId) {
      await this.loadAnalysisData(state.currentAnalysisId);
    }
  },

  unmount() {
    this.destroyCharts();
  },

  destroyCharts() {
    this.charts.forEach((c) => {
      try {
        c.destroy();
      } catch (e) {}
    });
    this.charts = [];
  },

  render() {
    this.destroyCharts();
    this.container.replaceChildren();

    // 1. Analyze Input Card
    const inputField = h("input", {
      type: "text",
      placeholder: "e.g. pallets/flask or https://github.com/pallets/flask",
      className: "btn-secondary",
      style: { flex: "1", padding: "0 12px", height: "36px", borderRadius: "6px" },
    });

    const submitBtn = h("button", { className: "btn btn-primary" }, "Analyze Repository");
    const errorBanner = h("div", {
      className: "badge badge-danger",
      style: { display: "none", padding: "8px 12px", width: "100%", justifyContent: "flex-start" },
    });

    submitBtn.addEventListener("click", async () => {
      const val = inputField.value.trim();
      if (!val) return;
      errorBanner.style.display = "none";
      submitBtn.disabled = true;
      submitBtn.textContent = "Submitting...";

      try {
        const res = await api.postAnalysis(val);
        const { analysis_id, job_id, repo } = res.data;
        state.setAnalysis(analysis_id, repo);
        await this.pollJob(job_id, analysis_id, repo);
      } catch (err) {
        errorBanner.textContent = err.message || "Failed to enqueue analysis.";
        errorBanner.style.display = "flex";
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Analyze Repository";
      }
    });

    inputField.addEventListener("keydown", (e) => {
      if (e.key === "Enter") submitBtn.click();
    });

    const inputCard = h("div", { className: "card" },
      h("h3", { className: "card-title" }, "Analyze a GitHub Repository"),
      errorBanner,
      h("div", { style: { display: "flex", gap: "8px" } }, inputField, submitBtn)
    );

    // 2. Stepper Card (hidden by default)
    this.stepperContainer = h("div", { className: "card", style: { display: "none" } });

    // 3. Results Container
    this.resultsContainer = h("div", { style: { display: "flex", flexDirection: "column", gap: "24px" } });

    this.container.appendChild(inputCard);
    this.container.appendChild(this.stepperContainer);
    this.container.appendChild(this.resultsContainer);

    if (!state.currentAnalysisId) {
      this.resultsContainer.appendChild(
        h("div", { className: "card" },
          h("div", { className: "empty-state" },
            h("div", { className: "empty-state-icon" }, icons.analyzer(24)),
            h("h3", { className: "empty-state-title" }, "No Repository Analyzed Yet"),
            h("p", { className: "empty-state-desc" }, "Enter a public GitHub repository name or URL above to begin real-time analysis.")
          )
        )
      );
    }
  },

  async pollJob(jobId, analysisId, repoName) {
    this.stepperContainer.style.display = "flex";
    this.resultsContainer.replaceChildren();

    const updateStepperUI = (activeStage, status) => {
      const stepsNodes = STAGES.map((st) => {
        let icon = icons.info(16);
        let statusText = "Pending";
        let badgeClass = "badge-neutral";

        if (st.id === activeStage && status === "running") {
          statusText = "Running...";
          badgeClass = "badge-info";
        } else if (status === "succeeded" || (st.id === "resolve" && activeStage !== "resolve")) {
          statusText = "Completed";
          badgeClass = "badge-success";
        } else if (status === "failed") {
          statusText = "Failed";
          badgeClass = "badge-danger";
        }

        return h("div", { style: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 0" } },
          h("span", { style: { fontWeight: "500" } }, st.label),
          h("span", { className: `badge ${badgeClass}` }, statusText)
        );
      });

      this.stepperContainer.replaceChildren(
        h("h3", { className: "card-title" }, `Analyzing ${repoName}...`),
        ...stepsNodes
      );
    };

    while (true) {
      try {
        const res = await api.getJob(jobId);
        const job = res.data;
        updateStepperUI(job.stage, job.status);

        if (job.status === "succeeded") {
          await this.loadAnalysisData(analysisId);
          break;
        } else if (job.status === "failed" || job.status === "cancelled") {
          this.stepperContainer.appendChild(
            h("div", { className: "badge badge-danger", style: { marginTop: "12px", padding: "8px" } },
              job.error_message || "Analysis failed."
            )
          );
          break;
        }
      } catch (e) {
        console.error("Polling error:", e);
      }
      await new Promise((r) => setTimeout(r, 1500));
    }
  },

  async loadAnalysisData(analysisId) {
    this.destroyCharts();
    this.resultsContainer.replaceChildren(
      h("div", { className: "card" },
        h("div", { className: "empty-state" },
          h("p", { className: "empty-state-desc" }, "Loading repository analysis...")
        )
      )
    );

    try {
      const res = await api.getRepositoryData(analysisId);
      const data = res.data;
      this.renderResults(data);
    } catch (err) {
      this.resultsContainer.replaceChildren(
        h("div", { className: "card" },
          h("div", { className: "empty-state" },
            h("h3", { className: "empty-state-title" }, "Analysis Results Unavailable"),
            h("p", { className: "empty-state-desc" }, err.message)
          )
        )
      );
    }
  },

  renderResults(data) {
    this.destroyCharts();
    this.resultsContainer.replaceChildren();

    // 1. Repo Metadata Card
    const metaCard = h("div", { className: "card" },
      h("div", { className: "card-header" },
        h("h2", { style: { fontSize: "18px", fontWeight: "600" } }, data.full_name),
        h("span", { className: "badge badge-info" }, data.license || "No License")
      ),
      h("p", { style: { color: "var(--text-2)", fontSize: "14px" } }, data.description || "No description provided."),
      h("div", { style: { display: "flex", gap: "16px", fontSize: "12px", color: "var(--text-2)" } },
        h("span", {}, `Default Branch: ${data.default_branch}`),
        h("span", {}, `Size: ${Math.round(data.size_kb / 1024)} MB`)
      )
    );

    // 2. Stats Grid
    const statCards = [
      { label: "Stars", value: data.stars.toLocaleString() },
      { label: "Forks", value: data.forks.toLocaleString() },
      { label: "Open Issues", value: data.open_issues.toLocaleString() },
      { label: "Contributors", value: data.contributors_count.toLocaleString() },
    ].map((s) => h("div", { className: "card", style: { padding: "16px" } },
      h("span", { className: "text-caption" }, s.label),
      h("span", { style: { fontSize: "24px", fontWeight: "600", marginTop: "4px" } }, s.value)
    ));

    const statsGrid = h("div", {
      style: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "16px" }
    }, ...statCards);

    // 3. Languages Donut Chart
    const langLabels = Object.keys(data.languages || {});
    const langValues = Object.values(data.languages || {});
    const langCanvas = h("canvas");

    const langTable = h("table", { style: { width: "100%", fontSize: "13px", borderCollapse: "collapse" } },
      h("thead", {},
        h("tr", { style: { textAlign: "left", color: "var(--text-2)", borderBottom: "1px solid var(--border)" } },
          h("th", { style: { padding: "6px" } }, "Language"),
          h("th", { style: { padding: "6px", textAlign: "right" } }, "Share")
        )
      ),
      h("tbody", {},
        ...langLabels.map((l, i) => h("tr", { style: { borderBottom: "1px solid var(--border)" } },
          h("td", { style: { padding: "6px" } }, l),
          h("td", { style: { padding: "6px", textAlign: "right" } }, `${langValues[i]}%`)
        ))
      )
    );

    const langContainer = makeChartContainer("Languages Breakdown", langCanvas, langTable);

    // 4. Commits Bar Chart (52 weeks)
    const commitLabels = (data.commit_activity_52w || []).map((_, i) => `W${i + 1}`);
    const commitValues = (data.commit_activity_52w || []).map((w) => w.total || 0);
    const commitCanvas = h("canvas");

    const commitTable = h("table", { style: { width: "100%", fontSize: "13px", borderCollapse: "collapse" } },
      h("thead", {},
        h("tr", { style: { textAlign: "left", color: "var(--text-2)", borderBottom: "1px solid var(--border)" } },
          h("th", { style: { padding: "6px" } }, "Week"),
          h("th", { style: { padding: "6px", textAlign: "right" } }, "Commits")
        )
      ),
      h("tbody", {},
        ...commitLabels.map((w, i) => h("tr", { style: { borderBottom: "1px solid var(--border)" } },
          h("td", { style: { padding: "6px" } }, w),
          h("td", { style: { padding: "6px", textAlign: "right" } }, commitValues[i])
        ))
      )
    );

    const commitContainer = makeChartContainer("Weekly Commit Velocity (52 Weeks)", commitCanvas, commitTable);

    const chartsGrid = h("div", {
      style: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "16px" }
    }, langContainer, commitContainer);

    // 5. Plaintext README Preview (XSS safe via textContent)
    const readmeCard = h("div", { className: "card" },
      h("h3", { className: "card-title" }, `README Preview (${data.readme?.path || "README.md"})`),
      h("pre", {
        className: "font-mono",
        style: {
          backgroundColor: "var(--bg)",
          padding: "16px",
          borderRadius: "6px",
          maxHeight: "360px",
          overflow: "auto",
          fontSize: "13px",
          whiteSpace: "pre-wrap",
          lineHeight: "1.5",
        },
      }, data.readme?.content || "No README content found.")
    );

    this.resultsContainer.appendChild(metaCard);
    this.resultsContainer.appendChild(statsGrid);
    this.resultsContainer.appendChild(chartsGrid);
    this.resultsContainer.appendChild(readmeCard);

    // Render charts
    const donut = createDonutChart(langCanvas, langLabels, langValues, "Percentage");
    if (donut) this.charts.push(donut);

    const bar = createBarChart(commitCanvas, commitLabels, commitValues, "Commits");
    if (bar) this.charts.push(bar);
  },
};
