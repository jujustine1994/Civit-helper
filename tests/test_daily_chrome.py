import itertools
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from civit_helper import daily_chrome
from civit_helper.daily_chrome import DailyChrome


class DailyChromeTests(unittest.TestCase):
    @patch('civit_helper.daily_chrome.subprocess.Popen')
    @patch('civit_helper.daily_chrome.chrome_running', return_value=True)
    def test_running_chrome_is_left_alone(self, _running, popen):
        with patch('civit_helper.daily_chrome.ctypes') as fake_ctypes:
            with DailyChrome():
                pass
        popen.assert_not_called()
        fake_ctypes.windll.user32.PostMessageW.assert_not_called()

    def test_extension_profile_skips_profiles_without_extension(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'Local State').write_text(json.dumps({'profile': {
                'last_used': 'Profile 3', 'info_cache': {'Default': {}, 'Profile 3': {}}}}), encoding='utf-8')
            for name, text in (('Default', daily_chrome.EXTENSION_ID), ('Profile 3', 'other')):
                (root / name).mkdir()
                (root / name / 'Secure Preferences').write_text(text, encoding='utf-8')
            self.assertEqual(daily_chrome.extension_profile(root), 'Default')
            self.assertIsNone(daily_chrome.extension_profile(root / 'missing'))

    @patch('civit_helper.daily_chrome.extension_profile', return_value='Default')
    @patch('civit_helper.daily_chrome.chrome_windows', return_value=[11])
    @patch('civit_helper.daily_chrome.chrome_path', return_value=Path('C:/Chrome/chrome.exe'))
    @patch('civit_helper.daily_chrome.subprocess.Popen')
    @patch('civit_helper.daily_chrome.chrome_running', return_value=False)
    def test_closed_chrome_starts_minimized_without_automation(self, _running, popen, _path, _windows, _profile):
        user32 = Mock()
        with patch.object(daily_chrome.ctypes, 'windll', Mock(user32=user32)), \
                patch('civit_helper.daily_chrome.time.sleep'):
            user32.IsWindow.return_value = True
            user32.IsIconic.side_effect = itertools.chain([False], itertools.repeat(True))  # Chrome ignored the minimized hint.
            with DailyChrome(wait=1):
                pass
        user32.ShowWindow.assert_called_once_with(11, daily_chrome.SW_SHOWMINNOACTIVE)
        command = popen.call_args.args[0]
        self.assertEqual(command, [str(Path('C:/Chrome/chrome.exe')), '--profile-directory=Default'])
        self.assertFalse(any('remote-debugging' in x or 'no-startup-window' in x for x in command))
        self.assertEqual(popen.call_args.kwargs['startupinfo'].wShowWindow, daily_chrome.SW_SHOWMINNOACTIVE)
        user32.PostMessageW.assert_called_once_with(11, daily_chrome.WM_CLOSE, 0, 0)

    @patch('civit_helper.daily_chrome.extension_profile', return_value='Default')
    @patch('civit_helper.daily_chrome.chrome_windows', return_value=[11])
    @patch('civit_helper.daily_chrome.chrome_path', return_value=Path('C:/Chrome/chrome.exe'))
    @patch('civit_helper.daily_chrome.subprocess.Popen')
    @patch('civit_helper.daily_chrome.chrome_running', return_value=False)
    def test_restored_startup_window_is_not_closed(self, _running, _popen, _path, _windows, _profile):
        user32 = Mock()
        with patch.object(daily_chrome.ctypes, 'windll', Mock(user32=user32)), \
                patch('civit_helper.daily_chrome.time.sleep'):
            user32.IsWindow.return_value = True
            user32.IsIconic.return_value = False
            with DailyChrome(wait=1):
                pass
        user32.PostMessageW.assert_not_called()

    def test_chrome_running_detects_process(self):
        self.assertIsInstance(daily_chrome.chrome_running(), bool)


if __name__ == '__main__':
    unittest.main()
