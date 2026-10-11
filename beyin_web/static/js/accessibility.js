export function navigationIndex(key, current, count) {
  if (!count) return -1;
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  if (key === "ArrowDown") return (current + 1 + count) % count;
  if (key === "ArrowUp") return (current - 1 + count) % count;
  return -1;
}

export function shouldFocusMain(previous, next) {
  return Boolean(previous && (previous.page !== next.page ||
    (next.page === "record" && previous.params.rid !== next.params.rid)));
}

export function reducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function scrollTo(node) {
  node?.scrollIntoView({ block: "start", behavior: reducedMotion() ? "instant" : "auto" });
}

export function preserveFocus(root) {
  const original = document.activeElement;
  if (!root.contains(original) || original === root) return () => {};
  const tag = original.tagName;
  const attributes = ["id", "data-tab", "data-date", "data-rid", "data-month-direction", "aria-label", "data-day"];
  const attribute = attributes.find(name => original.hasAttribute(name));
  const value = attribute && original.getAttribute(attribute);
  const href = original.getAttribute("href")?.split("?")[0];
  const text = original.textContent;
  const insideOpenDetails = original.closest("details")?.open;
  const selection = original.tagName === "INPUT" && ["search", "text"].includes(original.type) ?
    [original.selectionStart, original.selectionEnd] : null;
  let observer;
  function cancel() { observer?.disconnect(); document.removeEventListener("focusin", focusChanged); }
  function focusChanged(event) {
    if (event.target === root || event.target === document.body || event.target === document.documentElement) return;
    cancel();
  }
  function restore() {
    const target = [...root.querySelectorAll(tag)].find(node => attribute ? node.getAttribute(attribute) === value :
      href ? node.getAttribute("href")?.split("?")[0] === href : node.textContent === text);
    if (!target || target.disabled || target.closest("[hidden]")) return;
    if (insideOpenDetails) {
      for (let parent = target.closest("details"); parent; parent = parent.parentElement?.closest("details")) parent.open = true;
    }
    cancel();
    target.focus({ preventScroll: true });
    if (selection) target.setSelectionRange(...selection);
  }
  observer = new MutationObserver(restore);
  observer.observe(root, { childList: true, subtree: true });
  document.addEventListener("focusin", focusChanged);
  return cancel;
}
