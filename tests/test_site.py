import unittest
from civit_helper.site import decode_trpc, reaction_state, SiteError, ChromeSite


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


if __name__ == '__main__':
    unittest.main()
