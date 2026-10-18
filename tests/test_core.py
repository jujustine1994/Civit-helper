import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from civit_helper.state import Store, RunLock, BusyError, taipei_now
from civit_helper.core import execute, automatic_allowed, RunWindowExpired


class FakeSite:
    def __init__(self, count=80):
        self.values = {}
        self.count = count
        self.applied = []
        self.account_id = '123'

    def account(self):
        return self.account_id

    def candidates(self):
        yield [{'image': str(i), 'author': 'u' + str(i)} for i in range(self.count)]

    def state(self, kind, target):
        return self.values.get((kind, target), False)

    def apply(self, kind, target):
        if self.state(kind, target):
            raise AssertionError('must not toggle existing action')
        self.applied.append((kind, target))
        self.values[kind, target] = True


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / 'state.db')
        self.addCleanup(self.store.close)
        self.site = FakeSite()
        self.now = lambda: datetime(2026, 10, 18, 5, tzinfo=timezone(timedelta(hours=8)))

    def run_work(self):
        return execute(self.store, self.site, now=self.now, seconds=30)

    def test_exact_daily_targets_and_second_run_no_actions(self):
        self.assertEqual(self.run_work()['status'], 'complete')
        self.assertEqual(self.store.progress('2026-10-18'), {'heart': 50, 'follow': 3})
        self.run_work()
        self.assertEqual(len(self.site.applied), 53)

    def test_resume_partial_and_skip_existing_reactions(self):
        self.store.bind('123')
        for i in range(20):
            self.store.prepare('2026-10-18', 'heart', str(i))
            self.store.confirm('2026-10-18', 'heart', str(i))
            self.site.values['heart', str(i)] = True
        self.site.values['heart', '20'] = True
        self.site.values['follow', 'u20'] = True
        self.run_work()
        self.assertEqual(sum(k == 'heart' for k, t in self.site.applied), 30)
        self.assertNotIn(('heart', '20'), self.site.applied)
        self.assertNotIn(('follow', 'u20'), self.site.applied)

    def test_pending_success_reconciled_on_original_day(self):
        self.store.bind('123')
        self.store.prepare('2026-10-17', 'follow', 'old')
        self.site.values['follow', 'old'] = True
        self.run_work()
        self.assertEqual(self.store.progress('2026-10-17')['follow'], 1)
        self.assertEqual(self.store.progress('2026-10-18')['follow'], 3)
        self.assertFalse(self.store.pending())

    def test_unknown_pending_does_not_retry_toggle(self):
        self.store.bind('123')
        self.store.prepare('2026-10-18', 'heart', '0')
        self.site.values['heart', '0'] = None
        result = self.run_work()
        self.assertEqual(result['status'], 'unconfirmed')
        self.assertFalse(self.site.applied)
        self.assertEqual(len(self.store.pending()), 1)

    def test_failed_confirm_does_not_count_and_preserves_pending(self):
        self.site.apply = lambda kind, target: None
        self.assertEqual(self.run_work()['status'], 'unconfirmed')
        self.assertEqual(self.store.progress('2026-10-18'), {'heart': 0, 'follow': 0})
        self.assertTrue(self.store.pending())

    def test_account_mismatch_stops(self):
        self.store.bind('other')
        with self.assertRaisesRegex(ValueError, '帳號'):
            self.run_work()
        self.assertFalse(self.site.applied)

    def test_no_candidates_is_stalled_not_complete(self):
        self.site.count = 0
        self.assertEqual(self.run_work()['status'], 'stalled')

    def test_history_followed_never_repeated(self):
        self.store.bind('123')
        self.store.prepare('2026-10-17', 'follow', 'u0')
        self.store.confirm('2026-10-17', 'follow', 'u0')
        self.run_work()
        self.assertNotIn(('follow', 'u0'), self.site.applied)

    def test_auto_before_four_skips_manual_does_not(self):
        self.assertFalse(automatic_allowed(datetime(2026, 10, 18, 3, 59)))
        self.assertTrue(automatic_allowed(self.now().replace(hour=4, minute=0)))
        self.assertTrue(automatic_allowed(self.now().replace(hour=4, minute=3)))
        self.assertFalse(automatic_allowed(self.now().replace(hour=4, minute=5)))
        self.assertFalse(automatic_allowed(self.now()))
        self.assertFalse(automatic_allowed(self.now().replace(hour=18)))

    def test_lock_reentry_and_release(self):
        p = Path(self.tmp.name) / 'run.lock'
        with RunLock(p):
            with self.assertRaises(BusyError):
                with RunLock(p):
                    pass
        with RunLock(p):
            pass

    def test_midnight_during_navigation_prevents_click(self):
        current = [self.now().replace(hour=23, minute=59, second=59)]
        def navigate_then_click(kind, target):
            current[0] = current[0] + timedelta(seconds=2)
            if not self.site.before_write():
                raise RunWindowExpired()
            self.site.applied.append((kind, target))
        self.site.apply = navigate_then_click
        result = execute(self.store, self.site, now=lambda: current[0], seconds=30)
        self.assertEqual(result['status'], 'partial')
        self.assertFalse(self.site.applied)
        self.assertFalse(self.store.pending())
        self.assertEqual(self.store.progress('2026-10-18'), {'heart': 0, 'follow': 0})


if __name__ == '__main__':
    unittest.main()
