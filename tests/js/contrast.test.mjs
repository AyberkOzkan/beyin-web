import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";

const cssRoot = new URL("../../beyin_web/static/css/", import.meta.url);
const read = name => readFileSync(new URL(name, cssRoot), "utf8");
const lightTokens = read("tokens.css").split(":root[data-theme")[0];

function token(name) {
  const match = lightTokens.match(new RegExp(`--${name}:\\s*(#[0-9A-Fa-f]{6})\\s*;`));
  assert.ok(match, `--${name} is a six digit hex colour`);
  return match[1];
}

function luminance(hex) {
  const [r, g, b] = [1, 3, 5].map(index => parseInt(hex.slice(index, index + 2), 16) / 255)
    .map(value => (value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(first, second) {
  const [light, dark] = [luminance(first), luminance(second)].sort((a, b) => b - a);
  return (light + 0.05) / (dark + 0.05);
}

const grounds = ["paper", "card", "paper-side"];

test("the contrast formula matches the WCAG reference values", () => {
  assert.equal(contrast("#000000", "#FFFFFF"), 21);
  assert.equal(contrast("#777777", "#FFFFFF").toFixed(2), "4.48");
});

test("text colours reach 4.5:1 on every ground", () => {
  for (const name of ["ink", "ink-soft", "sage-deep"]) {
    for (const ground of grounds) {
      const ratio = contrast(token(name), token(ground));
      assert.ok(ratio >= 4.5, `--${name} on --${ground}: ${ratio.toFixed(2)}`);
    }
  }
});

test("amber, red and blue stay below 4.5:1 and are never a text colour", () => {
  for (const name of ["amber", "red", "blue"]) {
    assert.ok(grounds.some(ground => contrast(token(name), token(ground)) < 4.5), `--${name} became safe as text; this guard can go`);
  }
  const sheets = ["base.css", "layout.css", "components.css", ...readdirSync(new URL("pages/", cssRoot)).map(name => `pages/${name}`)];
  for (const sheet of sheets) {
    for (const rule of read(sheet).match(/[^{}]+\{[^{}]*\}/g) ?? []) {
      // An icon is a graphic, not text; the tone classes carry the colour to dots and icons through --tone.
      if (/\.icon\b|\.status-dot\b/.test(rule.split("{")[0])) continue;
      assert.doesNotMatch(rule, /(^|[;{\s])color:\s*var\(--(amber|red|blue)\)/, `${sheet}: ${rule.trim()}`);
    }
  }
  const components = read("components.css");
  assert.match(components, /\.badge:is\(\.tone-waiting, \.tone-blocked, \.tone-error, \.tone-knowledge\) \{ color: var\(--ink\); \}/);
  assert.match(components, /\.badge:is\(\.tone-waiting, \.tone-blocked, \.tone-error, \.tone-knowledge\)::before \{[^}]*background: var\(--tone\)/);
});

test("rows are not faded with opacity", () => {
  const pages = readdirSync(new URL("pages/", cssRoot)).map(name => `pages/${name}`);
  for (const sheet of ["layout.css", "components.css", ...pages]) {
    assert.doesNotMatch(read(sheet), /opacity\s*:/, sheet);
  }
});
