/**
 * Security Analysis Page (F3).
 * Displays severity breakdown, code security findings (Bandit/Semgrep),
 * masked exposed secrets (RULES B7: max 4 chars + ****), and vulnerable dependencies (OSV).
 */

import { api } from "../api.js";
import { state, subscribe } from "../state.js";
import { h } from "../ui/h.js";
import { icons } from "../ui/icons.js";

function getSeverityBadge(severity) {
  const sev = (severity || "LOW").toUpperCase();
  switch (sev) {
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

function renderSecurityPage() {
  const container = h("div", { className: "page-container" });
  let activeTab = "code"; // "code" | "secrets" | "deps"

  async function loadData() {
    container.textContent = "";

    const analysisId = state.activeAnalysisId;
    if (!analysisId) {
      container.appendChild(
        h("div", { className: "empty-state" },
          h("div", { className: "empty-icon", style: { color: "var(--color-fg-muted)", marginBottom: "var(--space-3)" } }, icons.shield()),
          h("h3", { style: { fontSize: "var(--text-lg)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-2)" } }, "No analysis selected"),
          h("p", { className: "text-muted", style: { marginBottom: "var(--space-4)" } }, "Analyze a GitHub repository first to view security scans and vulnerability assessments."),
          h("a", { href: "#/analyzer", className: "btn btn-primary" }, "Go to Repository Analyzer")
        )
      );
      return;
    }

    // Loading state
    container.appendChild(
      h("div", { className: "empty-state" },
        h("div", { className: "spinner", style: { margin: "0 auto var(--space-3) auto" } }),
        h("p", { className: "text-muted" }, "Scanning security findings and dependencies...")
      )
    );

    try {
      const resp = await api.getSecurityData(analysisId);
      const data = resp.data;
      container.textContent = "";

      // 1. Header
      const header = h("div", { style: { marginBottom: "var(--space-6)" } },
        h("div", { style: { display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "var(--space-3)" } },
          h("div", {},
            h("h2", { style: { fontSize: "var(--text-2xl)", fontWeight: "var(--font-bold)", color: "var(--color-fg-default)" } }, "Security Analysis"),
            h("p", { className: "text-muted", style: { fontSize: "var(--text-sm)" } }, `Repository: ${state.activeRepo || "Active Repository"} (Analysis #${analysisId})`)
          ),
          h("div", { className: "badge badge-neutral" }, `Generated: ${new Date(resp.meta.generated_at).toLocaleTimeString()}`)
        )
      );
      container.appendChild(header);

      // 2. Severity Summary Bar
      const summary = data.severity_summary || { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
      const severityGrid = h("div", { className: "grid grid-cols-4", style: { gap: "var(--space-4)", marginBottom: "var(--space-6)" } },
        h("div", { className: "card", style: { padding: "var(--space-4)", borderLeft: "4px solid #CF3A3A" } },
          h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase", fontWeight: "var(--font-semibold)" } }, "Critical"),
          h("div", { style: { fontSize: "var(--text-2xl)", fontWeight: "var(--font-bold)", color: summary.CRITICAL > 0 ? "#CF3A3A" : "inherit" } }, `${summary.CRITICAL}`)
        ),
        h("div", { className: "card", style: { padding: "var(--space-4)", borderLeft: "4px solid #D97706" } },
          h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase", fontWeight: "var(--font-semibold)" } }, "High"),
          h("div", { style: { fontSize: "var(--text-2xl)", fontWeight: "var(--font-bold)", color: summary.HIGH > 0 ? "#D97706" : "inherit" } }, `${summary.HIGH}`)
        ),
        h("div", { className: "card", style: { padding: "var(--space-4)", borderLeft: "4px solid #F59E0B" } },
          h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase", fontWeight: "var(--font-semibold)" } }, "Medium"),
          h("div", { style: { fontSize: "var(--text-2xl)", fontWeight: "var(--font-bold)", color: summary.MEDIUM > 0 ? "#B25E09" : "inherit" } }, `${summary.MEDIUM}`)
        ),
        h("div", { className: "card", style: { padding: "var(--space-4)", borderLeft: "4px solid var(--color-primary)" } },
          h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase", fontWeight: "var(--font-semibold)" } }, "Low / Info"),
          h("div", { style: { fontSize: "var(--text-2xl)", fontWeight: "var(--font-bold)", color: "inherit" } }, `${summary.LOW}`)
        )
      );
      container.appendChild(severityGrid);

      // 3. Tab Navigation & Content Container
      const tabContentContainer = h("div", {});

      const codeFindingsCount = (data.code_findings || []).length;
      const secretsCount = (data.secrets?.findings || []).length;
      const depsCount = (data.dependencies?.vulnerabilities || []).length;

      const codeTabBtn = h("button", {
        className: `btn ${activeTab === "code" ? "btn-primary" : "btn-secondary"} btn-sm`,
      }, `Code Findings (${codeFindingsCount})`);

      const secretsTabBtn = h("button", {
        className: `btn ${activeTab === "secrets" ? "btn-primary" : "btn-secondary"} btn-sm`,
      }, `Exposed Secrets (${secretsCount})`);

      const depsTabBtn = h("button", {
        className: `btn ${activeTab === "deps" ? "btn-primary" : "btn-secondary"} btn-sm`,
      }, `Dependencies (${depsCount})`);

      function updateTabs() {
        codeTabBtn.className = `btn ${activeTab === "code" ? "btn-primary" : "btn-secondary"} btn-sm`;
        secretsTabBtn.className = `btn ${activeTab === "secrets" ? "btn-primary" : "btn-secondary"} btn-sm`;
        depsTabBtn.className = `btn ${activeTab === "deps" ? "btn-primary" : "btn-secondary"} btn-sm`;
        renderActiveTabContent();
      }

      codeTabBtn.addEventListener("click", () => { activeTab = "code"; updateTabs(); });
      secretsTabBtn.addEventListener("click", () => { activeTab = "secrets"; updateTabs(); });
      depsTabBtn.addEventListener("click", () => { activeTab = "deps"; updateTabs(); });

      const tabsBar = h("div", { style: { display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-4)" } },
        codeTabBtn,
        secretsTabBtn,
        depsTabBtn
      );
      container.appendChild(tabsBar);
      container.appendChild(tabContentContainer);

      function renderActiveTabContent() {
        tabContentContainer.textContent = "";

        if (activeTab === "code") {
          const findings = data.code_findings || [];
          if (findings.length === 0) {
            tabContentContainer.appendChild(
              h("div", { className: "card", style: { padding: "var(--space-6)", textAlign: "center" } },
                h("p", { className: "text-muted" }, "No code security issues detected.")
              )
            );
            return;
          }

          const rows = findings.map(f =>
            h("tr", {},
              h("td", { style: { width: "100px" } }, getSeverityBadge(f.severity)),
              h("td", { style: { width: "100px", fontWeight: "var(--font-semibold)" } }, f.source),
              h("td", { className: "font-mono", style: { fontSize: "var(--text-xs)" } }, `${f.file}:${f.line}`),
              h("td", { className: "font-mono", style: { fontSize: "var(--text-xs)", color: "var(--color-fg-muted)" } }, f.rule_id),
              h("td", { style: { fontSize: "var(--text-xs)" } }, f.message)
            )
          );

          const table = h("div", { className: "card", style: { overflowX: "auto" } },
            h("table", { className: "table", style: { width: "100%", fontSize: "var(--text-xs)" } },
              h("thead", {},
                h("tr", {},
                  h("th", {}, "Severity"),
                  h("th", {}, "Scanner"),
                  h("th", {}, "File & Line"),
                  h("th", {}, "Rule ID"),
                  h("th", {}, "Description")
                )
              ),
              h("tbody", {}, ...rows)
            )
          );
          tabContentContainer.appendChild(table);

        } else if (activeTab === "secrets") {
          const secrets = data.secrets?.findings || [];
          if (secrets.length === 0) {
            tabContentContainer.appendChild(
              h("div", { className: "card", style: { padding: "var(--space-6)", textAlign: "center" } },
                h("p", { className: "text-muted" }, "No exposed secrets or credentials detected.")
              )
            );
            return;
          }

          const rows = secrets.map(s =>
            h("tr", {},
              h("td", { style: { width: "100px" } }, getSeverityBadge(s.severity || "HIGH")),
              h("td", { className: "font-mono", style: { fontSize: "var(--text-xs)" } }, `${s.file}:${s.line}`),
              h("td", { style: { textTransform: "capitalize", fontWeight: "var(--font-medium)" } }, s.type.replace(/_/g, " ")),
              h("td", { className: "font-mono", style: { fontSize: "var(--text-xs)", color: "#CF3A3A", fontWeight: "var(--font-bold)" } }, s.masked)
            )
          );

          const table = h("div", { className: "card", style: { overflowX: "auto" } },
            h("table", { className: "table", style: { width: "100%", fontSize: "var(--text-xs)" } },
              h("thead", {},
                h("tr", {},
                  h("th", {}, "Severity"),
                  h("th", {}, "File & Line"),
                  h("th", {}, "Secret Type"),
                  h("th", {}, "Masked Secret Value (RULES B7)")
                )
              ),
              h("tbody", {}, ...rows)
            )
          );
          tabContentContainer.appendChild(table);

        } else if (activeTab === "deps") {
          const vulns = data.dependencies?.vulnerabilities || [];
          if (vulns.length === 0) {
            tabContentContainer.appendChild(
              h("div", { className: "card", style: { padding: "var(--space-6)", textAlign: "center" } },
                h("p", { className: "text-muted" }, "No known dependency vulnerabilities found in manifests.")
              )
            );
            return;
          }

          const rows = [];
          for (const dep of vulns) {
            for (const adv of (dep.advisories || [])) {
              rows.push(
                h("tr", {},
                  h("td", { style: { width: "90px" } }, h("span", { className: "badge badge-neutral" }, dep.ecosystem)),
                  h("td", { style: { fontWeight: "var(--font-semibold)" } }, dep.name),
                  h("td", { className: "font-mono", style: { fontSize: "var(--text-xs)" } }, dep.version),
                  h("td", { className: "font-mono", style: { fontSize: "var(--text-xs)", color: "var(--color-primary)", fontWeight: "var(--font-bold)" } }, adv.id),
                  h("td", { style: { fontSize: "var(--text-xs)" } }, adv.summary || adv.details || "Security advisory")
                )
              );
            }
          }

          const table = h("div", { className: "card", style: { overflowX: "auto" } },
            h("table", { className: "table", style: { width: "100%", fontSize: "var(--text-xs)" } },
              h("thead", {},
                h("tr", {},
                  h("th", {}, "Ecosystem"),
                  h("th", {}, "Package"),
                  h("th", {}, "Version"),
                  h("th", {}, "Advisory ID"),
                  h("th", {}, "Summary")
                )
              ),
              h("tbody", {}, ...rows)
            )
          );
          tabContentContainer.appendChild(table);
        }
      }

      renderActiveTabContent();

    } catch (err) {
      container.textContent = "";
      container.appendChild(
        h("div", { className: "error-banner", style: { padding: "var(--space-4)" } },
          h("div", { style: { fontWeight: "var(--font-bold)", marginBottom: "var(--space-1)" } }, `Error loading security analysis (${err.code || "FAILED"})`),
          h("div", { style: { fontSize: "var(--text-sm)" } }, err.message || "Failed to load security findings.")
        )
      );
    }
  }

  const unsubscribe = subscribe(() => {
    loadData();
  });

  loadData();

  return {
    element: container,
    destroy: () => unsubscribe(),
  };
}

const securityPage = {
  title: "Security Analysis",
  instance: null,
  async mount(ctx) {
    this.instance = renderSecurityPage();
    ctx.container.replaceChildren(this.instance.element);
  },
  unmount() {
    if (this.instance && typeof this.instance.destroy === "function") {
      this.instance.destroy();
      this.instance = null;
    }
  },
};

export default securityPage;
