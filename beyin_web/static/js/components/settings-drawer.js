import { post } from "../api.js";
import { el, icon } from "../dom.js";
import { t, LANGUAGES, storeLanguage } from "../i18n.js";
import { CURSORS, storedCursor, applyCursor } from "../preferences.js";

// Beyin's own switches (capture, checks, context) are changed in Beyin; the page only points to their guides.
const BEYIN_DOCS = "https://github.com/avenoxai/avenoxbeyin/blob/main/docs/v3/";
const GUIDES = [["capture", "YAKALA.md"], ["preferences", "PREFERENCES.md"], ["update", "UPDATE.md"]];

function section(name, ...children) {
  return el("section", { class: "settings-section", "aria-labelledby": `settings-${name}` },
    el("h3", { id: `settings-${name}` }, t(`settings.${name}.title`)), children);
}

export function settingsDrawer({ language, onStopped }) {
  let opener;
  const stop = el("div", { class: "settings-stop" });
  const dialog = el("dialog", { class: "health-drawer settings-drawer", "aria-labelledby": "settings-title" },
    el("div", { class: "drawer-heading" }, el("h2", { id: "settings-title" }, t("shell.settings")),
      el("button", { class: "icon-button", type: "button", "aria-label": t("action.close"), onclick: close }, icon("x"))),
    section("language", el("div", { class: "row", role: "group", "aria-labelledby": "settings-language" },
      LANGUAGES.map(code => el("button", {
        type: "button", class: "button settings-language", lang: code, "data-language": code,
        "aria-pressed": String(code === language),
        onclick: () => { if (code !== language && storeLanguage(code)) location.reload(); },
      }, t(`settings.language.${code}`))))),
    section("cursor", el("p", { class: "muted" }, t("settings.cursor.note")),
      el("div", { class: "row", role: "group", "aria-labelledby": "settings-cursor" },
        CURSORS.map(name => el("button", {
          type: "button", class: "button settings-cursor", "data-cursor": name, "aria-pressed": String(name === storedCursor()),
          onclick: event => {
            const now = applyCursor(name);
            event.currentTarget.parentElement.querySelectorAll(".settings-cursor").forEach(button =>
              button.setAttribute("aria-pressed", String(button.dataset.cursor === now)));
          },
        }, t(`settings.cursor.${name}`))))),
    section("beyin", el("p", { class: "muted" }, t("settings.beyin.note")),
      el("ul", { class: "settings-guides" }, GUIDES.map(([name, file]) => el("li", {},
        el("a", { href: BEYIN_DOCS + file, target: "_blank", rel: "noopener noreferrer" },
          t(`settings.beyin.${name}`), icon("external-link")))))),
    section("stop", el("p", { class: "muted" }, t("settings.stop.note")), stop));

  function drawStop(confirming = false, failed = false) {
    stop.replaceChildren(...(confirming ? [el("div", { class: "settings-confirm", role: "group" },
      el("p", {}, t("settings.stop.confirm")),
      el("div", { class: "row" },
        el("button", { type: "button", class: "button settings-danger", onclick: () => void run() }, t("settings.stop.yes")),
        el("button", { type: "button", class: "button", onclick: () => drawStop() }, t("settings.stop.cancel"))))] :
      [el("button", { type: "button", class: "button settings-stop-button", onclick: () => drawStop(true) },
        icon("circle-x"), t("settings.stop.button")),
      failed && el("p", { class: "settings-error", role: "alert" }, t("settings.stop.error"))].filter(Boolean)));
  }

  async function run() {
    try {
      await post("/api/v1/shutdown");
    } catch (error) {
      if (error.code !== "unauthorized") drawStop(false, true);
      return;
    }
    close();
    onStopped();
  }

  function close() {
    if (dialog.open) dialog.close();
  }

  dialog.addEventListener("close", () => { drawStop(); opener?.focus(); });
  dialog.addEventListener("click", event => {
    if (event.target !== dialog) return;
    const bounds = dialog.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) close();
  });
  drawStop();
  return { root: dialog, open: () => {
    if (dialog.open) return;
    opener = document.activeElement;
    dialog.showModal();
  }, close };
}
