/**
 * Main application bootstrap and shell controller.
 */

import { h } from "./ui/h.js";
import { icons } from "./ui/icons.js";
import { Router } from "./router.js";

const NAV_ITEMS = [
  { id: "overview", label: "Overview", hash: "#/overview", icon: "overview" },
  { id: "analyzer", label: "Repository Analyzer", hash: "#/analyzer", icon: "analyzer" },
  { id: "quality", label: "Code Quality", hash: "#/quality", icon: "quality" },
  { id: "bugs", label: "Bug Prediction", hash: "#/bugs", icon: "bugs" },
  { id: "security", label: "Security Analysis", hash: "#/security", icon: "security" },
  { id: "health", label: "Repository Health", hash: "#/health", icon: "health" },
  { id: "docs", label: "Documentation", hash: "#/docs", icon: "docs" },
  { id: "developers", label: "Developer Analytics", hash: "#/developers", icon: "developers" },
  { id: "compare", label: "Repository Comparison", hash: "#/compare", icon: "compare" },
  { id: "assistant", label: "AI Assistant", hash: "#/assistant", icon: "assistant" },
  { id: "reports", label: "Reports", hash: "#/reports", icon: "reports" },
  { id: "models", label: "Model Performance", hash: "#/models", icon: "models" },
  { id: "settings", label: "Settings", hash: "#/settings", icon: "settings" },
];

function initShell() {
  const sidebar = document.getElementById("sidebar");
  const navContainer = document.getElementById("sidebar-nav");
  const collapseBtn = document.getElementById("collapse-btn");
  const menuToggleBtn = document.getElementById("menu-toggle-btn");
  const backdrop = document.getElementById("drawer-backdrop");
  const topbarTitle = document.getElementById("topbar-title");
  const contentArea = document.getElementById("content-inner");

  // Render navigation links
  NAV_ITEMS.forEach((item) => {
    const iconFn = icons[item.icon] || icons.info;
    const navLink = h(
      "a",
      {
        href: item.hash,
        className: "nav-item",
        title: item.label,
        dataset: { navId: item.id },
      },
      h("span", { className: "nav-icon" }, iconFn(18)),
      h("span", { className: "nav-label" }, item.label)
    );
    navLink.addEventListener("click", () => {
      // Close mobile drawer if opened
      sidebar.classList.remove("drawer-open");
      backdrop.classList.remove("active");
    });
    navContainer.appendChild(navLink);
  });

  // Restore sidebar collapse state
  let isCollapsed = false;
  try {
    isCollapsed = localStorage.getItem("sidebar_collapsed") === "true";
  } catch (e) {
    // Ignore localStorage access failures
  }

  function updateCollapseState(collapsed) {
    if (collapsed) {
      sidebar.classList.add("collapsed");
      collapseBtn.replaceChildren(icons.collapseRight(18));
      collapseBtn.setAttribute("title", "Expand sidebar");
    } else {
      sidebar.classList.remove("collapsed");
      collapseBtn.replaceChildren(icons.collapseLeft(18));
      collapseBtn.setAttribute("title", "Collapse sidebar");
    }
  }

  updateCollapseState(isCollapsed);

  collapseBtn.addEventListener("click", () => {
    isCollapsed = !isCollapsed;
    updateCollapseState(isCollapsed);
    try {
      localStorage.setItem("sidebar_collapsed", String(isCollapsed));
    } catch (e) {}
  });

  // Mobile menu drawer toggle
  menuToggleBtn.addEventListener("click", () => {
    sidebar.classList.toggle("drawer-open");
    backdrop.classList.toggle("active");
  });

  backdrop.addEventListener("click", () => {
    sidebar.classList.remove("drawer-open");
    backdrop.classList.remove("active");
  });

  // Initialize Router
  const router = new Router(contentArea, topbarTitle);
  router.init();
}

window.addEventListener("DOMContentLoaded", initShell);
