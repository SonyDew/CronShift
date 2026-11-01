"""Command-line interface for local cron schedule inspection."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sys
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .core import CronSchedule, CronSyntaxError, occurrences


class SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.exit(2, f"{self.prog}: error: invalid arguments\n")


def _bounded(value: str, label: str, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (ValueError, OverflowError):
        raise ValueError(f"{label} must be between {minimum} and {maximum}") from None
    if not minimum <= number <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return number


def _parse_after(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        raise ValueError("--from requires an ISO 8601 datetime with a UTC offset") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("--from requires an ISO 8601 datetime with a UTC offset")
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = SafeParser(prog="cronshift", description="Show future five-field cron matches in an IANA time zone.")
    parser.add_argument("expression", help="five-field cron expression (quote it in your shell)")
    parser.add_argument("--timezone", required=True, help="IANA zone, for example Europe/Berlin")
    parser.add_argument("--from", dest="after", help="ISO 8601 datetime with offset; defaults to current UTC time")
    parser.add_argument("--count", default="5", help="number of matches, 1-100 (default: 5)")
    parser.add_argument("--days", default="366", help="search horizon in 24-hour days, 1-3660 (default: 366)")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args(argv)
    try:
        schedule = CronSchedule.parse(args.expression)
        count = _bounded(args.count, "--count", 1, 100)
        days = _bounded(args.days, "--days", 1, 3660)
        after = _parse_after(args.after)
        if len(args.timezone) > 128 or not args.timezone.isascii():
            raise ValueError("invalid IANA time zone")
        try:
            zone = ZoneInfo(args.timezone)
        except (ZoneInfoNotFoundError, ValueError, OSError):
            raise ValueError("invalid IANA time zone") from None
        matches = occurrences(schedule, zone, after, count, days)
    except (CronSyntaxError, ValueError, OverflowError) as exc:
        print(f"cronshift: error: {exc}", file=sys.stderr)
        return 2
    complete = len(matches) == count
    if args.json:
        payload = {
            "timezone": zone.key,
            "status": "complete" if complete else "incomplete",
            "requested": count,
            "matches": [{"local": item.isoformat(), "utc": item.astimezone(timezone.utc).isoformat(),
                         "fold": item.fold} for item in matches],
        }
        print(json.dumps(payload, indent=2))
    else:
        for item in matches:
            print(f"{item.isoformat()}  UTC {item.astimezone(timezone.utc).isoformat()}  fold={item.fold}")
        if not complete:
            print("Not enough matches within the search horizon.", file=sys.stderr)
    return 0 if complete else 1
