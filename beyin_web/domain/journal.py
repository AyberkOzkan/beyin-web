from __future__ import annotations

import calendar
from collections import Counter
from collections.abc import Iterable
from datetime import date as Date, datetime, timedelta, timezone, tzinfo
from typing import Protocol, TypeVar

from beyin_web.vault.records import classify
from beyin_web.vault.scan import VaultSnapshot


class DatedReceipt(Protocol):
    @property
    def rid(self) -> str: ...

    @property
    def created_at(self) -> datetime: ...


class DatedCard(Protocol):
    @property
    def date(self) -> Date | str: ...


ReceiptT = TypeVar("ReceiptT", bound=DatedReceipt)
CardT = TypeVar("CardT", bound=DatedCard)


def _local_date(value: datetime, tz: tzinfo) -> Date:
    if value.utcoffset() is None:
        raise ValueError("Timestamps must be timezone-aware")
    return value.astimezone(tz).date()


def day(
    date: Date, receipts: Iterable[ReceiptT], cards: Iterable[CardT],
    snapshot: VaultSnapshot, tz: tzinfo,
) -> dict[str, object]:
    """Return the day's receipts, cards and changed records without copying models."""
    daily_receipts = sorted(
        (receipt for receipt in receipts if _local_date(receipt.created_at, tz) == date),
        key=lambda receipt: (receipt.created_at.astimezone(timezone.utc), receipt.rid),
    )
    daily_cards = [
        card for card in cards
        if (Date.fromisoformat(card.date) if isinstance(card.date, str) else card.date) == date
    ]
    changed = sorted(
        (record for record in snapshot.records.values()
         if classify(record) not in {"receipt", "index", "rejected", "memory"}
         and _local_date(record.mtime, tz) == date),
        key=lambda record: (record.mtime.astimezone(timezone.utc), record.rid),
    )
    return {"date": date.isoformat(), "receipts": daily_receipts,
            "cards": daily_cards, "changed": changed}


def month(
    year: int, month: int, receipts: Iterable[DatedReceipt], tz: tzinfo,
) -> dict[str, int]:
    """Map every ISO date in the month to its receipt count, including zeros."""
    counts = Counter(_local_date(receipt.created_at, tz) for receipt in receipts)
    return {Date(year, month, number).isoformat(): counts[Date(year, month, number)]
            for number in range(1, calendar.monthrange(year, month)[1] + 1)}


def heatmap(
    weeks: int, today: Date, receipts: Iterable[DatedReceipt], tz: tzinfo,
) -> dict[str, int]:
    """Return Monday–Sunday weeks ending in today's week; future cells stay zero."""
    if weeks < 0:
        raise ValueError("weeks must be nonnegative")
    if weeks == 0:
        return {}
    start = today - timedelta(days=today.weekday() + 7 * (weeks - 1))
    counts = Counter(_local_date(receipt.created_at, tz) for receipt in receipts)
    result: dict[str, int] = {}
    for offset in range(weeks * 7):
        current = start + timedelta(days=offset)
        result[current.isoformat()] = counts[current] if current <= today else 0
    return result
