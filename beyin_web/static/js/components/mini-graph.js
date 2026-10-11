import { get } from "../api.js";
import { el } from "../dom.js";
import { t } from "../i18n.js";
import { loadD3 } from "../d3.js";
import { errorState, skeleton } from "./index.js";
import { createSimulation, settleSimulation, kindColor, truncateTitle, screenToWorld, worldToScreen, findNode } from "./graph-core.js";
import { reducedMotion } from "../accessibility.js";

export function createMiniGraph(rid) {
  const root = el("div", { class: "mini-graph" });
  const state = { running: false, destroyed: false, draws: 0 };
  const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let simulation;
  let frame;
  let observer;
  let canvas;
  let transform;
  let nodes = [];
  let edges = [];
  let generation = 0;

  function stop() {
    state.running = false;
    simulation?.stop();
    cancelAnimationFrame(frame);
    root.dataset.running = "false";
  }

  function draw() {
    if (state.destroyed || !canvas || !transform) return;
    const bounds = canvas.getBoundingClientRect();
    const width = bounds.width;
    const height = bounds.height;
    if (!width || !height) return;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    const ctx = canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    const extentX = Math.max(50, ...nodes.map(node => Math.abs(node.x)));
    const extentY = Math.max(50, ...nodes.map(node => Math.abs(node.y)));
    transform = { x: width / 2, y: height / 2, k: Math.min(1, Math.max(0.1, (width - 80) / (extentX * 2)), (height - 60) / (extentY * 2)) };
    const styles = getComputedStyle(root);
    const color = name => styles.getPropertyValue(name).trim();
    ctx.strokeStyle = color("--line");
    ctx.lineWidth = 1;
    for (const edge of edges) {
      const source = worldToScreen(edge.source, transform);
      const target = worldToScreen(edge.target, transform);
      ctx.setLineDash(edge.type === "ref" ? [4, 3] : []);
      ctx.beginPath(); ctx.moveTo(source.x, source.y); ctx.lineTo(target.x, target.y); ctx.stroke();
    }
    ctx.setLineDash([]);
    ctx.font = `12px ${styles.getPropertyValue("--font-body").trim()}`;
    ctx.textAlign = "center";
    for (const node of nodes) {
      const point = worldToScreen(node, transform);
      const radius = node.id === rid ? 8 : 5;
      ctx.fillStyle = color(kindColor(node.kind));
      ctx.beginPath(); ctx.arc(point.x, point.y, radius, 0, Math.PI * 2); ctx.fill();
      if (node.project) {
        ctx.strokeStyle = color("--sage-deep");
        ctx.beginPath(); ctx.arc(point.x, point.y, radius + 2, 0, Math.PI * 2); ctx.stroke();
      }
      ctx.fillStyle = color("--ink");
      const labelY = point.y > height - 30 ? point.y - 14 : point.y + 21;
      ctx.fillText(truncateTitle(node.title, 14), Math.min(width - 48, Math.max(48, point.x)), labelY, 90);
    }
    root.dataset.draws = String(++state.draws);
  }

  function click(event) {
    if (state.destroyed || !transform) return;
    const bounds = canvas.getBoundingClientRect();
    const point = screenToWorld({ x: event.clientX - bounds.left, y: event.clientY - bounds.top }, transform);
    const node = findNode(nodes, point, 12 / transform.k);
    if (node && node.kind !== "unresolved") location.hash = `/not/${encodeURIComponent(node.id)}`;
  }

  function releaseCanvas() {
    stop();
    observer?.disconnect();
    canvas?.removeEventListener("click", click);
    canvas = null;
  }

  async function load() {
    if (state.destroyed) return;
    const current = ++generation;
    releaseCanvas();
    root.replaceChildren(skeleton(3));
    try {
      const data = await get("/api/v1/graph", { focus: rid, depth: 1 });
      if (state.destroyed || current !== generation) return;
      if (!data.nodes.some(node => node.id !== rid)) {
        root.replaceChildren(el("p", { class: "muted mini-graph-empty" }, t("knowledge.noNeighbors")));
        return;
      }
      const d3 = await loadD3();
      if (state.destroyed || current !== generation) return;
      canvas = el("canvas", { class: "mini-graph-canvas", role: "img", "aria-label": t("knowledge.graphDescription") });
      const list = el("ul", { class: "mini-graph-node-list", "aria-label": t("knowledge.graphNodes") },
        data.nodes.filter(node => node.kind !== "unresolved").map(node => el("li", {},
          el("a", { href: `#/not/${encodeURIComponent(node.id)}`, "aria-current": node.id === rid ? "page" : null }, node.title))));
      root.replaceChildren(canvas, list);
      simulation = createSimulation(d3, data.nodes, data.edges, { focus: rid });
      // Advance d3 manually: one owned animation loop can be cancelled completely.
      simulation.stop().alphaDecay(0.06);
      nodes = simulation.nodes();
      edges = simulation.force("link").links();
      transform = { x: 0, y: 0, k: 1 };
      canvas.addEventListener("click", click);
      observer = new ResizeObserver(draw);
      observer.observe(canvas);
      let ticks = 0;
      function advance() {
        if (state.destroyed || !state.running) return;
        simulation.tick(3);
        ticks += 3;
        draw();
        if (simulation.alpha() <= simulation.alphaMin() || ticks >= 180) stop();
        else frame = requestAnimationFrame(advance);
      }
      if (reducedMotion()) { settleSimulation(simulation); stop(); }
      else {
        state.running = true;
        root.dataset.running = "true";
        frame = requestAnimationFrame(advance);
      }
    } catch (error) {
      if (!state.destroyed && current === generation && error.code !== "unauthorized") {
        releaseCanvas();
        root.replaceChildren(errorState(t("knowledge.graphError"), () => void load()));
      }
    }
  }

  function preferenceChanged() {
    if (state.destroyed || !simulation || !canvas || !reducedMotion()) return;
    settleSimulation(simulation);
    stop();
    draw();
  }
  motion.addEventListener("change", preferenceChanged);
  void load();
  return { root, state, destroy() {
    state.destroyed = true;
    ++generation;
    motion.removeEventListener("change", preferenceChanged);
    releaseCanvas();
    root.dataset.destroyed = "true";
  } };
}
