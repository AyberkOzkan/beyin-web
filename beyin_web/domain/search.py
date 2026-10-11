from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Protocol

from beyin_web.vault.records import Record, classify
from beyin_web.vault.scan import VaultSnapshot


class SearchReceipt(Protocol):
    @property
    def rid(self) -> str: ...

    @property
    def created_at(self) -> datetime: ...

    @property
    def ref_rids(self) -> tuple[str, ...]: ...


_FOLD = dict(zip("İIıÇçŞşĞğÖöÜü", "iiiccssggoouu"))


def search_fold(text: str) -> str:
    folded: list[str] = []
    for char in text:
        lower = _FOLD.get(char, char.lower())
        folded.append(lower if len(lower) == 1 else char)
    return "".join(folded)


def _matches(text: str, words: tuple[str, ...]) -> list[tuple[int, int]]:
    matches: set[tuple[int, int]] = set()
    for word in words:
        start = text.find(word)
        while start >= 0:
            matches.add((start, start + len(word)))
            start = text.find(word, start + 1)
    return sorted(matches)


def _snippet(text: str, matches: list[tuple[int, int]]) -> tuple[str, list[list[int]]]:
    if not matches:
        return text[:160], []
    first_start, first_end = matches[0]
    size = max(160, first_end - first_start)
    start = max(0, first_start - (size - (first_end - first_start)) // 2)
    start = min(start, max(0, len(text) - size))
    end = min(len(text), start + size)
    highlights: list[list[int]] = []
    for left, right in matches:
        if left < start or right > end:
            continue
        left, right = left - start, right - start
        if highlights and left < highlights[-1][1]:
            highlights[-1][1] = max(highlights[-1][1], right)
        else:
            highlights.append([left, right])
    return text[start:end], highlights


def _summary(record: Record) -> dict[str, object]:
    return {"rid": record.rid, "title": record.title, "kind": record.kind,
            "project": record.project, "path": record.path,
            "mtime": record.mtime.isoformat(), "excerpt": record.excerpt}


def search(
    snapshot: VaultSnapshot, receipts: Iterable[SearchReceipt], q: str,
    kind: str | None = None, project: str | None = None, limit: int = 20,
) -> list[dict[str, object]]:
    """Search title and body; kind accepts stored kinds or classification names."""
    words = tuple(dict.fromkeys(search_fold(q).split()))
    if not words or limit <= 0:
        return []
    receipt_by_rid = {receipt.rid: receipt for receipt in receipts}
    ranked: list[tuple[tuple[bool, int, float, str], dict[str, object]]] = []
    for record in snapshot.records.values():
        category = classify(record)
        if category in {"index", "rejected"} or (kind is not None and kind not in {record.kind, category}):
            continue
        receipt = receipt_by_rid.get(record.rid) if category == "receipt" else None
        projects = getattr(receipt, "projects", None)
        if projects is None:
            projects = {
                target.project for target_rid in receipt.ref_rids
                if (target := snapshot.records.get(target_rid)) is not None
                and classify(target) not in {"index", "rejected", "receipt", "memory"}
                and target.project is not None
            } if receipt is not None else set()
        if project is not None and record.project != project and project not in projects:
            continue
        title = search_fold(record.title)
        body = search_fold(record.body)
        if not all(word in title or word in body for word in words):
            continue
        title_matches = _matches(title, words)
        body_matches = _matches(body, words)
        snippet, highlights = _snippet(
            record.body if body_matches else record.title,
            body_matches if body_matches else title_matches,
        )
        modified = receipt.created_at if receipt is not None else record.mtime
        if modified.utcoffset() is None:
            raise ValueError("Timestamps must be timezone-aware")
        rank = (not bool(title_matches), -(len(title_matches) + len(body_matches)),
                -modified.astimezone(timezone.utc).timestamp(), record.rid)
        ranked.append((rank, {**_summary(record), "snippet": snippet, "highlights": highlights}))
    return [result for _, result in sorted(ranked, key=lambda item: item[0])[:limit]]
