import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from cronshift import CronSchedule, CronSyntaxError, occurrences


UTC = timezone.utc


def instant(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


class CronScheduleTests(unittest.TestCase):
    def test_simple_match(self):
        schedule = CronSchedule.parse('30 2 * * *')
        self.assertTrue(schedule.matches(instant('2026-03-28T02:30:00Z')))
        self.assertFalse(schedule.matches(instant('2026-03-28T02:31:00Z')))

    def test_list_range_step(self):
        schedule = CronSchedule.parse('0,15-45/15 8-10/2 * JAN,MAR MON-FRI')
        self.assertTrue(schedule.matches(instant('2026-03-02T08:30:00Z')))
        self.assertTrue(schedule.matches(instant('2026-03-02T10:00:00Z')))
        self.assertFalse(schedule.matches(instant('2026-03-02T09:30:00Z')))
        self.assertFalse(schedule.matches(instant('2026-03-02T08:31:00Z')))
        self.assertFalse(schedule.matches(instant('2026-04-02T08:30:00Z')))

    def test_step_from_value(self):
        schedule = CronSchedule.parse('5/10 * * * *')
        self.assertEqual(schedule.minute.allowed, {5, 15, 25, 35, 45, 55})

    def test_sunday_alias(self):
        schedule = CronSchedule.parse('0 0 * * 7')
        self.assertTrue(schedule.matches(instant('2026-11-01T00:00:00Z')))
        self.assertFalse(schedule.matches(instant('2026-11-02T00:00:00Z')))

    def test_day_of_month_or_day_of_week(self):
        schedule = CronSchedule.parse('0 0 1 * MON')
        self.assertTrue(schedule.matches(instant('2026-11-01T00:00:00Z')))
        self.assertTrue(schedule.matches(instant('2026-11-02T00:00:00Z')))
        self.assertFalse(schedule.matches(instant('2026-11-03T00:00:00Z')))

    def test_wildcard_day_logic(self):
        schedule = CronSchedule.parse('0 0 * * MON')
        self.assertFalse(schedule.matches(instant('2026-11-01T00:00:00Z')))
        self.assertTrue(schedule.matches(instant('2026-11-02T00:00:00Z')))
        schedule = CronSchedule.parse('0 0 1 * *')
        self.assertTrue(schedule.matches(instant('2026-11-01T00:00:00Z')))
        self.assertFalse(schedule.matches(instant('2026-11-02T00:00:00Z')))

    def test_restricted_step_day_semantics(self):
        schedule = CronSchedule.parse('0 0 */1 * MON')
        self.assertTrue(schedule.matches(instant('2026-11-03T00:00:00Z')))

    def test_invalid_expressions(self):
        bad = ['* * * *', '* * * * * *', '60 * * * *', '0 24 * * *',
               '0 0 0 * *', '0 0 32 * *', '0 0 * 13 *', '0 0 * * 8',
               '*/0 * * * *', '*/61 * * * *', '1-0 * * * *',
               '1,,2 * * * *', '/2 * * * *', '1/2/3 * * * *',
               '0 0 * FOO *', '0 0 * * FRI-MON', '0 0 * * MONDAY',
               '０ * * * *', '0 * * * *' + ' ' * 257]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(CronSyntaxError):
                CronSchedule.parse(value)

    def test_naive_datetime_rejected(self):
        with self.assertRaises(ValueError):
            CronSchedule.parse('* * * * *').matches(datetime(2026, 1, 1))

    def test_spring_gap_skipped(self):
        schedule = CronSchedule.parse('30 2 * * *')
        matches = occurrences(schedule, ZoneInfo('Europe/Berlin'), instant('2026-03-28T00:00:00Z'), 3, 5)
        self.assertEqual([v.date().isoformat() for v in matches], ['2026-03-28', '2026-03-30', '2026-03-31'])
        self.assertEqual([v.utcoffset().total_seconds() / 3600 for v in matches], [1, 2, 2])

    def test_fall_fold_twice(self):
        schedule = CronSchedule.parse('30 2 * * *')
        matches = occurrences(schedule, ZoneInfo('Europe/Berlin'), instant('2026-10-24T00:00:00Z'), 4, 5)
        self.assertEqual([v.isoformat() for v in matches], [
            '2026-10-24T02:30:00+02:00', '2026-10-25T02:30:00+02:00',
            '2026-10-25T02:30:00+01:00', '2026-10-26T02:30:00+01:00'])
        self.assertEqual([v.fold for v in matches], [0, 0, 1, 0])

    def test_after_is_exclusive(self):
        schedule = CronSchedule.parse('* * * * *')
        result = occurrences(schedule, ZoneInfo('UTC'), instant('2026-11-01T00:00:00Z'), 2, 1)
        self.assertEqual(result[0].isoformat(), '2026-11-01T00:01:00+00:00')
        result = occurrences(schedule, ZoneInfo('UTC'), instant('2026-11-01T00:00:30Z'), 1, 1)
        self.assertEqual(result[0].minute, 1)

    def test_sparse_schedule_incomplete(self):
        schedule = CronSchedule.parse('0 0 29 FEB *')
        self.assertEqual(occurrences(schedule, ZoneInfo('UTC'), instant('2026-01-01T00:00:00Z'), 1, 366), [])

    def test_bad_occurrence_arguments(self):
        schedule = CronSchedule.parse('* * * * *')
        for count, days in [(0, 1), (101, 1), (1, 0), (1, 3661)]:
            with self.assertRaises(ValueError):
                occurrences(schedule, ZoneInfo('UTC'), instant('2026-01-01T00:00:00Z'), count, days)
        with self.assertRaises(ValueError):
            occurrences(schedule, ZoneInfo('UTC'), datetime(2026, 1, 1))


class BoundaryTests(unittest.TestCase):
    def test_partial_results_at_datetime_max(self):
        schedule = CronSchedule.parse('* * * * *')
        results = occurrences(schedule, ZoneInfo('UTC'),
                              instant('9999-12-31T23:58:00Z'), 2, 1)
        self.assertEqual([item.isoformat() for item in results],
                         ['9999-12-31T23:59:00+00:00'])

    def test_no_minutes_after_datetime_max(self):
        schedule = CronSchedule.parse('* * * * *')
        self.assertEqual(occurrences(schedule, ZoneInfo('UTC'),
                         instant('9999-12-31T23:59:00Z'), 1, 1), [])

    def test_utc_minimum_with_negative_zone_offset(self):
        schedule = CronSchedule.parse('0 0 * * *')
        results = occurrences(schedule, ZoneInfo('America/New_York'),
                              instant('0001-01-01T00:00:00Z'), 1, 2)
        self.assertEqual(len(results), 1)
        self.assertGreater(results[0].astimezone(UTC), instant('0001-01-01T00:00:00Z'))

    def test_horizon_excludes_next_minute(self):
        schedule = CronSchedule.parse('0 0 * * *')
        self.assertEqual(occurrences(schedule, ZoneInfo('UTC'),
                         instant('2026-11-01T00:00:00Z'), 1, 1),
                         [instant('2026-11-02T00:00:00Z')])
        self.assertEqual(occurrences(schedule, ZoneInfo('UTC'),
                         instant('2026-11-01T00:00:00Z'), 2, 1),
                         [instant('2026-11-02T00:00:00Z')])

    def test_offset_timestamp_is_converted_to_utc(self):
        schedule = CronSchedule.parse('* * * * *')
        results = occurrences(schedule, ZoneInfo('UTC'),
                              instant('2026-11-01T01:15:45+02:00'), 1, 1)
        self.assertEqual(results[0].isoformat(), '2026-10-31T23:16:00+00:00')

    def test_month_and_weekday_case_insensitive(self):
        schedule = CronSchedule.parse('0 0 * jan,Feb mon-fri')
        self.assertTrue(schedule.matches(instant('2026-02-02T00:00:00Z')))
        self.assertFalse(schedule.matches(instant('2026-03-02T00:00:00Z')))

    def test_no_value_leak_in_syntax_error(self):
        secret = 'private-token-123'
        with self.assertRaises(CronSyntaxError) as context:
            CronSchedule.parse(secret + ' * * * *')
        self.assertNotIn(secret, str(context.exception))


if __name__ == '__main__':
    unittest.main()
