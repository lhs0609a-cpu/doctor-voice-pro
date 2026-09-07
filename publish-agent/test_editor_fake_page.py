"""NaverEditor 를 로컬 가짜 SmartEditor 페이지(fake_editor/)에 대해 실제 브라우저로 돌려 본다.

    python test_editor_fake_page.py

네이버 접속 없음. 번들 Chromium(또는 크롬)이 없으면 전체 건너뜀.
검증하는 것: #mainFrame 프레임 탐지, 드래프트 팝업 취소, blogId 읽기, 키보드 insertText 로 제목/본문,
문단당 1회 Ctrl+B, 파일 선택창 가로채기 이미지 삽입 + 컴포넌트 증가 확인, 공개/검색/카테고리/태그,
예약 라디오 + datepicker 월 이동 + React 제어 select 설정·검증, 발행 후 레이어 닫힘 판정,
그리고 datepicker 가 안 뜨면 ScheduleError 로 발행 버튼이 눌리지 않는 것.
"""
from __future__ import annotations

import asyncio
import base64
import functools
import sys
import threading
import unittest
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from naver_editor import EditorError, NaverEditor, ScheduleError  # noqa: E402

JPEG_1PX = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
)
DATA_URL = "data:image/jpeg;base64," + base64.b64encode(JPEG_1PX).decode()

BLOCKS = [
    {"type": "text", "content": "임플란트 상담은 임플란트 전문의에게 받으세요. 두 번째 문장입니다. 세 번째 문장입니다."},
    {"type": "image", "image": DATA_URL},
    {"type": "text", "content": "사진 뒤 문단입니다. 임플란트 다시 언급."},
]


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def _browser_available() -> bool:
    async def probe():
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            try:
                b = await p.chromium.launch(headless=True)
                await b.close()
                return True
            except Exception:  # noqa: BLE001
                return False

    return asyncio.run(probe())


