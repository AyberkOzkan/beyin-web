from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from beyin_web.vault.scan import VaultSnapshot


LabelledItems = tuple[tuple[str, str], ...]

_HEADING = re.compile(r"^(#{2,3})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$")
_ITEM = re.compile(r"^[ \t]*-[ \t]+\*\*(.+?):\*\*[ \t]*(.*)$")
_DATE = r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
_STATUS_DATE = re.compile(r"\([^)]*?(" + _DATE + r")[^)]*\)")
_CARD_DATE = re.compile(r"^(" + _DATE + r")(?:[ \t]+([0-9]{2}:[0-9]{2}))?$")
_SESSION = re.compile(r"^[0-9a-z-]{6,}$")
_BULLET = re.compile(r"^[ \t]*-[ \t]+(.*)$")
_RULE = re.compile(r"^\*\*(" + _DATE + r") · (.+?):\*\*[ \t]*(.*)$", re.DOTALL)
_SCOPE = re.compile(r"[ \t]*\(kapsam:[ \t]*(.*?)\)[ \t]*$", re.IGNORECASE)
_REASON = re.compile(r"\*\*(?:neden|gerekçe|why):\*\*", re.IGNORECASE)
_SOURCE = re.compile(r"(?<!\S)(?:Kaynak|Source):[ \t]*", re.IGNORECASE)


@dataclass(frozen=True)
class Thread:
    title: str = ""
    owner: str = ""
    status: str = ""
    status_date: str = ""
    open: str = ""
    next_step: str = ""
    extra: LabelledItems = ()
    raw: str = ""


@dataclass(frozen=True)
class ThreadsDoc:
    active: tuple[Thread, ...] = ()
    closed: tuple[Thread, ...] = ()
    raw: str = ""
    structured: bool = False


@dataclass(frozen=True)
class SessionCard:
    date: str
    time: str
    label: str
    session: str
    items: LabelledItems
    next_step: str
    raw: str


class SessionCards(list[SessionCard]):
    """Keep the list contract while retaining a whole-file Markdown fallback."""

    raw: str
    structured: bool

    def __init__(self, cards: Iterable[SessionCard] = (), raw: str = "") -> None:
        super().__init__(cards)
        self.raw = raw
        self.structured = bool(self)


@dataclass(frozen=True)
class Rule:
    date: str = ""
    title: str = ""
    scope: str = ""
    text: str = ""
    reason: str = ""
    source: str = ""
    raw: str = ""


@dataclass(frozen=True)
class RulesDoc:
    rules: tuple[Rule, ...] = ()
    raw: str = ""
    structured: bool = False


@dataclass(frozen=True)
class Companion:
    threads: ThreadsDoc
    cards: SessionCards
    rules: RulesDoc
    core_rid: str | None
    soul_rid: str | None
    journal_rid: str | None
    warnings: tuple[str, ...]


