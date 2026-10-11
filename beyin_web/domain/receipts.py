from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from beyin_web.domain.tasks import _text
from beyin_web.vault.records import classify, receipt_project, receipt_summary
from beyin_web.vault.scan import VaultSnapshot


@dataclass(frozen=True)
class Receipt:
    rid: str
    created_at: datetime
    event_id: str | None
    harness: str | None
    session: str | None
    refs: tuple[str, ...]
    ref_rids: tuple[str, ...]
    summary: str
    learned: str | None
    projects: tuple[str, ...]
    project_inferred: bool


def _path_key(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\\", "/"))


def build_receipts(
    snapshot: VaultSnapshot, known_projects: Iterable[str],
) -> tuple[tuple[Receipt, ...], tuple[str, ...]]:
    records = sorted(snapshot.records.values(), key=lambda record: record.path)
    paths = {
        _path_key(record.path): record for record in records
        if classify(record) not in {"index", "rejected"}
    }
    names = tuple(known_projects)
    receipts: list[Receipt] = []
    warnings: list[str] = []
    for record in records:
        if classify(record) != "receipt":
            continue
        raw_date = _text(record.meta.get("created_at"))
        try:
            if raw_date is None:
                raise ValueError("Missing timestamp")
            created_at = datetime.fromisoformat(raw_date)
            if created_at.utcoffset() is None:
                raise ValueError("Missing timezone")
        except ValueError:
            warnings.append(f"invalid_created_at: {record.path}")
            continue
        raw_refs = record.meta.get("refs")
        refs = tuple(ref for ref in raw_refs if isinstance(ref, str)) if isinstance(raw_refs, (list, tuple)) else ()
        ref_rids: list[str] = []
        projects: set[str] = set()
        for ref in refs:
            resolved = paths.get(_path_key(ref))
            if resolved is None:
                continue
            if resolved.rid not in ref_rids:
                ref_rids.append(resolved.rid)
            if classify(resolved) != "memory" and resolved.project:
                projects.add(resolved.project)
        summary, learned = receipt_summary(record.body)
        inferred = False
        if not projects:
            project = receipt_project(summary, names)
            if project is not None:
                projects.add(project)
                inferred = True
        receipts.append(Receipt(
            rid=record.rid, created_at=created_at, event_id=_text(record.meta.get("event_id")),
            harness=_text(record.meta.get("harness")), session=_text(record.meta.get("session")),
            refs=refs, ref_rids=tuple(ref_rids), summary=summary, learned=learned,
            projects=tuple(sorted(projects)), project_inferred=inferred,
        ))
    receipts.sort(key=lambda receipt: snapshot.records[receipt.rid].path)
    receipts.sort(key=lambda receipt: receipt.created_at, reverse=True)
    return tuple(receipts), tuple(warnings)
