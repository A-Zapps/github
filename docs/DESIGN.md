# DESIGN: GitHub Repository Analyzer

Reference feel: Linear, Stripe, enterprise SaaS dashboards. Calm, flat, dense but not crowded. Light theme only.

All UI is vanilla HTML, CSS, JS. Colors, spacing, and type come from `frontend/css/tokens.css`. Do not hardcode values in components.

---

## 1. Tokens

Brief colors are kept exactly. Added tokens are marked (new).

```css
:root {
  /* Brand and surfaces (from brief) */
  --bg:            #F4F5F7;
  --surface:       #FFFFFF;
  --sidebar:       #ECEEF1;
  --primary:       #5267D8;
  --text:          #20242C;
  --border:        #E3E6EB;

  /* Primary states (new) */
  --primary-hover: #4457C2;
  --primary-press: #3A4AAD;
  --primary-subtle:#EEF0FB;

  /* Text levels (new) */
  --text-2:        #5B6270;   /* captions, table headers */
  --text-3:        #8A909C;   /* placeholders, disabled only */
  --border-strong: #D2D6DD;

  /* Status (new). Each has a text color and a soft background. */
  --success:       #1F7A55;  --success-bg: #E6F5EE;
  --warning:       #96650A;  --warning-bg: #FBF3E1;
  --danger:        #B73636;  --danger-bg:  #FBEAEA;
  --info:          #2C6FA8;  --info-bg:    #E8F1F9;

  /* Radius, shadow, motion (new) */
  --r-sm: 6px;  --r-md: 8px;  --r-lg: 12px;  --r-pill: 999px;
  --shadow-1: 0 1px 2px rgba(16,24,40,.04), 0 1px 3px rgba(16,24,40,.06);
  --shadow-2: 0 4px 12px rgba(16,24,40,.08);
  --t-fast: 120ms;  --t-base: 180ms;  --ease: cubic-bezier(.2,.0,.2,1);

  /* Spacing, 4px base */
  --s-1:4px; --s-2:8px; --s-3:12px; --s-4:16px; --s-5:24px; --s-6:32px; --s-7:48px;

  /* Layout */
  --sidebar-w: 248px;  --sidebar-w-collapsed: 64px;  --topbar-h: 56px;
  --content-max: 1280px;
}
```

Contrast: `--primary` on white is about 4.9:1, so white text on a primary button passes AA for normal text. `--text-3` fails AA for body text, so it is only for placeholders and disabled states. Use `--text-2` for anything the user must read.

## 2. Type

- Font: Inter, self-hosted in `vendor/fonts/` (woff2). Fallback: `system-ui, -apple-system, "Segoe UI", sans-serif`. Mono: `ui-monospace, "SF Mono", Consolas, monospace` for paths, SHAs, code.
- Base size 14px, line-height 1.5.

| Use | Size | Weight |
|---|---|---|
| Page title | 24px | 600 |
| Section title | 16px | 600 |
| Card title | 14px | 600 |
| Body | 14px | 400 |
| Caption, table header | 12px | 500, `--text-2` |
| Big number in stat card | 28px | 600, tabular numbers |

Use `font-variant-numeric: tabular-nums` on all numbers in tables and stat cards.

## 3. App shell

```
+----------+---------------------------------------------------+
| Sidebar  | Topbar: page title | repo chip | rate-limit meter |
| 248px    +---------------------------------------------------+
|          | Content (max 1280px, 24px padding)                |
| logo     |  [stat] [stat] [stat] [stat]                      |
| nav x13  |  [ chart card          ] [ chart card ]           |
| collapse |  [ table card                          ]          |
+----------+---------------------------------------------------+
```

