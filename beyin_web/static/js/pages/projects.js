import { get } from "../api.js";
import { el } from "../dom.js";
import { t, formatDate, relativeTime } from "../i18n.js";
import { card, listRow, progressBar, tabs, filterBox, emptyState, errorState, skeleton } from "../components/index.js";
import { mountMarkdown } from "../markdown.js";
import { scrollTo } from "../accessibility.js";
import { withoutLeadingTitle } from "./knowledge-model.js";
import { splitNote, taskIcon, filterProjects, projectCounts, newestProject, projectHash, firstSentence } from "./projects-model.js";

let active;

function current(state) {
  return active === state;
}

function empty(key) {
  return emptyState(t(`projects.${key}.emptyTitle`), t(`projects.${key}.empty`));
}

function activity(value) {
  return value ? el("time", { datetime: value, title: formatDate(value) },
    t("projects.lastActivity", { time: relativeTime(value) })) : el("small", {}, t("projects.noActivity"));
}

function progress(project) {
  return project.total > 0 ? progressBar(project.done, project.total) :
    el("small", { class: "projects-no-tasks" }, t("projects.noTasks"));
}

function drawList(state) {
  const projects = filterProjects(state.projects, state.query, state.tab);
  state.list.replaceChildren(...(projects.length ? projects.map(project => {
    const selected = project.name === state.name;
    return el("a", {
      class: `card projects-project${project.quiet ? " projects-quiet" : ""}${selected ? " projects-selected" : ""}`,
      href: projectHash(project.name, state.query, state.tab), "data-project": project.name,
      "aria-current": selected ? "page" : null,
    }, el("strong", {}, project.title || project.name),
    el("p", { class: "projects-summary" }, project.summary || ""), progress(project), activity(project.last_activity));
  }) : [empty("list")]));
}

function updateFilters(state) {
  if (!current(state)) return;
  // Replacing a filter edit keeps typing focused while the URL remains shareable.
  history.replaceState(null, "", projectHash(state.name, state.query, state.tab));
  drawList(state);
}

function drawControls(state) {
  const counts = projectCounts(state.projects);
  state.controls.replaceChildren(filterBox({ label: t("projects.filter"), value: state.query,
    onInput: value => { if (current(state)) { state.query = value; updateFilters(state); } } }),
  tabs(["all", "active"].map(id => ({ id, label: t(`projects.tab.${id}`, { count: counts[id] }) })), state.tab,
    id => { if (current(state)) { state.tab = id; updateFilters(state); } }));
}

function showEmpty(state, key = "project") {
  state.middle.replaceChildren(empty(key));
  for (const section of state.sections) section.content.replaceChildren(empty(section.key));
  state.page.setAttribute("aria-busy", "false");
}

function showProjectLoading(state) {
  state.page.setAttribute("aria-busy", "true");
  state.middle.replaceChildren(skeleton(5));
  for (const section of state.sections) section.content.replaceChildren(skeleton(3));
}

function mountNote(state, root, body, wikilinks) {
  root.replaceChildren();
  if (!body.trim()) { root.append(empty("note")); return; }
  const { intro, sections } = splitNote(body);
  if (sections.length <= 3) { mountMarkdown(root, body, wikilinks); return; }
  const contents = el("nav", { class: "projects-toc", "aria-labelledby": "projects-toc-title" },
    el("h3", { id: "projects-toc-title" }, t("projects.toc")));
  const list = el("ol");
  const details = sections.map((section, index) => {
    const content = el("div", { class: "projects-section-body" });
    mountMarkdown(content, section.body, wikilinks);
    const panel = el("details", { class: "projects-note-section", id: section.id, open: index === 0 },
      el("summary", {}, section.title), content);
    const link = el("a", { href: `#${section.id}` }, section.title);
    link.addEventListener("click", event => {
      event.preventDefault();
      panel.open = true;
      scrollTo(panel);
      panel.querySelector("summary").focus();
    }, { signal: state.listeners.signal });
    list.append(el("li", {}, link));
    return panel;
  });
  const expand = el("button", { class: "button projects-expand", type: "button" }, t("projects.expandAll"));
  expand.addEventListener("click", () => details.forEach(panel => { panel.open = true; }),
    { signal: state.listeners.signal });
  contents.append(list, expand);
  root.append(contents);
  if (intro.trim()) {
    const introduction = el("div", { class: "projects-note-intro" });
    mountMarkdown(introduction, intro, wikilinks);
    root.append(introduction);
  }
  root.append(...details);
}

async function loadNote(state, note, root) {
  const version = ++state.noteVersion;
  root.replaceChildren(skeleton(4));
  try {
    const record = note.rid ? await get(`/api/v1/records/${encodeURIComponent(note.rid)}`) : null;
    if (!current(state) || version !== state.noteVersion) return;
    // The page already prints the project title above the note.
    mountNote(state, root, withoutLeadingTitle(note.body || "", note.title), record?.wikilinks || {});
  } catch {
    if (current(state) && version === state.noteVersion) {
      root.replaceChildren(errorState(t("projects.note.error"), () => {
        if (current(state)) void loadNote(state, note, root);
      }));
    }
  }
}

function drawSection(section, values, makeRow) {
  section.content.replaceChildren(...(values.length ? values.map(makeRow) : [empty(section.key)]));
}

