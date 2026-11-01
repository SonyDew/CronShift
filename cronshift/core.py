"""Five-field cron matching against actual instants in an IANA time zone."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
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


def _matches_day(schedule: CronSchedule, day: date) -> bool:
    if day.month not in schedule.month.allowed:
        return False
    dom = day.day in schedule.day_of_month.allowed
    dow = (day.weekday() + 1) % 7 in schedule.day_of_week.allowed
    if schedule.day_of_month.wildcard:
        return dow
    if schedule.day_of_week.wildcard:
        return dom
    return dom or dow


def occurrences(schedule: CronSchedule, zone: ZoneInfo, after: datetime, count: int = 5,
                days: int = 366) -> list[datetime]:
    """List real local cron minutes after an instant, including both DST folds."""
    if after.tzinfo is None or after.utcoffset() is None:
        raise ValueError("a timezone-aware datetime is required")
    if not 1 <= count <= 100 or not 1 <= days <= 3660:
        raise ValueError("count or horizon outside supported range")

    utc_after = after.astimezone(timezone.utc)
    try:
        utc_end = utc_after + timedelta(days=days)
    except OverflowError:
        utc_end = datetime.max.replace(tzinfo=timezone.utc)
    try:
        first_day = utc_after.astimezone(zone).date()
    except OverflowError:
        first_day = date.max if utc_after.year == 9999 else date.min
    try:
        last_day = utc_end.astimezone(zone).date()
    except OverflowError:
        last_day = date.max if utc_end.year == 9999 else date.min

    result: list[datetime] = []
    day = first_day
    hours = sorted(schedule.hour.allowed)
    minutes = sorted(schedule.minute.allowed)
    while day <= last_day:
        if _matches_day(schedule, day):
            # Local wall-clock order is not UTC order during a fall DST fold.
            # Sort each day's candidates before selecting the next occurrence.
            candidates: list[tuple[datetime, datetime]] = []
            for hour in hours:
                for minute in minutes:
                    wall = datetime.combine(day, time(hour, minute))
                    for fold in (0, 1):
                        local = wall.replace(tzinfo=zone, fold=fold)
                        try:
                            utc = local.astimezone(timezone.utc)
                            back = utc.astimezone(zone)
                        except OverflowError:
                            continue
                        # A spring gap maps back to a different local minute.
                        if back.replace(tzinfo=None) != wall:
                            continue
                        if utc_after < utc <= utc_end:
                            candidates.append((utc, back))
            seen: set[datetime] = set()
            for utc, local in sorted(candidates, key=lambda pair: pair[0]):
                if utc not in seen:
                    result.append(local)
                    seen.add(utc)
                    if len(result) == count:
                        return result
        if day == date.max:
            break
        day += timedelta(days=1)
    return result
