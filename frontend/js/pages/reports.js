/**
 * Reports page (T8.3, ARCHITECTURE 12, DESIGN.md).
 * Features:
 * - Generate PDF report button
 * - Report history table with direct download links
 * - Executive metrics preview matching the PDF exactly
 * - Four states (loading, empty, error, loaded)
 */

import { api } from "../api.js";
import { state } from "../state.js";
import { h } from "../ui/h.js";
import { renderSkeleton } from "../ui/skeleton.js";
import { showToast } from "../ui/toast.js";

export default {
  title: "Executive Reports",

  async mount(container) {
    container.innerHTML = "";
    const analysisId = state.get("analysisId");

    if (!analysisId) {
      container.appendChild(
        h(
          "div",
          { class: "empty-state p-8 text-center" },
          h("h3", { class: "text-lg font-semibold mb-2" }, "No Repository Selected"),
          h("p", { class: "text-neutral-500 mb-4" }, "Select or analyze a GitHub repository to generate executive PDF reports."),
          h("a", { href: "#/analyzer", class: "btn btn-primary" }, "Go to Analyzer")
        )
      );
      return;
    }

    container.appendChild(renderSkeleton("card", 2));

    try {
      const [reportsResp, qualityResp, secResp, devResp] = await Promise.all([
        api.getReports(analysisId),
        api.getQualityData(analysisId).catch(() => ({ data: {} })),
        api.getSecurityData(analysisId).catch(() => ({ data: {} })),
        api.getDeveloperData(analysisId).catch(() => ({ data: {} })),
      ]);

      const reportsList = reportsResp.data || [];
      const qualityData = qualityResp.data || {};
      const secData = secResp.data || {};
      const devData = devResp.data || {};

      container.innerHTML = "";
      renderReportsView(container, analysisId, reportsList, qualityData, secData, devData);
    } catch (err) {
      container.innerHTML = "";
      container.appendChild(
        h(
          "div",
          { class: "p-8 text-center" },
          h("p", { class: "text-red-400 mb-4" }, `Failed to load reports: ${err.message}`),
          h("button", { class: "btn btn-outline", onclick: () => this.mount(container) }, "Retry")
        )
      );
    }
  },

  unmount() {},
};

function renderReportsView(container, analysisId, reportsList, qualityData, secData, devData) {
  // Top Header Banner
  const headerCard = h(
    "div",
    { class: "card p-6 mb-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4" },
    h("div", { class: "flex flex-col gap-1" },
      h("h3", { class: "text-base font-semibold text-neutral-100" }, "Enterprise Executive PDF Export"),
      h("p", { class: "text-xs text-neutral-400" },
        "Compile comprehensive multi-page PDF reports containing quality scores, defect risk models, security findings, developer metrics, and full audit logs."
      )
    ),
    h(
      "button",
      {
        id: "btn-generate-report",
        class: "btn btn-primary px-4 py-2 text-xs font-semibold whitespace-nowrap flex items-center gap-2",
        onclick: async (e) => {
          const btn = e.target;
          btn.disabled = true;
          btn.textContent = "Compiling PDF...";
          try {
            const res = await api.postGenerateReport(analysisId);
            showToast("PDF report generated successfully!", "success");
            // Reload page to reflect new report
            const reports = await api.getReports(analysisId);
            updateReportsTable(reports.data || []);
          } catch (err) {
            showToast(`Report generation failed: ${err.message}`, "error");
          } finally {
            btn.disabled = false;
            btn.textContent = "Generate Executive PDF";
          }
        },
      },
      "Generate Executive PDF"
    )
  );

  // Executive Preview Cards (matching PDF numbers)
  const score = qualityData.overall_score ?? "-";
  const debt = qualityData.tech_debt_hours ?? "-";
  const issues = secData.total_issues ?? 0;
  const busFactor = devData.bus_factor ?? "-";

  const previewRow = h(
    "div",
    { class: "grid grid-cols-2 md:grid-cols-4 gap-4 mb-6" },
    renderMetricTile("Overall Quality", `${score}/100`, "Composite score across 6 categories"),
    renderMetricTile("Tech Debt Estimate", `${debt}h`, "Estimated remediation time"),
    renderMetricTile("Security Issues", `${issues}`, "Vulnerabilities & secret exposures"),
    renderMetricTile("Bus Factor", `${busFactor} devs`, "Contributors carrying 50%+ commits")
  );

  // Reports History Table Card
  const tableContainer = h("div", { id: "reports-table-wrapper" });
  const reportsCard = h(
    "div",
    { class: "card p-6" },
    h("h4", { class: "text-sm font-semibold mb-4 text-neutral-200" }, "Generated Reports History"),
    tableContainer
  );

  container.appendChild(headerCard);
  container.appendChild(previewRow);
  container.appendChild(reportsCard);

  updateReportsTable(reportsList);

  function updateReportsTable(list) {
    tableContainer.innerHTML = "";
    if (list.length === 0) {
      tableContainer.appendChild(
        h(
          "div",
          { class: "p-8 text-center text-xs text-neutral-500 border border-neutral-800/60 rounded-lg" },
          "No reports generated yet for this analysis. Click 'Generate Executive PDF' above to create one."
        )
      );
      return;
    }

    const rows = list.map((r) =>
      h(
        "tr",
        { class: "border-b border-neutral-800/50 hover:bg-neutral-800/30 transition-colors" },
        h("td", { class: "py-3 px-4 font-mono text-xs text-neutral-200" }, r.filename),
        h("td", { class: "py-3 px-4 text-xs text-neutral-400" }, r.created_at ? new Date(r.created_at).toLocaleString() : "-"),
        h("td", { class: "py-3 px-4 text-right" },
          h(
            "a",
            {
              href: r.download_url,
              download: r.filename,
              class: "btn btn-outline text-xs py-1 px-3",
              target: "_blank",
            },
            "Download PDF"
          )
        )
      )
    );

    const table = h(
      "table",
      { class: "w-full text-left text-xs" },
      h(
        "thead",
        { class: "border-b border-neutral-800 text-neutral-400 uppercase text-[10px] tracking-wider font-mono" },
        h("tr", {},
          h("th", { class: "py-2 px-4" }, "Report Filename"),
          h("th", { class: "py-2 px-4" }, "Created At"),
          h("th", { class: "py-2 px-4 text-right" }, "Action")
        )
      ),
      h("tbody", {}, ...rows)
    );

    tableContainer.appendChild(table);
  }
}

function renderMetricTile(label, value, caption) {
  return h(
    "div",
    { class: "card p-4 flex flex-col gap-1 border border-neutral-800/60" },
    h("span", { class: "text-[11px] text-neutral-400 uppercase tracking-wider font-mono" }, label),
    h("span", { class: "text-2xl font-bold text-neutral-100 font-mono my-1" }, value),
    h("span", { class: "text-[10px] text-neutral-500" }, caption)
  );
}
