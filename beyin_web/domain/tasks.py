from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from beyin_web.vault.links import fold_name, without_code
from beyin_web.vault.records import classify
from beyin_web.vault.scan import VaultSnapshot


TASK_STATUSES = frozenset({"inbox", "active", "waiting", "blocked", "done", "cancelled"})
OPEN_STATUSES = frozenset({"inbox", "active", "waiting", "blocked"})


def natural_key(title: str) -> tuple[str | int, ...]:
    return tuple(int(part) if part.isdecimal() else part for part in re.split(r"(\d+)", fold_name(title)))


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


@dataclass(frozen=True)
class Task:
    rid: str
    id: str
    title: str
    status: str
    owner: str | None
    revision: int | None
    next_action: str | None
    due_at: str | None
    review_at: str | None
    project: str | None
    checklist_done: int
    checklist_total: int


def build_tasks(snapshot: VaultSnapshot) -> tuple[Task, ...]:
    tasks: list[Task] = []
    for record in snapshot.records.values():
        if classify(record) != "task":
            continue
        meta = record.meta
        status = _text(meta.get("status"))
        revision = meta.get("revision")
        boxes = re.findall(r"^[ \t]*- +\[([xX ~])\](?:[ \t]|$)", without_code(record.body), re.MULTILINE)
        tasks.append(Task(
            rid=record.rid, id=_text(meta.get("id")) or PurePosixPath(record.path).stem,
            title=record.title, status=status if status in TASK_STATUSES else "unknown",
            owner=_text(meta.get("owner")), revision=revision if type(revision) is int else None,
            next_action=_text(meta.get("next_action")), due_at=_text(meta.get("due_at")),
            review_at=_text(meta.get("review_at")), project=record.project,
            checklist_done=sum(box.lower() == "x" for box in boxes), checklist_total=len(boxes),
        ))
    return tuple(sorted(tasks, key=lambda task: (natural_key(task.title), task.title, snapshot.records[task.rid].path)))
