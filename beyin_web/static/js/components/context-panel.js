import { el } from "../dom.js";
import { t, formatDate } from "../i18n.js";
import { card, badge, listRow } from "./index.js";
import { createMiniGraph } from "./mini-graph.js";
import { firstSentence, recordKind, receiptDate } from "../pages/knowledge-model.js";

function links(records, className) {
  return el("div", { class: className }, records.length ? records.map(record =>
    listRow({ title: record.title, href: `#/not/${encodeURIComponent(record.rid)}` })) :
    el("p", { class: "muted" }, t("knowledge.noLinks")));
}

export function createContextPanel(record) {
  const graph = createMiniGraph(record.rid);
  const date = formatDate(record.mtime);
  const root = el("aside", { class: "context-panel stack", "aria-label": t("knowledge.context") },
    card(t("knowledge.context"), [el("dl", { class: "context-fields" },
      el("dt", {}, t("knowledge.project")), el("dd", { "data-field": "project" }, record.project ?
        el("a", { href: `#/projeler/${encodeURIComponent(record.project)}` }, record.project) : t("knowledge.general")),
      el("dt", {}, t("knowledge.kind")), el("dd", {}, badge(recordKind(record.kind))),
      el("dt", {}, t("knowledge.modified")), el("dd", {}, el("time", { datetime: record.mtime }, date)),
      el("dt", {}, t("knowledge.path")), el("dd", { class: "context-path" }, record.path))], "info"),
    card(t("knowledge.graph"), [graph.root, el("a", { class: "context-graph-link", href: `#/grafik?odak=${encodeURIComponent(record.rid)}` }, t("knowledge.openGraph"))], "waypoints"),
    card(t("knowledge.links"), [
      el("h3", {}, t("knowledge.outgoing")), links(record.links_out || [], "context-outgoing"),
      el("div", { class: "context-unresolved" }, (record.unresolved || []).map(name =>
        el("span", { class: "wikilink-unresolved" }, name))),
      el("h3", {}, t("knowledge.incoming")), links(record.links_in || [], "context-incoming")], "link"),
    card(t("knowledge.receipts"), [el("div", { class: "context-receipts" }, record.receipts?.length ? record.receipts.map(receipt => {
      const day = receiptDate(receipt.time);
      return listRow({ title: firstSentence(receipt.summary), description: formatDate(`${day}T12:00:00`),
        href: `#/gunlukler/${day}`, leading: "receipt" });
    }) : el("p", { class: "muted" }, t("knowledge.noReceipts")))], "receipt"));
  return { root, destroy() { graph.destroy(); } };
}
