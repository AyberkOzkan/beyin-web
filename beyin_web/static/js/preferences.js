const CURSOR_KEY = "beyin-web.cursor";
export const CURSORS = ["ink", "system"];

// Kept in this browser only; a private window simply starts from the default again.
export function storedCursor() {
  try {
    const value = localStorage.getItem(CURSOR_KEY);
    return CURSORS.includes(value) ? value : CURSORS[0];
  } catch { return CURSORS[0]; }
}

export function applyCursor(value) {
  const cursor = CURSORS.includes(value) ? value : CURSORS[0];
  document.documentElement.dataset.cursor = cursor;
  try { localStorage.setItem(CURSOR_KEY, cursor); } catch { /* the choice lasts until the page is closed */ }
  return cursor;
}
