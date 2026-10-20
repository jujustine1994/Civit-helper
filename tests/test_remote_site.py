import time
import unittest
from unittest.mock import MagicMock, Mock, patch
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

    def test_only_window_created_during_init_is_minimized(self):
        windows = [[1], [1, 2]]  # 1 = user's existing window, 2 = tool window from init
        bridge = MagicMock()
        bridge.command.side_effect = lambda op, **kw: (time.sleep(0.5), {'headers': {}, 'filters': {'browsingLevel': 1}})[1]
        with patch('civit_helper.remote_site.Bridge', return_value=bridge), \
                patch('civit_helper.remote_site.chrome_windows', side_effect=lambda: windows[0] if len(windows) == 1 else windows.pop(0)), \
                patch('civit_helper.remote_site.minimize_windows') as minimize:
            site = BridgeSite().__enter__()
        self.assertEqual(site.tool_windows, [2])
        self.assertTrue(all(1 not in call.args[0] for call in minimize.call_args_list))
        minimize.assert_called_with([2])


if __name__ == '__main__':
    unittest.main()
