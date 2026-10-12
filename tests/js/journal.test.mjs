import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  adjacentReceiptDays, calendarGrid, clockText, dayLabel, daySummary, heatmapWeeks, isDate,
  latestReceiptDay, monthLabel, receiptDays, shiftMonth, toneBucket, upcomingGroups,
} from "../../beyin_web/static/js/pages/journal-model.js";

const golden = JSON.parse(readFileSync(new URL("../fixtures/golden/journal_heatmap.json", import.meta.url), "utf8"));
const goldenDay = JSON.parse(readFileSync(new URL("../fixtures/golden/journal_day.json", import.meta.url), "utf8"));
const goldenHome = JSON.parse(readFileSync(new URL("../fixtures/golden/home.json", import.meta.url), "utf8"));

test("day summary counts receipts, distinct sources, learned lines and session cards", () => {
  assert.deepEqual(daySummary(goldenDay), { receipts: 1, workedNotes: 1, learned: 0, sessions: 1 });
  const data = {
    receipts: [
      { refs: [{ rid: "shared" }, { rid: "second" }], learned: "A lesson." },
      { refs: [{ rid: "shared" }, { rid: "shared" }], learned: null },
      { learned: "" }, { refs: [], learned: "  " },
    ], cards: [{}, {}],
  };
  assert.deepEqual(daySummary(data), { receipts: 4, workedNotes: 2, learned: 1, sessions: 2 });
  assert.deepEqual(daySummary({}), { receipts: 0, workedNotes: 0, learned: 0, sessions: 0 });
});

test("upcoming groups keep the golden server order and drop tasks without actions", () => {
  assert.deepEqual(upcomingGroups(goldenHome), {
    dated: goldenHome.upcoming, steps: [goldenHome.tasks[0]], moreDated: 0, moreSteps: 0,
  });
  const tasks = [{ rid: "missing" }, { next_action: null }, { next_action: "" }, { next_action: " \n " },
    { rid: "action", next_action: "Continue." }];
  assert.deepEqual(upcomingGroups({ tasks }).steps, [tasks[4]]);
});

test("upcoming groups apply each limit independently and count the remainder", () => {
  const home = {
    upcoming: Array.from({ length: 8 }, (_, index) => ({ rid: `date-${8 - index}` })),
    tasks: Array.from({ length: 6 }, (_, index) => ({ rid: `task-${6 - index}`, next_action: "Continue." })),
  };
  const before = structuredClone(home);
  for (const limit of [0, 2, 5, 10]) {
    assert.deepEqual(upcomingGroups(home, limit), {
      dated: home.upcoming.slice(0, limit), steps: home.tasks.slice(0, limit),
      moreDated: Math.max(0, 8 - limit), moreSteps: Math.max(0, 6 - limit),
    });
  }
  assert.deepEqual(upcomingGroups(home), upcomingGroups(home, 5));
  assert.deepEqual(home, before);
});

test("empty home has two empty upcoming groups", () => {
  const empty = { dated: [], steps: [], moreDated: 0, moreSteps: 0 };
  assert.deepEqual(upcomingGroups({}), empty);
  assert.deepEqual(upcomingGroups({ upcoming: [], tasks: [] }), empty);
});

test("calendar begins on Monday and pads both ends to complete weeks", () => {
  for (const [month, offset, length] of [
    ["2026-01", 3, 31], ["2026-02", 6, 28], ["2026-04", 2, 30],
    ["2026-06", 0, 30], ["2026-08", 5, 31], ["2024-02", 3, 29],
  ]) {
    const cells = calendarGrid(month);
    const dates = cells.filter(Boolean);
    assert.equal(cells.indexOf(`${month}-01`), offset);
    assert.equal(cells.length % 7, 0);
    assert.equal(dates.length, length);
    assert.equal(dates.at(-1), `${month}-${length}`);
    assert.equal(cells.slice(0, offset).every(value => value === null), true);
    assert.equal(cells.slice(offset + length).every(value => value === null), true);
    assert.equal(new Set(dates).size, length);
  }
});

test("all month lengths and century leap-year rules are preserved", () => {
  const lengths = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  for (let month = 1; month <= 12; month++) {
    assert.equal(calendarGrid(`2026-${String(month).padStart(2, "0")}`).filter(Boolean).length, lengths[month - 1]);
  }
  assert.equal(calendarGrid("2000-02").filter(Boolean).length, 29);
  assert.equal(calendarGrid("1900-02").filter(Boolean).length, 28);
  assert.equal(calendarGrid("2100-02").filter(Boolean).length, 28);
  assert.equal(isDate("2026-02-29"), false);
  assert.equal(isDate("2024-02-29"), true);
  assert.throws(() => calendarGrid("2026-13"), RangeError);
});

