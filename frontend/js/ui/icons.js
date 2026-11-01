/**
 * Lucide-style SVG icons builder.
 */

const SVG_NS = "http://www.w3.org/2000/svg";

function createSvg(contentPaths, size = 18) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.75");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");

  for (const pathDef of contentPaths) {
    const el = document.createElementNS(SVG_NS, pathDef.tag);
    for (const [k, v] of Object.entries(pathDef.attrs)) {
      el.setAttribute(k, v);
    }
    svg.appendChild(el);
  }
  return svg;
}

export const icons = {
  overview: (s) => createSvg([
    { tag: "rect", attrs: { x: "3", y: "3", width: "7", height: "9", rx: "1" } },
    { tag: "rect", attrs: { x: "14", y: "3", width: "7", height: "5", rx: "1" } },
    { tag: "rect", attrs: { x: "14", y: "12", width: "7", height: "9", rx: "1" } },
    { tag: "rect", attrs: { x: "3", y: "16", width: "7", height: "5", rx: "1" } }
  ], s),
  analyzer: (s) => createSvg([
    { tag: "circle", attrs: { cx: "11", cy: "11", r: "8" } },
    { tag: "line", attrs: { x1: "21", y1: "21", x2: "16.65", y2: "16.65" } }
  ], s),
  quality: (s) => createSvg([
    { tag: "circle", attrs: { cx: "12", cy: "12", r: "10" } },
    { tag: "path", attrs: { d: "m4.93 4.93 4.24 4.24" } },
    { tag: "path", attrs: { d: "m14.83 9.17 4.24-4.24" } },
    { tag: "path", attrs: { d: "m14.83 14.83 4.24 4.24" } },
    { tag: "path", attrs: { d: "m9.17 14.83-4.24 4.24" } },
    { tag: "circle", attrs: { cx: "12", cy: "12", r: "4" } }
  ], s),
  bugs: (s) => createSvg([
    { tag: "rect", attrs: { width: "8", height: "14", x: "8", y: "6", rx: "4" } },
    { tag: "path", attrs: { d: "m19 7-3 2" } },
    { tag: "path", attrs: { d: "m5 7 3 2" } },
    { tag: "path", attrs: { d: "m19 19-3-2" } },
    { tag: "path", attrs: { d: "m5 19 3-2" } },
    { tag: "path", attrs: { d: "M20 13h-4" } },
    { tag: "path", attrs: { d: "M4 13h4" } },
    { tag: "path", attrs: { d: "m10 4 1 2" } },
    { tag: "path", attrs: { d: "m14 4-1 2" } }
  ], s),
  security: (s) => createSvg([
    { tag: "path", attrs: { d: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10" } }
  ], s),
  health: (s) => createSvg([
    { tag: "path", attrs: { d: "M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z" } }
  ], s),
  docs: (s) => createSvg([
    { tag: "path", attrs: { d: "M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z" } },
    { tag: "path", attrs: { d: "M6 6h10" } },
    { tag: "path", attrs: { d: "M6 10h10" } }
  ], s),
  developers: (s) => createSvg([
    { tag: "path", attrs: { d: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" } },
    { tag: "circle", attrs: { cx: "9", cy: "7", r: "4" } },
    { tag: "path", attrs: { d: "M22 21v-2a4 4 0 0 0-3-3.87" } },
    { tag: "path", attrs: { d: "M16 3.13a4 4 0 0 1 0 7.75" } }
  ], s),
  compare: (s) => createSvg([
    { tag: "path", attrs: { d: "m16 3 4 4-4 4" } },
    { tag: "path", attrs: { d: "M20 7H4" } },
    { tag: "path", attrs: { d: "m8 21-4-4 4-4" } },
    { tag: "path", attrs: { d: "M4 17h16" } }
  ], s),
  assistant: (s) => createSvg([
    { tag: "path", attrs: { d: "M12 8V4H8" } },
    { tag: "rect", attrs: { width: "16", height: "12", x: "4", y: "8", rx: "2" } },
    { tag: "path", attrs: { d: "M2 14h2" } },
    { tag: "path", attrs: { d: "M20 14h2" } },
    { tag: "path", attrs: { d: "M15 13v2" } },
    { tag: "path", attrs: { d: "M9 13v2" } }
  ], s),
  reports: (s) => createSvg([
    { tag: "path", attrs: { d: "M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" } },
    { tag: "polyline", attrs: { points: "14 2 14 8 20 8" } },
    { tag: "line", attrs: { x1: "16", y1: "13", x2: "8", y2: "13" } },
    { tag: "line", attrs: { x1: "16", y1: "17", x2: "8", y2: "17" } }
  ], s),
  models: (s) => createSvg([
    { tag: "path", attrs: { d: "M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" } },
    { tag: "polyline", attrs: { points: "3.29 7 12 12 20.71 7" } },
    { tag: "line", attrs: { x1: "12", y1: "22", x2: "12", y2: "12" } }
  ], s),
  settings: (s) => createSvg([
    { tag: "path", attrs: { d: "M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" } },
    { tag: "circle", attrs: { cx: "12", cy: "12", r: "3" } }
  ], s),
  collapseLeft: (s) => createSvg([
    { tag: "polyline", attrs: { points: "15 18 9 12 15 6" } }
  ], s),
  collapseRight: (s) => createSvg([
    { tag: "polyline", attrs: { points: "9 18 15 12 9 6" } }
  ], s),
  menu: (s) => createSvg([
    { tag: "line", attrs: { x1: "4", y1: "6", x2: "20", y2: "6" } },
    { tag: "line", attrs: { x1: "4", y1: "12", x2: "20", y2: "12" } },
    { tag: "line", attrs: { x1: "4", y1: "18", x2: "20", y2: "18" } }
  ], s),
  info: (s) => createSvg([
    { tag: "circle", attrs: { cx: "12", cy: "12", r: "10" } },
    { tag: "line", attrs: { x1: "12", y1: "16", x2: "12", y2: "12" } },
    { tag: "line", attrs: { x1: "12", y1: "8", x2: "12.01", y2: "8" } }
  ], s),
  alertCircle: (s) => createSvg([
    { tag: "circle", attrs: { cx: "12", cy: "12", r: "10" } },
    { tag: "line", attrs: { x1: "12", y1: "8", x2: "12", y2: "12" } },
    { tag: "line", attrs: { x1: "12", y1: "16", x2: "12.01", y2: "16" } }
  ], s),
  checkCircle: (s) => createSvg([
    { tag: "circle", attrs: { cx: "12", cy: "12", r: "10" } },
    { tag: "polyline", attrs: { points: "9 12 11 14 15 10" } }
  ], s),
  bug: (s) => icons.bugs(s),
  shield: (s) => icons.security(s),
  users: (s) => icons.developers(s),
  book: (s) => icons.docs(s),
  heart: (s) => icons.health(s)
};
