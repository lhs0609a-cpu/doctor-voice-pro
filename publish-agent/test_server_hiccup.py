"""서버가 잠깐 내려가 있어도 실행기는 흔들리지 않는다.

2026-10-21 13:29 신고: 위례 원고를 올리던 중 "블로그 'compete3651' 처리 중 오류: HTTP 502" 가
나고 크롬 창이 저절로 닫혔다. 서버가 메모리 부족으로 죽었다가 약 20초 뒤 다시 뜬 사이였다.
- 그 사이의 요청은 기다렸다 다시 보낸다(서버 클라이언트).
- 그래도 안 되면 그 블로그만 다음 바퀴로 미루고, 멀쩡한 크롬 창은 닫지 않는다(run_once).
"""
import argparse
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent  # noqa: E402
import journal  # noqa: E402
import server_client  # noqa: E402
from server_client import ServerClient, ServerError  # noqa: E402


def _client(statuses):
    """보낼 때마다 statuses 를 차례로 돌려주는 서버. 몇 번 불렸는지 센다."""
    seen = []

    def handler(request):
        seen.append(request.url.path)
        status = statuses[min(len(seen), len(statuses)) - 1]
        return httpx.Response(status, json={"detail": "x"} if status >= 400 else [])

    client = ServerClient("https://example.invalid")
    client._http = httpx.Client(transport=httpx.MockTransport(handler))
    return client, seen


class RetryTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(server_client.time, "sleep")   # 실제로 기다리지 않는다
        self.sleep = patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_502_while_the_server_restarts_is_waited_out(self):
        client, seen = _client([502, 502, 200])
        self.assertEqual(client.summary(), [])
        self.assertEqual(len(seen), 3)

    def test_it_gives_up_after_a_while_and_says_why(self):
        client, seen = _client([503])
        with self.assertRaises(ServerError) as caught:
            client.summary()
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(len(seen), len(server_client.RETRY_WAITS) + 1)

    def test_an_ordinary_refusal_is_not_repeated(self):
        """서버가 '안 된다'고 답한 것은 다시 물어도 같다 — 바로 올려 보낸다."""
        client, seen = _client([400])
        with self.assertRaises(ServerError):
            client.summary()
        self.assertEqual(len(seen), 1)
        self.sleep.assert_not_called()


class KeepsTheWindowTest(unittest.IsolatedAsyncioTestCase):
    async def _run(self, error):
        closed = []

        class Pool:
            async def close(self, key=None):
                closed.append(key)

        class Client:
            def summary(self):
                return [{"blog_ref_id": "r", "naver_blog_id": "compete3651", "label": "위례",
                         "status": "active", "pending": 1}]

        async def failing_blog(*a, **k):
            raise error

        async def no_cafe(*a, **k):
            return 0

        async def no_flush(*a, **k):
            return None

        args = argparse.Namespace(blog=None, journal=None, stop_event=threading.Event())
        with mock.patch.object(agent, "process_blog", failing_blog), \
                mock.patch.object(agent, "process_cafe", no_cafe), \
                mock.patch.object(journal, "flush", no_flush):
            await agent.run_once(Client(), Pool(), args)
        return closed

    async def test_a_server_outage_leaves_chrome_open(self):
        self.assertEqual(await self._run(ServerError(502, "")), [])

    async def test_a_browser_failure_still_resets_that_window(self):
        """크롬 쪽이 터진 것은 예전처럼 창을 닫고 다음 바퀴에 새로 연다."""
        self.assertEqual(await self._run(RuntimeError("page crashed")), ["compete3651"])


if __name__ == "__main__":
    unittest.main()
