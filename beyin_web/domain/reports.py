from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import date, timedelta, timezone, tzinfo

from beyin_web.domain.journal import _local_date
from beyin_web.domain.projects import Project
from beyin_web.domain.receipts import Receipt
from beyin_web.domain.tasks import OPEN_STATUSES, Task
from beyin_web.vault.links import LinkIndex
from beyin_web.vault.records import classify
from beyin_web.vault.scan import VaultSnapshot


def build_report(
    snapshot: VaultSnapshot, links: LinkIndex, tasks: Iterable[Task], receipts: Iterable[Receipt],
    projects: Iterable[Project], anchor: date, today: date, tz: tzinfo,
) -> dict[str, object]:
    dated = tuple((receipt, _local_date(receipt.created_at, tz)) for receipt in receipts)
    task_list = tuple(tasks)
    week_start = anchor - timedelta(days=anchor.weekday())
    week_end = week_start + timedelta(days=6)
    month_end = min(week_end, today)
    month_start = month_end - timedelta(days=29)

    def eligible(rid: str) -> bool:
        record = snapshot.records.get(rid)
        return record is not None and classify(record) not in {"memory", "index"}

    def selected(start: date, end: date) -> tuple[Receipt, ...]:
        return tuple(receipt for receipt, day in dated if start <= day <= end)

    def period(start: date, end: date) -> dict[str, object]:
        length = (end - start).days + 1
        counts = Counter(day for _, day in dated if start <= day <= end)
        items = selected(start, end)
        return {
            "start": start.isoformat(), "end": end.isoformat(),
            "days": {(start + timedelta(days=offset)).isoformat(): counts[start + timedelta(days=offset)]
                     for offset in range(length)},
            "receipts": len(items),
            "previous_receipts": sum(start.toordinal() - length <= day.toordinal() < start.toordinal()
                                     for _, day in dated),
            "active_days": len(counts),
            "worked_notes": len({rid for receipt in items for rid in receipt.ref_rids if eligible(rid)}),
            "learned_count": sum(bool(receipt.learned) for receipt in items),
        }

    weekly = selected(week_start, week_end)
    monthly = selected(month_start, month_end)
    learned = [{"rid": receipt.rid, "time": receipt.created_at.astimezone(tz).isoformat(),
                "day": _local_date(receipt.created_at, tz).isoformat(), "text": receipt.learned,
                "projects": receipt.projects}
               for receipt in sorted(weekly, key=lambda item: (item.created_at.astimezone(timezone.utc), item.rid))
               if receipt.learned]
    project_rows = [
        {"name": project.name, "title": project.title, "done": project.done, "total": project.total,
         "quiet": project.quiet,
         "open_tasks": sum(task.project == project.name and task.status in OPEN_STATUSES for task in task_list),
         "week_receipts": sum(project.name in receipt.projects for receipt in weekly),
         "month_receipts": sum(project.name in receipt.projects for receipt in monthly)}
        for project in projects
    ]
    project_rows.sort(key=lambda item: (-item["month_receipts"], item["name"]))
    categories = Counter(classify(record) for record in snapshot.records.values())
    groups: dict[str | None, dict[str, int]] = {}
    for record in snapshot.records.values():
        category = classify(record)
        if category not in {"note", "knowledge"}:
            continue
        group = groups.setdefault(record.project, {"notes": 0, "knowledge": 0})
        group["notes" if category == "note" else "knowledge"] += 1
    by_project = [{"project": name, **counts} for name, counts in groups.items()]
    by_project.sort(key=lambda item: (item["project"] is None,
                                      -(item["notes"] + item["knowledge"]), item["project"] or ""))
    worked = Counter(rid for receipt in monthly for rid in set(receipt.ref_rids) if eligible(rid))
    most_worked = sorted(worked, key=lambda rid: (-worked[rid], snapshot.records[rid].title,
                                                snapshot.records[rid].path))[:5]
    return {
        "today": today.isoformat(), "week": period(week_start, week_end),
        "month": period(month_start, month_end), "learned": learned, "projects": project_rows,
        "knowledge": {
            "counts": {"notes": categories["note"], "knowledge": categories["knowledge"],
                       "tasks": categories["task"], "receipts": len(dated),
                       "links": sum(len(targets) for targets in links.outgoing.values())},
            "by_project": by_project,
            "most_worked": [{"rid": rid, "receipts": worked[rid]} for rid in most_worked],
        },
    }
