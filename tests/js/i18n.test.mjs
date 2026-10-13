import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  LANGUAGES, chooseLanguage, currentLocale, setMessages, t, messageList, formatDate, formatTime, relativeTime,
} from "../../beyin_web/static/js/i18n.js";
import { monthLabel as goalsMonth } from "../../beyin_web/static/js/pages/goals-model.js";
import { dayLabel, monthLabel as journalMonth } from "../../beyin_web/static/js/pages/journal-model.js";
import { rangeLabel } from "../../beyin_web/static/js/pages/reports-model.js";

const load = language => JSON.parse(readFileSync(new URL(`../../beyin_web/static/i18n/${language}.json`, import.meta.url), "utf8"));
const files = Object.fromEntries(LANGUAGES.map(language => [language, load(language)]));
const placeholders = text => [...text.matchAll(/\{(\w+)\}/g)].map(match => match[1]).sort();
const forms = value => (typeof value === "string" ? [value] : Array.isArray(value) ? value : Object.values(value));
const CATEGORIES = ["zero", "one", "two", "few", "many", "other"];

test("every language has the same keys in the same order, with the same placeholders", () => {
  const [first, ...others] = LANGUAGES;
  for (const language of others) {
    assert.deepEqual(Object.keys(files[language]), Object.keys(files[first]), language);
    for (const [key, value] of Object.entries(files[first])) {
      const other = files[language][key];
      assert.equal(Array.isArray(other), Array.isArray(value), key);
      if (Array.isArray(value)) assert.equal(other.length, value.length, key);
      else for (const form of forms(other)) assert.deepEqual(placeholders(form), placeholders(forms(value)[0]), key);
    }
  }
});

test("every message is a non-empty string, a list of strings or a set of plural forms", () => {
  for (const [language, messages] of Object.entries(files)) {
    assert.doesNotThrow(() => new Intl.DateTimeFormat(messages["meta.locale"]), language);
    assert.equal(messages["meta.locale"].split("-")[0], language);
    for (const [key, value] of Object.entries(messages)) {
      const where = `${language}: ${key}`;
      if (value && typeof value === "object" && !Array.isArray(value)) {
        assert.ok(Object.hasOwn(value, "other"), where);
        assert.ok(Object.keys(value).every(category => CATEGORIES.includes(category)), where);
        assert.ok(placeholders(value.other).includes("count"), where);
      }
      for (const form of forms(value)) assert.ok(typeof form === "string" && form.trim(), where);
    }
  }
});

test("the English file carries no untranslated Turkish text", () => {
  // The font sample shows Turkish letters on purpose, and the language setting names Turkish in Turkish.
  const turkishLetters = new Set(["showcase.fontSample", "settings.language.tr"]);
  // Names, symbols and patterns that read the same in both languages.
  const same = new Set(["shell.brand", "shell.documentTitle", "shell.version", "shell.searchShortcut", "projects.taskLabel",
    "knowledge.dateTime", "home.dateTime", "reports.learnedTime", "reports.rangeSameMonth", "reports.rangeFull",
    "reports.activeDaysValue", "memory.tabCount", "component.progressValue", "goals.field.period.long", "goals.habits.day",
    "health.beyin", "showcase.codeSample", "showcase.filterValue", "graph.kind.receipt", "settings.language.tr",
    "settings.language.en", "settings.beyin.title"]);
  for (const [key, value] of Object.entries(files.en)) {
    if (key === "meta.locale") continue;
    if (!turkishLetters.has(key)) {
      for (const form of forms(value)) assert.doesNotMatch(form.replaceAll("Beyin", ""), /[çğıöşüÇĞİÖŞÜ]/, key);
    }
    if (same.has(key)) assert.deepEqual(value, files.tr[key], key);
    else assert.notDeepEqual(value, files.tr[key], key);
  }
});

test("the viewer's choice wins over the server's default, and unknown codes fall back", () => {
  assert.deepEqual(LANGUAGES, ["tr", "en"]);
  assert.equal(chooseLanguage("en", "tr"), "en");
  assert.equal(chooseLanguage(null, "en"), "en");
  assert.equal(chooseLanguage("tr", "en"), "tr");
  for (const stored of [null, undefined, "", "de", "../en", "EN", "constructor", 3]) {
    assert.equal(chooseLanguage(stored, "en"), "en");
    assert.equal(chooseLanguage(stored, undefined), "tr");
    assert.equal(chooseLanguage(stored, "xx"), "tr");
  }
});

test("dates, times, counts and plurals follow the language of the messages", () => {
  const now = Date.parse("2026-01-12T12:00:00Z");
  try {
    setMessages(files.en);
    assert.equal(currentLocale(), "en-GB");
    assert.equal(t("shell.recordCount", { count: 1 }), "1 record");
    assert.equal(t("shell.recordCount", { count: 30 }), "30 records");
    assert.equal(t("shell.recordCount", { count: 0 }), "0 records");
    assert.equal(t("shell.recordCount"), "{count} records");
    assert.equal(t("search.summary", { count: 1, seconds: "0.02" }), "1 result found (0.02 seconds)");
    assert.deepEqual(messageList("journal.weekdays"), ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]);
    assert.equal(relativeTime(now - 7200000, now), "2 hours ago");
    assert.equal(relativeTime(now + 120000, now), "in 2 minutes");
    assert.equal(relativeTime(now - 86400000, now), "1 day ago");
    assert.match(formatDate(now), /12 January 2026/);
    assert.match(formatTime(now), /^\d{2}:\d{2}$/);
    assert.equal(goalsMonth("2026-01"), "January 2026");
    assert.equal(journalMonth("2026-01"), "January 2026");
    assert.match(dayLabel("2026-01-12"), /^Monday,? 12 January 2026$/);
    assert.equal(rangeLabel("2026-01-05", "2026-01-11"), "5–11 January 2026");
    assert.equal(rangeLabel("2026-01-26", "2026-02-01"), "26 January 2026 – 1 February 2026");
    setMessages(files.tr);
    assert.equal(currentLocale(), "tr-TR");
    assert.equal(t("shell.recordCount", { count: 1 }), "1 kayıt");
    assert.equal(goalsMonth("2026-01"), "Ocak 2026");
    assert.equal(dayLabel("2026-01-12"), "12 Ocak 2026 Pazartesi");
    assert.equal(rangeLabel("2026-01-05", "2026-01-11"), "5–11 Ocak 2026");
    setMessages({});
    assert.equal(currentLocale(), "tr-TR");
  } finally { setMessages(files.tr); }
});