@unittest.skipUnless(_browser_available(), "Playwright Chromium 이 설치되지 않았습니다 (playwright install chromium)")
class TestEditorOnFakePage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = functools.partial(_Quiet, directory=str(HERE / "fake_editor"))
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _run(self, coro):
        return asyncio.run(coro)

    async def _with_editor(self, query, fn):
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1280, "height": 900})
            try:
                ed = NaverEditor(page, write_url=f"{self.base}/write.html{query}")
                return await fn(ed, page)
            finally:
                await browser.close()

    async def _state(self, ed):
        f = await ed.frame()
        return await f.evaluate("() => window.__state")

    # ------------------------------------------------------------ 전체 흐름
    def test_full_flow_schedules_correctly(self):
        async def body(ed: NaverEditor, page):
            await ed.open_write_page()
            f = await ed.frame()
            self.assertNotEqual(f, page.main_frame, "에디터는 #mainFrame 안에 있어야 한다")
            self.assertTrue(await ed.dismiss_draft_popup())
            self.assertEqual(await ed.read_blog_id(), "testblog")

            await ed.set_title("테스트 제목입니다")
            n = await ed.insert_body_blocks(BLOCKS, ["임플란트"])
            self.assertEqual(n, 1)

            await ed.open_publish_layer()
            await ed.set_open_type("public")
            await ed.set_search_allow(False)
            await ed.set_category("24")
            self.assertEqual(await ed.set_tags(["#임플란트", "치과 상담"]), 2)
            await ed.set_schedule(datetime(2026, 11, 5, 14, 37))

            out = await ed.publish()
            self.assertIsNotNone(out)
            self.assertTrue(out.ok, out.message)
            self.assertFalse(out.uncertain)
            return await self._state(ed)

        st = self._run(self._with_editor("", body))
        pub = st["published"]
        self.assertIsNotNone(pub, "발행 버튼이 눌려야 한다")
        self.assertEqual(st["draft"], "cancel")
        self.assertEqual(pub["title"], "테스트 제목입니다")
        self.assertEqual(pub["openType"], "open_public")
        self.assertFalse(pub["search"])
        self.assertEqual(pub["category"], "임플란트 칼럼")
        self.assertEqual(pub["tags"], ["임플란트", "치과 상담"])
        self.assertTrue(pub["reserve"])
        self.assertEqual(pub["date"], "2026. 11. 05")
        self.assertEqual((pub["hour"], pub["minute"]), ("14", "30"), "분은 10분 단위 내림")
        self.assertEqual(pub["images"], 1)
        self.assertEqual(st["imageFiles"], 1, "파일 선택창 경로로 업로드")
        self.assertEqual(st["lastImage"]["type"], "image/jpeg")
        self.assertEqual(st["lastImage"]["size"], len(JPEG_1PX))
        # 본문: 모바일 포맷(한 줄 한 문장, 두 문장마다 빈 줄) + 굵게 1회/문단 + 사진 뒤 문단이 이미지 뒤에
        text = pub["bodyText"]
        self.assertIn("임플란트 상담은 임플란트 전문의에게 받으세요.", text)
        self.assertIn("세 번째 문장입니다.", text)
        self.assertIn("사진 뒤 문단입니다.", text)
        self.assertLess(text.index("세 번째 문장입니다."), text.index("사진 뒤 문단입니다."))
        html = pub["bodyHtml"]
        self.assertTrue("<b>임플란트</b>" in html or "font-weight: bold" in html or "<strong>임플란트</strong>" in html, html[:300])
        self.assertEqual(html.count("<b>임플란트</b>") + html.count("<strong>임플란트</strong>"), 2, "문단(블록)당 1회씩 두 번")
        # 사진 뒤 문단이 이미지 다음 컴포넌트에 들어갔는지(첫 문단 HTML 에는 없어야 한다)
        first_para = html.split("<!--PARA-->")[0]
        self.assertNotIn("사진 뒤 문단", first_para)

    # ------------------------------------------------------------ 예약 실패 → 발행 금지
    def test_datepicker_missing_raises_before_publish(self):
        async def body(ed: NaverEditor, page):
            await ed.open_write_page()
            await ed.dismiss_draft_popup()
            await ed.set_title("예약 실패 케이스")
            await ed.insert_body_blocks([{"type": "text", "content": "본문."}], [])
            await ed.open_publish_layer()
            with self.assertRaises(ScheduleError):
                await ed.set_schedule(datetime(2026, 11, 5, 14, 30))
            return await self._state(ed)

        st = self._run(self._with_editor("?breakdate=1", body))
        self.assertIsNone(st["published"], "예약 실패 시 발행 버튼은 절대 눌리면 안 된다")

    def test_past_date_is_disabled(self):
        async def body(ed: NaverEditor, page):
            await ed.open_write_page()
            await ed.dismiss_draft_popup()
            await ed.open_publish_layer()
            with self.assertRaises(ScheduleError):
                await ed.set_schedule(datetime(2026, 9, 1, 10, 0))  # 가짜 페이지의 '오늘'은 2026-09-03
            return await self._state(ed)

        st = self._run(self._with_editor("", body))
        self.assertIsNone(st["published"])

    def test_missing_category_raises(self):
        async def body(ed: NaverEditor, page):
            await ed.open_write_page()
            await ed.dismiss_draft_popup()
            await ed.open_publish_layer()
            with self.assertRaises(EditorError) as cm:
                await ed.set_category("없는 카테고리")
            self.assertIn("사용 가능한 카테고리", str(cm.exception))
            self.assertIn("공지(7)", str(cm.exception))
            return await self._state(ed)

        st = self._run(self._with_editor("", body))
        self.assertIsNone(st["published"])

    def test_dry_run_does_not_click_publish(self):
        async def body(ed: NaverEditor, page):
            await ed.open_write_page()
            await ed.dismiss_draft_popup()
            await ed.open_publish_layer()
            await ed.set_schedule(datetime(2026, 9, 3, 23, 50))
            self.assertIsNone(await ed.publish(dry_run=True))
            return await self._state(ed)

        st = self._run(self._with_editor("", body))
        self.assertIsNone(st["published"])

    def test_drop_fallback_when_no_toolbar_button(self):
        async def body(ed: NaverEditor, page):
            await ed.open_write_page()
            await ed.dismiss_draft_popup()
            f = await ed.frame()
            await f.evaluate("() => document.getElementById('imgbtn').remove()")
            n = await ed.insert_body_blocks([{"type": "text", "content": "앞."}, {"type": "image", "image": DATA_URL}], [])
            self.assertEqual(n, 1)
            return await self._state(ed)

        st = self._run(self._with_editor("", body))
        self.assertEqual(st["imageDrops"], 1, "툴바 버튼이 없으면 합성 드롭으로 폴백")
        self.assertEqual(st["imageFiles"], 0)


