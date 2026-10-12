from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields, is_dataclass, replace
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from pathlib import PurePosixPath
from threading import RLock
from typing import TYPE_CHECKING, cast
from urllib.parse import parse_qs, urlsplit

from beyin_web.domain import graph, journal
from beyin_web.domain.obsidian import obsidian_uri, obsidian_vault_uri
from beyin_web.domain.projects import Project, build_projects
from beyin_web.domain.receipts import Receipt, build_receipts
from beyin_web.domain.reports import build_report
from beyin_web.domain.search import search
from beyin_web.domain.tasks import OPEN_STATUSES, TASK_STATUSES, Task, build_tasks
from beyin_web.runtime.beyin_cli import RuntimeUnavailable, health_summary
from beyin_web.vault.companion import Companion, SessionCard, load_companion
from beyin_web.vault.links import LinkIndex, build_links, without_code
from beyin_web.vault.records import Record, classify
from beyin_web.vault.scan import VaultSnapshot

if TYPE_CHECKING:
    from beyin_web.http.server import BeyinHTTPServer, RequestHandler


def record_summary(record: Record) -> dict[str, object]:
    return {"rid": record.rid, "title": record.title, "kind": record.kind,
            "project": record.project, "path": record.path,
            "mtime": record.mtime.isoformat(), "excerpt": record.excerpt}


def _json(value: object) -> object:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _json(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(item) for item in value]
    return value


def _fields(value: object) -> dict[str, object]:
    return cast(dict[str, object], _json(value))


def _period(now: datetime) -> str:
    return "morning" if 5 <= now.hour < 12 else "day" if 12 <= now.hour < 18 else "evening"


