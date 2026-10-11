import { el, icon } from "../dom.js";
import { t } from "../i18n.js";
import { clockText } from "../pages/journal-model.js";

export function timeline(receipts) {
  // The day API already orders receipts by timestamp and rid.
  return el("ol", { class: "journal-timeline" }, receipts.map(receipt =>
    el("li", { class: "journal-receipt", "data-rid": receipt.rid, "data-event-id": receipt.event_id },
      el("time", { class: "journal-receipt-time", datetime: receipt.time }, clockText(receipt.time)),
      el("div", { class: "journal-receipt-content" },
        el("div", { class: "row journal-receipt-badges" },
          el("span", { class: "badge journal-harness" }, icon("bot"), receipt.harness),
          receipt.projects.map(project => el("span", {
            class: `badge journal-project${receipt.project_inferred ? " journal-project-inferred" : ""}`,
            title: receipt.project_inferred ? t("journal.inferredProject") : project,
          }, project))),
        el("p", { class: "journal-summary" }, receipt.summary),
        receipt.learned && el("p", { class: "journal-learned" },
          el("strong", {}, t("journal.learned")), el("span", {}, receipt.learned)),
        receipt.refs.length > 0 && el("div", { class: "journal-refs" },
          el("small", {}, t("journal.sources")), receipt.refs.map(record =>
            el("a", { href: `#/not/${encodeURIComponent(record.rid)}` }, icon("file-text"), record.title)))))));
}
