const colors = Object.freeze({
  note: "--sage", untrusted: "--sage", fact: "--blue", knowledge: "--blue",
  task: "--amber", memory: "--sage-deep", receipt: "--ink-soft",
  rejected: "--red", unresolved: "--line", index: "--ink-soft",
});

export function kindColor(kind) {
  return colors[kind] || "--ink-soft";
}

export function truncateTitle(title, maximum = 24) {
  const chars = Array.from(String(title ?? ""));
  const limit = Math.max(0, Math.trunc(maximum));
  return chars.length <= limit ? chars.join("") : limit === 0 ? "" : chars.slice(0, limit - 1).join("") + "…";
}

export function worldToScreen(point, transform = { x: 0, y: 0, k: 1 }) {
  return { x: point.x * transform.k + transform.x, y: point.y * transform.k + transform.y };
}

export function screenToWorld(point, transform = { x: 0, y: 0, k: 1 }) {
  return { x: (point.x - transform.x) / transform.k, y: (point.y - transform.y) / transform.k };
}

export function findNode(nodes, point, radius = 10) {
  let found = null;
  let distance = Infinity;
  for (const node of nodes) {
    const squared = (node.x - point.x) ** 2 + (node.y - point.y) ** 2;
    if (squared <= (node.radius ?? radius) ** 2 && squared < distance) {
      found = node;
      distance = squared;
    }
  }
  return found;
}

export function createSimulation(d3, nodes, edges, { focus = null, distance = 70, charge = -100 } = {}) {
  // d3 mutates its inputs; copy API objects so cached responses remain reusable.
  const workingNodes = nodes.map(node => ({ ...node }));
  const ids = new Set(workingNodes.map(node => node.id));
  const workingEdges = edges.map(edge => ({ ...edge,
    source: typeof edge.source === "object" ? edge.source.id : edge.source,
    target: typeof edge.target === "object" ? edge.target.id : edge.target,
  })).filter(edge => ids.has(edge.source) && ids.has(edge.target));
  const selected = workingNodes.find(node => node.id === focus);
  if (selected) { selected.fx = 0; selected.fy = 0; selected.x = 0; selected.y = 0; }
  return d3.forceSimulation(workingNodes)
    .force("link", d3.forceLink(workingEdges).id(node => node.id).distance(distance))
    .force("charge", d3.forceManyBody().strength(charge))
    .force("collision", d3.forceCollide(22))
    .force("x", d3.forceX(0).strength(0.04))
    .force("y", d3.forceY(0).strength(0.04));
}
