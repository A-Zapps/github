"""ReportLab PDF report builder with strict XML escaping for untrusted repository strings (T8.2)."""

import io
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from backend.app.reports.charts import (
    render_bug_distribution_chart,
    render_quality_breakdown_bars,
    render_security_summary_bars,
)


def safe_text(val: Any) -> str:
    """Escape untrusted text to prevent ReportLab XML markup injection crashes (T8.2)."""
    if val is None:
        return ""
    s = str(val)
    # xml_escape escapes &, <, >
    escaped = xml_escape(s)
    # Also escape double quotes
    return escaped.replace('"', "&quot;")


def build_analysis_pdf(
    analysis_id: int,
    repo_data: Dict[str, Any],
    quality_data: Dict[str, Any],
    bugs_data: Dict[str, Any],
    security_data: Dict[str, Any],
    health_data: Dict[str, Any],
    dev_data: Dict[str, Any],
    recs_data: Dict[str, Any],
    appendix_data: Dict[str, Any],
    output_path: Optional[str] = None,
) -> bytes:
    """Compile comprehensive executive PDF report with embedded charts and sanitized tables."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        output_path or buf,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()

    # Custom styles adhering to DESIGN tokens
    primary_color = colors.HexColor("#5267D8")
    dark_text = colors.HexColor("#20242C")
    muted_text = colors.HexColor("#5B6270")
    border_color = colors.HexColor("#E3E6EB")

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=primary_color,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=muted_text,
        spaceAfter=15,
    )
    h2_style = ParagraphStyle(
        "ReportH2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=dark_text,
        spaceBefore=14,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=dark_text,
    )
    body_bold = ParagraphStyle(
        "ReportBodyBold",
        parent=body_style,
        fontName="Helvetica-Bold",
    )
    table_cell = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10.5,
        textColor=dark_text,
    )
    table_cell_header = ParagraphStyle(
        "TableCellHeader",
        parent=table_cell,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#FFFFFF"),
    )

    story: List[Any] = []

    # 1. Header / Cover Banner
    repo_name = safe_text(repo_data.get("full_name", f"Repository #{analysis_id}"))
    head_sha = safe_text(appendix_data.get("head_sha", "unknown")[:8])
    gen_date = safe_text(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))

    story.append(Paragraph("GitHub Repository Analysis Report", title_style))
    story.append(Paragraph(f"Repository: <b>{repo_name}</b> | Commit: <b>{head_sha}</b> | Date: {gen_date}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=border_color, spaceAfter=15))

    # 2. Executive Summary Metrics Grid
    overall_score = quality_data.get("overall_score", 0)
    debt_hours = quality_data.get("tech_debt_hours", 0)
    total_issues = security_data.get("total_issues", 0)
    bus_factor = dev_data.get("bus_factor", 1)

    summary_table_data = [
        [
            Paragraph("<b>Overall Quality</b>", body_style),
            Paragraph("<b>Tech Debt Estimate</b>", body_style),
            Paragraph("<b>Security Issues</b>", body_style),
            Paragraph("<b>Bus Factor</b>", body_style),
        ],
        [
            Paragraph(f"<font size=14 color='{primary_color}'><b>{overall_score}/100</b></font>", body_style),
            Paragraph(f"<font size=14><b>{debt_hours}h</b></font>", body_style),
            Paragraph(f"<font size=14 color='#B73636'><b>{total_issues}</b></font>", body_style),
            Paragraph(f"<font size=14><b>{bus_factor} dev(s)</b></font>", body_style),
        ],
    ]
    summary_t = Table(summary_table_data, colWidths=[130, 130, 130, 130])
    summary_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4F5F7")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, border_color),
        ("BOX", (0, 0), (-1, -1), 1, border_color),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_t)
    story.append(Spacer(1, 15))

    # 3. Quality & Bug Prediction Visuals
    story.append(Paragraph("Quality Breakdown & Defect Risk", h2_style))

    components = quality_data.get("components", {})
    bug_summary = bugs_data.get("summary", {})

    chart_quality_png = render_quality_breakdown_bars(components)
    chart_bugs_png = render_bug_distribution_chart(bug_summary)

    chart_table_data = [
        [
            Image(io.BytesIO(chart_quality_png), width=310, height=155),
            Image(io.BytesIO(chart_bugs_png), width=210, height=155),
        ]
    ]
    chart_t = Table(chart_table_data, colWidths=[320, 210])
    chart_t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(chart_t)
    story.append(Spacer(1, 10))

    # 4. Security Findings Summary
    story.append(Paragraph("Security & Vulnerabilities", h2_style))
    sev_summary = security_data.get("severity_summary", {})
    chart_sec_png = render_security_summary_bars(sev_summary)

    code_findings = security_data.get("code_findings", [])
    findings_rows = [
        [
            Paragraph("<b>Severity</b>", table_cell_header),
            Paragraph("<b>Source</b>", table_cell_header),
            Paragraph("<b>Location</b>", table_cell_header),
            Paragraph("<b>Finding Message</b>", table_cell_header),
        ]
    ]

    for f in code_findings[:5]:
        sev = safe_text(f.get("severity", "LOW"))
        src = safe_text(f.get("source", "Linter"))
        loc = safe_text(f"{f.get('file', '')}:{f.get('line', '')}")
        msg = safe_text(f.get("message", ""))
        findings_rows.append([
            Paragraph(f"<b>{sev}</b>", table_cell),
            Paragraph(src, table_cell),
            Paragraph(loc, table_cell),
            Paragraph(msg, table_cell),
        ])

    if len(findings_rows) == 1:
        findings_rows.append([Paragraph("No code vulnerabilities detected.", table_cell), Paragraph("-", table_cell), Paragraph("-", table_cell), Paragraph("-", table_cell)])

    sec_table = Table(findings_rows, colWidths=[65, 60, 140, 265])
    sec_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), primary_color),
        ("GRID", (0, 0), (-1, -1), 0.5, border_color),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    sec_flow_table = Table([[Image(io.BytesIO(chart_sec_png), width=180, height=115), sec_table]], colWidths=[190, 340])
    sec_flow_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(sec_flow_table)
    story.append(Spacer(1, 10))

    # 5. Top Recommendations Panel
    story.append(Paragraph("Actionable Recommendations", h2_style))
    recs = recs_data.get("recommendations", [])
    rec_table_data = [
        [
            Paragraph("<b>Priority</b>", table_cell_header),
            Paragraph("<b>Title & Evidence</b>", table_cell_header),
            Paragraph("<b>Effort</b>", table_cell_header),
            Paragraph("<b>Expected Impact</b>", table_cell_header),
        ]
    ]

    for r in recs[:5]:
        prio = safe_text(r.get("priority", "medium").upper())
        title = safe_text(r.get("title", ""))
        ev = safe_text(r.get("evidence", ""))
        eff = safe_text(r.get("effort", "medium"))
        imp = safe_text(r.get("impact", ""))
        desc = f"<b>{title}</b><br/><font color='#5B6270'>Evidence: {ev}</font>"

        rec_table_data.append([
            Paragraph(prio, table_cell),
            Paragraph(desc, table_cell),
            Paragraph(eff, table_cell),
            Paragraph(imp, table_cell),
        ])

    if len(rec_table_data) == 1:
        rec_table_data.append([Paragraph("None", table_cell), Paragraph("Repository is in good shape with no critical action items.", table_cell), Paragraph("-", table_cell), Paragraph("-", table_cell)])

    rec_t = Table(rec_table_data, colWidths=[60, 260, 60, 150])
    rec_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), primary_color),
        ("GRID", (0, 0), (-1, -1), 0.5, border_color),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(rec_t)
    story.append(Spacer(1, 15))

    # 6. Appendix
    story.append(HRFlowable(width="100%", thickness=0.5, color=border_color, spaceAfter=8))
    story.append(Paragraph("Appendix & Audit Trail", h2_style))

    appendix_rows = [
        [
            Paragraph("<b>Parameter</b>", body_bold),
            Paragraph("<b>Recorded Value</b>", body_bold),
        ],
        [Paragraph("Analyzer Version", body_style), Paragraph(safe_text(appendix_data.get("analyzer_version", "1.0.0")), body_style)],
        [Paragraph("Full Head SHA", body_style), Paragraph(safe_text(appendix_data.get("head_sha", "unknown")), body_style)],
        [Paragraph("Analysis Timestamp", body_style), Paragraph(safe_text(appendix_data.get("generated_at", gen_date)), body_style)],
        [Paragraph("Model Artifacts", body_style), Paragraph(safe_text(appendix_data.get("model_versions", "bug_risk:1.0, repo_health:1.0")), body_style)],
        [Paragraph("Max Files Scan Cap", body_style), Paragraph(safe_text(appendix_data.get("max_files", 3000)), body_style)],
        [Paragraph("Max File Size Cap", body_style), Paragraph(safe_text(f"{appendix_data.get('max_file_kb', 500)} KB"), body_style)],
    ]
    app_t = Table(appendix_rows, colWidths=[180, 350])
    app_t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, border_color),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F4F5F7")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(app_t)

    # Build document
    doc.build(story)

    if output_path:
        with open(output_path, "rb") as f:
            return f.read()

    buf.seek(0)
    return buf.getvalue()
