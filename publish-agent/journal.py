"""Local durable checkpoints and result outbox; never stores browser credentials."""
import json
import sqlite3
from pathlib import Path


class Journal:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # One owner per profiles directory; another process must not recover a
        # journal whose writer is still actively working.
        self.lock = open(Path(path).parent / '.agent.lock', 'a+b')
        try:
            import os
            self.lock.seek(0)
            if os.name == 'nt':
                import msvcrt
                if self.lock.read(1) == b'':
                    self.lock.write(b'0')
                    self.lock.flush()
                self.lock.seek(0)
                msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock.close()
            raise RuntimeError('이 프로필 폴더에서 다른 실행기가 이미 동작 중입니다')
        self.db = sqlite3.connect(str(path))
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS attempts (token TEXT PRIMARY KEY, job_id TEXT NOT NULL, stage TEXT NOT NULL, report TEXT)")
        self.db.commit()

    def start(self, job):
        with self.db:
            self.db.execute("INSERT INTO attempts VALUES (?, ?, 'editing', NULL)", (job['lock_token'], job['id']))

    def finalizing(self, token):
        with self.db:
            self.db.execute("UPDATE attempts SET stage='finalizing' WHERE token=?", (token,))

    def save_result(self, token, report):
        with self.db:
            self.db.execute("UPDATE attempts SET report=? WHERE token=?", (json.dumps(report, ensure_ascii=False), token))

    def pending(self):
        return list(self.db.execute("SELECT token, job_id, stage, report FROM attempts ORDER BY rowid"))

    def acknowledge(self, token):
        with self.db:
            self.db.execute("DELETE FROM attempts WHERE token=?", (token,))

    def close(self):
        self.db.close()
        self.lock.close()


async def flush(journal, client):
    """Persist recovery decisions before transport. A failed ACK never retypes."""
    import asyncio
    for token, job_id, stage, serialized in journal.pending():
        report = json.loads(serialized) if serialized else {
            'ok': False, 'uncertain': stage == 'finalizing',
            'release': stage != 'finalizing', 'message': '실행기 재시작 후 복구',
        }
        journal.save_result(token, report)
        await asyncio.to_thread(client.report_result, job_id, token, **report)
        journal.acknowledge(token)
