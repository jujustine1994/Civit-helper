import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from civit_helper.login import login_command, open_native_login


class LoginTests(unittest.TestCase):
    def test_native_login_uses_dedicated_profile_without_automation(self):
        command = login_command(Path('C:/Chrome/chrome.exe'), Path('C:/Tool/runtime/chrome-profile'))
        self.assertEqual(command[0], str(Path('C:/Chrome/chrome.exe')))
        self.assertIn('--user-data-dir=' + str(Path('C:/Tool/runtime/chrome-profile')), command)
        self.assertEqual(command[-1], 'https://civitai.red/images')
        self.assertFalse(any('remote-debugging' in x or 'automation' in x or 'disable-' in x for x in command))

    @patch('civit_helper.login.subprocess.Popen')
    def test_login_waits_until_user_closes_browser(self, popen):
        proc = Mock()
        popen.return_value = proc
        open_native_login(Path('C:/Chrome/chrome.exe'), Path('C:/Tool/profile'))
        proc.wait.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
