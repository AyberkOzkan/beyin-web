import markdownit from "../../vendor/markdown-it.esm.min.js";

const markdown = markdownit({ html: false, linkify: false });
const taskIcons = Object.freeze({
  done: "circle-check", active: "circle-dot", waiting: "circle-pause", blocked: "circle-x",
  inbox: "circle", cancelled: "ban",
});

export function taskIcon(status) {
  return Object.hasOwn(taskIcons, status) ? taskIcons[status] : "circle-dashed";
}

export function splitNote(body) {
  const lines = String(body).replace(/^\uFEFF/, "").replace(/\r\n?/g, "\n").split("\n");
  const headings = [];
  // Token line maps respect nested and indented code while slicing the original Markdown.
  for (const token of markdown.parse(lines.join("\n"), {})) {
    if (token.type !== "heading_open" || token.tag !== "h2" || token.level !== 0) continue;
    const index = token.map[0];
    const line = lines[index];
    const heading = /^ {0,3}##(?:[ \t]+(.*?)|[ \t]*)$/.exec(line);
    if (heading) headings.push({ index, title: (heading[1] || "").replace(/[ \t]+#+[ \t]*$/, "").trim() });
  }
  return {
    intro: lines.slice(0, headings[0]?.index ?? lines.length).join("\n"),
    sections: headings.map((heading, index) => ({
      id: `projects-note-section-${index + 1}`, title: heading.title,
      body: lines.slice(heading.index + 1, headings[index + 1]?.index ?? lines.length).join("\n"),
    })),
  };
}

function normalized(value) {
  return String(value || "").normalize("NFC").toLocaleLowerCase("tr-TR");
}

export function filterProjects(projects, query = "", tab = "all") {
  const search = normalized(query).trim();
  return projects.filter(project => (tab !== "active" || !project.quiet) &&
    [project.name, project.title, project.summary].some(value => normalized(value).includes(search)));
}

export function projectCounts(projects) {
  return { all: projects.length, active: projects.filter(project => !project.quiet).length };
}

export function newestProject(projects) {
  const timestamp = project => {
    const value = Date.parse(project.last_activity);
    return Number.isFinite(value) ? value : -Infinity;
  };
  return projects.reduce((newest, project) => !newest || timestamp(project) > timestamp(newest) ? project : newest, null);
}

export function projectHash(name = "", query = "", tab = "all") {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (tab === "active") params.set("tab", tab);
  const suffix = params.toString();
  return `#/projeler${name ? `/${encodeURIComponent(name)}` : ""}${suffix ? `?${suffix}` : ""}`;
}

export function firstSentence(value) {
  const text = typeof value === "string" ? value.replace(/`|\*\*|__/g, "").trim() : "";
  const ending = /[.!?…]+[”’"']*(?=\s|$)|\n/.exec(text);
  return ending ? text.slice(0, ending.index + ending[0].length).trim() : text;
}
