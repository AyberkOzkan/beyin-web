const files = ["d3-dispatch", "d3-quadtree", "d3-timer", "d3-force"];
let loading;

// The vendored d3 modules are UMD builds that extend window.d3 and must run in dependency order.
export function loadD3() {
  loading ||= files.reduce((previous, name) => previous.then(() => new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = `/static/vendor/${name}.min.js`;
    script.addEventListener("load", resolve, { once: true });
    script.addEventListener("error", () => reject(new Error("d3_load_failed")), { once: true });
    document.head.append(script);
  })), Promise.resolve()).then(() => window.d3, error => { loading = undefined; throw error; });
  return loading;
}
