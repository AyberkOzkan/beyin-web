import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { greetingKey, firstSentence, dailyQuote, weeklyBars, changeKey } from "../../beyin_web/static/js/pages/home-model.js";
import { setMessages, t } from "../../beyin_web/static/js/i18n.js";

const messages = JSON.parse(readFileSync(new URL("../../beyin_web/static/i18n/tr.json", import.meta.url), "utf8"));
setMessages(messages);

test("greeting selects translated periods and optional names", () => {
  for (const period of ["morning", "day", "evening"]) {
    assert.equal(greetingKey(period), `home.greeting.${period}`);
    assert.equal(greetingKey(period, "  "), `home.greeting.${period}`);
    assert.equal(greetingKey(period, "Deniz"), `home.greeting.${period}Named`);
    assert.ok(Object.hasOwn(messages, greetingKey(period)));
  }
  assert.equal(greetingKey("unknown"), "home.greeting.day");
  assert.equal(t(greetingKey("morning", "Deniz"), { name: "Deniz" }), "Günaydın, Deniz.");
});

test("first sentence preserves punctuation and handles absent actions", () => {
  for (const [input, expected] of [[null, ""], ["", ""], ["   ", ""],
    ["İlk adımı yap. Sonra devam et.", "İlk adımı yap."],
    ["Bitti mi? Sonraki adım.", "Bitti mi?"], ["Dur! Bekle.", "Dur!"],
    ["İlk satır\nİkinci satır", "İlk satır"], ["  Tek cümle  ", "Tek cümle"],
    ["3.11 sürümünü dene. Devam et.", "3.11 sürümünü dene."], ["“Bitti.” Devam et.", "“Bitti.”"],
    ["`develop`'tan **dal** aç. Sonra PR.", "develop'tan dal aç."]]) {
    assert.equal(firstSentence(input), expected);
  }
});

test("daily quote cycles by calendar day including leap years", () => {
  const quotes = ["one", "two", "three", "four", "five"];
  assert.equal(dailyQuote(quotes, new Date(2026, 0, 1)), "one");
  assert.equal(dailyQuote(quotes, new Date(2026, 0, 2)), "two");
  assert.equal(dailyQuote(quotes, new Date(2026, 0, 6)), "one");
  assert.equal(dailyQuote(quotes, new Date(2024, 2, 1)), "one");
  assert.equal(dailyQuote(quotes, new Date(2025, 2, 1)), "five");
  assert.equal(dailyQuote(quotes, new Date(2026, 0, 12, 0)), dailyQuote(quotes, new Date(2026, 0, 12, 23)));
  assert.equal(dailyQuote([], new Date()), "");
});

test("weekly bars sort days and scale finite nonnegative counts", () => {
  assert.deepEqual(weeklyBars({ "2026-01-14": 4, "2026-01-12": 2, "2026-01-13": 0 }), [
    { date: "2026-01-12", count: 2, height: 50 }, { date: "2026-01-13", count: 0, height: 0 },
    { date: "2026-01-14", count: 4, height: 100 },
  ]);
  assert.deepEqual(weeklyBars({ day: 0 }, 80), [{ date: "day", count: 0, height: 0 }]);
  assert.deepEqual(weeklyBars({ day: 4 }, 80), [{ date: "day", count: 4, height: 80 }]);
  for (const value of [-2, NaN, Infinity]) assert.equal(weeklyBars({ day: value })[0].height, 0);
  assert.deepEqual(weeklyBars({}), []);
  const golden = JSON.parse(readFileSync(new URL("../fixtures/golden/home.json", import.meta.url), "utf8"));
  assert.equal(weeklyBars(golden.week.days).length, 7);
});

test("counter change selects plus text or no-change text", () => {
  assert.equal(t(changeKey(3), { count: 3 }), "+3 son 7 günde");
  assert.equal(t(changeKey(0), { count: 0 }), "son 7 günde değişiklik yok");
});
