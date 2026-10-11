from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import PurePosixPath

from beyin_web.domain.receipts import Receipt
from beyin_web.domain.tasks import OPEN_STATUSES, Task, natural_key
from beyin_web.vault.links import fold_name
from beyin_web.vault.records import classify
from beyin_web.vault.scan import VaultSnapshot


@dataclass(frozen=True)
class Project:
    name: str
    note_rid: str | None
    title: str
    summary: str
    task_rids: tuple[str, ...]
    knowledge_rids: tuple[str, ...]
    receipt_rids: tuple[str, ...]
    done: int
    total: int
    last_activity: datetime
    quiet: bool


def build_projects(
    snapshot: VaultSnapshot, tasks: Iterable[Task], receipts: Iterable[Receipt], now: datetime,
) -> tuple[Project, ...]:
    records = sorted(
        (record for record in snapshot.records.values() if classify(record) not in {"index", "rejected", "receipt"}),
        key=lambda record: record.path,
    )
    task_list = tuple(tasks)
    receipt_list = tuple(receipts)
    names = {record.project for record in records if record.project}
    projects: list[Project] = []
    for name in sorted(names, key=lambda name: (natural_key(name), name)):
        members = [record for record in records if record.project == name]
        notes = [record for record in members if classify(record) == "note"]
        note = next(
            (record for record in notes if fold_name(PurePosixPath(record.path).stem) == fold_name(name)),
            notes[0] if notes else None,
        )
        project_tasks = sorted(
            (task for task in task_list if task.project == name and task.rid in snapshot.records
             and classify(snapshot.records[task.rid]) == "task"),
            key=lambda task: (natural_key(task.title), task.title, snapshot.records[task.rid].path),
        )
        project_receipts = sorted(
            (receipt for receipt in receipt_list if name in receipt.projects), key=lambda receipt: receipt.rid,
        )
        project_receipts.sort(key=lambda receipt: receipt.created_at, reverse=True)
        last_activity = max(
            [record.mtime for record in members] + [receipt.created_at for receipt in project_receipts],
        )
        projects.append(Project(
            name=name, note_rid=note.rid if note else None, title=note.title if note else name,
            summary=note.excerpt if note else "", task_rids=tuple(task.rid for task in project_tasks),
            knowledge_rids=tuple(record.rid for record in members if classify(record) == "knowledge"),
            receipt_rids=tuple(receipt.rid for receipt in project_receipts),
            done=sum(task.status == "done" for task in project_tasks),
            total=sum(task.status != "cancelled" for task in project_tasks), last_activity=last_activity,
            quiet=not any(task.status in OPEN_STATUSES for task in project_tasks)
            and now - last_activity >= timedelta(days=30),
        ))
    return tuple(projects)
