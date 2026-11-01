/**
 * Hyperscript DOM element builder enforcing textContent and safe attribute setting.
 * Protects against XSS injection by never using innerHTML (RULES B8).
 *
 * @param {string} tag
 * @param {Object} [props]
 * @param {...(Node|string|number)} [children]
 * @returns {HTMLElement}
 */
export function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);

  if (props) {
    for (const [key, val] of Object.entries(props)) {
      if (val === undefined || val === null) continue;

      if (key.startsWith('on') && typeof val === 'function') {
        const eventName = key.slice(2).toLowerCase();
        el.addEventListener(eventName, val);
      } else if (key === 'className' || key === 'class') {
        el.className = val;
      } else if (key === 'style' && typeof val === 'object') {
        Object.assign(el.style, val);
      } else if (key === 'dataset' && typeof val === 'object') {
        Object.assign(el.dataset, val);
      } else if (typeof val === 'boolean') {
        if (val) el.setAttribute(key, '');
        else el.removeAttribute(key);
      } else {
        el.setAttribute(key, String(val));
      }
    }
  }

  for (const child of children.flat(Infinity)) {
    if (child === undefined || child === null || child === false) continue;
    if (child instanceof Node) {
      el.appendChild(child);
    } else {
      el.appendChild(document.createTextNode(String(child)));
    }
  }

  return el;
}
