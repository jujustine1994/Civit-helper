import subprocess
import unittest
from pathlib import Path


class ConnectionDiagnosticsTests(unittest.TestCase):
    def test_worker_reports_network_and_authentication_errors_without_secrets(self):
        root = Path(__file__).resolve().parent.parent
        result = subprocess.run(['node', str(root / 'tests/extension_connection_fixture.mjs')],
                                cwd=root, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('EXTENSION_CONNECTION_FIXTURE_OK', result.stdout)
