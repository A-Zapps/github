import { h } from "../ui/h.js";
import { icons } from "../ui/icons.js";

function createEmptyState(title, desc) {
  return h("div", { className: "card" },
    h("div", { className: "empty-state" },
      h("div", { className: "empty-state-icon" }, icons.info(24)),
      h("h3", { className: "empty-state-title" }, "Not built yet"),
      h("p", { className: "empty-state-desc" }, desc || `The ${title} module is scheduled for implementation in a later phase.`)
    )
  );
}

export function makePlaceholderPage(title, desc) {
  return {
    title,
    async mount(ctx) {
      ctx.container.replaceChildren(createEmptyState(title, desc));
    },
    unmount() {}
  };
}
