"""Five-field cron matching against actual instants in an IANA time zone."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


class CronSyntaxError(ValueError):
    """An expression is outside the supported five-field cron syntax."""


_MONTHS = {name: index for index, name in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1
)}
_DAYS = {name: index for index, name in enumerate(
    ("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT")
)}


@dataclass(frozen=True)
class Field:
    allowed: frozenset[int]
    wildcard: bool


def _number(token: str, minimum: int, maximum: int, names: dict[str, int], label: str) -> int:
    if token.upper() in names:
        return names[token.upper()]
    if not token.isascii() or not token.isdecimal():
        raise CronSyntaxError(f"invalid {label} field")
    number = int(token)
    if not minimum <= number <= maximum:
        raise CronSyntaxError(f"invalid {label} field")
    return number


def _field(text: str, minimum: int, maximum: int, label: str, names: dict[str, int] | None = None) -> Field:
    names = names or {}
    allowed: set[int] = set()
    for part in text.split(","):
        if not part or part.count("/") > 1:
            raise CronSyntaxError(f"invalid {label} field")
        base, slash, step_text = part.partition("/")
        if slash:
            if not step_text.isascii() or not step_text.isdecimal():
                raise CronSyntaxError(f"invalid {label} field")
            step = int(step_text)
            if not 1 <= step <= maximum - minimum + 1:
                raise CronSyntaxError(f"invalid {label} field")
        else:
            step = 1
        if base == "*":
            first, last = minimum, maximum
        elif "-" in base:
            if base.count("-") != 1:
                raise CronSyntaxError(f"invalid {label} field")
            start, end = base.split("-")
            first = _number(start, minimum, maximum, names, label)
            last = _number(end, minimum, maximum, names, label)
            if first > last:
                raise CronSyntaxError(f"invalid {label} field")
        else:
            first = _number(base, minimum, maximum, names, label)
            last = maximum if slash else first
        allowed.update(range(first, last + 1, step))
    if label == "day-of-week" and 7 in allowed:
        allowed.remove(7)
        allowed.add(0)
    return Field(frozenset(allowed), text == "*")


@dataclass(frozen=True)
class CronSchedule:
    minute: Field
    hour: Field
    day_of_month: Field
    month: Field
    day_of_week: Field

    @classmethod
    def parse(cls, expression: str) -> CronSchedule:
        if len(expression) > 256:
            raise CronSyntaxError("cron expression is too long")
        parts = expression.split()
        if len(parts) != 5:
            raise CronSyntaxError("cron expression must contain five fields")
        return cls(
            _field(parts[0], 0, 59, "minute"),
            _field(parts[1], 0, 23, "hour"),
            _field(parts[2], 1, 31, "day-of-month"),
            _field(parts[3], 1, 12, "month", _MONTHS),
            _field(parts[4], 0, 7, "day-of-week", _DAYS),
        )

    def matches(self, local: datetime) -> bool:
        if local.tzinfo is None or local.utcoffset() is None:
            raise ValueError("a timezone-aware datetime is required")
        if local.minute not in self.minute.allowed or local.hour not in self.hour.allowed:
            return False
        if local.month not in self.month.allowed:
            return False
        dom = local.day in self.day_of_month.allowed
        dow = (local.weekday() + 1) % 7 in self.day_of_week.allowed
        if self.day_of_month.wildcard:
            return dow
        if self.day_of_week.wildcard:
            return dom
        return dom or dow


def occurrences(schedule: CronSchedule, zone: ZoneInfo, after: datetime, count: int = 5,
                days: int = 366) -> list[datetime]:
    """Return local times strictly after `after`, ordered by UTC instant.

    Iterating over UTC minutes avoids constructing nonexistent local times and
    preserves both occurrences of a repeated local minute during a DST fold.
    """
    if after.tzinfo is None or after.utcoffset() is None:
        raise ValueError("a timezone-aware datetime is required")
    if not 1 <= count <= 100 or not 1 <= days <= 3660:
        raise ValueError("count or horizon outside supported range")
    start = after.astimezone(timezone.utc).replace(second=0, microsecond=0) + timedelta(minutes=1)
    result: list[datetime] = []
    for index in range(days * 1440):
        local = (start + timedelta(minutes=index)).astimezone(zone)
        if schedule.matches(local):
            result.append(local)
            if len(result) == count:
                break
    return result
