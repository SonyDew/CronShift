import contextlib
import io
import json
import unittest
from unittest.mock import patch

from cronshift.cli import main


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                code = main(list(args))
            except SystemExit as exc:
                code = exc.code
        return code, stdout.getvalue(), stderr.getvalue()

    def test_json_fold(self):
        code, out, err = self.run_cli('30 2 * * *', '--timezone', 'Europe/Berlin',
            '--from', '2026-10-24T00:00:00Z', '--count', '4', '--days', '5', '--json')
        self.assertEqual(code, 0)
        self.assertFalse(err)
        data = json.loads(out)
        self.assertEqual(data['status'], 'complete')
        self.assertEqual(len(data['matches']), 4)
        self.assertEqual(data['matches'][2]['fold'], 1)
        self.assertEqual(data['matches'][2]['utc'], '2026-10-25T01:30:00+00:00')

    def test_text(self):
        code, out, err = self.run_cli('0 0 * * *', '--timezone', 'UTC',
            '--from', '2026-11-01T00:00:00Z', '--count', '1')
        self.assertEqual(code, 0)
        self.assertIn('2026-11-02T00:00:00+00:00', out)
        self.assertIn('fold=0', out)
        self.assertFalse(err)

    def test_partial_results_code_one(self):
        code, out, err = self.run_cli('0 0 29 FEB *', '--timezone', 'UTC',
            '--from', '2026-01-01T00:00:00Z', '--days', '1', '--json')
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)['matches'], [])
        self.assertFalse(err)

    def test_invalid_expression_does_not_echo_input(self):
        code, out, err = self.run_cli('SECRET=hidden * * * *', '--timezone', 'UTC')
        self.assertEqual(code, 2)
        self.assertNotIn('SECRET=hidden', err + out)

    def test_invalid_timezone_does_not_echo_input(self):
        code, out, err = self.run_cli('* * * * *', '--timezone', 'secret-zone-name')
        self.assertEqual(code, 2)
        self.assertNotIn('secret-zone-name', err + out)

    def test_naive_from_rejected(self):
        code, out, err = self.run_cli('* * * * *', '--timezone', 'UTC', '--from', '2026-11-01T00:00:00')
        self.assertEqual(code, 2)
        self.assertIn('UTC offset', err)

    def test_invalid_range(self):
        for arg, value in [('--count', '0'), ('--count', '101'), ('--days', '0'), ('--days', '3661'), ('--count', 'secret')]:
            with self.subTest(arg=arg, value=value):
                code, out, err = self.run_cli('* * * * *', '--timezone', 'UTC', arg, value)
                self.assertEqual(code, 2)
                self.assertNotIn(value if value == 'secret' else 'never-seen', err + out)

    def test_missing_arguments_safe(self):
        code, out, err = self.run_cli('--timezone', 'private-timezone')
        self.assertEqual(code, 2)
        self.assertNotIn('private-timezone', err)

    def test_no_network_or_file_writes(self):
        with patch('builtins.open', side_effect=AssertionError('file opened')):
            code, out, err = self.run_cli('0 0 * * *', '--timezone', 'UTC',
                '--from', '2026-11-01T00:00:00Z', '--count', '1')
        self.assertEqual(code, 0)


if __name__ == '__main__':
    unittest.main()
