# CronShift

**Status: In Development (Day 6 of SonyDev GitHub Marathon, November 1, 2026).**

CronShift lists future matches of a five-field cron expression in an IANA time zone. It evaluates actual UTC minutes and converts them to local time. Nonexistent local times during a spring DST transition are skipped; repeated local times during a fall transition appear twice with distinct UTC timestamps.

## Install

Requires Python 3.10 or newer and IANA time-zone data available to Python's `zoneinfo` module. Git is not required to run the CLI.

```sh
python -m pip install .
```

Run without installing from the repository root:

```sh
python -m cronshift '30 2 * * *' --timezone Europe/Berlin --from '2026-03-28T00:00:00+00:00' --count 3
```

## Usage

```sh
cronshift '30 2 * * *' --timezone Europe/Berlin --from '2026-10-24T00:00:00Z' --count 4
cronshift '0 9 * * MON-FRI' --timezone America/New_York --from '2026-11-01T00:00:00Z' --json
cronshift '0 0 1 * MON' --timezone UTC --days 30 --count 5
```

The five fields are minute (0-59), hour (0-23), day of month (1-31), month (1-12), and day of week (0-7, where 0 and 7 mean Sunday). Supported syntax: `*`, comma lists, ranges (`1-5`), steps (`*/15`, `1-10/2`, `5/10`), and three-letter English month and weekday names. A day matches when either the day-of-month or day-of-week field matches if both fields are restricted; otherwise the unrestricted field is ignored. This follows traditional cron day matching. `*/1` is treated as restricted for this rule; use `*` for an unrestricted field.

`--from` requires an ISO 8601 timestamp with an explicit offset or `Z`. If omitted, the current UTC time is used. Matches are strictly after this instant. `--count` defaults to 5 (maximum 100). `--days` defaults to 366 (maximum 3660); each day is 24 hours from the supplied instant. The output is ordered by UTC time and includes both the local offset and UTC instant. `fold=1` marks the second occurrence of a repeated local time.

Exit codes: `0` if the requested number of matches is found, `1` if the horizon ends first (partial matches are printed), and `2` for invalid arguments or expressions. `--json` returns `timezone`, `status`, `requested`, and a `matches` array with `local`, `utc`, and `fold` fields. Errors are written to stderr.

## Limitations

This is not a cron daemon and does not execute commands. It supports five-field expressions only: no seconds, year field, `@daily` aliases, `L`, `W`, `#`, `?`, or implementation-specific macros. It uses the host's installed time-zone database; results may change when that database is updated. Some cron implementations choose different behavior for repeated or nonexistent DST minutes. CronShift always lists both real occurrences in a fold and skips nonexistent minutes. A sparse schedule may not produce the requested number of matches within the search horizon.

## Development

```sh
python -m unittest discover -s tests -v
python -m cronshift --help
```

Runtime dependencies: Python standard library only. Packaging uses setuptools. No network calls or file modifications are made by the CLI.

## Development checks (November 1, 2026)

On Linux with Python 3.13.5, all 34 `unittest` tests passed. A wheel was built without downloading dependencies, installed in a separate virtual environment, and the installed `cronshift` command was run. The examples above were exercised. Tests cover spring DST gaps, autumn folds, invalid input, output codes, and dates near the supported `datetime` boundaries.

The scanner returns partial results if it reaches the end of Python's representable datetime range. Sparse schedules can require scanning millions of UTC minutes; the maximum horizon is 3,660 days. Windows and Python 3.10–3.12 have not been tested.
