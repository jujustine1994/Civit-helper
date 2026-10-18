import time
import unittest
from unittest.mock import Mock
from civit_helper.core import RunWindowExpired
from civit_helper.remote_site import BridgeSite


class RemoteSiteTests(unittest.TestCase):
    def site(self):
        site = object.__new__(BridgeSite)
        site.state = lambda *args: False
        site.account = lambda: '7'
        site.before_write = lambda: True
        site.client_headers = {'x-client': 'web'}
        site.work_day = '2020-01-01'
        site.write_expires_at = int((time.time() + 2) * 1000)
        site.bridge = Mock()
        site.bridge.command.return_value = {'accepted': True}
        return site

    def test_remote_action_keeps_original_day_and_deadline(self):
        site = self.site()
        site.apply('heart', '42')
        args = site.bridge.command.call_args.kwargs
        self.assertEqual(args['day'], '2020-01-01')
        self.assertLessEqual(args['expiresAt'], site.write_expires_at)

    def test_remote_checks_window_after_account_read(self):
        site = self.site()
        allowed = [True]
        site.before_write = lambda: allowed[0]
        def account():
            allowed[0] = False
            return '7'
        site.account = account
        with self.assertRaises(RunWindowExpired):
            site.apply('heart', '42')
        site.bridge.command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
