"""Boundary and regression checks for wall-clock candidate enumeration."""

import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
import unittest
from zoneinfo import ZoneInfo

from cronshift import CronSchedule, occurrences
from cronshift.cli import main


def utc(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


class LocalMinuteTests(unittest.TestCase):
    def test_historical_offset_with_seconds(self):
        zone = ZoneInfo('Europe/Amsterdam')
        result = occurrences(CronSchedule.parse('20 0 * * *'), zone,
                             utc('1900-01-01T00:00:00Z'), 1, 2)
        self.assertEqual(result[0].isoformat(), '1900-01-01T00:20:00+00:19:32')
        self.assertEqual(result[0].astimezone(timezone.utc), utc('1900-01-01T00:00:28Z'))

    def test_historical_second_offset_is_exclusive(self):
        zone = ZoneInfo('Europe/Amsterdam')
        result = occurrences(CronSchedule.parse('20 0 * * *'), zone,
                             utc('1900-01-01T00:00:28Z'), 1, 2)
        self.assertEqual(result[0].date().isoformat(), '1900-01-02')

    def test_lord_howe_half_hour_fall_fold(self):
        result = occurrences(CronSchedule.parse('45 1 * * *'),
                             ZoneInfo('Australia/Lord_Howe'),
                             utc('2026-04-04T00:00:00Z'), 2, 3)
        self.assertEqual([x.fold for x in result], [0, 1])
        self.assertEqual([x.astimezone(timezone.utc).isoformat() for x in result],
                         ['2026-04-04T14:45:00+00:00', '2026-04-04T15:15:00+00:00'])

    def test_fall_fold_is_sorted_by_instant_not_wall_clock(self):
        result = occurrences(CronSchedule.parse('* 2 * * *'),
                             ZoneInfo('Europe/Berlin'),
                             utc('2026-10-24T23:59:00Z'), 62, 1)
        self.assertEqual([x.fold for x in result[:60]], [0] * 60)
        self.assertEqual([x.fold for x in result[60:]], [1, 1])
        self.assertEqual(result[60].minute, 0)
        instants = [x.astimezone(timezone.utc) for x in result]
        self.assertEqual(instants, sorted(set(instants)))

    def test_skipped_calendar_day_in_apia(self):
        result = occurrences(CronSchedule.parse('0 0 * * *'),
                             ZoneInfo('Pacific/Apia'),
                             utc('2011-12-28T00:00:00Z'), 4, 7)
        self.assertEqual([x.date().isoformat() for x in result],
                         ['2011-12-28', '2011-12-29', '2011-12-31', '2012-01-01'])

    def test_sparse_schedule_maximum_horizon(self):
        result = occurrences(CronSchedule.parse('0 0 31 FEB *'),
                             ZoneInfo('UTC'), utc('2026-01-01T00:00:00Z'), 1, 3660)
        self.assertEqual(result, [])

    def test_boundary_at_end_of_horizon(self):
        schedule = CronSchedule.parse('0 0 * * *')
        self.assertEqual(occurrences(schedule, ZoneInfo('UTC'),
                         utc('2026-11-01T00:00:00Z'), 1, 1)[0],
                         utc('2026-11-02T00:00:00Z'))
        self.assertEqual(occurrences(schedule, ZoneInfo('UTC'),
                         utc('2026-11-01T00:00:01Z'), 1, 1)[0],
                         utc('2026-11-02T00:00:00Z'))

    def test_datetime_max_with_positive_zone(self):
        result = occurrences(CronSchedule.parse('* * * * *'),
                             ZoneInfo('Pacific/Kiritimati'),
                             utc('9999-12-31T20:00:00Z'), 1, 1)
        self.assertEqual(result, [])

    def test_datetime_min_with_historical_seconds(self):
        result = occurrences(CronSchedule.parse('0 0 * * *'),
                             ZoneInfo('America/New_York'),
                             utc('0001-01-01T00:00:00Z'), 1, 1)
        self.assertEqual(result[0].astimezone(timezone.utc),
                         utc('0001-01-01T04:56:02Z'))

    def test_fold_no_duplicate_on_fixed_offset(self):
        result = occurrences(CronSchedule.parse('* * * * *'), ZoneInfo('UTC'),
                             utc('2026-11-01T00:00:00Z'), 5, 1)
        self.assertEqual(len(set(result)), 5)
        self.assertEqual([x.fold for x in result], [0] * 5)

    def test_cli_historical_offset_json(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(['20 0 * * *', '--timezone', 'Europe/Amsterdam',
                         '--from', '1900-01-01T00:00:00Z', '--count', '1', '--json'])
        self.assertEqual(code, 0)
        self.assertFalse(stderr.getvalue())
        match = json.loads(stdout.getvalue())['matches'][0]
        self.assertEqual(match['local'], '1900-01-01T00:20:00+00:19:32')
        self.assertEqual(match['utc'], '1900-01-01T00:00:28+00:00')

    def test_matches_utc_minute_reference_in_modern_zones(self):
        # Independent minute-by-minute reference for contemporary offsets.
        start = utc('2026-10-24T00:00:00Z')
        for name in ('Europe/Berlin', 'America/New_York', 'Australia/Lord_Howe'):
            zone = ZoneInfo(name)
            for expression in ('30 2 * * *', '0,15 1-3 * * *', '0 0 1 * MON'):
                with self.subTest(zone=name, expression=expression):
                    schedule = CronSchedule.parse(expression)
                    expected = []
                    for index in range(1, 4 * 1440 + 1):
                        candidate = start + timedelta(minutes=index)
                        local = candidate.astimezone(zone)
                        if schedule.matches(local):
                            expected.append(candidate)
                            if len(expected) == 10:
                                break
                    actual = occurrences(schedule, zone, start, 10, 4)
                    self.assertEqual([x.astimezone(timezone.utc) for x in actual], expected)

    def test_new_search_keeps_original_files_unchanged(self):
        # The occurrence engine operates on datetimes and time-zone metadata.
        # It does not accept a file path or create an output file.
        before = utc('2026-10-25T00:00:00Z')
        schedule = CronSchedule.parse('30 2 * * *')
        first = occurrences(schedule, ZoneInfo('Europe/Berlin'), before, 2, 1)
        second = occurrences(schedule, ZoneInfo('Europe/Berlin'), before, 2, 1)
        self.assertEqual(first, second)
        self.assertEqual(before, utc('2026-10-25T00:00:00Z'))


if __name__ == '__main__':
    unittest.main()
