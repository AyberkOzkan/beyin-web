import { get } from "../api.js";
import { el } from "../dom.js";
import { t } from "../i18n.js";
import { headingArt, filterBox, listRow, emptyState, errorState, skeleton } from "../components/index.js";
import { mountRecordView } from "../components/reader.js";
import { filterGroups, firstNote } from "./knowledge-model.js";

let active;

function address(rid, query) {
  return `#/bilgi${rid ? `/${encodeURIComponent(rid)}` : ""}${query ? `?q=${encodeURIComponent(query)}` : ""}`;
}

function updateList(state) {
  if (active !== state) return;
  const groups = filterGroups(state.groups, state.query);
  state.list.replaceChildren(...(groups.length ? groups.map(group => {
    const name = group.project || t("knowledge.general");
    return el("details", { class: "knowledge-group", open: true, "data-project": group.project || "" },
      el("summary", {}, name), group.records.map(record => listRow({ title: record.title,
        description: record.summary || record.excerpt || "", selected: record.rid === state.rid,
        href: address(record.rid, state.query) })));
  }) : [emptyState(t("knowledge.emptyTitle"), t(state.query ? "knowledge.noMatches" : "knowledge.emptyMessage"))]));
}

async function load(state) {
  if (active !== state) return;
  const request = ++state.request;
  state.list.replaceChildren(skeleton(4));
  try {
    const data = await get("/api/v1/knowledge");
    if (active !== state || request !== state.request) return;
    state.groups = data.groups;
    if (!state.rid) {
      const note = firstNote(state.groups);
      if (note) { location.replace(address(note.rid, state.query)); return; }
      state.reader.replaceChildren(emptyState(t("knowledge.emptyTitle"), t("knowledge.emptyMessage")));
      state.context.replaceChildren(el("p", { class: "muted" }, t("knowledge.noContext")));
    }
    updateList(state);
  } catch (error) {
    if (active !== state || request !== state.request || error.code === "unauthorized") return;
    state.list.replaceChildren(errorState(t("knowledge.listError"), () => void load(state)));
    if (!state.rid) {
      state.reader.replaceChildren(errorState(t("knowledge.listError"), () => void load(state)));
      state.context.replaceChildren(errorState(t("knowledge.listError"), () => void load(state)));
    }
  }
}

export function render(root, params = {}) {
  destroy();
  const state = { rid: params.rid, query: params.q || "", groups: [], request: 0,
    reader: el("div", { class: "knowledge-reader" }, skeleton(5)),
    context: el("div", { class: "knowledge-context" }, skeleton(5)),
    list: el("div", { class: "knowledge-list" }, skeleton(4)) };
  active = state;
  const filter = filterBox({ label: t("knowledge.filter"), value: state.query });
  state.input = filter.querySelector("input");
  state.filterChanged = event => {
    if (active !== state) return;
    const value = event.target.value;
    state.query = value;
    history.replaceState(history.state, "", address(state.rid, value));
    updateList(state);
  };
  state.input.addEventListener("input", state.filterChanged);
  const sidebar = el("nav", { class: "card knowledge-sidebar", "aria-label": t("knowledge.notes") }, filter, state.list);
  root.replaceChildren(el("div", { class: "knowledge-page" },
    el("header", { class: "page-heading" }, el("h1", {}, t("page.knowledge.title")), el("p", {}, t("page.knowledge.description")), headingArt("knowledge")),
    el("div", { class: "three-columns knowledge-columns" }, sidebar, state.reader, state.context)));
  if (state.rid) state.view = mountRecordView(state.reader, state.context, state.rid);
  void load(state);
}

export function destroy() {
  active?.view?.destroy();
  if (active) active.input.removeEventListener("input", active.filterChanged);
  active = null;
}
