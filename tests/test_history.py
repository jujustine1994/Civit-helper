import tempfile
import unittest
from pathlib import Path

from civit_helper.history import format_history, row_fields
from civit_helper.state import Store


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'state.db')
        db = self.store.db
        with db:
            db.execute("INSERT INTO runs VALUES (1,'2026-10-20T04:00:00+08:00','2026-10-20T04:08:12+08:00','scheduled/run','complete','done')")
            db.execute("INSERT INTO runs VALUES (2,'2026-10-20T09:00:00+08:00','2026-10-20T09:00:05+08:00','manual/doctor','ready','ping')")
            db.execute("INSERT INTO runs VALUES (3,'2026-10-21T04:00:00+08:00','2026-10-21T04:00:40+08:00','scheduled/run','error','工具分頁載入逾時')")
            for i in range(3):
                db.execute("INSERT INTO actions VALUES ('2026-10-20','heart',?, 'confirmed','x','2026-10-20T04:01:00+08:00')", (str(i),))
            db.execute("INSERT INTO actions VALUES ('2026-10-20','follow','9','confirmed','x','2026-10-20T04:02:00+08:00')")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_history_lists_only_task_runs_with_counts_per_run(self):
        runs = self.store.history()
        self.assertEqual([r['id'] for r in runs], [3, 1])  # newest first, doctor excluded
        self.assertEqual(runs[1]['added'], {'heart': 3, 'follow': 1})
        self.assertEqual(runs[0]['added'], {'heart': 0, 'follow': 0})
        self.assertEqual(runs[1]['day_total'], {'heart': 3, 'follow': 1})
        with self.store.db:
            self.store.db.execute("INSERT INTO actions VALUES ('2026-10-20','heart','late','confirmed','x','2026-10-20T10:00:00+08:00')")
        # A later run's actions must not change what an earlier run reported.
        self.assertEqual(self.store.history()[1]['day_total'], {'heart': 3, 'follow': 1})

    def test_human_fields_are_readable(self):
        ok, failed = row_fields(self.store.history()[1]), row_fields(self.store.history()[0])
        self.assertEqual((ok['source'], ok['result'], ok['heart'], ok['duration'], ok['note']),
                         ('排程', '✅ 完成', '+3', '8分12秒', ''))
        self.assertEqual((failed['result'], failed['note']), ('❌ 失敗', '工具分頁載入逾時'))
        text = format_history(self.store.history())
        self.assertIn('2026-10-20 04:00 | 排程 | ✅ 完成 | +3 | +1', text)
        self.assertNotIn('run_id', text)


if __name__ == '__main__':
    unittest.main()
