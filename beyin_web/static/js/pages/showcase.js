import { el, icon } from "../dom.js";
import { t } from "../i18n.js";
import { mountMarkdown } from "../markdown.js";
import { card, listRow, badge, statusDot, progressBar, tabs, filterBox, emptyState, errorState, skeleton, illustrationSlot } from "../components/index.js";

export function render(root) {
  const colors = ["paper", "paper-side", "card", "line", "ink", "ink-soft", "sage", "sage-deep", "amber", "blue", "red"];
  const markdown = el("div", { id: "showcase-markdown" });
  mountMarkdown(markdown, t("showcase.markdownBody"), { Atlas: "df96cd83303a" });
  const states = el("div", { class: "stack" },
    emptyState(), errorState(), errorState(t("state.errorMessage"), () => {}), skeleton(3), skeleton(1));
  const selectedTab = el("p", { class: "muted", "aria-live": "polite" }, t("showcase.tabAll"));
  const sections = [
    card(t("showcase.colors"), el("div", { class: "row" }, colors.map(color =>
      el("div", { class: "swatch" }, el("div", { class: `swatch-color swatch-${color}` }), el("code", {}, `--${color}`))))),
    card(t("showcase.typography"), [el("h1", {}, t("showcase.heading")), el("h2", {}, t("showcase.subheading")),
      el("h3", {}, t("showcase.sectionHeading")), el("p", { id: "turkish-sample" }, t("showcase.fontSample")),
      el("small", {}, t("showcase.secondary")), el("p", {}, el("code", {}, t("showcase.codeSample")))]),
    card(t("showcase.badges"), el("div", { class: "stack" },
      el("div", { class: "row" }, ["note", "knowledge", "task", "receipt", "memory", "index", "rejected", "unknown"].map(kind => badge(kind))),
      el("div", { class: "row" }, ["inbox", "active", "waiting", "blocked", "done", "cancelled", "unknown"].map(status => badge(status, "status"))),
      el("div", { class: "row" }, ["inbox", "active", "waiting", "blocked", "done", "cancelled", "unknown"].map(status => el("span", { class: "row" }, statusDot(status), t(`status.${status}`)))))),
    card(t("showcase.lists"), [
      listRow({ title: t("showcase.rowTitle"), description: t("showcase.rowDescription"), href: "#/not/df96cd83303a", trailing: badge("note") }),
      listRow({ title: t("showcase.selectedRow"), description: t("showcase.rowDescription"), selected: true, href: "#/projeler/atlas", trailing: statusDot("active") }),
      listRow({ title: t("showcase.simpleRow"), leading: null })], "list-todo"),
    card(t("showcase.progress"), el("div", { class: "stack" }, progressBar(0), progressBar(3, 5), progressBar(100))),
    card(t("showcase.controls"), el("div", { class: "stack" },
      tabs([{ id: "all", label: t("showcase.tabAll") }, { id: "active", label: t("showcase.tabActive") }, { id: "disabled", label: t("showcase.tabDisabled"), disabled: true }], "all", id => { selectedTab.textContent = t(id === "all" ? "showcase.tabAll" : "showcase.tabActive"); }), selectedTab,
      filterBox(), filterBox({ value: t("showcase.filterValue") }), filterBox({ disabled: true }),
      el("div", { class: "row" }, el("button", { class: "button", type: "button" }, icon("check"), t("showcase.button")),
        el("button", { class: "button", type: "button", disabled: true }, t("showcase.tabDisabled"))),
      el("button", { class: "button", type: "button", onclick: () => document.dispatchEvent(new CustomEvent("beyin:health")) }, icon("activity"), t("health.title")))),
    card(t("showcase.states"), states),
    card(t("showcase.illustrations"), [el("p", { class: "muted" }, t("showcase.illustrationMessage")),
      ["hero-saray", "yan-agac", "baslik-daglar", "kart-cam"].map(name => illustrationSlot(name))]),
    card(t("showcase.markdown"), markdown, "book-open"),
  ];
  sections[0].classList.add("showcase-wide");
  sections.at(-1).classList.add("showcase-wide");
  root.replaceChildren(el("div", { class: "page-heading" }, el("h1", {}, t("page.showcase.title")),
    el("p", {}, t("page.showcase.description"))), el("div", { class: "showcase-grid" }, sections));
}

export function destroy() {}