test("month navigation crosses year boundaries without altering selected days", () => {
  assert.equal(shiftMonth("2026-01", -1), "2025-12");
  assert.equal(shiftMonth("2026-12", 1), "2027-01");
  assert.equal(shiftMonth("2024-03", -1), "2024-02");
  assert.equal(shiftMonth("0001-01", -1), null);
  assert.equal(shiftMonth("9999-12", 1), null);
});

test("heatmap buckets represent zero, 1–2, 3–5 and 6+ receipts", () => {
  for (const [count, tone] of [[0, 0], [1, 1], [2, 1], [3, 2], [5, 2], [6, 3], [50, 3]]) {
    assert.equal(toneBucket(count), tone);
  }
  const weeks = heatmapWeeks(golden.days);
  assert.equal(weeks.length, 20);
  assert.equal(weeks.flat().length, 140);
  for (const week of weeks) {
    assert.equal(week.length, 7);
    assert.equal(new Date(`${week[0].date}T00:00:00Z`).getUTCDay(), 1);
    assert.equal(new Date(`${week[6].date}T00:00:00Z`).getUTCDay(), 0);
    for (const cell of week) assert.equal(cell.tone, toneBucket(golden.days[cell.date]));
  }
  assert.equal(weeks.at(-1).at(-1).date, "2026-01-18");
  assert.ok(weeks.flat().filter(cell => cell.date > golden.today).every(cell => cell.count === 0));
  assert.deepEqual(heatmapWeeks({}), []);
});

test("receipt navigation skips empty days and disables absent neighbors", () => {
  assert.deepEqual(receiptDays(golden.days), ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-12"]);
  for (const [date, previous, next] of [
    ["2026-01-04", null, "2026-01-05"], ["2026-01-05", null, "2026-01-06"],
    ["2026-01-06", "2026-01-05", "2026-01-07"], ["2026-01-08", "2026-01-07", "2026-01-12"],
    ["2026-01-12", "2026-01-07", null], ["2026-02-01", "2026-01-12", null],
  ]) assert.deepEqual(adjacentReceiptDays(golden.days, date), { previous, next });
  assert.deepEqual(adjacentReceiptDays({}, golden.today), { previous: null, next: null });
});

test("default date is the latest receipt day, falling back to the server's today", () => {
  assert.equal(latestReceiptDay(golden.days, "2026-01-15"), "2026-01-12");
  assert.equal(latestReceiptDay({ "2026-01-02": 2, "2026-01-01": 1 }, golden.today), "2026-01-02");
  assert.equal(latestReceiptDay({}, golden.today), golden.today);
  assert.equal(latestReceiptDay({ "2026-01-18": 0 }, golden.today), golden.today);
});

test("clock text keeps the timestamp's own offset and supports fractional seconds", () => {
  for (const [time, expected] of [
    ["2026-01-06T01:30:00+03:00", "01:30"], ["2026-01-05T22:30:00-08:00", "22:30"],
    ["2026-01-12T15:00:00.250000+03:00", "15:00"], ["2026-01-12T00:10:00Z", "00:10"],
    [null, ""], ["2026-01-12", ""],
  ]) assert.equal(clockText(time), expected);
});

test("calendar dates and receipt clocks ignore the browser's timezone", () => {
  const moduleUrl = new URL("../../beyin_web/static/js/pages/journal-model.js", import.meta.url).href;
  const source = `import { clockText, dayLabel, monthLabel, calendarGrid } from ${JSON.stringify(moduleUrl)};
    process.stdout.write(JSON.stringify([clockText('2026-01-06T01:30:00+03:00'),
      dayLabel('2026-10-03'), monthLabel('2026-01'), calendarGrid('2026-01').indexOf('2026-01-01')]));`;
  for (const timezone of ["UTC", "America/Los_Angeles", "Pacific/Kiritimati"]) {
    const result = execFileSync(process.execPath, ["--input-type=module", "--eval", source], {
      encoding: "utf8", env: { ...process.env, TZ: timezone },
    });
    assert.deepEqual(JSON.parse(result), ["01:30", "3 Ekim 2026 Cumartesi", "Ocak 2026", 3]);
  }
  assert.equal(dayLabel("2026-10-03"), "3 Ekim 2026 Cumartesi");
  assert.equal(monthLabel("2026-01"), "Ocak 2026");
});
