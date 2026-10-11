import { el, icon } from "../dom.js";
import { t } from "../i18n.js";
import { loadD3 } from "../d3.js";
import { createSimulation, kindColor, projectColor, truncateTitle, screenToWorld, worldToScreen, findNode } from "./graph-core.js";
import { adjacency, focusDistances, searchMatches } from "../pages/graph-model.js";

export async function createGraphCanvas(data, { focus = "", onSelect = () => {}, onFocus = () => {} } = {}) {
  const d3 = await loadD3();
  const root = el("div", { class: "graph-stage" });
  const canvas = el("canvas", { class: "graph-canvas", role: "img", "aria-label": t("graph.canvas"),
    "data-nodes": data.nodes.length, "data-edges": data.edges.length, "data-running": "false", "data-draws": "0" });
  const list = el("ul", { class: "graph-node-list", "aria-label": t("graph.nodeList") });
  const controller = new AbortController();
  const listen = (target, name, callback, options = {}) => target.addEventListener(name, callback, { ...options, signal: controller.signal });
  const neighbors = adjacency(data.nodes, data.edges);
  const depths = focusDistances(focus, neighbors);
  const simulation = createSimulation(d3, data.nodes.map(node => ({ ...node, width: 148, height: 36 })), data.edges,
    { focus, distance: 190, charge: -650, collision: 82, center: true }).stop().alphaDecay(0.06);
  const nodes = simulation.nodes();
  const edges = simulation.force("link").links();
  const byId = new Map(nodes.map(node => [node.id, node]));
  const buttons = new Map();
  const state = { destroyed: false, running: false, draws: 0 };
  let frame = null, dirty = true, hovered = null, selected = focus, matches = new Set(), pointer = null;
  let width = 0, height = 0, ratio = 1, automaticFit = true, centered = null;
  let transform = { x: 0, y: 0, k: 1 };
  let colors = {}, font = "";

  function stop() {
    simulation.stop();
    if (frame !== null) cancelAnimationFrame(frame);
    frame = null;
    state.running = false;
    canvas.dataset.running = "false";
  }

  function fitTransform() {
    if (!nodes.length) return;
    const left = Math.min(...nodes.map(node => node.x - node.width / 2));
    const right = Math.max(...nodes.map(node => node.x + node.width / 2));
    const top = Math.min(...nodes.map(node => node.y - node.height / 2));
    const bottom = Math.max(...nodes.map(node => node.y + node.height / 2));
    const spanX = focus ? 2 * Math.max(Math.abs(left), Math.abs(right)) : right - left;
    const spanY = focus ? 2 * Math.max(Math.abs(top), Math.abs(bottom)) : bottom - top;
    const k = Math.max(0.08, Math.min(1.2, (width - 70) / Math.max(1, spanX), (height - 140) / Math.max(1, spanY)));
    transform = { k, x: width / 2 - (focus ? 0 : (left + right) / 2) * k,
      y: height / 2 - (focus ? 0 : (top + bottom) / 2) * k };
  }

  function draw() {
    if (state.destroyed || document.hidden || !width || !height) return;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    const highlighted = hovered ? new Set([hovered, ...(neighbors.get(hovered) || [])]) : null;
    for (const edge of edges) {
      const source = worldToScreen(edge.source, transform), target = worldToScreen(edge.target, transform);
      ctx.globalAlpha = highlighted && !(edge.source.id === hovered || edge.target.id === hovered) ? 0.15 :
        focus && (depths.get(edge.source.id) > 1 || depths.get(edge.target.id) > 1) ? 0.3 : 0.7;
      ctx.strokeStyle = colors["--ink-soft"];
      ctx.lineWidth = 1;
      ctx.setLineDash(edge.type === "ref" ? [5, 4] : []);
      ctx.beginPath(); ctx.moveTo(source.x, source.y); ctx.lineTo(target.x, target.y); ctx.stroke();
    }
    ctx.setLineDash([]);
    ctx.font = `14px ${font}`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (const node of nodes) {
      const point = worldToScreen(node, transform);
      const active = node.id === selected || matches.has(node.id) || node.id === focus;
      ctx.globalAlpha = highlighted && !highlighted.has(node.id) ? 0.16 : focus && depths.get(node.id) > 1 ? 0.3 : 1;
      ctx.fillStyle = colors[kindColor(node.kind)] || colors["--ink-soft"];
      const box = transform.k >= 0.55;
      const nodeWidth = node.width * transform.k, nodeHeight = node.height * transform.k;
      ctx.beginPath();
      if (box) ctx.roundRect(point.x - nodeWidth / 2, point.y - nodeHeight / 2, nodeWidth, nodeHeight, 8 * transform.k);
      else ctx.arc(point.x, point.y, active ? 7 : 5, 0, Math.PI * 2);
      ctx.fill();
      if (active) {
        ctx.strokeStyle = colors["--ink"];
        ctx.lineWidth = 5;
        ctx.stroke();
      }
      if (node.project) {
        ctx.strokeStyle = colors[projectColor(node.project)];
        ctx.lineWidth = 2;
        ctx.stroke();
      }
      if (box || highlighted?.has(node.id)) {
        ctx.fillStyle = colors["--ink"];
        ctx.fillText(truncateTitle(node.title, 22), point.x, box ? point.y : point.y + 20, box ? nodeWidth - 16 : 155);
      }
    }
    ctx.globalAlpha = 1;
    canvas.dataset.draws = String(++state.draws);
    canvas.dataset.zoom = String(transform.k);
    dirty = false;
  }

  function advance() {
    frame = null;
    if (state.destroyed || document.hidden) { stop(); return; }
    const moving = simulation.alpha() > simulation.alphaMin();
    if (moving) {
      simulation.tick(3);
      if (automaticFit) fitTransform();
      if (centered) {
        const node = byId.get(centered);
        transform.x = width / 2 - node.x * transform.k;
        transform.y = height / 2 - node.y * transform.k;
      }
      dirty = true;
    }
    if (dirty) draw();
    if (simulation.alpha() > simulation.alphaMin() || pointer?.node) frame = requestAnimationFrame(advance);
    else stop();
  }

  function requestDraw(reheat = false) {
    if (state.destroyed) return;
    dirty = true;
    if (reheat) simulation.alpha(Math.max(0.2, simulation.alpha()));
    if (document.hidden) return;
    state.running = true;
    canvas.dataset.running = "true";
    if (frame === null) frame = requestAnimationFrame(advance);
  }

  function resize() {
    if (state.destroyed) return;
    const bounds = canvas.getBoundingClientRect();
    const oldWidth = width, oldHeight = height;
    width = bounds.width; height = bounds.height; ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
    const styles = getComputedStyle(root);
    colors = Object.fromEntries(["--ink", "--ink-soft", "--line", "--sage", "--sage-deep", "--blue", "--amber", "--red"]
      .map(name => [name, styles.getPropertyValue(name).trim()]));
    font = styles.getPropertyValue("--font-body").trim();
    if (automaticFit) fitTransform();
    else { transform.x += (width - oldWidth) / 2; transform.y += (height - oldHeight) / 2; }
    requestDraw();
  }

  function select(id) {
    if (state.destroyed || !byId.has(id)) return;
    selected = id;
    canvas.dataset.selected = id;
    for (const [key, button] of buttons) button.setAttribute("aria-pressed", String(key === id));
    onSelect(byId.get(id));
    requestDraw(true);
  }

  function center(id) {
    const node = byId.get(id);
    if (!node || state.destroyed) return;
    automaticFit = false;
    centered = id;
    transform = { k: Math.max(0.8, transform.k), x: 0, y: 0 };
    transform.x = width / 2 - node.x * transform.k;
    transform.y = height / 2 - node.y * transform.k;
    select(id);
  }

  function zoom(factor, point = { x: width / 2, y: height / 2 }) {
    const world = screenToWorld(point, transform);
    const k = Math.max(0.08, Math.min(3, transform.k * factor));
    transform = { k, x: point.x - world.x * k, y: point.y - world.y * k };
    automaticFit = false;
    centered = null;
    requestDraw(true);
  }

  const eventPoint = event => {
    const bounds = canvas.getBoundingClientRect();
    return { x: event.clientX - bounds.left, y: event.clientY - bounds.top };
  };
  const nodeAt = point => findNode(nodes, screenToWorld(point, transform), 9 / transform.k, transform.k >= 0.55);

  listen(canvas, "wheel", event => {
    event.preventDefault();
    zoom(Math.exp(-event.deltaY * 0.001), eventPoint(event));
  }, { passive: false });
  listen(canvas, "pointerdown", event => {
    if (event.button !== 0) return;
    const point = eventPoint(event), node = nodeAt(point);
    pointer = { id: event.pointerId, start: point, last: point, node, moved: false };
    canvas.setPointerCapture(event.pointerId);
    automaticFit = false;
    centered = null;
    if (node) {
      const world = screenToWorld(point, transform);
      pointer.offset = { x: node.x - world.x, y: node.y - world.y };
      node.fx = node.x; node.fy = node.y;
      simulation.alphaTarget(0.1);
    }
    requestDraw(true);
  });
  listen(canvas, "pointermove", event => {
    const point = eventPoint(event);
    if (pointer && pointer.id === event.pointerId) {
      if (Math.hypot(point.x - pointer.start.x, point.y - pointer.start.y) > 4) pointer.moved = true;
      if (pointer.node) {
        const world = screenToWorld(point, transform);
        pointer.node.fx = world.x + pointer.offset.x; pointer.node.fy = world.y + pointer.offset.y;
      } else {
        transform.x += point.x - pointer.last.x; transform.y += point.y - pointer.last.y;
      }
      pointer.last = point;
      requestDraw(true);
    } else {
      const id = nodeAt(point)?.id || null;
      if (hovered !== id) { hovered = id; canvas.dataset.hovered = id || ""; requestDraw(); }
    }
  });
  function release(event, cancelled = false) {
    if (!pointer || pointer.id !== event.pointerId) return;
    const held = pointer;
    pointer = null;
    simulation.alphaTarget(0);
    if (held.node) {
      held.node.fx = held.node.id === focus ? 0 : null;
      held.node.fy = held.node.id === focus ? 0 : null;
      if (!cancelled && !held.moved) select(held.node.id);
    }
    if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
    requestDraw(true);
  }
  listen(canvas, "pointerup", event => release(event));
  listen(canvas, "pointercancel", event => release(event, true));
  listen(canvas, "lostpointercapture", event => release(event, true));
  listen(canvas, "pointerleave", () => { if (!pointer) { hovered = null; requestDraw(); } });
  listen(canvas, "dblclick", event => { const node = nodeAt(eventPoint(event)); if (node) onFocus(node.id); });
  listen(document, "visibilitychange", () => {
    if (document.hidden) {
      if (pointer) release({ pointerId: pointer.id }, true);
      stop();
    } else { resize(); requestDraw(); }
  });

  for (const node of nodes) {
    const button = el("button", { type: "button", "data-rid": node.id, "aria-pressed": String(node.id === selected) }, node.title);
    listen(button, "click", () => select(node.id));
    listen(button, "keydown", event => { if (event.key === "Enter" && event.shiftKey) { event.preventDefault(); onFocus(node.id); } });
    buttons.set(node.id, button);
    list.append(el("li", {}, button));
  }
  const legend = el("div", { class: "graph-legend", "aria-label": t("graph.legend") },
    ["note", "fact", "task", "memory", "receipt"].map(kind => el("span", { class: "graph-legend-item" },
      el("span", { class: `graph-swatch graph-swatch-${kind}`, "aria-hidden": "true" }), t(`graph.kind.${kind}`))),
    el("small", {}, t("graph.projectRing")), el("small", {}, t("graph.edgeLegend")));
  const controls = el("div", { class: "graph-zoom" });
  for (const [name, key, callback] of [
    ["zoom-in", "zoomIn", () => zoom(1.25)], ["zoom-out", "zoomOut", () => zoom(0.8)],
    ["maximize", "fit", () => { automaticFit = true; centered = null; fitTransform(); requestDraw(true); }],
  ]) {
    const button = el("button", { class: "icon-button", type: "button", "aria-label": t(`graph.${key}`), title: t(`graph.${key}`) }, icon(name));
    listen(button, "click", callback);
    controls.append(button);
  }
  root.append(canvas, list, legend, controls);
  const observer = new ResizeObserver(resize);
  observer.observe(canvas);
  listen(window, "resize", resize);
  return { root, canvas, state, select, center, setSearch(query) {
    matches = new Set(searchMatches(nodes, query).map(node => node.id));
    canvas.dataset.matches = String(matches.size);
    for (const [id, button] of buttons) button.dataset.match = String(matches.has(id));
    requestDraw();
  }, destroy() {
    state.destroyed = true;
    controller.abort();
    observer.disconnect();
    stop();
    canvas.dataset.destroyed = "true";
  } };
}
