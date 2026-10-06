import asyncio
import tempfile
from pathlib import Path
import unittest
from journal import Journal, flush
from server_client import ServerError


class Client:
    def __init__(self):
        self.calls = []
        self.fail = False          # True 면 전송 자체가 끊긴다
        self.refuse = None         # ServerError 로 돌려줄 상태 코드

    def report_result(self, job_id, token, **report):
        self.calls.append((job_id, token, report))
        if self.fail:
            raise ConnectionError('ACK lost')
        if self.refuse:
            raise ServerError(self.refuse, '결과를 적용할 수 없는 작업 상태입니다')
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
            # 연결이 끊겨도 flush 는 터지지 않는다 — 터지면 run_once 가 첫 줄에서 죽어
            # 그 바퀴에는 발행이 한 건도 돌지 않는다. 기록은 쥔 채 다음 바퀴로 넘긴다.
            asyncio.run(flush(journal, client))
            self.assertEqual(len(journal.pending()), 1)
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

    def test_unapplicable_result_is_dropped_not_retried_forever(self):
        """서버가 영영 받지 않을 기록(409)은 버린다.

        쥐고 있으면 flush 가 매 바퀴 같은 자리에서 멈춰, 그 PC 는 계정을 바꿔도 블로그를
        바꿔도 한 건도 올리지 못한다(2026-10-06 사용자 신고)."""
        for status in (400, 404, 409):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                journal = Journal(Path(tmp) / 'outbox.db')
                journal.start({'id': 'job', 'lock_token': 'token'})
                journal.save_result('token', {'ok': True})
                client = Client()
                client.refuse = status
                asyncio.run(flush(journal, client))          # 터지지 않는다
                self.assertEqual(journal.pending(), [])      # 그리고 다시 시도하지 않는다
                journal.close()

    def test_server_hiccup_keeps_the_record(self):
        """잠깐 밀어낸 것(429)이나 서버 오류(5xx)는 기록을 쥔 채 다음 바퀴에 다시 올린다."""
        for status in (429, 503):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                journal = Journal(Path(tmp) / 'outbox.db')
                journal.start({'id': 'job', 'lock_token': 'token'})
                journal.save_result('token', {'ok': True})
                client = Client()
                client.refuse = status
                asyncio.run(flush(journal, client))
                self.assertEqual(len(journal.pending()), 1)
                client.refuse = None
                asyncio.run(flush(journal, client))
                self.assertEqual(journal.pending(), [])
                journal.close()

    def test_auth_loss_still_stops_the_loop(self):
        """인증이 끊긴 것은 숨기지 않는다 — 바깥 루프가 멈추고 '다시 연결하라'고 알려야 한다."""
        with tempfile.TemporaryDirectory() as tmp:
            journal = Journal(Path(tmp) / 'outbox.db')
            journal.start({'id': 'job', 'lock_token': 'token'})
            journal.save_result('token', {'ok': True})
            client = Client()
            client.refuse = 401
            with self.assertRaises(ServerError):
                asyncio.run(flush(journal, client))
            self.assertEqual(len(journal.pending()), 1)
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
