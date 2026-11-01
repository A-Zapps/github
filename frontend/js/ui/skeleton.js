/**
 * Skeleton loading placeholder components.
 * Provides pulsing placeholder UI while data loads.
 */

import { h } from "./h.js";

/**
 * Render a skeleton loading placeholder.
 * @param {"card"|"table"|"text"} type - The skeleton variant to render.
 * @param {number} count - Number of skeleton items to generate.
 * @returns {HTMLElement}
 */
export function renderSkeleton(type = "card", count = 1) {
  const items = [];

  for (let i = 0; i < count; i++) {
    let skeleton;

    switch (type) {
      case "card":
        skeleton = h(
          "div",
          {
            class: "skeleton-card",
            style: {
              backgroundColor: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: "var(--r-lg)",
              padding: "var(--s-5)",
              display: "flex",
              flexDirection: "column",
              gap: "var(--s-3)",
            },
          },
          h("div", {
            class: "skeleton-line",
            style: {
              height: "14px",
              width: "40%",
              backgroundColor: "var(--border)",
              borderRadius: "var(--r-sm)",
              animation: "skeleton-pulse 1.5s ease-in-out infinite",
            },
          }),
          h("div", {
            class: "skeleton-line",
            style: {
              height: "10px",
              width: "80%",
              backgroundColor: "var(--border)",
              borderRadius: "var(--r-sm)",
              animation: "skeleton-pulse 1.5s ease-in-out 0.1s infinite",
            },
          }),
          h("div", {
            class: "skeleton-line",
            style: {
              height: "10px",
              width: "60%",
              backgroundColor: "var(--border)",
              borderRadius: "var(--r-sm)",
              animation: "skeleton-pulse 1.5s ease-in-out 0.2s infinite",
            },
          })
        );
        break;

      case "table":
        skeleton = h(
          "div",
          {
            class: "skeleton-table",
            style: {
              backgroundColor: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: "var(--r-lg)",
              padding: "var(--s-4)",
              display: "flex",
              flexDirection: "column",
              gap: "var(--s-3)",
            },
          },
          ...Array.from({ length: 4 }, (_, j) =>
            h("div", {
              class: "skeleton-line",
              style: {
                height: "12px",
                width: j === 0 ? "100%" : `${70 + Math.random() * 25}%`,
                backgroundColor: "var(--border)",
                borderRadius: "var(--r-sm)",
                animation: `skeleton-pulse 1.5s ease-in-out ${j * 0.1}s infinite`,
              },
            })
          )
        );
        break;

      case "text":
      default:
        skeleton = h(
          "div",
          {
            class: "skeleton-text",
            style: {
              display: "flex",
              flexDirection: "column",
              gap: "var(--s-2)",
            },
          },
          h("div", {
            class: "skeleton-line",
            style: {
              height: "12px",
              width: "90%",
              backgroundColor: "var(--border)",
              borderRadius: "var(--r-sm)",
              animation: "skeleton-pulse 1.5s ease-in-out infinite",
            },
          }),
          h("div", {
            class: "skeleton-line",
            style: {
              height: "12px",
              width: "70%",
              backgroundColor: "var(--border)",
              borderRadius: "var(--r-sm)",
              animation: "skeleton-pulse 1.5s ease-in-out 0.15s infinite",
            },
          })
        );
        break;
    }

    items.push(skeleton);
  }

  // Inject keyframes if not already present
  if (!document.getElementById("skeleton-keyframes")) {
    const styleEl = document.createElement("style");
    styleEl.id = "skeleton-keyframes";
    styleEl.textContent = `
      @keyframes skeleton-pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.4; }
      }
    `;
    document.head.appendChild(styleEl);
  }

  const wrapper = h(
    "div",
    {
      class: "skeleton-wrapper",
      style: {
        display: "flex",
        flexDirection: "column",
        gap: "var(--s-4)",
        width: "100%",
      },
    },
    ...items
  );

  return wrapper;
}
