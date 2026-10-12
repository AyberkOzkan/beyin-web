from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from beyin_web.vault.frontmatter import parse_frontmatter
from beyin_web.vault.links import fold_name, without_code
from beyin_web.vault.scan import VaultSnapshot


HORIZONS = frozenset({"long", "year", "theme"})
MAX_TITLE = 120
MAX_LABEL = 40
MAX_STEPS = 30
_STEP = re.compile(r"^([ \t]*- +\[)([xX ])(\][ \t]+)(.*?)[ \t]*$")
_DAY = re.compile(r"^[ \t]*- +([0-9]{4}-[0-9]{2}-[0-9]{2})[ \t]*$")
_ASCII = str.maketrans("çğıöşüâîû", "cgiosuaiu")


class GoalConflict(Exception):
    """The file no longer holds what the request was made against."""


@dataclass(frozen=True)
class Step:
    index: int
    text: str
    done: bool


@dataclass(frozen=True)
class Goal:
    rid: str
    title: str
    horizon: str
    period: str | None
    area: str | None
    summary: str
    steps: tuple[Step, ...]
    done: int
    total: int


@dataclass(frozen=True)
class Habit:
    rid: str
    title: str
    days: tuple[str, ...]


def _label(value: object) -> str | None:
    if isinstance(value, int) and not isinstance(value, bool):
        value = str(value)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _lines(body: str) -> tuple[list[str], list[str]]:
    """Return the body's lines and the same lines with code hidden, index for index."""
    raw = body.splitlines(keepends=True)
    masked = without_code(body).splitlines(keepends=True)
    if len(raw) != len(masked):
        raise GoalConflict("unreadable")
    return raw, masked


def read_steps(body: str) -> tuple[Step, ...]:
    try:
        raw, masked = _lines(body.lstrip("﻿"))
    except GoalConflict:
        return ()
    steps: list[Step] = []
    for line, visible in zip(raw, masked):
        if _STEP.match(visible.rstrip("\r\n")) and (match := _STEP.match(line.rstrip("\r\n"))):
            steps.append(Step(len(steps), match[4], match[2] != " "))
    return tuple(steps)


def read_days(body: str) -> tuple[str, ...]:
    days: set[str] = set()
    for line in without_code(body).splitlines():
        match = _DAY.match(line)
        if match:
            try:
                days.add(date.fromisoformat(match[1]).isoformat())
            except ValueError:
                pass
    return tuple(sorted(days))


def build_goals(snapshot: VaultSnapshot) -> tuple[Goal, ...]:
    goals: list[Goal] = []
    for record in snapshot.records.values():
        if record.kind != "goal":
            continue
        horizon = record.meta.get("horizon")
        steps = read_steps(record.body)
        goals.append(Goal(
            rid=record.rid, title=record.title,
            horizon=horizon if isinstance(horizon, str) and horizon in HORIZONS else "long",
            period=_label(record.meta.get("period")), area=_label(record.meta.get("area")),
            # A goal that is only a checklist has no sentence of its own; its steps are shown as steps.
            summary="" if re.match(r"- +\[[xX ]\]", record.excerpt) else record.excerpt, steps=steps,
            done=sum(step.done for step in steps), total=len(steps),
        ))
    return tuple(sorted(goals, key=lambda goal: (
        goal.horizon, goal.period is None, fold_name(goal.period or ""), fold_name(goal.title),
        snapshot.records[goal.rid].path)))


def build_habits(snapshot: VaultSnapshot) -> tuple[Habit, ...]:
    habits = [Habit(record.rid, record.title, read_days(record.body))
              for record in snapshot.records.values() if record.kind == "habit"]
    return tuple(sorted(habits, key=lambda habit: (fold_name(habit.title), snapshot.records[habit.rid].path)))


def areas(goals: Sequence[Goal]) -> list[dict[str, object]]:
    names: dict[str, str] = {}
    members: dict[str, list[Goal]] = {}
    for goal in goals:
        if goal.horizon == "theme" or goal.area is None:
            continue
        # "Sağlık" and "sağlık" are one area; the first spelling met names it.
        key = fold_name(goal.area)
        names.setdefault(key, goal.area)
        members.setdefault(key, []).append(goal)
    return [{"name": names[key], "goals": len(members[key]),
             "done": sum(goal.done for goal in members[key]),
             "total": sum(goal.total for goal in members[key])} for key in sorted(members)]


def _body_offset(text: str) -> int:
    body = parse_frontmatter(text)[1]
    if not text.endswith(body):
        raise GoalConflict("unreadable")
    return len(text) - len(body)


def set_step(text: str, index: int, expected: str, done: bool) -> str:
    """Tick or untick the index-th checkbox, provided it still reads as the client saw it."""
    offset = _body_offset(text)
    raw, masked = _lines(text[offset:])
    position = -1
    for number, visible in enumerate(masked):
        if not _STEP.match(visible.rstrip("\r\n")):
            continue
        position += 1
        if position != index:
            continue
        ending = raw[number][len(raw[number].rstrip("\r\n")):]
        match = _STEP.match(raw[number].rstrip("\r\n"))
        if match is None or match[4] != expected:
            raise GoalConflict("step_changed")
        raw[number] = f"{match[1]}{'x' if done else ' '}{match[3]}{match[4]}{ending}"
        return text[:offset] + "".join(raw)
    raise GoalConflict("step_missing")


def set_day(text: str, day: date, done: bool) -> str:
    """Add or remove one "- YYYY-MM-DD" line; asking twice changes nothing."""
    offset = _body_offset(text)
    raw, masked = _lines(text[offset:])
    stamp = day.isoformat()
    marked = [number for number, visible in enumerate(masked)
              if (match := _DAY.match(visible.rstrip("\r\n"))) and match[1] == stamp]
    if done and not marked:
        newline = "\r\n" if "\r\n" in text else "\n"
        if raw and not raw[-1].endswith(("\n", "\r")):
            raw[-1] += newline
        raw.append(f"- {stamp}{newline}")
    elif not done and marked:
        raw = [line for number, line in enumerate(raw) if number not in marked]
    return text[:offset] + "".join(raw)


def clean_line(value: object, limit: int) -> str | None:
    """One trimmed line of plain text, or None when the value cannot be stored as one."""
    if not isinstance(value, str):
        return None
    text = unicodedata.normalize("NFC", value).strip()
    if not text or len(text) > limit or any(unicodedata.category(char).startswith("C") for char in text):
        return None
    return text


def slug(title: str) -> str:
    folded = unicodedata.normalize("NFKD", fold_name(title).translate(_ASCII))
    name = re.sub(r"[^a-z0-9]+", "-", folded.encode("ascii", "ignore").decode("ascii")).strip("-")
    return name[:60].rstrip("-")


def _document(meta: dict[str, object], title: str, lines: Sequence[str]) -> str:
    front = json.dumps({**meta, "visibility": "internal"}, ensure_ascii=False, indent=2)
    return f"---\n{front}\n---\n# {title}\n\n" + "".join(f"{line}\n" for line in lines)


def goal_document(title: str, horizon: str, period: str | None, area: str | None, steps: Sequence[str]) -> str:
    meta: dict[str, object] = {"kind": "goal", "horizon": horizon}
    if period:
        meta["period"] = period
    if area:
        meta["area"] = area
    return _document(meta, title, [f"- [ ] {step}" for step in steps])


def habit_document(title: str) -> str:
    return _document({"kind": "habit"}, title, [])
