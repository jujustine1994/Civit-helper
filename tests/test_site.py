import unittest
from civit_helper.site import decode_trpc, reaction_state, follow_state, SiteError, ChromeSite


class SiteTests(unittest.TestCase):
    def test_trpc_superjson_and_error(self):
        self.assertEqual(decode_trpc([{'result': {'data': {'json': [1, 2]}}}]), [1, 2])
        with self.assertRaises(SiteError):
            decode_trpc([{'error': {'json': {'message': 'UNAUTHORIZED'}}}])
        with self.assertRaises(SiteError):
            decode_trpc({'unexpected': True})

    def test_reaction_schema_strict_missing_is_not_unknown(self):
        self.assertTrue(reaction_state({'42': ['Heart', 'Like']}, '42'))
        self.assertFalse(reaction_state({'42': ['Like']}, '42'))
        self.assertFalse(reaction_state({}, '42'))
        with self.assertRaises(SiteError):
            reaction_state([], '42')
        with self.assertRaises(SiteError):
            reaction_state({'42': [{'reaction': 'Heart'}]}, '42')

    def test_apply_rechecks_state_and_refuses_existing(self):
        site = object.__new__(ChromeSite)
        site.state = lambda kind, target: True
        with self.assertRaisesRegex(SiteError, '已'):
            site.apply('heart', '42')

    def test_unknown_state_refuses_click(self):
        site = object.__new__(ChromeSite)
        site.state = lambda kind, target: None
        with self.assertRaises(SiteError):
            site.apply('follow', '42')

    def test_following_state_is_strict(self):
        self.assertTrue(follow_state([42, 43], '42'))
        self.assertFalse(follow_state([43], '42'))
        for invalid in ({}, [{'id': 42}], ['42'], [True]):
            with self.assertRaises(SiteError):
                follow_state(invalid, '42')

    def test_inspect_invalid_following_does_not_report_ready(self):
        site = object.__new__(ChromeSite)
        site.headed = False
        site.client_headers = {'x-client': 'web'}
        site.account = lambda: '42'
        site.query = lambda *args: {}
        with self.assertRaises(SiteError):
            site.inspect()


if __name__ == '__main__':
    unittest.main()
