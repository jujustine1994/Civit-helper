import json
import threading
import unittest
import urllib.request
import urllib.error
from civit_helper.bridge import Bridge, BridgeError


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.bridge = Bridge(token='unit-test-secret', port=0)
        self.bridge.__enter__()
        self.addCleanup(self.bridge.__exit__)
        self.base = f'http://127.0.0.1:{self.bridge.port}'
        self.origin = 'chrome-extension://' + 'a' * 32

    def request(self, path='/poll', token='unit-test-secret', origin=None, data=None, host=None):
        headers = {'X-Civit-Helper-Token': token, 'Origin': origin or self.origin}
        if host:
            headers['Host'] = host
        req = urllib.request.Request(self.base + path,
                                     data=json.dumps(data).encode() if data is not None else None,
                                     headers=headers)
        return urllib.request.urlopen(req, timeout=3)

    def test_rejects_wrong_token_and_web_origin_and_host(self):
        for opts in ({'token': 'wrong'}, {'origin': 'https://example.com'}, {'host': 'example.com'}):
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.request(**opts)
            self.assertEqual(error.exception.code, 403)

    def test_only_paired_origin_can_poll(self):
        self.request().close()
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request(origin='chrome-extension://' + 'b' * 32)
        self.assertEqual(error.exception.code, 403)

    def test_command_result_is_correlated_and_not_redelivered(self):
        returned = []
        worker = threading.Thread(target=lambda: returned.append(self.bridge.command('init', timeout=2)))
        worker.start()
        command = json.load(self.request())['command']
        self.assertEqual(command['op'], 'init')
        self.assertIsNone(json.load(self.request())['command'])
        self.request('/result', data={'id': command['id'], 'ok': True, 'result': {'ready': True}}).close()
        worker.join(3)
        self.assertEqual(returned, [{'ready': True}])
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/result', data={'id': command['id'], 'ok': True, 'result': {}})

    def test_extension_can_authenticate_when_browser_omits_origin_header(self):
        req = urllib.request.Request(self.base + '/poll', headers={
            'X-Civit-Helper-Token': 'unit-test-secret',
            'X-Civit-Helper-Origin': self.origin})
        with urllib.request.urlopen(req, timeout=3) as response:
            self.assertIsNone(json.load(response)['command'])

    def test_health_checks_authentication_without_delivering_work(self):
        data = json.load(self.request('/health'))
        self.assertEqual(data['protocol'], 1)
        self.assertTrue(data['authenticated'])
        self.assertNotIn('unit-test-secret', json.dumps(data))

    def test_diagnostics_distinguish_rejected_token_from_no_connection(self):
        self.assertEqual(self.bridge.diagnostics()['requests_received'], 0)
        with self.assertRaises(urllib.error.HTTPError):
            self.request(token='wrong')
        diagnostics = self.bridge.diagnostics()
        self.assertEqual(diagnostics['requests_received'], 1)
        self.assertEqual(diagnostics['rejections']['token_mismatch'], 1)
        self.assertNotIn('unit-test-secret', json.dumps(diagnostics))


if __name__ == '__main__':
    unittest.main()
