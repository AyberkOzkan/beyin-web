import { get } from "../api.js";
import { el, icon } from "../dom.js";
import { t, formatDate, formatTime } from "../i18n.js";
import { mountMarkdown } from "../markdown.js";
import { withoutLeadingTitle } from "../pages/knowledge-model.js";
import { badge, emptyState, errorState, skeleton } from "./index.js";
import { createContextPanel } from "./context-panel.js";
import { recordKind } from "../pages/knowledge-model.js";

export function createReader(record) {
  let destroyed = false;
  const root = el("article", { class: "card record-reader", "data-rid": record.rid });
  const path = el("input", { class: "reader-path", readonly: true, value: record.path,
    "aria-label": t("knowledge.path"), hidden: true });
  const feedback = el("span", { class: "muted", role: "status" });
  async function copyPath() {
    try {
      if (!navigator.clipboard?.writeText) throw new Error("clipboard_unavailable");
      await navigator.clipboard.writeText(record.path);
      if (!destroyed) feedback.textContent = t("knowledge.copied");
    } catch {
      if (destroyed) return;
      path.hidden = false;
      path.focus();
      path.select();
      feedback.textContent = t("knowledge.copyFallback");
    }
  }
  const copy = el("button", { type: "button", class: "button" }, t("knowledge.copyPath"));
  copy.addEventListener("click", copyPath);
  const toggle = el("summary", { "aria-label": t("knowledge.actions") }, icon("ellipsis"));
  const menu = el("details", { class: "reader-menu" }, toggle, copy);
  if (typeof record.obsidian_uri === "string" && record.obsidian_uri.startsWith("obsidian://open?")) {
    menu.append(el("a", { class: "button", href: record.obsidian_uri }, t("knowledge.openObsidian")));
  }
  function escape(event) {
    if (event.key !== "Escape" || !menu.open) return;
    event.preventDefault();
    event.stopPropagation();
    menu.open = false;
    toggle.focus();
  }
  function outside(event) { if (!menu.contains(event.target)) menu.open = false; }
  document.addEventListener("keydown", escape);
  document.addEventListener("click", outside);
  const metadata = el("div", { class: "row reader-metadata" }, badge(recordKind(record.kind)),
    record.kind === "untrusted" && el("span", { class: "badge reader-untrusted" }, t("knowledge.untrusted")),
    record.project && el("a", { href: `#/projeler/${encodeURIComponent(record.project)}` }, record.project),
    el("time", { datetime: record.mtime, title: t("knowledge.modified"), class: "muted" },
      t("knowledge.dateTime", { date: formatDate(record.mtime), time: formatTime(record.mtime) })));
  root.append(el("header", { class: "reader-header" }, el("h2", { class: "reader-title" }, record.title), menu),
    metadata, path, feedback);
  const body = el("div", { class: "reader-body" });
  mountMarkdown(body, withoutLeadingTitle(record.body, record.title), record.wikilinks);
  if (record.kind === "task") {
    const meta = record.meta || {};
    root.append(el("dl", { class: "reader-task context-fields" },
      el("dt", {}, t("knowledge.status")), el("dd", { "data-field": "status" }, badge(meta.status, "status")),
      el("dt", {}, t("knowledge.owner")), el("dd", { "data-field": "owner" }, meta.owner || t("knowledge.unspecified")),
      el("dt", {}, t("knowledge.nextAction")), el("dd", { "data-field": "next_action" }, meta.next_action || t("knowledge.unspecified"))),
    el("details", { class: "reader-task-body" }, el("summary", {}, t("knowledge.taskBody")), body));
  } else root.append(body);
  document.dispatchEvent(new CustomEvent("beyin:record", { detail: { obsidianUri: record.obsidian_uri ?? "" } }));
  return { root, destroy() {
    if (destroyed) return;
    destroyed = true;
    document.dispatchEvent(new CustomEvent("beyin:record", { detail: { obsidianUri: null } }));
    copy.removeEventListener("click", copyPath);
    document.removeEventListener("keydown", escape);
    document.removeEventListener("click", outside);
  } };
}

export function mountRecordView(readerRoot, contextRoot, rid) {
  let destroyed = false;
  let request = 0;
  let reader;
  let context;
  function dispose() { reader?.destroy(); context?.destroy(); reader = null; context = null; }
  async function load() {
    if (destroyed) return;
    const current = ++request;
    dispose();
    readerRoot.replaceChildren(skeleton(5));
    contextRoot.replaceChildren(skeleton(5));
    try {
      const data = await get(`/api/v1/records/${encodeURIComponent(rid)}`);
      if (destroyed || current !== request) return;
      reader = createReader(data);
      context = createContextPanel(data);
      readerRoot.replaceChildren(reader.root);
      contextRoot.replaceChildren(context.root);
    } catch (error) {
      if (destroyed || current !== request || error.code === "unauthorized") return;
      const missing = error.code === "not_found";
      readerRoot.replaceChildren(missing ? emptyState(t("knowledge.notFound"), t("knowledge.notFoundMessage")) :
        errorState(t("knowledge.recordError"), () => void load()));
      contextRoot.replaceChildren(missing ? el("p", { class: "muted" }, t("knowledge.noContext")) :
        errorState(t("knowledge.recordError"), () => void load()));
    }
  }
  void load();
  return { destroy() { destroyed = true; ++request; dispose(); } };
}
