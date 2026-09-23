"""예약을 걸면 기다리지 말고 지금 네이버 예약을 걸러 간다.

작업 루프는 한 바퀴 돌고 나면 다음 주기까지 쉰다. 그동안 사용자가 홈페이지에서 예약을 걸면
'예약했는데 왜 가만히 있냐'가 된다. 홈페이지가 이 PC의 창구를 두드리면 그 잠을 깨운다.
"""
import argparse
import asyncio
import json
import sys
import threading
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent  # noqa: E402
import local_bridge  # noqa: E402
from local_bridge import LocalBridge  # noqa: E402


class WakeTheLoopTest(unittest.IsolatedAsyncioTestCase):
    async def test_the_pause_ends_the_moment_a_new_booking_arrives(self):
        args = argparse.Namespace(stop_event=threading.Event(), wake_event=threading.Event())

        async def wake_soon():
            await asyncio.sleep(0.2)
            args.wake_event.set()

        task = asyncio.create_task(wake_soon())
        started = asyncio.get_running_loop().time()
        await agent.interruptible_pause(30, args)       # 30초를 기다릴 참이었다
        waited = asyncio.get_running_loop().time() - started
        await task
        self.assertLess(waited, 3, f'{waited:.1f}초나 기다렸다')

    async def test_an_untouched_pause_still_waits(self):
        args = argparse.Namespace(stop_event=threading.Event(), wake_event=threading.Event())
        started = asyncio.get_running_loop().time()
        await agent.interruptible_pause(0.5, args)
        self.assertGreaterEqual(asyncio.get_running_loop().time() - started, 0.4)


class BridgeWakeTest(unittest.TestCase):
    def setUp(self):
        # 이 PC에서 진짜 실행기가 돌고 있으면 정해진 포트를 이미 쥐고 있다(윈도우는 같은 포트에
        # 또 붙는 것을 막지 않아 요청이 그쪽으로 간다). 테스트는 빈 포트를 받아서 쓴다.
        self._ports = local_bridge.PORTS
        local_bridge.PORTS = (0,)

    def tearDown(self):
        local_bridge.PORTS = self._ports

    def test_the_homepage_can_knock_and_the_launcher_answers(self):
        called = []

        def wake():
            called.append(True)
            return True, '바로 확인하러 갑니다'

        bridge = LocalBridge(status=lambda: {'ok': True}, pair=lambda code: (True, '', {}), wake=wake)
        port = bridge.start()
        self.assertIsNotNone(port, '창구를 열지 못했습니다')
        try:
            request = urllib.request.Request(f'http://127.0.0.1:{port}/wake', data=b'{}',
                                             headers={'Content-Type': 'application/json',
                                                      'Origin': 'https://doctor-voice-pro-ghwi.vercel.app'},
                                             method='POST')
            with urllib.request.urlopen(request, timeout=5) as response:
                body = json.loads(response.read())
            self.assertTrue(body['ok'])
            self.assertEqual(called, [True])
        finally:
            bridge.stop()

    def test_a_launcher_without_the_wake_door_says_not_found(self):
        """옛 실행기에는 이 창구가 없다 — 홈페이지는 조용히 넘어가고 다음 주기를 기다린다."""
        bridge = LocalBridge(status=lambda: {'ok': True}, pair=lambda code: (True, '', {}))
        port = bridge.start()
        try:
            request = urllib.request.Request(f'http://127.0.0.1:{port}/wake', data=b'{}',
                                             headers={'Content-Type': 'application/json',
                                                      'Origin': 'https://doctor-voice-pro-ghwi.vercel.app'},
                                             method='POST')
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request, timeout=5)
            self.assertEqual(caught.exception.code, 404)
        finally:
            bridge.stop()


if __name__ == '__main__':
    unittest.main()
