/**
 * Documentation Analysis Page (F6).
 * README section detection, completeness checklist, suggestions, and grade.
 */

import { api } from "../api.js";
import { state, subscribe } from "../state.js";
import { h } from "../ui/h.js";
import { icons } from "../ui/icons.js";

function getStatusBadge(status) {
  switch (status) {
    case "found":
      return h("span", { className: "badge badge-success" }, "FOUND");
    case "weak":
      return h("span", { className: "badge badge-warning" }, "WEAK (<60 chars)");
    default:
      return h("span", { className: "badge badge-danger" }, "MISSING");
  }
}

function getGradeColor(grade) {
  switch (grade) {
    case "A":
      return "var(--color-success)";
    case "B":
      return "var(--color-primary)";
    case "C":
      return "var(--color-warning)";
    default:
      return "var(--color-danger)";
  }
}

function renderDocsPage() {
  const container = h("div", { className: "page-container" });

  async function loadData() {
    container.textContent = "";

    const analysisId = state.activeAnalysisId;
    if (!analysisId) {
      container.appendChild(
        h("div", { className: "empty-state" },
          h("div", { className: "empty-icon", style: { color: "var(--color-fg-muted)", marginBottom: "var(--space-3)" } }, icons.book()),
          h("h3", { style: { fontSize: "var(--text-lg)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-2)" } }, "No analysis selected"),
          h("p", { className: "text-muted", style: { marginBottom: "var(--space-4)" } }, "Select or analyze a GitHub repository first to evaluate documentation quality."),
          h("a", { href: "#/analyzer", className: "btn btn-primary" }, "Go to Repository Analyzer")
        )
      );
      return;
    }

    container.appendChild(
      h("div", { className: "empty-state" },
        h("div", { className: "spinner", style: { margin: "0 auto var(--space-3) auto" } }),
        h("p", { className: "text-muted" }, "Parsing README and evaluating documentation completeness...")
      )
    );

    try {
      const resp = await api.getDocsData(analysisId);
      const data = resp.data || {};
      container.textContent = "";

      const hasReadme = data.has_readme;
      const score = data.overall_score || 0;
      const grade = data.grade || "F";
      const checklist = data.checklist || {};
      const suggestions = data.suggestions || [];
      const sections = data.sections || [];

      // 1. Header
      const header = h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "var(--space-6)" } },
        h("div", null,
          h("h2", { style: { fontSize: "var(--text-2xl)", fontWeight: "var(--font-bold)", marginBottom: "var(--space-1)" } }, "Documentation Analysis"),
          h("p", { className: "text-muted" }, "Assessment of project onboarding documentation, setup guides, examples, and license declarations.")
        ),
        h("div", { style: { display: "flex", alignItems: "center", gap: "var(--space-2)" } },
          h("span", { className: "badge badge-neutral" }, `File: ${data.filename || "None"}`),
          h("span", { className: "badge badge-neutral" }, "Model: doc_sections")
        )
      );
      container.appendChild(header);

      // 2. Score Hero & Section Coverage Bar
      const gradeColor = getGradeColor(grade);
      const heroCard = h("div", { className: "card", style: { marginBottom: "var(--space-6)", padding: "var(--space-6)" } },
        h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center" } },
          h("div", { style: { display: "flex", alignItems: "center", gap: "var(--space-5)" } },
            h("div", {
              style: {
                width: "68px",
                height: "68px",
                borderRadius: "50%",
                backgroundColor: `${gradeColor}15`,
                color: gradeColor,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "var(--text-3xl)",
                fontWeight: "var(--font-bold)",
                border: `3px solid ${gradeColor}`,
                flexShrink: 0,
              },
            }, grade),
            h("div", null,
              h("div", { className: "text-muted", style: { fontSize: "var(--text-xs)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: "var(--font-semibold)" } }, "Documentation Completeness"),
              h("div", { style: { fontSize: "var(--text-3xl)", fontWeight: "var(--font-bold)", color: "var(--color-fg-default)" } }, `${score}/100`),
              h("div", { style: { fontSize: "var(--text-xs)", color: "var(--color-fg-muted)", marginTop: "2px" } },
                hasReadme ? "Evaluated against 4 core open-source documentation standards" : "No README found in repository"
              )
            )
          ),
          h("div", { style: { textAlign: "right" } },
            h("span", { className: `badge ${score >= 80 ? "badge-success" : score >= 50 ? "badge-warning" : "badge-danger"}`, style: { fontSize: "var(--text-sm)", padding: "var(--space-2) var(--space-4)" } },
              score >= 80 ? "WELL DOCUMENTED" : score >= 50 ? "NEEDS IMPROVEMENT" : "POOR DOCUMENTATION"
            )
          )
        )
      );
      container.appendChild(heroCard);

      // 3. Section Completeness Checklist
      const checklistCard = h("div", { className: "card", style: { padding: "0", overflow: "hidden", marginBottom: "var(--space-6)" } },
        h("div", { style: { padding: "var(--space-4)", borderBottom: "1px solid var(--color-border)" } },
          h("h3", { style: { fontSize: "var(--text-md)", fontWeight: "var(--font-semibold)" } }, "Core Section Checklist")
        ),
        h("table", { className: "table" },
          h("thead", null,
            h("tr", null,
              h("th", { style: { width: "240px" } }, "Expected Section"),
              h("th", { style: { width: "160px" } }, "Status"),
              h("th", { style: { width: "100px" } }, "Score Weight"),
              h("th", null, "Finding / Recommendation")
            )
          ),
          h("tbody", null,
            Object.entries(checklist).map(([key, item]) =>
              h("tr", null,
                h("td", { style: { fontWeight: "var(--font-semibold)" } }, item.title),
                h("td", null, getStatusBadge(item.status)),
                h("td", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" } }, `${item.earned}/${item.weight} pts`),
                h("td", { className: "text-muted", style: { fontSize: "var(--text-xs)" } },
                  item.suggestion || `Found substantive section (${item.char_count} characters).`
                )
              )
            )
          )
        )
      );
      container.appendChild(checklistCard);

      // 4. Actionable Suggestions (if any missing/weak)
      if (suggestions.length > 0) {
        const suggestionsCard = h("div", { className: "card", style: { marginBottom: "var(--space-6)", borderLeft: "4px solid var(--color-warning)" } },
          h("h3", { style: { fontSize: "var(--text-md)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-3)", display: "flex", alignItems: "center", gap: "var(--space-2)" } },
            icons.alertCircle(18),
            "Documentation Recommendations"
          ),
          h("div", { style: { display: "flex", flexDirection: "column", gap: "var(--space-2)" } },
            suggestions.map((s) =>
              h("div", { style: { display: "flex", gap: "var(--space-2)", fontSize: "var(--text-sm)", color: "var(--color-fg-muted)" } },
                h("span", { style: { color: "var(--color-warning)", fontWeight: "var(--font-bold)" } }, "•"),
                h("span", null, s)
              )
            )
          )
        );
        container.appendChild(suggestionsCard);
      }

      // 5. Detected Sections Breakdown
      if (sections.length > 0) {
        const sectionsCard = h("div", { className: "card", style: { padding: "0", overflow: "hidden" } },
          h("div", { style: { padding: "var(--space-4)", borderBottom: "1px solid var(--color-border)" } },
            h("h3", { style: { fontSize: "var(--text-md)", fontWeight: "var(--font-semibold)" } }, "Detected README Sections")
          ),
          h("table", { className: "table" },
            h("thead", null,
              h("tr", null,
                h("th", { style: { width: "160px" } }, "Classified Category"),
                h("th", { style: { width: "100px" } }, "Length"),
                h("th", null, "Text Preview")
              )
            ),
            h("tbody", null,
              sections.map((sec) =>
                h("tr", null,
                  h("td", null, h("span", { className: "badge badge-neutral", style: { textTransform: "capitalize" } }, sec.category)),
                  h("td", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" } }, `${sec.length} chars`),
                  h("td", { style: { fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--color-fg-muted)" } }, sec.preview)
                )
              )
            )
          )
        );
        container.appendChild(sectionsCard);
      }

    } catch (err) {
      container.textContent = "";
      container.appendChild(
        h("div", { className: "empty-state" },
          h("div", { className: "empty-icon", style: { color: "var(--color-danger)", marginBottom: "var(--space-3)" } }, icons.alertCircle()),
          h("h3", { style: { fontSize: "var(--text-lg)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-2)" } }, "Failed to load documentation analysis"),
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

const docsPage = {
  title: "Documentation",
  instance: null,
  async mount(ctx) {
    this.instance = renderDocsPage();
    ctx.container.replaceChildren(this.instance.element);
  },
  unmount() {
    if (this.instance && typeof this.instance.destroy === "function") {
      this.instance.destroy();
      this.instance = null;
    }
  },
};

export default docsPage;