def _path_key(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\\", "/"))


def _targets(body: str) -> tuple[str, ...]:
    return tuple(sorted({unicodedata.normalize("NFC", match[1].split("|", 1)[0].split("#", 1)[0].strip())
                         for match in re.finditer(r"!?\[\[([^\[\]\r\n]+)\]\]", without_code(body))
                         if match[1].split("|", 1)[0].split("#", 1)[0].strip()}))


def _warnings(warnings: tuple[str, ...]) -> list[dict[str, object]]:
    result = []
    for warning in sorted(set(warnings)):
        code, separator, path = warning.partition(": ")
        result.append({"code": code, "path": path if separator else None})
    return result


class APIError(Exception):
    def __init__(self, status: int, code: str, parameter: str | None = None) -> None:
        self.status = status
        self.code = code
        self.message = f"invalid_parameter: {parameter}" if parameter else code


@dataclass(frozen=True)
class Models:
    links: LinkIndex
    companion: Companion
    tasks: tuple[Task, ...]
    receipts: tuple[Receipt, ...]
    warnings: tuple[str, ...]
    targets: Mapping[str, str]


class API:
    def __init__(
        self, server: BeyinHTTPServer, *, clock: Callable[[], datetime] | None = None,
        tz: tzinfo | None = None,
    ) -> None:
        self.server = server
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.tz = tz
        self._lock = RLock()
        self._generation: int | None = None
        self._models: Models | None = None
        self._responses: dict[tuple[object, ...], dict[str, object]] = {}
        self._project_cache: dict[date, tuple[Project, ...]] = {}

    def _derive(self, snapshot: VaultSnapshot) -> Models:
        if self._models is None:
            tasks = build_tasks(snapshot)
            names = {record.project for record in snapshot.records.values()
                     if record.project and classify(record) not in {"index", "rejected", "receipt"}}
            receipts, warnings = build_receipts(snapshot, names)
            companion = load_companion(snapshot)
            targets = sorted({target for record in snapshot.records.values() for target in _targets(record.body)})
            # Let the vault resolver handle names, collisions and self-links too.
            probes = {f"api-target-{index}": Record(
                f"api-target-{index}", f".api-targets/[{index}].md", "note", "", None,
                "internal", snapshot.scanned_at, {}, f"[[{target}]]", "", None,
            ) for index, target in enumerate(targets)}
            resolved = build_links(replace(snapshot, records={**snapshot.records, **probes}))
            target_rids = {target: resolved.outgoing[f"api-target-{index}"][0]
                           for index, target in enumerate(targets)
                           if resolved.outgoing[f"api-target-{index}"]}
            self._models = Models(build_links(snapshot), companion, tasks, receipts,
                                  warnings + companion.warnings, target_rids)
        return self._models

    def handle(self, request: RequestHandler, match: re.Match[str]) -> None:
        snapshot = self.server.source.snapshot()
        now = self.clock()
        now = now.astimezone(self.tz) if self.tz is not None else now.astimezone()
        path = match["endpoint"]
        try:
            query = parse_qs(urlsplit(request.path).query, keep_blank_values=True,
                             encoding="utf-8", errors="strict")
            with self._lock:
                if snapshot.generation != self._generation:
                    self._generation = snapshot.generation
                    self._models = None
                    self._responses.clear()
                    self._project_cache.clear()
                data, etag = self._response(path, query, snapshot, now)
            payload = cast(dict[str, object], _json({"generation": snapshot.generation, **data}))
            request.send_json(payload, etag=etag)
        except (ValueError, UnicodeError):
            request.send_json({"generation": snapshot.generation,
                               "error": {"code": "bad_request", "message": "invalid_parameter: query"}}, 400)
        except APIError as error:
            request.send_json({"generation": snapshot.generation,
                               "error": {"code": error.code, "message": error.message}}, error.status)

    def _response(
        self, path: str, query: dict[str, list[str]], snapshot: VaultSnapshot, now: datetime,
    ) -> tuple[dict[str, object], str | None]:
        allowed = {
            "tasks": {"project", "status"}, "search": {"q", "mode", "kind", "project", "limit"},
            "graph": {"kinds", "project", "receipts", "unresolved", "connected_only", "focus", "depth"},
            "journal/heatmap": {"weeks"},
            "reports": {"week"},
        }.get(path, set())
        for name, values in query.items():
            if name not in allowed or len(values) != 1:
                raise APIError(400, "bad_request", name)
        params = {key: values[0] for key, values in query.items()}
        if path in {"pulse", "health"}:
            available = self.server.runtime.available
            health = health_summary(self.server.runtime.doctor() if available else None)
            directory = health.get("companion_dir")
            if isinstance(directory, str):
                directory = _path_key(directory)
                root = _path_key(str(snapshot.root)).rstrip("/")
                if directory.startswith(root + "/"):
                    directory = directory[len(root) + 1:]
                if directory == root or PurePosixPath(directory).is_absolute() or re.match(r"^[A-Za-z]:", directory) or ".." in PurePosixPath(directory).parts:
                    directory = None
                health["companion_dir"] = directory
            if path == "pulse":
                data = {"scanned_at": snapshot.scanned_at.isoformat(), "records": len(snapshot.records),
                        "vault_name": snapshot.root.name, "drawings": dict(self.server.drawings),
                        "obsidian_uri": obsidian_vault_uri(str(self.server.settings.vault)),
                        "hidden_private": snapshot.hidden_private,
                        "beyin": {"available": available, "version": health["installed_version"],
                                  "up_to_date": health["up_to_date"]}}
            else:
                models = self._derive(snapshot)
                data = {"health_summary": health, "warnings": _warnings(snapshot.warnings + models.warnings),
                        "hidden_private": snapshot.hidden_private, "records": len(snapshot.records),
                        "counts": dict(sorted(Counter(classify(record) for record in snapshot.records.values()).items())),
                        "beyin_available": available}
            digest = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:20]
            return data, f'"{snapshot.generation}-{digest}"'
        dynamic = (now.date().isoformat(), _period(now)) if path in {"home", "journal/heatmap"} else (
            (now.date().isoformat(),) if path in {"projects", "reports"} or path.startswith("projects/") else ())
        key = (path, tuple(sorted(params.items())), *dynamic)
        beyin_search = path == "search" and params.get("mode") == "beyin"
        if beyin_search or key not in self._responses:
            data = self._build(path, params, snapshot, self._derive(snapshot), now)
            if not beyin_search:
                # Search queries are unbounded; do not let one long session grow the cache forever.
                if len(self._responses) >= 256:
                    self._responses.clear()
                self._responses[key] = data
        else:
            data = self._responses[key]
        etag = '"' + "-".join((str(snapshot.generation), *dynamic)) + '"'
        return data, None if beyin_search else etag

    @staticmethod
    def _integer(params: Mapping[str, str], name: str, default: int, maximum: int, minimum: int = 1) -> int:
        raw = params.get(name, str(default))
        if not re.fullmatch(r"[0-9]+", raw) or len(raw) > 8:
            raise APIError(400, "bad_request", name)
        value = int(raw)
        if not minimum <= value <= maximum:
            raise APIError(400, "bad_request", name)
        return value

    @staticmethod
    def _record(snapshot: VaultSnapshot, rid: str) -> Record:
        if rid not in snapshot.records:
            raise APIError(404, "not_found")
        return snapshot.records[rid]

    @staticmethod
    def _task(task: Task, snapshot: VaultSnapshot) -> dict[str, object]:
        return {**_fields(task), "record": record_summary(snapshot.records[task.rid])}

    @staticmethod
    def _receipt(receipt: Receipt, snapshot: VaultSnapshot, tz: tzinfo) -> dict[str, object]:
        return {"rid": receipt.rid, "time": receipt.created_at.astimezone(tz).isoformat(),
                "event_id": receipt.event_id, "harness": receipt.harness, "session": receipt.session,
                "summary": receipt.summary, "learned": receipt.learned, "projects": receipt.projects,
                "project_inferred": receipt.project_inferred,
                "refs": [record_summary(snapshot.records[rid]) for rid in receipt.ref_rids]}

    @staticmethod
    def _card(card: SessionCard, tz: tzinfo) -> dict[str, object]:
        timestamp = None
        if card.time:
            try:
                timestamp = datetime.fromisoformat(f"{card.date}T{card.time}").replace(tzinfo=tz).isoformat()
            except ValueError:
                pass
        return {**_fields(card), "time": timestamp}

    def _projects(self, snapshot: VaultSnapshot, models: Models, now: datetime) -> tuple[Project, ...]:
        today = now.date()
        if today not in self._project_cache:
            self._project_cache[today] = build_projects(
                snapshot, models.tasks, models.receipts, datetime.combine(today, time(), now.tzinfo))
        return self._project_cache[today]

    def _build(
        self, path: str, params: dict[str, str], snapshot: VaultSnapshot, models: Models, now: datetime,
    ) -> dict[str, object]:
        tz = now.tzinfo
        assert tz is not None
        if path == "reports":
            raw = params.get("week", now.date().isoformat())
            try:
                if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw):
                    raise ValueError
                anchor = date.fromisoformat(raw)
                start = anchor - timedelta(days=anchor.weekday())
                if start > now.date() - timedelta(days=now.weekday()):
                    raise ValueError
                end = start + timedelta(days=6)
                min(end, now.date()) - timedelta(days=29)
            except (ValueError, OverflowError):
                raise APIError(400, "bad_request", "week") from None
            result = build_report(snapshot, models.links, models.tasks, models.receipts,
                                  self._projects(snapshot, models, now), anchor, now.date(), tz)
            knowledge = cast(dict[str, object], result["knowledge"])
            worked = cast(list[dict[str, object]], knowledge["most_worked"])
            knowledge["most_worked"] = [
                {"record": record_summary(snapshot.records[cast(str, item["rid"])]), "receipts": item["receipts"]}
                for item in worked
            ]
            return result
        if path == "projects":
            return {"projects": self._projects(snapshot, models, now)}
        if path.startswith("projects/"):
            project = next((item for item in self._projects(snapshot, models, now)
                            if item.name == path[len("projects/"):]), None)
            if project is None:
                raise APIError(404, "not_found")
            note = snapshot.records.get(project.note_rid) if project.note_rid else None
            return {"project": project, "note": {**record_summary(note), "body": note.body} if note else None,
                    "tasks": [self._task(task, snapshot) for task in models.tasks if task.rid in project.task_rids],
                    "knowledge": [record_summary(snapshot.records[rid]) for rid in project.knowledge_rids],
                    "receipts": [self._receipt(receipt, snapshot, tz) for rid in project.receipt_rids[:5]
                                 for receipt in models.receipts if receipt.rid == rid]}
        if path == "tasks":
            status = params.get("status") or None
            if status is not None and status not in TASK_STATUSES | {"unknown"}:
                raise APIError(400, "bad_request", "status")
            return {"tasks": [self._task(task, snapshot) for task in models.tasks
                              if (not params.get("project") or task.project == params["project"])
                              and (status is None or task.status == status)]}
        if path == "knowledge":
            summaries: dict[str, str] = {}
            for record in sorted(snapshot.records.values(), key=lambda item: item.path):
                if classify(record) == "index" or PurePosixPath(record.path).name == "index.md":
                    for match in re.finditer(r"^[ \t]*- +\[\[([^\]]+)\]\]:[ \t]*(.+)$",
                                             without_code(record.body), re.MULTILINE):
                        target = _targets(f"[[{match[1]}]]")
                        if target and target[0] in models.targets:
                            summaries.setdefault(models.targets[target[0]], match[2].strip())
            groups: dict[str | None, list[dict[str, object]]] = {}
            for record in sorted(snapshot.records.values(), key=lambda item: (item.title, item.path)):
                if classify(record) == "knowledge":
                    groups.setdefault(record.project, []).append({**record_summary(record),
                                                                  "summary": summaries.get(record.rid, record.excerpt)})
            return {"groups": [{"project": project, "records": groups[project]}
                               for project in sorted(groups, key=lambda item: (item is not None, item or ""))]}
        if path.startswith("records/"):
            record = self._record(snapshot, path[len("records/"):])
            return {**record_summary(record), "meta": record.meta, "body": record.body,
                    "obsidian_uri": obsidian_uri(str(self.server.settings.vault), record.path),
                    "links_out": [record_summary(snapshot.records[rid]) for rid in models.links.outgoing.get(record.rid, ())],
                    "links_in": [record_summary(snapshot.records[rid]) for rid in models.links.incoming.get(record.rid, ())],
                    "unresolved": models.links.unresolved.get(record.rid, ()),
                    "receipts": [self._receipt(receipt, snapshot, tz) for receipt in models.receipts if record.rid in receipt.ref_rids],
                    "wikilinks": {target: models.targets[target] for target in _targets(record.body) if target in models.targets}}
        if path.startswith("journal/months/"):
            raw = path[len("journal/months/"):]
            try:
                if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", raw):
                    raise ValueError
                selected = date.fromisoformat(raw + "-01")
            except ValueError:
                raise APIError(400, "bad_request", "month") from None
            return {"month": raw, "days": journal.month(selected.year, selected.month, models.receipts, tz)}
        if path.startswith("journal/days/"):
            raw = path[len("journal/days/"):]
            try:
                if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw):
                    raise ValueError
                selected = date.fromisoformat(raw)
            except ValueError:
                raise APIError(400, "bad_request", "day") from None
            result = journal.day(selected, models.receipts, models.companion.cards, snapshot, tz)
            return {**result, "receipts": [self._receipt(receipt, snapshot, tz) for receipt in result["receipts"]],
                    "cards": [self._card(card, tz) for card in result["cards"]],
                    "changed": [record_summary(record) for record in result["changed"]]}
        if path == "journal/heatmap":
            weeks = self._integer(params, "weeks", 20, 520, 0)
            # The client must not guess the date from its own clock or zone.
            return {"today": now.date().isoformat(), "days": journal.heatmap(weeks, now.date(), models.receipts, tz)}
        if path == "graph":
            flags = {}
            for name, default in (("receipts", "0"), ("unresolved", "0"), ("connected_only", "1")):
                if params.get(name, default) not in {"0", "1"}:
                    raise APIError(400, "bad_request", name)
                flags[name] = params.get(name, default) == "1"
            kinds = params.get("kinds")
            self._validate_kinds(kinds.split(",") if kinds else (), snapshot, "kinds")
            depth = self._integer(params, "depth", 1, 10, 0)
            if "depth" in params and not params.get("focus"):
                raise APIError(400, "bad_request", "depth")
            result = graph.build_graph(snapshot, models.links, models.receipts,
                                       kinds=kinds.split(",") if kinds else None, project=params.get("project") or None,
                                       include_receipts=flags["receipts"], include_unresolved=flags["unresolved"],
                                       connected_only=flags["connected_only"] if not params.get("focus") else False)
            if params.get("focus"):
                self._record(snapshot, params["focus"])
                neighbors = graph.neighborhood(params["focus"], models.links, depth)
                result = {"nodes": [node for node in result["nodes"] if node["id"] in neighbors],
                          "edges": [edge for edge in result["edges"] if edge["source"] in neighbors and edge["target"] in neighbors]}
            return result
        if path == "search":
            limit = self._integer(params, "limit", 20, 50)
            mode = params.get("mode", "local")
            if mode not in {"local", "beyin"}:
                raise APIError(400, "bad_request", "mode")
            kind = params.get("kind") or None
            self._validate_kinds([kind] if kind else [], snapshot, "kind")
            if mode == "local":
                results = search(snapshot, models.receipts, params.get("q", ""), kind=kind,
                                 project=params.get("project") or None, limit=limit)
                return {"results": [{**record_summary(snapshot.records[result["rid"]]),
                                     "snippet": result["snippet"], "highlights": result["highlights"]} for result in results]}
            try:
                context = self.server.runtime.context(params.get("q", ""), project=params.get("project") or None, limit=limit)
            except RuntimeUnavailable as error:
                raise APIError(504 if error.code == "timeout" else 503,
                               "timeout" if error.code == "timeout" else "runtime_unavailable") from None
            by_path = {_path_key(record.path): record for record in snapshot.records.values()}
            results = []
            raw_records = context.get("records", [])
            if not isinstance(raw_records, list):
                raise APIError(503, "runtime_unavailable")
            omitted = context.get("omitted_count", 0)
            omitted = omitted if type(omitted) is int and omitted >= 0 else 0
            for item in raw_records:
                source = item.get("source") if isinstance(item, Mapping) else None
                record = by_path.get(_path_key(source)) if isinstance(source, str) else None
                if record is None:
                    omitted += 1
                elif kind is None or kind in {record.kind, classify(record)}:
                    text = item.get("text", "")
                    if not isinstance(text, str):
                        raise APIError(503, "runtime_unavailable")
                    results.append({**record_summary(record), "text": text})
            return {"results": results[:limit], "abstained": context.get("abstained", False),
                    "stale_count": context.get("stale_count", 0), "omitted": omitted}
        if path == "memory":
            companion = models.companion
            identities = [snapshot.records[rid] for rid in (companion.core_rid, companion.soul_rid) if rid]
            return {"identity": {"structured": False, "raw": "\n\n".join(record.body for record in identities),
                                 "records": [{**record_summary(record), "body": record.body} for record in identities]},
                    "rules": {"structured": companion.rules.structured, "raw": companion.rules.raw, "items": companion.rules.rules},
                    "last_session": {"structured": companion.cards.structured, "raw": companion.cards.raw,
                                     "card": self._card(companion.cards[0], tz) if companion.cards else None},
                    "threads": {"structured": companion.threads.structured, "raw": companion.threads.raw,
                                "active": companion.threads.active, "closed": companion.threads.closed}}
        if path == "home":
            return self._home(snapshot, models, now)
        raise APIError(404, "not_found")

    @staticmethod
    def _validate_kinds(kinds: list[str] | tuple[str, ...], snapshot: VaultSnapshot, parameter: str) -> None:
        valid = {"note", "knowledge", "fact", "task", "receipt", "memory", "index", "rejected", "untrusted", "inference", "preference"}
        valid.update(record.kind for record in snapshot.records.values())
        if any(kind not in valid for kind in kinds):
            raise APIError(400, "bad_request", parameter)

    def _home(self, snapshot: VaultSnapshot, models: Models, now: datetime) -> dict[str, object]:
        tz = now.tzinfo
        assert tz is not None
        start = now.date() - timedelta(days=6)
        records = [record for record in snapshot.records.values() if classify(record) not in {"index", "rejected", "memory", "receipt"}]
        categories = {name: [record for record in records if classify(record) == kind]
                      for name, kind in (("notes", "note"), ("knowledge", "knowledge"))}
        categories["open_tasks"] = [snapshot.records[task.rid] for task in models.tasks if task.status in OPEN_STATUSES]
        counts = {name: {"total": len(items), "last_7_days": sum(start <= record.mtime.astimezone(tz).date() <= now.date() for record in items)}
                  for name, items in categories.items()}
        counts["receipts"] = {"total": len(models.receipts), "last_7_days": sum(start <= receipt.created_at.astimezone(tz).date() <= now.date() for receipt in models.receipts)}
        projects = sorted(self._projects(snapshot, models, now), key=lambda project: (-project.last_activity.timestamp(), project.name))
        upcoming = []
        for record in records:
            for field in ("due_at", "review_at"):
                value = record.meta.get(field)
                if isinstance(value, str):
                    try:
                        due = datetime.fromisoformat(value) if "T" in value else date.fromisoformat(value)
                        due_date = due.astimezone(tz).date() if isinstance(due, datetime) else due
                        if isinstance(due, datetime) and due.utcoffset() is None:
                            continue
                    except ValueError:
                        continue
                    if due_date >= now.date():
                        upcoming.append({"record": record_summary(record), "field": field, "date": due_date.isoformat(), "value": due.isoformat()})
        upcoming.sort(key=lambda item: (item["date"], item["record"]["rid"], item["field"]))
        week = journal.heatmap(1, now.date(), models.receipts, tz)
        week_start = now.date() - timedelta(days=now.weekday())
        return {"greeting": {"period": _period(now), "display_name": self.server.settings.display_name},
                "last_session": self._card(models.companion.cards[0], tz) if models.companion.cards else None,
                "counts": counts, "threads": models.companion.threads.active,
                "projects": [{**_fields(project), "note_count": sum(record.project == project.name for record in records if classify(record) == "note")} for project in projects],
                "tasks": [self._task(task, snapshot) for task in models.tasks if task.status in {"active", "waiting", "blocked"}],
                "recent": [record_summary(record) for record in sorted(records, key=lambda record: (-record.mtime.timestamp(), record.path))[:5]],
                "week": {"days": week, "receipts": sum(week.values()), "changed": sum(week_start <= record.mtime.astimezone(tz).date() <= now.date() for record in records)},
                "upcoming": upcoming}


def register_api(
    server: BeyinHTTPServer, *, clock: Callable[[], datetime] | None = None, tz: tzinfo | None = None,
) -> API:
    api = API(server, clock=clock, tz=tz)
    pattern = r"/api/v1/(?P<endpoint>pulse|home|projects(?:/[^/]+)?|tasks|knowledge|records/[^/]+|journal/(?:months/[^/]+|days/[^/]+|heatmap)|graph|search|memory|reports|health)"
    server.routes = [(route, handler) for route, handler in server.routes if route.pattern != pattern]
    server.register(pattern, api.handle)
    server.api = api
    return api
