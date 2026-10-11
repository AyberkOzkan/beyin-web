export function el(tag, attributes = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (name.startsWith("on") && typeof value === "function") {
      node.addEventListener(name.slice(2).toLowerCase(), value);
    } else if (value !== false && value != null) {
      node.setAttribute(name, value === true ? "" : String(value));
    }
  }
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

let inlineIcons = false;

export async function prepareIcons() {
  // Inline the sprite everywhere: browsers disagree on external <use> references under a strict CSP.
  const response = await fetch("/static/vendor/lucide-sprite.svg", { credentials: "same-origin" });
  if (!response.ok) throw new Error("icon_load_failed");
  const parsed = new DOMParser().parseFromString(await response.text(), "image/svg+xml");
  if (parsed.querySelector("parsererror")) throw new Error("icon_parse_failed");
  const sprite = document.importNode(parsed.documentElement, true);
  sprite.setAttribute("class", "icon-sprite");
  sprite.setAttribute("aria-hidden", "true");
  document.body.prepend(sprite);
  inlineIcons = true;
}

export function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "icon");
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS(svg.namespaceURI, "use");
  use.setAttribute("href", inlineIcons ? `#${name}` : `/static/vendor/lucide-sprite.svg#${name}`);
  svg.append(use);
  return svg;
}
