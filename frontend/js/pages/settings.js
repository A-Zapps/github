/**
 * Settings configuration page (F12, v1): token status, live rate limits, and cache limits.
 */

import { api } from "../api.js";
import { state } from "../state.js";
import { h } from "../ui/h.js";
import { icons } from "../ui/icons.js";

export default {
  title: "Settings",

  async mount(ctx) {
    this.container = ctx.container;
    this.renderLoading();
    await this.loadSettingsData();
  },

  unmount() {},

  renderLoading() {
    this.container.replaceChildren(
      h("div", { className: "card" },
        h("div", { className: "empty-state" },
          h("p", { className: "empty-state-desc" }, "Loading runtime settings...")
        )
      )
    );
  },

  async loadSettingsData() {
    try {
      const [settingsRes, rateLimitRes] = await Promise.all([
        api.getSettings(),
        api.getRateLimit(),
      ]);

      const cfg = settingsRes.data;
      const rl = rateLimitRes.data;

      // Update global state with live rate limit
      state.setRateLimit(rl.remaining, rl.limit);

      this.render(cfg, rl);
    } catch (err) {
      this.container.replaceChildren(
        h("div", { className: "card" },
          h("div", { className: "empty-state" },
            h("h3", { className: "empty-state-title" }, "Failed to Load Settings"),
            h("p", { className: "empty-state-desc" }, err.message)
          )
        )
      );
    }
  },

  render(cfg, rl) {
    this.container.replaceChildren();

    // 1. GitHub Token Status Card
    const tokenBadge = cfg.github_token_configured
      ? h("span", { className: "badge badge-success" }, "Configured (5,000 req/hr)")
      : h("span", { className: "badge badge-warning" }, "Not Configured (60 req/hr)");

    const authCard = h("div", { className: "card" },
      h("div", { className: "card-header" },
        h("h3", { className: "card-title" }, "GitHub API Authentication"),
        tokenBadge
      ),
      h("p", { style: { color: "var(--text-2)", fontSize: "14px" } },
        "GitHub API token provides elevated rate limits (5,000 requests/hr). Set GITHUB_TOKEN in your .env file."
      )
    );

    // 2. Live Rate Limit Card
    const ratePct = rl.limit > 0 ? Math.round((rl.remaining / rl.limit) * 100) : 100;
    const resetDate = rl.reset ? new Date(rl.reset * 1000).toLocaleTimeString() : "N/A";

    const rateCard = h("div", { className: "card" },
      h("div", { className: "card-header" },
        h("h3", { className: "card-title" }, "Live GitHub Rate Limit"),
        h("span", { className: "badge badge-info" }, `${rl.remaining} / ${rl.limit} Remaining`)
      ),
      h("div", { style: { marginTop: "8px" } },
        h("div", { className: "rate-limit-bar", style: { width: "100%", height: "8px" } },
          h("div", { className: "rate-limit-fill", style: { width: `${ratePct}%` } })
        )
      ),
      h("div", { style: { display: "flex", justifyContent: "space-between", marginTop: "8px", fontSize: "12px", color: "var(--text-2)" } },
        h("span", {}, `Reset Time: ${resetDate}`),
        h("span", {}, `Usage: ${rl.used} requests made`)
      )
    );

    // 3. Pipeline & Cache Limits
    const limitsCard = h("div", { className: "card" },
      h("h3", { className: "card-title" }, "Pipeline Limits & Cache Configuration"),
      h("div", { style: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "16px", marginTop: "8px" } },
        h("div", { className: "card", style: { padding: "12px" } },
          h("span", { className: "text-caption" }, "ETag Cache TTL"),
          h("span", { style: { fontSize: "18px", fontWeight: "600", marginTop: "4px" } }, `${cfg.cache_ttl_seconds} seconds`)
        ),
        h("div", { className: "card", style: { padding: "12px" } },
          h("span", { className: "text-caption" }, "Max Repository Size"),
          h("span", { style: { fontSize: "18px", fontWeight: "600", marginTop: "4px" } }, `${cfg.max_repo_size_mb} MB`)
        ),
        h("div", { className: "card", style: { padding: "12px" } },
          h("span", { className: "text-caption" }, "Max Files Materialized"),
          h("span", { style: { fontSize: "18px", fontWeight: "600", marginTop: "4px" } }, `${cfg.max_files} files`)
        ),
        h("div", { className: "card", style: { padding: "12px" } },
          h("span", { className: "text-caption" }, "Max Individual File Size"),
          h("span", { style: { fontSize: "18px", fontWeight: "600", marginTop: "4px" } }, `${cfg.max_file_kb} KB`)
        )
      )
    );

    this.container.appendChild(authCard);
    this.container.appendChild(rateCard);
    this.container.appendChild(limitsCard);
  },
};
