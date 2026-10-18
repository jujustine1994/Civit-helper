import subprocess
import unittest
from pathlib import Path


class ExtensionWindowTests(unittest.TestCase):
    def test_minimized_window_and_cleanup_preserve_user_tabs(self):
        root = Path(__file__).resolve().parent.parent
        result = subprocess.run(['node', str(root / 'tests/extension_window_fixture.mjs')],
                                cwd=root, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('EXTENSION_WINDOW_FIXTURE_OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
