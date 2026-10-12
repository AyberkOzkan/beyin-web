import { get, startPulse } from "./api.js";
import { setMessages, t, formatDate, formatTime } from "./i18n.js";
import { el, icon, prepareIcons } from "./dom.js";
import { parseRoute } from "./router.js";
import { navigationIndex, shouldFocusMain, preserveFocus } from "./accessibility.js";
import { errorState, statusDot, skeleton, illustrationSlot, setDrawings, obsidianTarget } from "./components/index.js";
import { healthDrawer } from "./components/health-drawer.js";
import { indicatorState } from "./pages/memory-model.js";
import * as placeholder from "./pages/placeholder.js";
import * as showcase from "./pages/showcase.js";
import * as home from "./pages/home.js";
import * as projects from "./pages/projects.js";
import * as knowledge from "./pages/knowledge.js";
import * as record from "./pages/record.js";
import * as journal from "./pages/journal.js";
import * as graph from "./pages/graph.js";
import * as search from "./pages/search.js";
import * as memory from "./pages/memory.js";
import * as reports from "./pages/reports.js";

const navigation = [
  ["home", "#/", "house"], ["projects", "#/projeler", "folder-kanban"],
  ["knowledge", "#/bilgi", "book-open"], ["journal", "#/gunlukler", "calendar-days"],
  ["graph", "#/grafik", "waypoints"], ["search", "#/arama", "search"], ["memory", "#/hafiza", "brain"],
  ["reports", "#/raporlar", "scroll-text"],
];
const pages = { showcase, home, projects, knowledge, record, journal, graph, search, memory, reports };
let currentPage;
let stopPulse = () => {};
let unauthorized = false;
let drawer;
let translationsReady = false;
let currentRoute;
let cancelFocus = () => {};
let vaultObsidianUri;
let recordObsidianUri = null;

function updateObsidianLink() {
  const actions = document.querySelector(".topbar-actions");
  let link = actions.querySelector(".obsidian-link");
  const target = obsidianTarget(vaultObsidianUri, recordObsidianUri);
  if (!target) { link?.remove(); return; }
  if (!link) {
    link = el("a", { class: "button obsidian-link" },
      icon("external-link"), el("span", { class: "obsidian-link-text" }, t("shell.openObsidian")));
    actions.prepend(link);
  }
  link.setAttribute("href", target.href);
  link.setAttribute("aria-label", t(target.labelKey));
}