- Sidebar: `--sidebar` background, 1px right border. Logo and name at top. 13 nav items in the fixed order from PRD section 5. Collapse button at the bottom.
- Nav item: 36px high, icon 18px, label 14px. Hover: background `rgba(32,36,44,.05)`. Active: `--primary-subtle` background, `--primary` text and icon, 2px left bar in `--primary`. Set `aria-current="page"`.
- Collapsed (64px): icons only, label shows as tooltip on hover and focus. State saved in `localStorage` (wrapped in try/catch).
- Topbar: page title, current repo chip (`owner/name` + short SHA, mono), rate-limit meter (small bar + "4,812 left"), no other chrome.
- Breakpoints:
  - 1200px and up: sidebar expanded by default.
  - 768 to 1199px: sidebar collapsed by default.
  - Under 768px: sidebar is an off-canvas drawer opened with a menu button in the topbar. Grids become one column.

## 4. Components

Build each once in `components.css` and a matching helper in `ui/`.

| Component | Spec |
|---|---|
| Card | `--surface`, 1px `--border`, `--r-lg`, `--shadow-1`, padding 16 or 24. Hover lift (`--shadow-2`) only if the card is clickable. |
| Stat card | Label (caption), big number, optional delta or sub-label, optional small sparkline. |
| Button | Heights 32 and 36. Primary (filled indigo), Secondary (white, 1px `--border-strong`), Ghost, Danger. Radius `--r-md`. Disabled at 50% with `not-allowed`. Loading state shows a small spinner and keeps width. |
| Input, select | 36px high, 1px `--border-strong`, radius `--r-md`. Focus: 2px `--primary` ring with 2px offset. |
| Badge | Pill, 12px text, soft background plus colored text. Always has text, never color alone. |
| Risk badge | Low = success, Medium = warning, High = danger. |
| Severity badge | Info, Low, Medium, High, Critical. Critical uses solid `--danger` with white text. |
| Health badge | Healthy = success, Moderately Active = info, Declining = warning, Inactive = neutral grey. |
| Table | Sticky header, 12px uppercase-free header text in `--text-2`, row height 44, 1px row dividers, hover row `--bg`. Sortable columns show an arrow and `aria-sort`. Numeric columns right-aligned. Paths in mono with middle truncation and full text in `title`. Pagination at 25 rows. |
| Tabs | Underline style, 2px `--primary` line on the active tab. Arrow-key navigation. |
| Stepper | Used for analysis stages. Vertical list: pending (grey dot), running (spinner), done (check), failed (x, with message). |
| Progress bar | 6px, `--border` track, `--primary` fill. |
| Skeleton | Grey blocks with a slow shimmer. Static under reduced motion. |
| Toast | Bottom right, 4 s, `role="status"`. Errors stay until closed. |
| Empty state | Icon, one-line title, one-line help, one primary action. |
| Error state | Icon, plain message, error code in mono caption, Retry button. |
| Partial banner | Yellow strip: "Some parts failed: Security. Other results are shown." with a details link. |
| Tooltip | Dark charcoal, 12px, 150 ms delay. Works on focus. |
| Modal, drawer | Focus trap, Escape closes, scrim at 40% charcoal. |
| Gauge | Semi-circle SVG for scores 0 to 100. Number inside. Text label of the grade. |
| Code block | Mono 13px, `--bg` background, line numbers optional, horizontal scroll. Plain text only. |

Icons: Lucide set as inline SVG sprite in `ui/icons.js`, 18px, 1.75 stroke, `currentColor`.

## 5. Charts (Chart.js)

Global defaults in `ui/charts.js`:

- Font Inter 12px, color `--text-2`.
- Grid lines `--border`, no vertical grid on bar charts, no chart border.
- Tooltip: charcoal background, white text, radius 8.
- Legend at the top left, point style circles, only when 2 or more series.
- `maintainAspectRatio: false`. Each chart sits in a container with a set height (220 to 320px).
- Animation 300 ms ease-out. Off under reduced motion.
- No 3D, no pie charts. Use donut for part-of-whole with 6 slices or fewer.

Palette (in order): `#5267D8`, `#8E9BEA`, `#2F3F9E`, `#9AA1AE`, `#C7CCF3`, `#5B6270`. Semantic colors (success, warning, danger) are used only when the value means good, caution, or bad.

