import { get } from "../api.js";
import { el, icon } from "../dom.js";
import { t, formatDate, formatTime } from "../i18n.js";
import { card, progressBar, emptyState, errorState, skeleton } from "./index.js";
import { memorySize, warningsPreview, warningCodes } from "../pages/memory-model.js";

function entry(label, value) {
  return el("div", { class: "health-entry" }, el("dt", {}, t(label)), el("dd", {}, value));
}

function summary(data) {
  if (!data.beyin_available) return el("p", { class: "health-plain" }, t("health.plain"));
  const health = data.health_summary;
  if (!health || !Object.values(health).some(value => value !== null)) {
    return el("p", { class: "health-unavailable" }, t("health.unavailable"));
  }
  const sync = health.last_sync_status;
  return el("dl", { class: "health-summary" },
    entry("health.version", health.installed_version || t("health.unknown")),
    entry("health.upToDate", health.up_to_date === true ? t("health.current") :
      health.up_to_date === false ? t("health.outdated") : t("health.unknown")),
    entry("health.lastSync", health.last_sync_at ? `${formatDate(health.last_sync_at)} · ${formatTime(health.last_sync_at)}` : t("health.unknown")),
    entry("health.syncStatus", ["succeeded", "failed", "skipped", "pending", "running"].includes(sync) ? t(`health.sync.${sync}`) : sync || t("health.unknown")),
    entry("health.missingReceipts", health.potential_missing_receipts ?? t("health.unknown")));
}

function files(data) {
  const items = Object.entries(data.health_summary?.memory_files || {});
  if (!items.length) return emptyState(t("health.files"), t("health.filesEmpty"));
  return el("div", { class: "stack health-files" }, items.map(([name, file]) => {
    const size = memorySize(file);
    return el("div", { class: `health-file${size.overLimit ? " health-over-limit" : ""}` },
      el("strong", {}, name),
      el("p", {}, t(size.limit === null ? "health.size" : "health.sizeLimit", { chars: size.chars, limit: size.limit })),
      size.limit !== null && progressBar(Math.round(size.ratio * 100), 100, t("health.fileProgress", { name })),
      size.overLimit && el("strong", { class: "tone-error" }, t("health.overLimit")));
  }));
}

function interfaceHealth(data) {
  const warnings = warningsPreview(data.warnings);
  return el("div", { class: "health-interface" },
    el("p", {}, t("health.records", { count: data.records })),
    el("p", { class: "health-hidden" }, t("health.hidden", { count: data.hidden_private })),
    el("h3", {}, t("health.warnings")),
    warnings.visible.length ? el("ul", { class: "health-warnings" }, warnings.visible.map(warning =>
      el("li", {}, el("span", {}, warningCodes.has(warning.code) ? t(`health.warning.${warning.code}`) : warning.code),
        warning.path && el("code", {}, warning.path)))) : el("p", { class: "muted" }, t("health.noWarnings")),
    warnings.remaining > 0 && el("p", {}, t("health.moreWarnings", { count: warnings.remaining })));
}

export function healthDrawer() {
  const body = el("div", { class: "stack health-body", "aria-live": "polite" });
  let opener;
  let request = 0;
  const dialog = el("dialog", { class: "health-drawer", "aria-labelledby": "health-title" },
    el("div", { class: "drawer-heading" }, el("h2", { id: "health-title" }, t("health.title")),
      el("button", { class: "icon-button", type: "button", "aria-label": t("action.close"), onclick: close }, icon("x"))), body);

  function close() {
    request++;
    if (dialog.open) dialog.close();
  }

  async function load() {
    const current = ++request;
    body.setAttribute("aria-busy", "true");
    body.replaceChildren(skeleton(5));
    try {
      const data = await get("/api/v1/health");
      if (current !== request || !dialog.open) return;
      body.replaceChildren(card(t("health.beyin"), [summary(data)]),
        card(t("health.files"), [files(data)]), card(t("health.interface"), [interfaceHealth(data)]));
    } catch (error) {
      if (current !== request || !dialog.open || error.code === "unauthorized") return;
      body.replaceChildren(errorState(t("health.error"), () => void load()));
    } finally {
      if (current === request && dialog.open) body.setAttribute("aria-busy", "false");
    }
  }

  dialog.addEventListener("cancel", event => { event.preventDefault(); close(); });
  dialog.addEventListener("close", () => {
    if (!dialog.open) { request++; opener?.focus(); }
  });
  dialog.addEventListener("click", event => {
    if (event.target !== dialog) return;
    const bounds = dialog.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) close();
  });
  return { root: dialog, open: () => {
    if (dialog.open) return;
    opener = document.activeElement;
    dialog.showModal();
    void load();
  }, close };
}
