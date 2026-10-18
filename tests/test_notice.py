import unittest
from civit_helper.notice import Countdown, requires_warning


class NoticeTests(unittest.TestCase):
    def test_unanswered_schedule_executes_after_three_minutes(self):
        clock = [100.0]
        notice = Countdown(now=lambda: clock[0])
        self.assertEqual(notice.decision(), 'waiting')
        clock[0] = 279.9
        self.assertEqual(notice.decision(), 'waiting')
        clock[0] = 280.0
        self.assertEqual(notice.decision(), 'execute')

    def test_closing_cancels_even_after_deadline(self):
        clock = [0.0]
        notice = Countdown(now=lambda: clock[0])
        notice.cancel()
        clock[0] = 200.0
        self.assertEqual(notice.decision(), 'cancelled')

    def test_only_scheduled_run_requires_warning(self):
        self.assertTrue(requires_warning('run', 'scheduled'))
        self.assertFalse(requires_warning('run', 'manual'))
        self.assertFalse(requires_warning('inspect', 'scheduled'))
        self.assertFalse(requires_warning('login', 'manual'))


if __name__ == '__main__':
    unittest.main()
