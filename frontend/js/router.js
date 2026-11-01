/**
 * Hash router for client-side navigation.
 */

const ROUTES = {
  "#/overview": () => import("./pages/overview.js"),
  "#/analyzer": () => import("./pages/analyzer.js"),
  "#/quality": () => import("./pages/quality.js"),
  "#/bugs": () => import("./pages/bugs.js"),
  "#/security": () => import("./pages/security.js"),
  "#/health": () => import("./pages/health.js"),
  "#/docs": () => import("./pages/docs.js"),
  "#/developers": () => import("./pages/developers.js"),
  "#/compare": () => import("./pages/compare.js"),
  "#/assistant": () => import("./pages/assistant.js"),
  "#/reports": () => import("./pages/reports.js"),
  "#/models": () => import("./pages/model-performance.js"),
  "#/settings": () => import("./pages/settings.js"),
};

export class Router {
  constructor(contentContainer, titleElement) {
    this.container = contentContainer;
    this.titleElement = titleElement;
    this.currentPage = null;

    window.addEventListener("hashchange", () => this.handleRoute());
  }

  init() {
    if (!window.location.hash || !ROUTES[this.cleanHash(window.location.hash)]) {
      window.location.hash = "#/overview";
    } else {
      this.handleRoute();
    }
  }

  cleanHash(hash) {
    const qIndex = hash.indexOf("?");
    return qIndex === -1 ? hash : hash.slice(0, qIndex);
  }

  async handleRoute() {
    const rawHash = window.location.hash || "#/overview";
    const clean = this.cleanHash(rawHash);
    const loader = ROUTES[clean];

    if (!loader) {
      window.location.hash = "#/overview";
      return;
    }

    // Update active nav item
    document.querySelectorAll(".nav-item").forEach((item) => {
      const itemHash = this.cleanHash(item.getAttribute("href") || "");
      if (itemHash === clean) {
        item.setAttribute("aria-current", "page");
      } else {
        item.removeAttribute("aria-current");
      }
    });

    if (this.currentPage && typeof this.currentPage.unmount === "function") {
      try {
        this.currentPage.unmount();
      } catch (e) {
        console.error("Error unmounting page:", e);
      }
    }

    try {
      const module = await loader();
      const page = module.default;
      this.currentPage = page;

      if (this.titleElement && page && page.title) {
        this.titleElement.textContent = page.title;
        document.title = `${page.title} - GitHub Repository Analyzer`;
      }

      if (typeof page === "function") {
        const result = page();
        if (result instanceof Node) {
          this.container.replaceChildren(result);
        } else if (result && result.element instanceof Node) {
          this.container.replaceChildren(result.element);
          this.currentPage = {
            unmount: result.destroy || (() => {}),
          };
        }
      } else if (page && typeof page.mount === "function") {
        await page.mount({
          container: this.container,
          hash: rawHash,
        });
      }
    } catch (err) {
      console.error("Failed to load page for route:", clean, err);
    }
  }
}
