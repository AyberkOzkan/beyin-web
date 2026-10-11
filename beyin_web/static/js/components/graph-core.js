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

export function findNode(nodes, point, radius = 10, boxes = false) {
  let found = null;
  let distance = Infinity;
  for (const node of nodes) {
    const squared = (node.x - point.x) ** 2 + (node.y - point.y) ** 2;
    const inside = boxes && node.width && node.height ?
      Math.abs(node.x - point.x) <= node.width / 2 && Math.abs(node.y - point.y) <= node.height / 2 :
      squared <= (node.radius ?? radius) ** 2;
    if (inside && squared < distance) {
      found = node;
      distance = squared;
    }
  }
  return found;
}

export function projectColor(project) {
  const palette = ["--sage-deep", "--blue", "--amber", "--red", "--ink-soft"];
  let hash = 0;
  for (const character of String(project ?? "")) hash = (hash * 31 + character.codePointAt(0)) >>> 0;
  return palette[hash % palette.length];
}

export function createSimulation(d3, nodes, edges, {
  focus = null, distance = 70, charge = -100, collision = 22, center = false,
  attraction = 0.04, linkStrength = null,
} = {}) {
  // d3 mutates its inputs; copy API objects so cached responses remain reusable.
  const workingNodes = nodes.map(node => ({ ...node }));
  const ids = new Set(workingNodes.map(node => node.id));
  const workingEdges = edges.map(edge => ({ ...edge,
    source: typeof edge.source === "object" ? edge.source.id : edge.source,
    target: typeof edge.target === "object" ? edge.target.id : edge.target,
  })).filter(edge => ids.has(edge.source) && ids.has(edge.target));
  const selected = workingNodes.find(node => node.id === focus);
  if (selected) { selected.fx = 0; selected.fy = 0; selected.x = 0; selected.y = 0; }
  const link = d3.forceLink(workingEdges).id(node => node.id).distance(distance);
  if (linkStrength !== null) link.strength(linkStrength);
  const simulation = d3.forceSimulation(workingNodes)
    .force("link", link)
    .force("charge", d3.forceManyBody().strength(charge))
    .force("collision", d3.forceCollide(collision))
    .force("x", d3.forceX(0).strength(attraction))
    .force("y", d3.forceY(0).strength(attraction));
  if (center) simulation.force("center", d3.forceCenter(0, 0));
  return simulation;
}

export function nodeRadius(degree = 0) {
  return Math.min(16, 4 + 2 * Math.sqrt(Math.max(0, degree)));
}

export function labelOpacity(scale, highlighted = false) {
  return highlighted ? 1 : Math.max(0, Math.min(1, (scale - 0.5) / 0.3));
}

// Zoomed out, the dots shrink with the view; at a fixed size they would cover the gaps between them.
export function displayRadius(degree, scale) {
  return nodeRadius(degree) * Math.min(1, Math.max(0.4, Math.sqrt(scale)));
}

function hashSeed(value) {
  let hash = 2166136261;
  for (const character of String(value)) {
    hash ^= character.codePointAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function randomSequence(seed) {
  let value = hashSeed(seed);
  return () => {
    value = (Math.imul(value, 1664525) + 1013904223) >>> 0;
    return value / 4294967296;
  };
}

export function driftParameters(id) {
  const random = randomSequence(id);
  return { amplitude: 5 + random() * 3, phaseX: random() * Math.PI * 2,
    phaseY: random() * Math.PI * 2, periodX: 7 + random() * 6, periodY: 7 + random() * 6 };
}

export function driftOffset(id, seconds, parameters = driftParameters(id)) {
  const { amplitude, phaseX, phaseY, periodX, periodY } = parameters;
  const first = seconds * Math.PI * 2 / periodX + phaseX;
  const second = seconds * Math.PI * 2 / periodY + phaseY;
  return { x: amplitude * (0.7 * Math.sin(first) + 0.3 * Math.sin(second)),
    y: amplitude * (0.7 * Math.sin(first + Math.PI / 2) + 0.3 * Math.sin(second + Math.PI / 2)) };
}

export function starField(seed, count = 140) {
  const random = randomSequence(seed);
  return Array.from({ length: count }, () => ({ x: 0.02 + random() * 0.96, y: 0.02 + random() * 0.96,
    size: 1 + random() * 0.5, opacity: 0.2 + random() * 0.35 }));
}

const endpointId = endpoint => typeof endpoint === "object" ? endpoint.id : endpoint;

export function layoutMetrics(nodes, edges) {
  const byId = new Map(nodes.map(node => [node.id, node]));
  const neighbors = new Map(nodes.map(node => [node.id, new Set()]));
  let minimumDistance = Infinity;
  for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
    minimumDistance = Math.min(minimumDistance, Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y));
  }
  const lengths = [];
  for (const edge of edges) {
    const source = byId.get(endpointId(edge.source)), target = byId.get(endpointId(edge.target));
    if (!source || !target || source === target) continue;
    lengths.push(Math.hypot(source.x - target.x, source.y - target.y));
    neighbors.get(source.id).add(target.id);
    neighbors.get(target.id).add(source.id);
  }
  lengths.sort((a, b) => a - b);
  const middle = Math.floor(lengths.length / 2);
  const medianLinkDistance = !lengths.length ? 0 : lengths.length % 2 ? lengths[middle] : (lengths[middle - 1] + lengths[middle]) / 2;
  const leafSpreads = [];
  for (const node of nodes) {
    const leaves = [...neighbors.get(node.id)].filter(id => neighbors.get(id).size === 1);
    if (leaves.length < 2) continue;
    const distances = leaves.map(id => Math.hypot(byId.get(id).x - node.x, byId.get(id).y - node.y));
    leafSpreads.push({ id: node.id, leaves: leaves.length, ratio: Math.max(...distances) / Math.min(...distances) });
  }
  return { minimumDistance, medianLinkDistance, leafSpreads };
}