def _key(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold().replace("\u0307", "").replace("ı", "i").strip()


def _lines(text: str) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    offset = 0
    fence = ""
    fence_length = 0
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        if offset == 0:
            line = line.lstrip("\ufeff")
        marker = re.match(r"^[ \t]*(`{3,}|~{3,})(.*)$", line)
        visible = line
        if fence:
            visible = ""
            if marker and marker[1][0] == fence and len(marker[1]) >= fence_length and not marker[2].strip():
                fence = ""
        elif marker:
            fence, fence_length = marker[1][0], len(marker[1])
            visible = ""
        result.append((offset, visible))
        offset += len(raw_line)
    return result


def _items(text: str) -> LabelledItems:
    return tuple((match[1].strip(), match[2].strip()) for _, line in _lines(text)
                 if (match := _ITEM.match(line)))


def _thread(title: str, raw: str) -> Thread:
    fields: dict[str, str] = {}
    extra: list[tuple[str, str]] = []
    items = _items(raw)
    status_names = {"durum", "son durum", "status"}
    last_status = next((index for index in reversed(range(len(items)))
                        if _key(items[index][0]).split("(", 1)[0].strip() in status_names), -1)
    aliases = {"sahip": "owner", "owner": "owner", "durum": "status",
               "son durum": "status", "status": "status", "açik": "open",
               "open": "open", "sonraki adim": "next_step", "next step": "next_step"}
    for index, (label, value) in enumerate(items):
        key = _key(label)
        status_label = key.split("(", 1)[0].strip()
        field = aliases.get(status_label if status_label in status_names else key)
        if field is None or (field == "status" and index != last_status):
            extra.append((label, value))
        else:
            if field == "status":
                date = _STATUS_DATE.search(label)
                fields["status_date"] = date[1] if date else ""
            fields[field] = value
    return Thread(title=title, raw=raw, extra=tuple(extra), **fields)


def parse_threads(text: str) -> ThreadsDoc:
    headings = [(offset, match[1], match[2]) for offset, line in _lines(text)
                if (match := _HEADING.match(line))]
    has_sections = any(level == "##" for _, level, _ in headings)
    active: list[Thread] = []
    closed: list[Thread] = []
    section = "" if has_sections else "active"
    active_names = {"active threads", "aktif konular", "açik konular"}
    closed_names = {"closed threads", "kapanan", "kapali konular"}
    for index, (start, level, title) in enumerate(headings):
        if level == "##":
            key = _key(title)
            section = "active" if key in active_names else "closed" if key in closed_names else ""
        elif section:
            end = headings[index + 1][0] if index + 1 < len(headings) else len(text)
            thread = _thread(title.strip(), text[start:end])
            (active if section == "active" else closed).append(thread)
    return ThreadsDoc(tuple(active), tuple(closed), text, bool(active or closed))


def parse_last_session(text: str) -> SessionCards:
    headings = [(offset, match[2]) for offset, line in _lines(text)
                if (match := _HEADING.match(line)) and match[1] == "##"]
    cards: list[SessionCard] = []
    for index, (start, title) in enumerate(headings):
        if _key(title) in ("önceki oturumlar", "previous"):
            break
        parts = title.split(" · ")
        date = _CARD_DATE.fullmatch(parts[0])
        if date is None or len(parts) < 2:
            continue
        session = parts.pop() if len(parts) > 2 and _SESSION.fullmatch(parts[-1]) else ""
        label = " · ".join(parts[1:]).strip()
        if not label:
            continue
        end = headings[index + 1][0] if index + 1 < len(headings) else len(text)
        raw = text[start:end]
        items = _items(raw)
        next_step = next((value for key, value in reversed(items) if _key(key) == "sonraki adim"), "")
        cards.append(SessionCard(date[1], date[2] or "", label, session, items, next_step, raw))
    return SessionCards(cards, text)


def _rule(content: str, raw: str) -> Rule:
    match = _RULE.fullmatch(content.strip())
    if match is None:
        return Rule(text=content.strip(), raw=raw)
    title, body = match[2].strip(), match[3].strip()
    scope_match = _SCOPE.search(title)
    scope = scope_match[1].strip() if scope_match else ""
    if scope_match:
        title = title[:scope_match.start()].strip()
    if not title:
        return Rule(text=content.strip(), raw=raw)
    sources = list(_SOURCE.finditer(body))
    source = ""
    if sources:
        source_match = sources[-1]
        source = body[source_match.end():].strip()
        body = body[:source_match.start()].strip()
    reason_match = _REASON.search(body)
    reason = ""
    if reason_match:
        reason = body[reason_match.end():].strip()
        body = body[:reason_match.start()].strip()
    return Rule(match[1], title, scope, body, reason, source, raw)


def parse_rules(text: str) -> RulesDoc:
    boundaries = [(offset, line) for offset, line in _lines(text)
                  if _BULLET.match(line) or re.match(r"^#{1,6}(?:[ \t]|$)", line)]
    rules: list[Rule] = []
    structured = False
    for index, (start, line) in enumerate(boundaries):
        bullet = _BULLET.match(line)
        if bullet is None:
            continue
        end = boundaries[index + 1][0] if index + 1 < len(boundaries) else len(text)
        raw = text[start:end]
        # Slice the original block to retain multiline content and line endings.
        prefix_length = bullet.start(1)
        bom_length = 1 if start == 0 and text.startswith("\ufeff") else 0
        rule = _rule(raw[prefix_length + bom_length:], raw)
        structured = structured or bool(rule.date)
        rules.append(rule)
    return RulesDoc(tuple(rules), text, structured)


def load_companion(snapshot: VaultSnapshot) -> Companion:
    records = {record.role: record for record in snapshot.records.values() if record.role}
    threads_record = records.get("threads")
    cards_record = records.get("last_session")
    rules_record = records.get("rules")
    threads = parse_threads(threads_record.body) if threads_record else ThreadsDoc()
    cards = parse_last_session(cards_record.body) if cards_record else SessionCards()
    rules = parse_rules(rules_record.body) if rules_record else RulesDoc()
    warnings = tuple(f"{code}: {record.path}" for record, document, code in (
        (threads_record, threads, "threads_unstructured"),
        (cards_record, cards, "last_session_unstructured"),
        (rules_record, rules, "rules_unstructured"),
    ) if record is not None and not document.structured)
    return Companion(threads, cards, rules,
                     records["core"].rid if "core" in records else None,
                     records["soul"].rid if "soul" in records else None,
                     records["journal"].rid if "journal" in records else None, warnings)
