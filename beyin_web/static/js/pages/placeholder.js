import { el } from "../dom.js";
import { t } from "../i18n.js";
import { emptyState } from "../components/index.js";

export function render(root, params) {
  const page = params.page;
  root.replaceChildren(
    el("div", { class: "page-heading" }, el("h1", {}, t(`page.${page}.title`)), el("p", {}, t(`page.${page}.description`))),
    el("section", { class: "card" }, emptyState(t("state.soonTitle"), t("state.soonMessage"))));
}

export function destroy() {}
