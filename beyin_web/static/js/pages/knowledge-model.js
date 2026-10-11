export function groupNotes(records) {
  const groups = new Map();
  for (const record of records) {
    const project = record.project || null;
    if (!groups.has(project)) groups.set(project, []);
    groups.get(project).push(record);
  }
  return [...groups].map(([project, notes]) => ({ project, records: notes }));
}

export function filterGroups(groups, query = "") {
  const needle = query.normalize("NFC").trim().toLocaleLowerCase("tr-TR");
  return groups.map(group => ({ ...group, records: group.records.filter(record =>
    [record.title, record.summary, record.excerpt, group.project].some(value =>
      typeof value === "string" && value.normalize("NFC").toLocaleLowerCase("tr-TR").includes(needle)))
  })).filter(group => group.records.length);
}

export function firstNote(groups) {
  return groups.find(group => group.records.length)?.records[0] || null;
}

export function firstSentence(value) {
  const text = typeof value === "string" ? value.replace(/`|\*\*|__/g, "").trim() : "";
  const ending = /[.!?…]+[”’"']*(?=\s|$)|\n/.exec(text);
  return ending ? text.slice(0, ending.index + ending[0].length).trim() : text;
}

// The reader prints the title itself; a body that opens with the same heading would repeat it.
export function withoutLeadingTitle(body, title) {
  const text = typeof body === "string" ? body : "";
  const match = /^\s*#[ \t]+(.+?)[ \t]*#*[ \t]*(?:\r?\n|$)/.exec(text);
  const same = match && match[1].trim().normalize("NFC") === String(title ?? "").trim().normalize("NFC");
  return same ? text.slice(match[0].length) : text;
}

export function recordKind(kind) {
  return kind === "fact" ? "knowledge" : kind === "untrusted" ? "note" : kind;
}

export function receiptDate(value) {
  // Journal buckets use the timestamp's local date, including its explicit offset.
  return typeof value === "string" ? value.slice(0, 10) : "";
}
