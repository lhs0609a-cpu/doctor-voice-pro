import asyncio
import tempfile
from pathlib import Path
import unittest
from journal import Journal, flush


class Client:
    def __init__(self):
        self.calls = []
        self.fail = False

    def report_result(self, job_id, token, **report):
        self.calls.append((job_id, token, report))
        if self.fail:
            raise ConnectionError('ACK lost')
        return {'success': True}


class JournalTests(unittest.TestCase):
    def test_lost_ack_replays_identical_result_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'outbox.db'
            journal = Journal(path)
            journal.start({'id': 'job', 'lock_token': 'token'})
            journal.save_result('token', {'ok': True, 'url': 'https://blog.naver.com/test/123'})
            client = Client()
            client.fail = True
            with self.assertRaises(ConnectionError):
                asyncio.run(flush(journal, client))
            journal.close()
            journal = Journal(path)
            client.fail = False
            asyncio.run(flush(journal, client))
            self.assertEqual(client.calls[0], client.calls[1])
            self.assertEqual(journal.pending(), [])
            journal.close()

    def test_restart_before_and_after_finalizing(self):
        for finalizing in (False, True):
            with self.subTest(finalizing=finalizing), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'outbox.db'
                journal = Journal(path)
                journal.start({'id': 'job', 'lock_token': 'token'})
                if finalizing:
                    journal.finalizing('token')
                journal.close()
                journal = Journal(path)
                client = Client()
                asyncio.run(flush(journal, client))
                report = client.calls[0][2]
                self.assertEqual(report['uncertain'], finalizing)
                self.assertEqual(report['release'], not finalizing)
                journal.close()

    def test_second_process_owner_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Journal(Path(tmp) / 'outbox.db')
            try:
                with self.assertRaises(RuntimeError):
                    Journal(Path(tmp) / 'second.db')
            finally:
                journal.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
