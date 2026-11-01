/**
 * Toast notification system.
 * Displays brief, auto-dismissing messages at the bottom-right of the viewport.
 * All content is rendered via textContent to prevent XSS (RULES B5).
 */

/**
 * Show a toast notification.
 * @param {string} message - The text message to display.
 * @param {"success"|"error"|"warning"|"info"} [variant="info"] - Toast variant.
 * @param {number} [durationMs=4000] - Auto-dismiss duration in milliseconds.
 */
export function showToast(message, variant = "info", durationMs = 4000) {
  // Ensure toast container exists
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    Object.assign(container.style, {
      position: "fixed",
      bottom: "24px",
      right: "24px",
      display: "flex",
      flexDirection: "column",
      gap: "8px",
      zIndex: "9999",
      pointerEvents: "none",
      maxWidth: "380px",
    });
    document.body.appendChild(container);
  }

  // Inject keyframes if not already present
  if (!document.getElementById("toast-keyframes")) {
    const styleEl = document.createElement("style");
    styleEl.id = "toast-keyframes";
    styleEl.textContent = `
      @keyframes toast-slide-in {
        from { opacity: 0; transform: translateX(40px); }
        to   { opacity: 1; transform: translateX(0); }
      }
      @keyframes toast-slide-out {
        from { opacity: 1; transform: translateX(0); }
        to   { opacity: 0; transform: translateX(40px); }
      }
    `;
    document.head.appendChild(styleEl);
  }

  const VARIANT_COLORS = {
    success: { bg: "var(--success-bg, #E6F5EE)", color: "var(--success, #1F7A55)", border: "var(--success, #1F7A55)" },
    error:   { bg: "var(--danger-bg, #FBEAEA)",  color: "var(--danger, #B73636)",  border: "var(--danger, #B73636)" },
    warning: { bg: "var(--warning-bg, #FBF3E1)", color: "var(--warning, #96650A)", border: "var(--warning, #96650A)" },
    info:    { bg: "var(--info-bg, #E8F1F9)",    color: "var(--info, #2C6FA8)",    border: "var(--info, #2C6FA8)" },
  };

  const colors = VARIANT_COLORS[variant] || VARIANT_COLORS.info;

  const toast = document.createElement("div");
  Object.assign(toast.style, {
    padding: "12px 16px",
    borderRadius: "var(--r-md, 8px)",
    backgroundColor: colors.bg,
    color: colors.color,
    border: `1px solid ${colors.border}`,
    fontFamily: "var(--font-sans, Inter, system-ui, sans-serif)",
    fontSize: "13px",
    fontWeight: "500",
    lineHeight: "1.4",
    boxShadow: "var(--shadow-2, 0 4px 12px rgba(16,24,40,.08))",
    animation: "toast-slide-in 0.25s var(--ease, ease) forwards",
    pointerEvents: "auto",
    cursor: "pointer",
    maxWidth: "100%",
    wordBreak: "break-word",
  });

  // Use textContent for XSS safety (RULES B5)
  toast.textContent = message;

  toast.addEventListener("click", () => dismissToast(toast));

  container.appendChild(toast);

  // Auto-dismiss
  const timer = setTimeout(() => dismissToast(toast), durationMs);
  toast._dismissTimer = timer;
}

function dismissToast(toast) {
  if (toast._dismissed) return;
  toast._dismissed = true;

  if (toast._dismissTimer) {
    clearTimeout(toast._dismissTimer);
  }

  toast.style.animation = "toast-slide-out 0.2s var(--ease, ease) forwards";
  toast.addEventListener("animationend", () => {
    toast.remove();
  });
}
