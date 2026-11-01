"""Matplotlib chart renderer for PDF reports matching DESIGN.md tokens (T8.1)."""

import io
from typing import Any, Dict

import matplotlib

matplotlib.use("Agg")  # Non-interactive headless backend
import matplotlib.pyplot as plt
import numpy as np

# DESIGN.md Color Tokens
COLOR_PRIMARY = "#5267D8"
COLOR_PRIMARY_LIGHT = "#8E9BEA"
COLOR_PRIMARY_DARK = "#2F3F9E"
COLOR_NEUTRAL = "#9AA1AE"
COLOR_TEXT = "#20242C"
COLOR_TEXT_MUTED = "#5B6270"
COLOR_BORDER = "#E3E6EB"

COLOR_SUCCESS = "#1F7A55"
COLOR_WARNING = "#96650A"
COLOR_DANGER = "#B73636"
COLOR_INFO = "#2C6FA8"


def render_bug_distribution_chart(bug_counts: Dict[str, int]) -> bytes:
    """Render a clean donut chart of bug risk distribution."""
    fig, ax = plt.subplots(figsize=(4.5, 3.2), dpi=150)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")

    labels = ["Low Risk", "Medium Risk", "High Risk"]
    counts = [
        bug_counts.get("low", 0),
        bug_counts.get("medium", 0),
        bug_counts.get("high", 0),
    ]
    colors = [COLOR_SUCCESS, COLOR_WARNING, COLOR_DANGER]

    # Filter zero counts if all not zero
    if sum(counts) == 0:
        counts = [1]
        labels = ["No Data"]
        colors = [COLOR_NEUTRAL]

    wedges, texts, autotexts = ax.pie(
        counts,
        labels=labels,
        colors=colors,
        autopct=lambda pct: f"{pct:.0f}%" if pct > 5 else "",
        startangle=90,
        wedgeprops=dict(width=0.45, edgecolor="#FFFFFF", linewidth=2),
        textprops=dict(color=COLOR_TEXT, fontsize=8),
    )
    for at in autotexts:
        at.set_color("#FFFFFF")
        at.set_fontsize(8)
        at.set_weight("bold")

    ax.set_title("Bug Risk Distribution", fontsize=10, weight="bold", color=COLOR_TEXT, pad=10)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), transparent=False)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def render_quality_breakdown_bars(components: Dict[str, Dict[str, Any]]) -> bytes:
    """Render a horizontal bar chart of quality component scores (0-100)."""
    fig, ax = plt.subplots(figsize=(6.0, 3.0), dpi=150)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")

    categories = []
    scores = []

    for name, data in components.items():
        categories.append(name.replace("_", " ").title())
        scores.append(float(data.get("score", 0)))

    if not categories:
        categories = ["Overall Quality"]
        scores = [0]

    y_pos = np.arange(len(categories))

    # Color bars based on score threshold
    bar_colors = [
        COLOR_SUCCESS if s >= 75 else COLOR_WARNING if s >= 50 else COLOR_DANGER
        for s in scores
    ]

    bars = ax.barh(y_pos, scores, align="center", color=bar_colors, height=0.55, edgecolor="none")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(categories, fontsize=8, color=COLOR_TEXT)
    ax.invert_yaxis()  # Labels read top-to-bottom
    ax.set_xlim(0, 100)
    ax.set_xlabel("Score (0 - 100)", fontsize=8, color=COLOR_TEXT_MUTED)

    # Styling
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(COLOR_BORDER)
    ax.spines["bottom"].set_color(COLOR_BORDER)
    ax.xaxis.grid(True, linestyle="--", alpha=0.5, color=COLOR_BORDER)
    ax.yaxis.grid(False)

    for bar, score in zip(bars, scores):
        ax.text(
            bar.get_width() + 1.5,
            bar.get_y() + bar.get_height() / 2,
            f"{int(score)}",
            va="center",
            ha="left",
            fontsize=8,
            weight="bold",
            color=COLOR_TEXT,
        )

    ax.set_title("Code Quality Components", fontsize=10, weight="bold", color=COLOR_TEXT, pad=10)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), transparent=False)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def render_security_summary_bars(severity_summary: Dict[str, int]) -> bytes:
    """Render vertical bar chart of security findings by severity level."""
    fig, ax = plt.subplots(figsize=(4.5, 2.8), dpi=150)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")

    levels = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    counts = [severity_summary.get(lvl, 0) for lvl in levels]
    colors = [COLOR_DANGER, "#D9534F", COLOR_WARNING, COLOR_INFO]

    bars = ax.bar(levels, counts, color=colors, width=0.5, edgecolor="none")
    ax.set_ylabel("Findings", fontsize=8, color=COLOR_TEXT_MUTED)
    ax.set_title("Security Findings by Severity", fontsize=10, weight="bold", color=COLOR_TEXT, pad=10)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(COLOR_BORDER)
    ax.spines["bottom"].set_color(COLOR_BORDER)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5, color=COLOR_BORDER)
    ax.xaxis.grid(False)
    ax.tick_params(axis="x", labelsize=8, colors=COLOR_TEXT)
    ax.tick_params(axis="y", labelsize=8, colors=COLOR_TEXT_MUTED)

    for bar, count in zip(bars, counts):
        if count > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.2,
                str(count),
                ha="center",
                va="bottom",
                fontsize=8,
                weight="bold",
                color=COLOR_TEXT,
            )

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), transparent=False)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