Every chart has a "View as table" toggle that shows the same data in a table. Every chart has an `aria-label` that states its main finding in one sentence.

## 6. Pages

| Page | Contents | Charts |
|---|---|---|
| Overview | Analyze box. Four stat cards (Quality score, Bug risk, Health class, Security findings). Recommendations (top 5). Recent analyses table. | Mini sparklines are optional. |
| Repository Analyzer | Input and stage stepper. Then: metadata card, stats row (stars, forks, issues, PRs, contributors), README preview as plain text, file tree summary. | Languages donut, commits per week bar (52 weeks) |
| Code Quality | Gauge with grade. Component score bars with weights. Percentile vs corpus. Worst 10 files table. Tech debt estimate with its label. | Complexity histogram, maintainability by top-level folder, duplication bar |
| Bug Prediction | Model badge (name, version). Risk distribution row. Sortable file table: path, tier, probability, top 3 drivers. Filters by tier and language. Not trained and unsupported-language states. | Risk donut, scatter of complexity vs recent churn colored by tier |
| Security Analysis | Severity counts. Tabs: Code findings, Secrets, Dependencies. Each finding: file, line, rule, severity, short explanation. Secrets masked. | Severity bar, category bar |
| Repository Health | Large health badge, class probability bars, signals table (value, what it means). Model badge. | Commits per month line, issues opened vs closed |
| Documentation | Gauge. Checklist of expected sections (found, missing, weak). Section detection list. Suggestions. | Section coverage bar |
| Developer Analytics | Stats row. Top contributors table. Bus factor card with a one-line explanation. | Commits by contributor bar, weekday x hour heatmap (canvas grid), PR merge time histogram, issue close time histogram |
| Repository Comparison | Pick 2 to 4 analyses. Metric table with best value marked. Cluster map. | Radar of normalized scores, PCA scatter with the corpus as light dots |
| AI Assistant | Mode selector (Explain file, Find bugs, Summarize architecture, Suggest improvements, Ask). File picker. Chat thread. Citations as clickable chips that open a code panel. Banner: "AI answers can be wrong. Check the cited code." | none |
| Reports | Generate button, job progress, list of past reports with download. | none |
| Model Performance | One card per model: algorithm, version, trained date, corpus size, headline metrics next to baselines, confusion matrix, curves, feature importance, link to model card. Models not trained show a "Not trained" card with the command to run. | Confusion matrix grid, ROC and PR curves, importance bar |
| Settings | Token status (set or not, never the value), rate limit, cache TTL, analysis limits, clear cache, LLM status, sidebar default. | none |

## 7. Motion

- Hover and focus transitions: 120 ms.
- Page change: 180 ms fade of the content area.
- Chart draw: 300 ms.
- Nothing bounces or loops except spinners and skeleton shimmer.
- Under `prefers-reduced-motion: reduce`: no transitions longer than 1 ms, no shimmer.

## 8. Writing in the UI

- Sentence case. Short. No exclamation marks.
- Say what happened and what to do. "GitHub rate limit reached. Try again at 14:32." Not "Oops, something went wrong."
- Probabilities as percent with no decimals ("73%"). Scores as integers.
- Dates as `12 Mar 2026`. Times in the user's local zone.
- Every prediction shows its model name and version in a small caption.
- Terms to explain with a tooltip: cyclomatic complexity, bus factor, PR-AUC, maintainability index.

## 9. Accessibility checklist

- Text contrast 4.5:1 or better.
- Focus ring visible on every control.
- Sidebar and tabs work with the keyboard.
- Tables have `<caption>` (visually hidden is fine).
- Charts have text alternatives and a table view.
- Touch targets at least 40px on mobile.
- Live regions for job progress and toasts.

## 10. Do not

- No gradients except flat fills. No glow. No glassmorphism.
- No emoji in the UI.
- No more than one primary button in a view.
- No new colors outside the tokens.
- No dark mode in v1.