export function createSkySimulation(d3, nodes, edges, focus = "") {
  const simulation = createSimulation(d3, nodes, edges, { focus, charge: -1000, collision: 24,
    attraction: 0.002, linkStrength: 0.18,
    // Different preferred lengths keep a hub's leaves spread over several orbits.
    distance: edge => 160 + (hashSeed(`${edge.source.id}:${edge.target.id}`) % 280),
  }).stop().alphaDecay(0.06);
  const working = simulation.nodes();
  const neighbors = new Map(working.map(node => [node.id, new Set()]));
  for (const edge of simulation.force("link").links()) {
    neighbors.get(edge.source.id).add(edge.target.id);
    neighbors.get(edge.target.id).add(edge.source.id);
  }
  const seen = new Set(), components = [];
  for (const node of working) {
    if (seen.has(node.id)) continue;
    const component = [node.id];
    seen.add(node.id);
    for (let i = 0; i < component.length; i++) for (const id of neighbors.get(component[i])) {
      if (!seen.has(id)) { seen.add(id); component.push(id); }
    }
    components.push(component);
  }
  if (components.length > 1) {
    const targets = new Map();
    let cursor = 0;
    for (const component of components) {
      const radius = Math.sqrt(component.length) * 180;
      for (const id of component) targets.set(id, cursor + radius);
      cursor += radius * 2 + 240;
    }
    const origin = focus && targets.has(focus) ? targets.get(focus) : cursor / 2;
    simulation.force("x", d3.forceX(node => targets.get(node.id) - origin).strength(0.025));
  }
  return simulation;
}

// The stage is wider than it is tall, and the forces have no preferred direction: turning the
// layout so that its longest axis lies along x changes nothing but the use of the stage.
// Partial steps (the default) follow a layout that is still forming without spinning a round blob.
export function alignToHorizontal(nodes, { pivot = null, full = false } = {}) {
  const count = nodes.length;
  if (count < 3) return 0;
  let meanX = 0, meanY = 0;
  for (const node of nodes) { meanX += node.x; meanY += node.y; }
  meanX /= count; meanY /= count;
  let xx = 0, yy = 0, xy = 0;
  for (const node of nodes) {
    const dx = node.x - meanX, dy = node.y - meanY;
    xx += dx * dx; yy += dy * dy; xy += dx * dy;
  }
  if (!(xx + yy)) return 0;
  const anisotropy = Math.hypot(xx - yy, 2 * xy) / (xx + yy);
  const angle = 0.5 * Math.atan2(2 * xy, xx - yy) * (full ? 1 : anisotropy);
  if (Math.abs(angle) < 1e-4) return 0;
  const cos = Math.cos(-angle), sin = Math.sin(-angle);
  const centerX = pivot ? pivot.x : meanX, centerY = pivot ? pivot.y : meanY;
  for (const node of nodes) {
    const dx = node.x - centerX, dy = node.y - centerY;
    node.x = centerX + dx * cos - dy * sin;
    node.y = centerY + dx * sin + dy * cos;
    if (Number.isFinite(node.vx) && Number.isFinite(node.vy)) {
      const vx = node.vx, vy = node.vy;
      node.vx = vx * cos - vy * sin;
      node.vy = vx * sin + vy * cos;
    }
  }
  return angle;
}

export function settleSimulation(simulation, maximum = 180) {
  simulation.stop();
  for (let tick = 0; tick < maximum && simulation.alpha() > simulation.alphaMin(); tick++) simulation.tick();
  simulation.alpha(0);
}
