# CronShift

**Status: Completed MVP (Day 6 of SonyDev GitHub Marathon, November 1, 2026).**

CronShift lists future matches of a five-field cron expression in an IANA time zone. It enumerates local calendar minutes, checks each against the time-zone database, and orders valid matches by UTC instant. Nonexistent local minutes during a spring clock change are skipped. Repeated local minutes during a fall clock change appear twice, with different UTC timestamps.

## Install

Requires Python 3.10 or newer and IANA time-zone data available through Python's `zoneinfo` module. No runtime packages are required beyond the standard library.

```sh
python -m pip install .
```

Run directly from the repository root without installing:

```sh
python -m cronshift '30 2 * * *' --timezone Europe/Berlin --from '2026-03-28T00:00:00Z' --count 3
```

## Usage

```sh
cronshift '30 2 * * *' --timezone Europe/Berlin --from '2026-10-24T00:00:00Z' --count 4
cronshift '0 9 * * MON-FRI' --timezone America/New_York --from '2026-11-01T00:00:00Z' --json
cronshift '0 0 1 * MON' --timezone UTC --from '2026-11-01T00:00:00Z' --days 30 --count 5
```

Fields are minute (0–59), hour (0–23), day of month (1–31), month (1–12), and day of week (0–7, with 0 and 7 representing Sunday). Supported syntax: `*`, comma lists, ranges (`1-5`), steps (`*/15`, `1-10/2`, `5/10`), and three-letter English month and weekday names. When both day-of-month and day-of-week are restricted, either may match. `*/1` is restricted for this rule; use `*` for an unrestricted field.

`--from` takes an ISO 8601 timestamp with an explicit UTC offset or `Z`. It defaults to the current UTC time. Matches must be strictly after that instant and no later than the `--days` horizon. `--count` defaults to 5 (maximum 100); `--days` defaults to 366 (maximum 3660). Days are 24-hour periods from the supplied instant, not local calendar days. The output includes local time, UTC time, offset, and `fold` (1 for the second occurrence of a repeated local minute).

Exit codes: `0` when all requested matches are found, `1` when the horizon or supported datetime range ends first (partial results are printed), and `2` for invalid input. JSON output contains `timezone`, `status`, `requested`, and `matches`, each with `local`, `utc`, and `fold`. Errors are written to stderr without echoing the invalid input.

## Limitations

CronShift does not execute commands or install cron jobs. It supports five fields only: no seconds or year field, `@daily`, `L`, `W`, `#`, `?`, or implementation-specific extensions. DST behavior differs between cron implementations; CronShift explicitly includes both real occurrences of a repeated minute and skips nonexistent minutes. Results depend on the installed IANA time-zone database. Historic offsets containing seconds are supported, but some cron daemons may not schedule such historical wall-clock instants in the same way.

No network requests or input-file modifications are performed by the CLI. A time-zone database must be available locally; on some Windows systems this requires installing `tzdata` separately. Windows and Python 3.10–3.12 have not been tested.

## Development

```sh
python -m unittest discover -s tests -v
python -m cronshift --help
```

Build-time packaging uses setuptools. There are no Python runtime dependencies.

## Development Report — November 1, 2026

Tested on Linux with Python 3.13.5. All 47 `unittest` tests passed. The tests cover parsing, exit codes, invalid-input redaction, spring gaps, fall folds, half-hour transitions, skipped calendar days, historical offsets containing seconds, and dates near the `datetime` limits. The CLI examples above were exercised. A wheel was built with `pip wheel --no-deps --no-build-isolation`, installed offline in a separate virtual environment, and its `cronshift` entry point was run.

The evening revision replaced UTC-minute scanning with local-minute candidate enumeration and UTC round-trip validation. This fixes historic second-offset scheduling and reduces work for sparse expressions. In a local comparison using `0 0 31 FEB *`, a 3,660-day horizon and UTC, the previous scanner took 6.085 seconds and the revised scanner took 0.0017 seconds. These are single-run measurements, not cross-platform benchmarks.

The tool remains an inspection CLI, not a replacement for a particular cron daemon. No stable release has been tagged.
