import { el, icon } from "../dom.js";
import { t } from "../i18n.js";
import { loadD3 } from "../d3.js";
import { createSkySimulation, settleSimulation, kindColor, projectColor, truncateTitle,
  screenToWorld, worldToScreen, findNode, displayRadius, labelOpacity, alignToHorizontal, driftParameters, driftOffset, starField } from "./graph-core.js";
import { adjacency, focusDistances, searchMatches } from "../pages/graph-model.js";

export async function createGraphCanvas(data, { focus = "", onSelect = () => {}, onFocus = () => {} } = {}) {
  const d3 = await loadD3();
  const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const root = el("div", { class: "graph-stage" });
  const canvas = el("canvas", { class: "graph-canvas", role: "img", "aria-label": t("graph.canvas"),
    "data-nodes": data.nodes.length, "data-edges": data.edges.length, "data-running": "false",
    "data-drifting": "false", "data-settled": "false", "data-draws": "0" });
  const list = el("ul", { class: "graph-node-list", "aria-label": t("graph.nodeList") });
  const controller = new AbortController();
  const listen = (target, name, callback, options = {}) => target.addEventListener(name, callback, { ...options, signal: controller.signal });
  const neighbors = adjacency(data.nodes, data.edges);
  const depths = focusDistances(focus, neighbors);
  const simulation = createSkySimulation(d3, data.nodes, data.edges, focus);
  const nodes = simulation.nodes();
  const edges = simulation.force("link").links();
  const byId = new Map(nodes.map(node => [node.id, node]));
  const parameters = new Map(nodes.map(node => [node.id, driftParameters(node.id)]));
  const buttons = new Map(), halos = new Map();
  const stars = starField("beyin-sky");
  const state = { destroyed: false, running: false, draws: 0 };
  let frame = null, dirty = true, hovered = null, selected = focus, matches = new Set(), pointer = null;
  let width = 0, height = 0, ratio = 1, automaticFit = true, centered = null;
  let transform = { x: 0, y: 0, k: 1 };
  let colors = {}, font = "", paused = false, driftTime = 0, previousTime = null, hasDrifted = false;
  let displayed = new Map(), aligned = false;
  const pivot = focus ? { x: 0, y: 0 } : null;
  const moving = () => simulation.alpha() > simulation.alphaMin();
  const drifting = () => !state.destroyed && !document.hidden && !motion.matches && !paused && !selected && !pointer && !moving();

  function stop() {
    simulation.stop();
    if (frame !== null) cancelAnimationFrame(frame);
    frame = null;
    previousTime = null;
    state.running = false;
    canvas.dataset.running = "false";
    canvas.dataset.drifting = "false";
  }

  function offset(node) {
    return !hasDrifted || motion.matches || moving() || pointer?.node === node ? { x: 0, y: 0 } :
      driftOffset(node.id, driftTime, parameters.get(node.id));
  }

  function fitTransform() {
    if (!nodes.length) return;
    const left = Math.min(...nodes.map(node => node.x - 12));
    const right = Math.max(...nodes.map(node => node.x + 12));
    const top = Math.min(...nodes.map(node => node.y - 12));
    const bottom = Math.max(...nodes.map(node => node.y + 12));
    const spanX = focus ? 2 * Math.max(Math.abs(left), Math.abs(right)) : right - left;
    const spanY = focus ? 2 * Math.max(Math.abs(top), Math.abs(bottom)) : bottom - top;
    // The controls sit on the bottom edge; the graph is fitted into the area above them.
    const padX = 50, padTop = 36, padBottom = 76;
    const k = Math.min(1.2, (width - 2 * padX) / Math.max(1, spanX), (height - padTop - padBottom) / Math.max(1, spanY));
    transform = { k: Math.max(0.001, k), x: width / 2 - (focus ? 0 : (left + right) / 2) * k,
      // A focused note stays in the exact middle of the stage.
      y: focus ? height / 2 : padTop + (height - padTop - padBottom) / 2 - (top + bottom) / 2 * k };
  }

  function halo(color) {
    if (halos.has(color)) return halos.get(color);
    const sprite = document.createElement("canvas");
    sprite.width = sprite.height = 96;
    const ctx = sprite.getContext("2d");
    // Token colors are hex; suffixes supply only the sprite's alpha channel.
    const gradient = ctx.createRadialGradient(48, 48, 0, 48, 48, 48);
    gradient.addColorStop(0, `${color}4d`);
    gradient.addColorStop(0.4, `${color}29`);
    gradient.addColorStop(1, `${color}00`);
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 96, 96);
    halos.set(color, sprite);
    return sprite;
  }

  function draw() {
    if (state.destroyed || document.hidden || !width || !height) return;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    ctx.globalAlpha = 1;
    ctx.fillStyle = colors["--space"];
    ctx.fillRect(0, 0, width, height);
    ctx.fillStyle = colors["--space-soft"];
    for (const star of stars) {
      ctx.globalAlpha = star.opacity;
      ctx.fillRect(star.x * width, star.y * height, star.size, star.size);
    }
    const anchors = new Set([hovered, selected].filter(Boolean));
    const highlighted = anchors.size ? new Set([...anchors].flatMap(id => [id, ...(neighbors.get(id) || [])])) : null;
    displayed = new Map(nodes.map(node => {
      const shift = offset(node);
      return [node.id, { ...worldToScreen({ x: node.x + shift.x, y: node.y + shift.y }, transform),
        id: node.id, radius: displayRadius(node.degree, transform.k) }];
    }));
    for (const edge of edges) {
      const source = displayed.get(edge.source.id), target = displayed.get(edge.target.id);
      const active = anchors.has(edge.source.id) || anchors.has(edge.target.id);
      ctx.globalAlpha = highlighted ? active ? 1 : 0.08 :
        focus && (depths.get(source.id) > 1 || depths.get(target.id) > 1) ? 0.3 : 0.65;
      ctx.strokeStyle = colors[active ? "--space-accent" : "--space-line"];
      ctx.lineWidth = active ? 1.5 : 1;
      ctx.setLineDash(edge.type === "ref" ? [5, 4] : []);
      ctx.beginPath(); ctx.moveTo(source.x, source.y); ctx.lineTo(target.x, target.y); ctx.stroke();
    }
    ctx.setLineDash([]);
    ctx.font = `14px ${font}`;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    for (const node of nodes) {
      const point = displayed.get(node.id), radius = point.radius;
      const active = node.id === selected || matches.has(node.id) || node.id === focus || highlighted?.has(node.id);
      const alpha = highlighted && !highlighted.has(node.id) ? 0.18 : focus && depths.get(node.id) > 1 ? 0.3 : 1;
      const color = colors[kindColor(node.kind)] || colors["--space-soft"];
      ctx.globalAlpha = alpha;
      ctx.drawImage(halo(color), point.x - radius * 2.5, point.y - radius * 2.5, radius * 5, radius * 5);
      ctx.fillStyle = color;
      ctx.beginPath(); ctx.arc(point.x, point.y, radius, 0, Math.PI * 2); ctx.fill();
      if (node.project) {
        ctx.strokeStyle = colors[projectColor(node.project)];
        ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.arc(point.x, point.y, radius + 2, 0, Math.PI * 2); ctx.stroke();
      }
      if (node.id === selected) {
        ctx.globalAlpha = 1;
        ctx.strokeStyle = colors["--space-accent"];
        ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.arc(point.x, point.y, radius + 5, 0, Math.PI * 2); ctx.stroke();
      }
      const opacity = labelOpacity(transform.k, active);
      if (opacity > 0) {
        ctx.globalAlpha = active ? opacity : alpha * opacity;
        ctx.fillStyle = colors["--space-ink"];
        ctx.fillText(truncateTitle(node.title, 28), point.x, point.y + radius + 8);
      }
    }
    ctx.globalAlpha = 1;
    ctx.resetTransform();
    canvas.dataset.draws = String(++state.draws);
    canvas.dataset.zoom = String(transform.k);
    canvas.dataset.settled = String(!moving());
    dirty = false;
  }

  function centerTransform() {
    if (automaticFit) fitTransform();
    if (centered) {
      const node = byId.get(centered), shift = offset(node);
      transform.x = width / 2 - (node.x + shift.x) * transform.k;
      transform.y = height / 2 - (node.y + shift.y) * transform.k;
    }
  }

  function advance(timestamp) {
    frame = null;
    if (state.destroyed || document.hidden) { stop(); return; }
    if (moving()) {
      simulation.tick(3);
      // Only the first layout is turned; a later drag must not swing the whole sky around.
      if (!aligned && !pointer) alignToHorizontal(nodes, { pivot });
      if (!moving()) aligned = true;
      centerTransform();
      dirty = true;
    }
    const drift = drifting();
    if (drift) {
      hasDrifted = true;
      if (previousTime !== null) driftTime += (timestamp - previousTime) / 1000;
      previousTime = timestamp;
      dirty = true;
    } else previousTime = null;
    canvas.dataset.drifting = String(drift);
    if (dirty) draw();
    if (moving() || drift) frame = requestAnimationFrame(advance);
    else stop();
  }

  function requestDraw(reheat = false) {
    if (state.destroyed) return;
    dirty = true;
    if (reheat) simulation.alpha(Math.max(0.2, simulation.alpha()));
    if (document.hidden) return;
    if (motion.matches || selected || paused) {
      stop();
      if (moving()) {
        settleSimulation(simulation);
        if (!aligned && !pointer) alignToHorizontal(nodes, { pivot, full: true });
        aligned = true;
      }
      centerTransform();
      draw();
      return;
    }
    state.running = true;
    canvas.dataset.running = "true";
    if (frame === null) frame = requestAnimationFrame(advance);
  }

  function resize() {
    if (state.destroyed || document.hidden) return;
    const bounds = canvas.getBoundingClientRect();
    const oldWidth = width, oldHeight = height;
    width = bounds.width; height = bounds.height; ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
    const styles = getComputedStyle(root);
    colors = Object.fromEntries(["--space", "--space-ink", "--space-soft", "--space-line", "--space-accent",
      "--ink-soft", "--line", "--sage", "--sage-deep", "--blue", "--amber", "--red"]
      .map(name => [name, styles.getPropertyValue(name).trim()]));
    font = styles.getPropertyValue("--font-body").trim();
    halos.clear();
    if (automaticFit) fitTransform();
    else { transform.x += (width - oldWidth) / 2; transform.y += (height - oldHeight) / 2; }
    requestDraw();
  }

  function select(id) {
    if (state.destroyed || id && !byId.has(id)) return;
    selected = id || "";
    if (!selected) centered = null;
    canvas.dataset.selected = selected;
    for (const [key, button] of buttons) button.setAttribute("aria-pressed", String(key === selected));
    onSelect(byId.get(selected) || null);
    requestDraw();
  }

  function center(id) {
    if (!byId.has(id) || state.destroyed) return;
    automaticFit = false;
    centered = id;
    transform.k = Math.max(0.8, transform.k);
    select(id);
  }

  function zoom(factor, point = { x: width / 2, y: height / 2 }) {
    const world = screenToWorld(point, transform);
    const k = Math.max(0.001, Math.min(3, transform.k * factor));
    transform = { k, x: point.x - world.x * k, y: point.y - world.y * k };
    automaticFit = false;
    centered = null;
    requestDraw();
  }

  const eventPoint = event => {
    const bounds = canvas.getBoundingClientRect();
    return { x: event.clientX - bounds.left, y: event.clientY - bounds.top };
  };
  const nodeAt = point => byId.get(findNode([...displayed.values()], point)?.id);

  listen(canvas, "wheel", event => {
    event.preventDefault();
    zoom(Math.exp(-event.deltaY * 0.001), eventPoint(event));
  }, { passive: false });
  listen(canvas, "pointerdown", event => {
    if (event.button !== 0) return;
    const point = eventPoint(event), node = nodeAt(point);
    const shift = node && offset(node);
    pointer = { id: event.pointerId, start: point, last: point, node, moved: false };
    previousTime = null;
    canvas.setPointerCapture(event.pointerId);
    automaticFit = false;
    centered = null;
    if (node) {
      pointer.original = { x: node.x, y: node.y };
      const world = screenToWorld(point, transform);
      node.x += shift.x; node.y += shift.y;
      pointer.offset = { x: node.x - world.x, y: node.y - world.y };
      node.fx = node.x; node.fy = node.y;
    }
    requestDraw();
  });
  listen(canvas, "pointermove", event => {
    const point = eventPoint(event);
    if (pointer && pointer.id === event.pointerId) {
      if (Math.hypot(point.x - pointer.start.x, point.y - pointer.start.y) > 4) pointer.moved = true;
      if (pointer.node) {
        const world = screenToWorld(point, transform);
        pointer.node.x = pointer.node.fx = world.x + pointer.offset.x;
        pointer.node.y = pointer.node.fy = world.y + pointer.offset.y;
      } else {
        transform.x += point.x - pointer.last.x; transform.y += point.y - pointer.last.y;
      }
      pointer.last = point;
      requestDraw();
    } else {
      const id = nodeAt(point)?.id || null;
      if (hovered !== id) { hovered = id; canvas.dataset.hovered = id || ""; requestDraw(); }
    }
  });
  function release(event, cancelled = false) {
    if (!pointer || pointer.id !== event.pointerId) return;
    const held = pointer;
    pointer = null;
    if (held.node) {
      if (!held.moved) Object.assign(held.node, held.original);
      else {
        const shift = offset(held.node);
        held.node.x -= shift.x; held.node.y -= shift.y;
      }
      held.node.fx = held.node.id === focus ? 0 : null;
      held.node.fy = held.node.id === focus ? 0 : null;
      if (!cancelled && !held.moved) select(held.node.id);
    } else if (!cancelled && !held.moved) select("");
    if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
    requestDraw(Boolean(held.node && held.moved));
  }
  listen(canvas, "pointerup", event => release(event));
  listen(canvas, "pointercancel", event => release(event, true));
  listen(canvas, "lostpointercapture", event => release(event, true));
  listen(canvas, "pointerleave", () => { if (!pointer) { hovered = null; canvas.dataset.hovered = ""; requestDraw(); } });
  listen(canvas, "dblclick", event => { const node = nodeAt(eventPoint(event)); if (node) onFocus(node.id); });
  listen(document, "keydown", event => {
    if (event.key === "Escape" && selected) { hovered = null; canvas.dataset.hovered = ""; select(""); }
  });
  listen(document, "visibilitychange", () => {
    if (document.hidden) {
      if (pointer) release({ pointerId: pointer.id }, true);
      stop();
    } else resize();
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
    ["maximize", "fit", () => { automaticFit = true; centered = null; fitTransform(); requestDraw(); }],
  ]) {
    const button = el("button", { class: "icon-button", type: "button", "aria-label": t(`graph.${key}`), title: t(`graph.${key}`) }, icon(name));
    listen(button, "click", callback);
    controls.append(button);
  }
  const pause = el("button", { class: "icon-button graph-motion", type: "button" }, icon("circle-pause"));
  function updatePause() {
    pause.hidden = motion.matches;
    pause.setAttribute("aria-pressed", String(paused));
    pause.setAttribute("aria-label", t(paused ? "graph.startMotion" : "graph.stopMotion"));
    pause.title = pause.getAttribute("aria-label");
  }
  listen(pause, "click", () => { paused = !paused; updatePause(); requestDraw(); });
  updatePause();
  controls.append(pause);
  root.append(canvas, list, legend, controls);
  const observer = new ResizeObserver(resize);
  observer.observe(canvas);
  listen(window, "resize", resize);
  listen(motion, "change", () => { updatePause(); requestDraw(); });
  return { root, canvas, state, select, center,
    positions() { return nodes.map(node => ({ id: node.id, x: node.x, y: node.y, degree: node.degree,
      screen: displayed.has(node.id) ? { ...displayed.get(node.id) } : null })); },
    setSearch(query) {
      matches = new Set(searchMatches(nodes, query).map(node => node.id));
      canvas.dataset.matches = String(matches.size);
      for (const [id, button] of buttons) button.dataset.match = String(matches.has(id));
      requestDraw();
    }, destroy() {
      state.destroyed = true;
      controller.abort();
      observer.disconnect();
      stop();
      halos.clear();
      canvas.dataset.destroyed = "true";
    } };
}
