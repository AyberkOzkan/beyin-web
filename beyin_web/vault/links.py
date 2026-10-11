from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from types import MappingProxyType

from beyin_web.vault.records import Record, classify
from beyin_web.vault.scan import VaultSnapshot


def fold_name(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    return unicodedata.normalize("NFC", value.replace("İ", "i").replace("I", "i").replace("ı", "i").lower())


def without_code(body: str) -> str:
    lines: list[str] = []
    fence: str | None = None
    fence_length = 0
    for line in body.lstrip("\ufeff").splitlines(keepends=True):
        if fence is not None:
            if re.fullmatch(rf" {{0,3}}{re.escape(fence)}{{{fence_length},}}[ \t]*", line.rstrip("\r\n")):
                fence = None
            lines.append("\n")
            continue
        opening = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)", line)
        if opening and (opening[1][0] != "`" or "`" not in opening[2]):
            fence, fence_length = opening[1][0], len(opening[1])
            lines.append("\n")
        else:
            lines.append(line)
    text = "".join(lines)
    spans = re.compile(r"(?<!`) (`+) (?!`) .*? (?<!`) \1 (?!`)", re.DOTALL | re.VERBOSE)
    return spans.sub(lambda match: "\n" * match[0].count("\n") or " ", text)


@dataclass(frozen=True)
class LinkIndex:
    outgoing: Mapping[str, tuple[str, ...]]
    incoming: Mapping[str, tuple[str, ...]]
    unresolved: Mapping[str, tuple[str, ...]]

    def __post_init__(self) -> None:
        for field in ("outgoing", "incoming", "unresolved"):
            value = getattr(self, field)
            object.__setattr__(self, field, MappingProxyType({key: tuple(items) for key, items in value.items()}))


def _target_key(value: str) -> str:
    value = fold_name(value)
    return value[:-3] if value.endswith(".md") else value


def build_links(snapshot: VaultSnapshot) -> LinkIndex:
    records = sorted(
        (record for record in snapshot.records.values() if classify(record) not in {"index", "rejected"}),
        key=lambda record: record.path,
    )
    paths: dict[str, Record] = {}
    names: dict[str, Record] = {}
    for record in sorted(records, key=lambda record: (len(record.path), record.path)):
        paths.setdefault(_target_key(record.path), record)
        names.setdefault(_target_key(PurePosixPath(record.path).name), record)
    outgoing: dict[str, tuple[str, ...]] = {}
    incoming: dict[str, set[str]] = {record.rid: set() for record in records}
    unresolved: dict[str, tuple[str, ...]] = {}
    order = {record.rid: record.path for record in records}
    for record in records:
        targets: set[str] = set()
        missing: set[str] = set()
        for match in re.finditer(r"!?\[\[([^\[\]\r\n]+)\]\]", without_code(record.body)):
            target = unicodedata.normalize("NFC", match[1].split("|", 1)[0].split("#", 1)[0].strip())
            if not target:
                continue
            resolved = (paths if "/" in target else names).get(_target_key(target))
            if resolved is None:
                missing.add(target)
            elif resolved.rid != record.rid:
                targets.add(resolved.rid)
                incoming[resolved.rid].add(record.rid)
        outgoing[record.rid] = tuple(sorted(targets, key=order.__getitem__))
        unresolved[record.rid] = tuple(sorted(missing))
    return LinkIndex(
        outgoing=outgoing,
        incoming={rid: tuple(sorted(sources, key=order.__getitem__)) for rid, sources in incoming.items()},
        unresolved=unresolved,
    )