function route() {
  if (unauthorized) return;
  const next = parseRoute(location.hash);
  const { page, params } = next;
  const main = document.getElementById("main");
  if (shouldFocusMain(currentRoute, next)) {
    cancelFocus();
    cancelFocus = () => {};
    main.focus({ preventScroll: true });
  } else if (main.contains(document.activeElement) && document.activeElement !== main) {
    cancelFocus();
    cancelFocus = preserveFocus(main);
  }
  // A second render can arrive before an async control has returned; keep its pending restoration.
  currentRoute = next;
  currentPage?.destroy();
  currentPage = pages[page] || placeholder;
  currentPage.render(main, { ...params, page });
  document.title = t("shell.documentTitle", { page: t(`page.${page}.title`) });
  document.querySelectorAll(".nav-link").forEach(link => {
    if (link.dataset.page === page || (page === "record" && link.dataset.page === "knowledge")) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
}

function showLogin() {
  unauthorized = true;
  stopPulse();
  if (!translationsReady) { location.replace("/"); return; }
  currentPage?.destroy();
  cancelFocus();
  drawer?.close();
  document.getElementById("shell").hidden = true;
  document.getElementById("startup").replaceChildren(el("section", { class: "login-screen card", id: "login-screen" },
    el("h1", {}, t("login.title")), el("p", {}, t("login.message"))));
}

function updatePulse(data) {
  vaultObsidianUri = data.obsidian_uri;
  updateObsidianLink();
  const indicator = document.querySelector(".local-status");
  const status = indicatorState(data);
  indicator.setAttribute("aria-label", t(status.key));
  indicator.replaceChildren(statusDot(status.tone, t(status.key)), t("shell.local"));
  document.getElementById("brand-version").textContent = data.beyin.version ? t("shell.version", { version: data.beyin.version }) : t("shell.plainMode");
  document.getElementById("vault-status").replaceChildren(
    el("p", { class: "vault-name" }, statusDot("active", t("shell.local")), el("strong", {}, data.vault_name)),
    el("p", { id: "vault-records", "data-count": data.records }, t("shell.recordCount", { count: data.records })),
    el("p", { class: "muted" }, t("shell.lastScan", { time: formatTime(data.scanned_at) })),
    el("small", {}, formatDate(data.scanned_at)));
}

function buildShell(pulse) {
  const skip = document.getElementById("skip-content");
  skip.textContent = t("shell.skipContent");
  skip.addEventListener("click", event => {
    event.preventDefault();
    document.getElementById("main").focus();
  });
  document.querySelector(".sidebar").setAttribute("aria-label", t("shell.sidebar"));
  document.getElementById("topbar").setAttribute("aria-label", t("shell.topbar"));
  document.getElementById("main").setAttribute("aria-label", t("shell.main"));
  setDrawings(pulse.drawings);
  const sidebarArt = illustrationSlot("sidebar-tree");
  document.getElementById("sidebar-art").replaceChildren(...(sidebarArt ? [sidebarArt] : []));
  const brand = document.getElementById("brand");
  brand.replaceChildren(icon("brain"), el("span", {}, el("span", { class: "brand-name" }, t("shell.brand")),
    el("small", { id: "brand-version", class: "brand-version" }, t("state.loading"))));
  const nav = document.getElementById("navigation");
  nav.setAttribute("aria-label", t("shell.navigation"));
  nav.replaceChildren(...navigation.map(([page, href, name]) => el("a", { class: "nav-link", href, "data-page": page }, icon(name), t(`page.${page}.title`))));
  nav.addEventListener("keydown", event => {
    const links = [...nav.querySelectorAll("a")];
    const current = links.indexOf(document.activeElement);
    const index = navigationIndex(event.key, current, links.length);
    if (current < 0 || index < 0) return;
    event.preventDefault();
    links[index].focus();
  });
  const search = el("input", { id: "global-search", type: "search", autocomplete: "off", placeholder: t("shell.searchPlaceholder"), "aria-label": t("shell.searchLabel") });
  search.addEventListener("keydown", event => {
    if (event.key === "Enter") { event.preventDefault(); location.hash = `/arama?q=${encodeURIComponent(search.value)}`; }
  });
  drawer = healthDrawer();
  document.body.append(drawer.root);
  document.getElementById("topbar").replaceChildren(
    el("label", { class: "global-search" }, icon("search"), search, el("kbd", {}, t("shell.searchShortcut"))),
    el("div", { class: "topbar-actions" }, el("button", { type: "button", class: "local-status", "aria-haspopup": "dialog", onclick: drawer.open },
      statusDot("active", t("shell.local")), t("shell.local")),
    el("button", { type: "button", class: "icon-button", disabled: true, "aria-label": t("shell.settings"), title: t("shell.settingsSoon") }, icon("settings"))));
  document.getElementById("vault-status").replaceChildren(skeleton(2));
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") { drawer.close(); return; }
    const target = event.target;
    const typing = target instanceof Element && (target.closest("input, textarea, select") || target.isContentEditable);
    if ((event.ctrlKey && event.key.toLowerCase() === "k") || (event.key === "/" && !typing && !event.ctrlKey && !event.altKey && !event.metaKey)) {
      if (drawer.root.open || unauthorized) return;
      event.preventDefault();
      search.focus();
    }
  });
  document.addEventListener("beyin:health", drawer.open);
  document.addEventListener("beyin:record", event => {
    recordObsidianUri = event.detail?.obsidianUri ?? null;
    updateObsidianLink();
  });
  // A page that refreshes itself exports handlesChanges; the others are simply rendered again.
  document.addEventListener("beyin:changed", () => { if (!currentPage?.handlesChanges) route(); });
  window.addEventListener("hashchange", route);
  document.getElementById("startup").replaceChildren();
  document.getElementById("shell").hidden = false;
  updatePulse(pulse);
  route();
  stopPulse = startPulse({ onPulse: updatePulse, onError: error => {
    if (error.code !== "unauthorized") document.getElementById("vault-status").replaceChildren(errorState(t("shell.pulseError")));
  } });
}

document.addEventListener("beyin:unauthorized", showLogin);
try {
  setMessages(await get("/static/i18n/tr.json"));
  translationsReady = true;
  await prepareIcons();
  const pulse = await get("/api/v1/pulse");
  if (!unauthorized) buildShell(pulse);
} catch (error) {
  if (!unauthorized) {
    const startup = document.getElementById("startup");
    const message = el("p", { class: "login-screen", role: "alert" }, error.message);
    startup.replaceChildren(message);
  }
}
