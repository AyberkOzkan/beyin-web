import { drawingSources } from "./index.js";
import { placeDoodles } from "./doodles-model.js";

const SVG = "http://www.w3.org/2000/svg";
const COLUMNS = ".three-columns, .record-columns, .graph-layout";

// A layer over the work area that scatters small doodles where the page leaves paper bare: under a short page
// and under the short columns of a long one. It never takes room and never covers content.
export function doodleLayer(workspace, main) {
  const seed = Math.floor(Math.random() * 1e9);
  const layer = document.createElementNS(SVG, "svg");
  layer.setAttribute("class", "doodle-layer");
  layer.setAttribute("aria-hidden", "true");
  layer.setAttribute("focusable", "false");
  workspace.append(layer);
  let page = "";
  let frame = 0;
  let drawn = "";

  function zones() {
    const base = workspace.getBoundingClientRect(), box = main.getBoundingClientRect(), style = getComputedStyle(main);
    const left = box.left + parseFloat(style.paddingLeft), right = box.right - parseFloat(style.paddingRight);
    const end = Math.max(box.top, ...[...main.querySelectorAll(":scope > *, :scope > * > *")].map(node => node.getBoundingClientRect().bottom));
    const found = [{ key: "foot", x: left - base.left, y: end + 22 - base.top, width: right - left, height: box.bottom - end - 34 }];
    main.querySelectorAll(COLUMNS).forEach((container, number) => {
      const columns = [...container.children].filter(column => column.getClientRects().length);
      const ends = columns.map(column => {
        const bounds = column.getBoundingClientRect();
        // A column that is itself a box ends where the box ends; a stack of boxes ends at its last box.
        if (column.matches(".card, .graph-area") || !column.children.length) return bounds.bottom;
        return Math.max(bounds.top, ...[...column.children].map(node => node.getBoundingClientRect().bottom));
      });
      const floor = Math.max(...ends);
      columns.forEach((column, index) => {
        const bounds = column.getBoundingClientRect();
        found.push({ key: `column-${number}-${index}`, x: bounds.left - base.left, y: ends[index] + 22 - base.top,
          width: bounds.width, height: floor - ends[index] - 30 });
      });
    });
    return found;
  }

  function draw() {
    frame = 0;
    const base = workspace.getBoundingClientRect();
    const items = placeDoodles(zones(), drawingSources("margin-doodle"), `${seed}:${page}`);
    const next = JSON.stringify([Math.round(base.width), Math.round(base.height), items]);
    if (next === drawn) return;
    drawn = next;
    layer.setAttribute("viewBox", `0 0 ${base.width} ${base.height}`);
    layer.replaceChildren(...items.map(item => {
      const image = document.createElementNS(SVG, "image");
      for (const [name, value] of Object.entries({ href: item.source, x: item.x, y: item.y, width: item.size, height: item.size,
        transform: `rotate(${item.turn} ${item.x + item.size / 2} ${item.y + item.size / 2})` })) image.setAttribute(name, value);
      return image;
    }));
  }

  const schedule = () => { if (!frame) frame = requestAnimationFrame(draw); };
  new ResizeObserver(schedule).observe(main);
  new MutationObserver(schedule).observe(main, { childList: true, subtree: true });
  main.addEventListener("load", schedule, true);
  window.addEventListener("resize", schedule);
  return { update(name) { page = name; schedule(); } };
}
