import markdownit from "../vendor/markdown-it.esm.min.js";

export function resolveWikilink(source, wikilinks = {}) {
  const [target, ...alias] = source.split("|");
  const name = target.split("#")[0].trim().normalize("NFC");
  const rid = Object.hasOwn(wikilinks, name) ? wikilinks[name] : null;
  return { label: alias.length ? alias.join("|") : target, rid: typeof rid === "string" ? rid : null };
}

const md = markdownit({ html: false, linkify: false, typographer: false });

export function headingLevels(levels, minimum = 3) {
  const first = levels[0] || minimum;
  let previous = minimum - 1;
  return levels.map(level => {
    previous = Math.min(6, previous + 1, Math.max(minimum, minimum + level - first));
    return previous;
  });
}

md.core.ruler.after("inline", "embedded_headings", state => {
  if (!state.env.embedded) return;
  const openings = state.tokens.filter(token => token.type === "heading_open");
  const levels = headingLevels(openings.map(token => Number(token.tag.slice(1))));
  let index = 0;
  for (const token of state.tokens) {
    if (token.type === "heading_open") token.tag = `h${levels[index]}`;
    if (token.type === "heading_close") token.tag = `h${levels[index++]}`;
  }
});

md.inline.ruler.before("link", "wikilink", (state, silent) => {
  if (state.src.slice(state.pos, state.pos + 2) !== "[[") return false;
  const end = state.src.indexOf("]]", state.pos + 2);
  if (end < 0 || state.src.slice(state.pos, end).includes("\n")) return false;
  if (!silent) {
    const token = state.push("wikilink", "", 0);
    token.content = state.src.slice(state.pos + 2, end);
  }
  state.pos = end + 2;
  return true;
});

md.renderer.rules.wikilink = (tokens, index, options, env) => {
  const { label, rid } = resolveWikilink(tokens[index].content, env.wikilinks);
  const text = md.utils.escapeHtml(label);
  // A wikilink nested inside a Markdown link must not produce a second anchor.
  if (!rid || env.insideLink) return `<span class="wikilink-unresolved">${text}</span>`;
  return `<a class="wikilink" href="#/not/${encodeURIComponent(rid)}">${text}</a>`;
};

const defaultLink = md.renderer.rules.link_open || ((tokens, index, options, env, renderer) => renderer.renderToken(tokens, index, options));
md.renderer.rules.link_open = (tokens, index, options, env, renderer) => {
  const token = tokens[index];
  const href = token.attrGet("href") || "";
  if (/^(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(href)) {
    token.attrSet("target", "_blank");
    token.attrSet("rel", "noopener noreferrer");
  }
  env.insideLink = true;
  return defaultLink(tokens, index, options, env, renderer);
};
md.renderer.rules.link_close = (tokens, index, options, env, renderer) => {
  env.insideLink = false;
  return renderer.renderToken(tokens, index, options);
};

md.renderer.rules.image = (tokens, index) => {
  // Vault images have no public asset endpoint. Render their alternative text too.
  return `<span class="image-alt">${md.utils.escapeHtml(tokens[index].content)}</span>`;
};

for (const type of ["th_open", "td_open"]) {
  md.renderer.rules[type] = (tokens, index, options, env, renderer) => {
    const token = tokens[index];
    const alignment = token.attrGet("style")?.match(/^text-align:(left|center|right)$/)?.[1];
    token.attrs = (token.attrs || []).filter(([name]) => name !== "style");
    if (alignment) token.attrSet("class", `align-${alignment}`);
    return renderer.renderToken(tokens, index, options);
  };
}

md.core.ruler.after("inline", "task_checkboxes", state => {
  for (let index = 2; index < state.tokens.length; index++) {
    const token = state.tokens[index];
    if (token.type !== "inline" || state.tokens[index - 1].type !== "paragraph_open" || state.tokens[index - 2].type !== "list_item_open") continue;
    const first = token.children?.[0];
    const match = first?.type === "text" && first.content.match(/^\[([ xX])\]\s+/);
    if (!match) continue;
    first.content = first.content.slice(match[0].length);
    state.tokens[index - 2].attrJoin("class", "task-item");
    const checkbox = new state.Token("task_checkbox", "input", 0);
    checkbox.meta = { checked: match[1].toLowerCase() === "x" };
    token.children.unshift(checkbox);
  }
});
md.renderer.rules.task_checkbox = (tokens, index) =>
  `<input class="task-checkbox" type="checkbox" disabled${tokens[index].meta.checked ? " checked" : ""}>`;

export function renderMarkdown(body, wikilinks = {}) {
  return md.render(String(body), { wikilinks, insideLink: false });
}

export function mountMarkdown(root, body, wikilinks = {}) {
  root.classList.add("markdown-body");
  // Embedded notes sit below the page and section titles, including notes mounted off-DOM.
  root.innerHTML = md.render(String(body), { wikilinks, insideLink: false, embedded: true });
}