async function loadProject(state) {
  if (!current(state)) return;
  const version = ++state.projectVersion;
  ++state.noteVersion;
  showProjectLoading(state);
  try {
    const data = await get(`/api/v1/projects/${encodeURIComponent(state.name)}`);
    if (!current(state) || version !== state.projectVersion) return;
    const project = data.project;
    const note = el("div", { id: "projects-note" });
    state.middle.replaceChildren(el("header", { class: "projects-detail-heading" },
      el("h2", { id: "projects-detail-title" }, project.title || project.name),
      el("div", { class: "projects-status row" }, progress(project), activity(project.last_activity))), note);
    if (data.note) void loadNote(state, data.note, note);
    else note.append(empty("note"));
    drawSection(state.sections[0], data.tasks, task => {
      const row = listRow({ title: task.title, description: task.next_action || "", leading: taskIcon(task.status),
        href: `#/not/${encodeURIComponent(task.rid)}` });
      row.classList.add("projects-task");
      row.dataset.status = task.status || "unknown";
      const status = ["done", "active", "waiting", "blocked", "inbox", "cancelled"].includes(task.status) ? task.status : "unknown";
      row.setAttribute("aria-label", t("projects.taskLabel", { title: task.title, status: t(`status.${status}`) }));
      row.querySelector(".icon").classList.add(`tone-${status}`);
      return row;
    });
    drawSection(state.sections[1], data.knowledge, record => listRow({ title: record.title,
      leading: "book-open", href: `#/not/${encodeURIComponent(record.rid)}` }));
    drawSection(state.sections[2], data.receipts.slice(0, 5), receipt => {
      const date = receipt.time?.slice(0, 10);
      return listRow({ title: firstSentence(receipt.summary), leading: "clock",
        description: date ? formatDate(date) : t("projects.noActivity"),
        href: date ? `#/gunlukler/${date}` : null });
    });
    state.page.setAttribute("aria-busy", "false");
  } catch (error) {
    if (!current(state) || version !== state.projectVersion) return;
    if (error.code === "not_found") { showEmpty(state); return; }
    const retry = () => { if (current(state)) void loadProject(state); };
    state.middle.replaceChildren(errorState(t("projects.project.error"), retry));
    for (const section of state.sections) {
      section.content.replaceChildren(errorState(t(`projects.${section.key}.error`), retry));
    }
    state.page.setAttribute("aria-busy", "false");
  }
}

async function loadList(state) {
  if (!current(state)) return;
  const version = ++state.listVersion;
  state.page.setAttribute("aria-busy", "true");
  state.list.replaceChildren(skeleton(6));
  try {
    const data = await get("/api/v1/projects");
    if (!current(state) || version !== state.listVersion) return;
    state.projects = data.projects;
    drawControls(state);
    drawList(state);
    if (!state.name) {
      const newest = newestProject(state.projects);
      if (newest) location.replace(projectHash(newest.name, state.query, state.tab));
      else showEmpty(state, "list");
    } else if (state.projects.some(project => project.name === state.name)) {
      void loadProject(state);
    } else {
      // A missing project is an ordinary empty state; the list remains usable.
      showEmpty(state);
    }
  } catch {
    if (!current(state) || version !== state.listVersion) return;
    const retry = () => { if (current(state)) void loadList(state); };
    state.list.replaceChildren(errorState(t("projects.list.error"), retry));
    if (state.name) void loadProject(state);
    else {
      state.middle.replaceChildren(errorState(t("projects.project.error"), retry));
      for (const section of state.sections) section.content.replaceChildren(errorState(t(`projects.${section.key}.error`), retry));
      state.page.setAttribute("aria-busy", "false");
    }
  }
}

export function render(root, params = {}) {
  destroy();
  const controls = el("div", { class: "projects-controls stack" }, skeleton(2));
  const list = el("div", { id: "projects-list", class: "stack" });
  const left = el("section", { class: "projects-left stack", "aria-labelledby": "projects-page-title" },
    el("h1", { id: "projects-page-title" }, t("page.projects.title")), controls, list);
  const middle = el("article", { class: "card projects-middle", "aria-label": t("projects.detail") });
  const sections = [["tasks", "list-todo"], ["knowledge", "book-open"], ["receipts", "history"]].map(([key, name]) => {
    const content = el("div", { class: "projects-section-content" });
    const section = card(t(`projects.${key}.title`), content, name);
    section.id = `projects-${key}`;
    return { key, content, root: section };
  });
  const right = el("aside", { class: "projects-right stack", "aria-label": t("projects.context") }, sections.map(section => section.root));
  const page = el("div", { class: "projects-page three-columns", "aria-busy": "true" }, left, middle, right);
  const state = { root, page, middle, controls, list, sections, name: params.name || "", query: params.q || "",
    tab: params.tab === "active" ? "active" : "all", projects: [], listeners: new AbortController(),
    listVersion: 0, projectVersion: 0, noteVersion: 0 };
  active = state;
  root.replaceChildren(page);
  showProjectLoading(state);
  void loadList(state);
}

export function destroy() {
  if (!active) return;
  active.listeners.abort();
  active.root.replaceChildren();
  active = null;
}
