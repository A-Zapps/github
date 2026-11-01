/**
 * Chart.js wrapper conforming strictly to DESIGN.md section 5.
 */

import { h } from "./h.js";

export const CHART_PALETTE = [
  "#5267D8",
  "#8E9BEA",
  "#2F3F9E",
  "#9AA1AE",
  "#C7CCF3",
  "#5B6270",
];

export function createDonutChart(canvas, labels, data, label = "Distribution") {
  if (typeof window.Chart === "undefined") {
    console.warn("Chart.js not loaded.");
    return null;
  }

  return new window.Chart(canvas, {
    type: "doughnut",
    data: {
      labels,
      datasets: [
        {
          label,
          data,
          backgroundColor: CHART_PALETTE.slice(0, labels.length),
          borderColor: "#FFFFFF",
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "top",
          align: "start",
          labels: {
            font: { family: "Inter, sans-serif", size: 12 },
            color: "#5B6270",
            usePointStyle: true,
            boxWidth: 8,
          },
        },
        tooltip: {
          backgroundColor: "#20242C",
          titleFont: { family: "Inter, sans-serif", size: 12 },
          bodyFont: { family: "Inter, sans-serif", size: 12 },
          cornerRadius: 8,
        },
      },
    },
  });
}

export function createBarChart(canvas, labels, data, label = "Count") {
  if (typeof window.Chart === "undefined") {
    console.warn("Chart.js not loaded.");
    return null;
  }

  return new window.Chart(canvas, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label,
          data,
          backgroundColor: "#5267D8",
          borderRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          grid: { display: false },
          ticks: { font: { family: "Inter, sans-serif", size: 11 }, color: "#5B6270" },
        },
        y: {
          grid: { color: "#E3E6EB" },
          ticks: { font: { family: "Inter, sans-serif", size: 11 }, color: "#5B6270" },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#20242C",
          titleFont: { family: "Inter, sans-serif", size: 12 },
          bodyFont: { family: "Inter, sans-serif", size: 12 },
          cornerRadius: 8,
        },
      },
    },
  });
}

export function makeChartContainer(title, chartCanvas, tableNode) {
  const toggleBtn = h("button", { className: "btn btn-secondary btn-sm" }, "View as table");
  let isTable = false;

  const chartWrapper = h("div", { style: { height: "240px", position: "relative" } }, chartCanvas);
  const tableWrapper = h("div", { style: { height: "240px", overflowY: "auto", display: "none" } }, tableNode);

  toggleBtn.addEventListener("click", () => {
    isTable = !isTable;
    if (isTable) {
      chartWrapper.style.display = "none";
      tableWrapper.style.display = "block";
      toggleBtn.textContent = "View as chart";
    } else {
      chartWrapper.style.display = "block";
      tableWrapper.style.display = "none";
      toggleBtn.textContent = "View as table";
    }
  });

  return h("div", { className: "card" },
    h("div", { className: "card-header" },
      h("h3", { className: "card-title" }, title),
      toggleBtn
    ),
    chartWrapper,
    tableWrapper
  );
}
