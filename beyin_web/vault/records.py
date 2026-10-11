from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import PurePosixPath
from types import MappingProxyType


MEMORY_ROLES: Mapping[str, str] = MappingProxyType({
    "Core.md": "core",
    "Soul.md": "soul",
    "Kurallar.md": "rules",
    "Last-Session.md": "last_session",
    "Threads.md": "threads",
    "Journal.md": "journal",
})


def _normalize_path(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\\", "/"))


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class Record:
    rid: str
    path: str
    kind: str
    title: str
    project: str | None
    visibility: str
    mtime: datetime
    meta: Mapping[str, object]
    body: str
    excerpt: str
    role: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "meta", _freeze(self.meta))


@dataclass(frozen=True)
class _DerivedReceiptRecord(Record):
    """Keep title provenance without changing Record fields or exposed metadata."""


def with_receipt_titles(records: Mapping[str, Record]) -> dict[str, Record]:
    names = {record.project for record in records.values()
             if record.project and classify(record) not in {"index", "rejected", "receipt"}}
    result = dict(records)
    for rid, record in records.items():
        if isinstance(record, _DerivedReceiptRecord):
            title = receipt_title(record.body, record.path, names)
            if title != record.title:
                result[rid] = replace(record, title=title)
    return result


def make_rid(rel_path: str) -> str:
    return hashlib.sha1(_normalize_path(rel_path).encode("utf-8")).hexdigest()[:12]


def classify(record: Record) -> str:
    if record.meta.get("generated") is True or record.kind == "receipt-index":
        return "index"
    if record.kind == "receipt":
        return "receipt"
    if record.kind == "task":
        return "task"
    if record.kind == "fact":
        return "knowledge"
    if record.kind in ("inference", "preference") and (
        record.meta.get("validity") == "rejected" or record.meta.get("status") == "rejected"
    ):
        return "rejected"
    if record.role:
        return "memory"
    return "note"


def _excerpt(body: str) -> str:
    paragraph: list[str] = []
    fence: str | None = None
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            if paragraph:
                break
            marker = stripped[:3]
            fence = None if fence == marker else marker if fence is None else fence
            continue
        if fence is not None:
            continue
        if not stripped or re.match(r"^#{1,6}(?:\s|$)", stripped):
            if paragraph:
                break
            continue
        paragraph.append(stripped)
    result = re.sub(r"\s+", " ", _plain_markdown(" ".join(paragraph))).strip()
    return result[:239].rstrip() + "…" if len(result) > 240 else result


def _plain_markdown(result: str) -> str:
    result = re.sub(
        r"!?\[\[([^\]]+)\]\]",
        lambda match: match[1].split("|", 1)[1] if "|" in match[1] else match[1].split("#", 1)[0],
        result,
    )
    result = re.sub(r"!?\[([^\]]*)\]\((?:[^()]|\([^()]*\))*\)", r"\1", result)
    result = re.sub(r"!?\[([^\]]+)\]\[[^\]]*\]", r"\1", result)
    for marker in ("**", "__", "~~", "*", "_", "`"):
        result = re.sub(
            rf"(?<!\w){re.escape(marker)}(.+?){re.escape(marker)}(?!\w)", r"\1", result,
        )
    return result


def receipt_summary(body: str) -> tuple[str, str | None]:
    from beyin_web.vault.links import fold_name

    lines: list[str] = []
    learned: list[str] = []
    for line in body.lstrip("\ufeff").splitlines():
        label, separator, value = line.strip().partition(":")
        if separator and fold_name(label) == "öğrenilen":
            value = value.strip()
            if value and fold_name(value) != "yok":
                learned.append(value)
        else:
            lines.append(line)
    return "\n".join(lines).strip(), "\n".join(learned) or None


def receipt_project(summary: str, known_projects: Iterable[str]) -> str | None:
    from beyin_web.vault.links import fold_name

    prefix, separator, _ = summary.partition(":")
    if separator:
        key = fold_name(prefix.strip())
        return next((name for name in sorted(known_projects) if fold_name(name) == key), None)
    return None


def receipt_title(body: str, path: str, known_projects: Iterable[str] = ()) -> str:
    summary, _ = receipt_summary(body)
    if receipt_project(summary, known_projects) is not None:
        summary = summary.partition(":")[2].lstrip()
    fallback = PurePosixPath(path).stem[:12] + "…"
    if summary.startswith(("~~~", "\x60\x60\x60")):
        return fallback
    plain = _plain_markdown(summary).strip()
    title = re.split(r"[.!?\r\n]", plain, maxsplit=1)[0].strip()
    if not title or "\ufffd" in title:
        return fallback
    if len(title) > 80:
        cut = title[:79]
        if not title[79].isspace() and " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        title = cut.rstrip() + "…"
    return title


def _memory_role(rel_path: str, companion_dir: str | None) -> str | None:
    if companion_dir is None:
        return None
    path = PurePosixPath(_normalize_path(rel_path))
    if path.parent == PurePosixPath(_normalize_path(companion_dir)):
        return MEMORY_ROLES.get(path.name)
    return None


def _heading(body: str) -> str | None:
    fence: str | None = None
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            fence = None if fence == marker else marker if fence is None else fence
        elif fence is None:
            match = re.match(r"^# +(.+?)\s*$", line)
            if match:
                return match[1].strip()
    return None


def build_record(
    rel_path: str,
    meta: Mapping[str, object],
    body: str,
    mtime: datetime,
    companion_dir: str | None = None,
) -> tuple[Record | None, str | None]:
    visibility = meta.get("visibility", "internal")
    if visibility == "private":
        return None, None
    if visibility not in ("public", "internal"):
        return None, "invalid_visibility"
    path = _normalize_path(rel_path)
    body = body.lstrip("\ufeff")
    kind = meta.get("kind", "note")
    if not isinstance(kind, str) or not kind:
        kind = "note"
    title = meta.get("title")
    record_type = Record
    if not isinstance(title, str) or not title.strip():
        title = receipt_title(body, path) if kind == "receipt" else _heading(body) or PurePosixPath(path).stem
        if kind == "receipt":
            record_type = _DerivedReceiptRecord
    project = meta.get("project")
    if not isinstance(project, str) or not project:
        project = None
    remaining = {key: value for key, value in meta.items() if key not in {"title", "kind", "project", "visibility"}}
    return record_type(
        rid=make_rid(path), path=path, kind=kind, title=title, project=project,
        visibility=visibility, mtime=mtime, meta=remaining, body=body,
        excerpt=_excerpt(body), role=_memory_role(path, companion_dir),
    ), None
