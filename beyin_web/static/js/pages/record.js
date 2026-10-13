import { el } from "../dom.js";
import { t } from "../i18n.js";
import { mountRecordView } from "../components/reader.js";
import { headingArt } from "../components/index.js";

let active;

export function render(root, params = {}) {
  destroy();
  const reader = el("div", { class: "knowledge-reader" });
  const context = el("div", { class: "knowledge-context" });
  root.replaceChildren(el("div", { class: "record-page" },
    el("header", { class: "page-heading" }, el("h1", {}, t("page.record.title")), el("p", {}, t("page.record.description")), headingArt("record")),
    el("div", { class: "record-columns" }, reader, context)));
  active = mountRecordView(reader, context, params.rid);
}

export function destroy() {
  active?.destroy();
  active = null;
}
