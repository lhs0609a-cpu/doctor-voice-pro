"""서버 인증이 끊겼을 때 작업 루프가 어떻게 끝나는가.

2026-09-23 실측: 실행기의 작업 스레드가 401 을 받고도 60초마다 계속 돌았다. 화면과 홈페이지에는
'자동 발행 실행 중' 초록불이 켜져 있었지만 발행 요청(claim)은 **한 번도 가지 않았다**.
멈추고 알려야 다시 연결해서 이어 갈 수 있다.
"""
import argparse
import asyncio
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent  # noqa: E402
from server_client import ServerError  # noqa: E402


def _args(**over):
    base = dict(server='https://example.invalid', email='a@b.c', password='x',
                profiles_dir='.', log_dir='.', blog=None, once=False, dry_run=True,
                headless=True, window_pos=None, interval=1, max_per_blog=1,
                min_gap=0, max_gap=0, captcha_wait=1, no_images=True, verbose=False,
                stop_event=threading.Event(), device_id='d', device_secret='s')
    base.update(over)
    return argparse.Namespace(**base)


class StopsOnAuthLossTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.calls = 0

    def _patch(self, error):
        async def fake_run_once(client, pool, args):
            self.calls += 1
            raise error

        class FakeJournal:
            def close(self):
                pass

        class FakePool:
            def __init__(self, *a, **k):
                pass

            async def close(self, *a):
                pass

        class FakeClient:
            def __init__(self, *a, **k):
                pass

            def device_login(self, *a, **k):
                return {'access_token': 't'}

            def close(self):
                pass

        class FakePlaywright:
            async def __aenter__(self):
                return object()

            async def __aexit__(self, *a):
                return False

        agent.run_once = fake_run_once
        agent.BrowserPool = FakePool
        agent.ServerClient = FakeClient
        agent.async_playwright = lambda: FakePlaywright()
        return _args(journal=FakeJournal())

    async def test_an_expired_session_stops_the_loop_instead_of_spinning(self):
        args = self._patch(ServerError(401, '인증이 필요합니다'))
        self.assertEqual(await agent.main_async(args), 3)
        self.assertEqual(self.calls, 1)          # 한 번 받고 바로 멈춘다

    async def test_an_ordinary_server_error_keeps_trying(self):
        """서버가 잠깐 흔들린 것은 다시 해 보면 된다 — 인증 문제와 섞지 않는다."""
        args = self._patch(ServerError(500, '서버 오류'))

        async def fake_run_once(client, pool, args):
            self.calls += 1
            if self.calls >= 2:          # 두 번째까지 돌았으면 충분하다
                args.stop_event.set()
            raise ServerError(500, '서버 오류')

        agent.run_once = fake_run_once
        args.interval = 0
        self.assertEqual(await agent.main_async(args), 0)
        self.assertEqual(self.calls, 2)


if __name__ == '__main__':
    unittest.main()