# ================================================================ agent.run_once 엔드투엔드 (가짜 서버 + 가짜 에디터)
@unittest.skipUnless(_browser_available(), "Playwright Chromium 이 설치되지 않았습니다 (playwright install chromium)")
class TestAgentEndToEnd(unittest.TestCase):
    """summary → 프로필 브라우저 → 로그인 확인 → blogId 대조 → claim → 글 작성/예약 → result 보고."""

    @classmethod
    def setUpClass(cls):
        import os
        import tempfile
        from datetime import timedelta

        from test_dryrun_offline import FakeHandler, FakeState

        handler = functools.partial(_Quiet, directory=str(HERE / "fake_editor"))
        cls.pages = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=cls.pages.serve_forever, daemon=True).start()
        cls.state = FakeState()
        cls.state.blog_id = "testblog"  # 가짜 에디터 iframe 의 blogId 와 일치
        cls.state.schedule = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT14:37")
        FakeHandler.state = cls.state
        cls.api = ThreadingHTTPServer(("127.0.0.1", 0), FakeHandler)
        threading.Thread(target=cls.api.serve_forever, daemon=True).start()
        cls.tmp = tempfile.mkdtemp(prefix="dv-agent-test-")
        os.environ["DV_WRITE_URL"] = f"http://127.0.0.1:{cls.pages.server_address[1]}/write.html"

    @classmethod
    def tearDownClass(cls):
        import os
        import shutil

        cls.pages.shutdown()
        cls.api.shutdown()
        os.environ.pop("DV_WRITE_URL", None)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _args(self, **over):
        import agent

        argv = ["--server", f"http://127.0.0.1:{self.api.server_address[1]}", "--email", "a@b.c", "--password", "pw",
                "--once", "--headless", "true", "--profiles-dir", self.tmp, "--log-dir", self.tmp, "--min-gap", "0", "--max-gap", "0"]
        for k, v in over.items():
            argv.append("--" + k.replace("_", "-"))
            if v is not True:
                argv.append(str(v))
        return agent.build_parser().parse_args(argv)

    def _run_once(self, args):
        import agent
        from playwright.async_api import async_playwright
        from server_client import ServerClient

        async def go():
            client = ServerClient(args.server)
            client.login(args.email, args.password)
            async with async_playwright() as pw:
                pool = agent.BrowserPool(pw, Path(args.profiles_dir), headless=True, window_pos=None)
                try:
                    await agent.run_once(client, pool, args)
                finally:
                    await pool.close()
                    client.close()

        self.state.requests.clear()
        asyncio.run(go())
        return [r for r in self.state.requests if r["path"].endswith("/result")]

    def test_dry_run_reports_without_publishing(self):
        results = self._run_once(self._args(dry_run=True))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["body"]["lock_token"], "L1")
        self.assertEqual((results[0]["body"]["ok"], results[0]["body"]["uncertain"], results[0]["body"]["message"]), (False, False, "dry-run"))
        paths = [r["path"] for r in self.state.requests]
        self.assertIn("/api/v1/campaign/agent/summary", paths)
        self.assertIn("/api/v1/campaign/agent/claim", paths)
        self.assertNotIn("/api/v1/campaign/blogs/b1/status", paths, "정상 로그인이면 블로그 상태를 건드리지 않는다")

    def test_real_run_reports_published(self):
        results = self._run_once(self._args())
        self.assertEqual(len(results), 1)
        b = results[0]["body"]
        self.assertTrue(b["ok"], b)
        self.assertFalse(b["uncertain"])

    def test_blog_mismatch_marks_login_required_and_claims_nothing(self):
        self.state.blog_id = "someoneelse"
        try:
            results = self._run_once(self._args())
        finally:
            self.state.blog_id = "testblog"
        self.assertEqual(results, [])
        status = [r for r in self.state.requests if r["path"].endswith("/status")]
        self.assertEqual(len(status), 1)
        self.assertEqual(status[0]["body"]["status"], "login_required")
        self.assertIn("testblog", status[0]["body"]["reason"])
        self.assertNotIn("/api/v1/campaign/agent/claim", [r["path"] for r in self.state.requests])


if __name__ == "__main__":
    unittest.main(verbosity=2)
