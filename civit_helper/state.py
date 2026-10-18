import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / 'runtime'
TAIPEI = timezone(timedelta(hours=8), 'Asia/Taipei')
TARGETS = {'heart': 50, 'follow': 3}


def taipei_now():
    return datetime.now(TAIPEI)


def setup_logging(source):
    folder = RUNTIME / 'logs'
    folder.mkdir(parents=True, exist_ok=True)
    handler = TimedRotatingFileHandler(folder / 'civit.log', when='midnight',
                                      backupCount=30, encoding='utf-8')
    formatter = logging.Formatter(f'%(asctime)s %(levelname)s [{source}] %(message)s')
    formatter.converter = lambda stamp: datetime.fromtimestamp(stamp, TAIPEI).timetuple()
    handler.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


class BusyError(RuntimeError):
    pass


class RunLock:
    """OS byte lock; Windows releases it automatically on process termination."""
    def __init__(self, path):
        self.path = Path(path)
        self.file = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = open(self.path, 'a+b')
        self.file.seek(0, os.SEEK_END)
        if self.file.tell() == 0:
            self.file.write(b'0')
            self.file.flush()
        self.file.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close()
            self.file = None
            raise BusyError('工具正在執行或登入中，請稍後再試。') from exc
        return self

    def __exit__(self, *args):
        if self.file:
            self.file.close()


class Store:
    def __init__(self, path=None):
        path = Path(path or RUNTIME / 'state.db')
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=15)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS actions (
                day TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('heart','follow')),
                target TEXT NOT NULL, status TEXT NOT NULL,
                created TEXT NOT NULL, confirmed TEXT,
                PRIMARY KEY(kind, target));
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY, started TEXT NOT NULL, ended TEXT,
                source TEXT NOT NULL, status TEXT NOT NULL, message TEXT NOT NULL);
        ''')
        self.db.commit()

    def close(self):
        self.db.close()

    def bind(self, account):
        account = str(account)
        row = self.db.execute("SELECT value FROM metadata WHERE key='account'").fetchone()
        if row and row[0] != account:
            raise ValueError('登入帳號與本工具綁定帳號不同，已停止以保護既有進度。')
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('account', ?)", (account,))

    def progress(self, day):
        result = dict.fromkeys(TARGETS, 0)
        for kind, count in self.db.execute(
                "SELECT kind,COUNT(*) FROM actions WHERE day=? AND status='confirmed' GROUP BY kind", (day,)):
            result[kind] = count
        return result

    def seen(self, kind, target):
        return self.db.execute('SELECT 1 FROM actions WHERE kind=? AND target=?',
                               (kind, str(target))).fetchone() is not None

    def prepare(self, day, kind, target):
        if kind not in TARGETS:
            raise ValueError('unknown action kind')
        with self.db:
            self.db.execute('INSERT INTO actions VALUES (?,?,?,?,?,NULL)',
                            (day, kind, str(target), 'pending', taipei_now().isoformat()))

    def confirm(self, day, kind, target):
        with self.db:
            self.db.execute("UPDATE actions SET status='confirmed',confirmed=? WHERE day=? AND kind=? AND target=?",
                            (taipei_now().isoformat(), day, kind, str(target)))
        logging.info('confirmed day=%s kind=%s target=%s', day, kind, target)

    def pending(self):
        return self.db.execute("SELECT day,kind,target FROM actions WHERE status='pending' ORDER BY created").fetchall()

    def discard_pending(self, kind, target):
        with self.db:
            self.db.execute("DELETE FROM actions WHERE kind=? AND target=? AND status='pending'", (kind, target))

    def start_run(self, source):
        with self.db:
            # Only called while holding the process lock: no live predecessor exists.
            self.db.execute("UPDATE runs SET status='interrupted',ended=?,message='程序中斷；下次將先核對待確認操作' WHERE ended IS NULL",
                            (taipei_now().isoformat(),))
            cursor = self.db.execute('INSERT INTO runs(started,source,status,message) VALUES (?,?,?,?)',
                                     (taipei_now().isoformat(), source, 'running', '執行中'))
        return cursor.lastrowid

    def end_run(self, run_id, status, message):
        with self.db:
            self.db.execute('UPDATE runs SET ended=?,status=?,message=? WHERE id=?',
                            (taipei_now().isoformat(), status, message, run_id))

    def status(self):
        row = self.db.execute('SELECT started,ended,source,status,message FROM runs ORDER BY id DESC LIMIT 1').fetchone()
        return {'day': taipei_now().date().isoformat(),
                'progress': self.progress(taipei_now().date().isoformat()),
                'pending': len(self.pending()),
                'last_run': dict(zip(('started', 'ended', 'source', 'status', 'message'), row)) if row else None}
