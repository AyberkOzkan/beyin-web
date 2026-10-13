// Where the margin doodles go. Pure: zones in, places out, so the rule can be tested without a page.

export function seeded(text) {
  let state = 2166136261;
  for (const char of String(text)) state = Math.imul(state ^ char.codePointAt(0), 16777619);
  return () => {
    state = (state + 0x6D2B79F5) | 0;
    let value = Math.imul(state ^ (state >>> 15), state | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

// A zone is a stretch of the page that nothing else uses. Small ones are left empty, large ones get a few
// doodles with room between them; the same seed always gives the same places, so nothing jumps on a redraw.
export function placeDoodles(zones, sources, seed) {
  const placed = [];
  let pool = [];
  for (const zone of zones) {
    if (!sources.length || zone.width < 150 || zone.height < 120) continue;
    const next = seeded(`${seed}:${zone.key}`);
    // A tall zone is taken in bands, a wide band in cells: one doodle at most in each, and not in every one.
    const bands = Math.max(1, Math.floor(zone.height / 300)), cells = Math.max(1, Math.min(4, Math.floor(zone.width / 340)));
    const high = zone.height / bands, wide = zone.width / cells;
    for (let band = 0; band < bands; band++) {
      for (let cell = 0; cell < cells; cell++) {
        const size = Math.round(Math.min(108, high - 28, wide - 56) * (0.72 + next() * 0.28));
        const skip = (band > 0 || cell > 0) && next() < 0.3;
        const x = zone.x + wide * cell + 24 + next() * Math.max(0, wide - size - 48);
        const y = zone.y + high * band + 12 + next() * Math.max(0, high - size - 24);
        const turn = Math.round((next() - 0.5) * 28);
        if (skip || size < 56) continue;
        if (!pool.length) pool = sources.map(source => [next(), source]).sort(([a], [b]) => a - b).map(([, source]) => source);
        placed.push({ source: pool.pop(), x: Math.round(x), y: Math.round(y), size, turn });
      }
    }
  }
  return placed;
}
