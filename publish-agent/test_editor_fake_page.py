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

    # ------------------------------------------------------- 예약 글 목록 읽기
    def test_reads_the_reservation_list(self):
        """예약 목록에서 (시각, 제목)을 읽는다. 날짜 표기가 섞여 있어도 읽혀야 한다."""
        async def body(ed: NaverEditor, page):
            return await ed.read_reservations("testblog", urls=[f"{self.base}/reserve.html"])

        rows = self._run(self._with_editor("", body))
        self.assertEqual([r["at"] for r in rows], [
            datetime(2026, 9, 23, 14, 30), datetime(2026, 9, 25, 18, 0), datetime(2026, 9, 26, 9, 10)])
        self.assertEqual(rows[0]["title"], "아토피 초기 증상 확인법")

    def test_reads_the_reservation_list_from_the_write_screen(self):
        """관리자 주소를 몰라도 읽는다 — 글쓰기 화면의 '예약 발행 N건' 칩이 진짜 목록이다.

        추측한 관리자 주소는 실제로 한 번도 열리지 않았다(2026-09-23 실측). 칩은 우리가 이미
        열어 둔 화면에 있으니 주소를 맞힐 필요가 없다."""
        async def body(ed: NaverEditor, page):
            return await ed.read_reservations("testblog")

        rows = self._run(self._with_editor("", body))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["title"], "예약 글 1")

    def test_a_write_screen_saying_zero_is_zero_not_unknown(self):
        async def body(ed: NaverEditor, page):
            return await ed.read_reservations("testblog")

        self.assertEqual(self._run(self._with_editor("?reserve=0", body)), [])

    def test_reading_fewer_rows_than_the_chip_claims_is_treated_as_unread(self):
        """3건이라는데 2줄만 읽혔다면 '다 읽었다'고 하면 안 된다.

        못 읽은 자리를 빈 자리로 알면 같은 시각에 또 걸린다 — 저품질의 지름길이다.
        여기서는 관리자 주소로도 못 읽게 두었으므로 결과는 None(못 읽음)이어야 한다."""
        async def body(ed: NaverEditor, page):
            return await ed.read_reservations("testblog")

        self.assertIsNone(self._run(self._with_editor("?reserve=3&reservebad=1", body)))

    def test_empty_list_is_zero_not_a_failure(self):
        """'예약된 글이 없습니다' 는 0건이다. 못 읽음(None)과 섞이면 남의 자리에 겹쳐 잡는다."""
        async def body(ed: NaverEditor, page):
            return await ed.read_reservations("testblog", urls=[f"{self.base}/reserve.html?empty=1"])

        self.assertEqual(self._run(self._with_editor("", body)), [])

    def test_unreadable_screen_returns_none(self):
        async def body(ed: NaverEditor, page):
            return await ed.read_reservations("testblog", urls=[f"{self.base}/reserve.html?broken=1"])

        self.assertIsNone(self._run(self._with_editor("", body)))

    def test_falls_back_to_the_next_candidate_url(self):
        """첫 주소가 죽어 있어도 다음 후보에서 읽으면 된다(네이버가 주소를 바꿔도 버틴다)."""
        async def body(ed: NaverEditor, page):
            return await ed.read_reservations("testblog", urls=[
                f"{self.base}/no-such-page.html", f"{self.base}/reserve.html"])

        self.assertEqual(len(self._run(self._with_editor("", body))), 3)

    # ------------------------------------------------------------ 발행 뒤 글 주소
    def test_publish_harvests_post_url_from_completion_toast(self):
        # 완료 안내창에 글 링크가 뜨면 그 번호를 가져온다 → 서버가 '주소로 확인된 예약'으로 처리
        async def body(ed: NaverEditor, page):
            await ed.open_write_page()
            await ed.dismiss_draft_popup()
            await ed.set_title("주소 수확")
            await ed.open_publish_layer()
            await ed.set_schedule(datetime(2026, 11, 5, 14, 37))
            return await ed.publish()

        out = self._run(self._with_editor("?postlink=1", body))
        self.assertTrue(out.ok, out.message)
        self.assertEqual(out.url, "https://blog.naver.com/testblog/223456789012")

    def test_publish_waits_for_the_photo_to_finish_uploading(self):
        """사진이 '전송중'인 동안에는 발행 레이어로 넘어가지 않는다.

        컴포넌트가 생긴 것만 보고 넘어가면 전송이 끝나기 전에 발행돼 사진이 빠진 글이 나간다
        (2026-09-21 실측: 실제 네이버에서 움짤이 0/1 인 채로 발행 단계로 넘어갔다)."""
        async def body(ed: NaverEditor, page):
            await ed.open_write_page()
            await ed.dismiss_draft_popup()
            await page.evaluate("() => { window.__uploadDelayMs = 2500; }")
            f = await ed.frame()
            await f.evaluate("() => { window.__uploadDelayMs = 2500; }")
            await ed.set_title("전송 중 발행 금지")
            await ed.insert_body_blocks(BLOCKS, [])
            during = await f.evaluate(
                "() => document.querySelectorAll('.se-component.se-image .se-image-uploading').length")
            await ed.open_publish_layer()
            after = await f.evaluate(
                "() => document.querySelectorAll('.se-component.se-image .se-image-uploading').length")
            settled = await f.evaluate(
                "() => [...document.querySelectorAll('.se-component.se-image img')].length")
            return during, after, settled

        during, after, settled = self._run(self._with_editor("", body))
        self.assertEqual(during, 0, "본문 삽입이 끝났는데 아직 '전송중'인 사진이 남아 있다")
        self.assertEqual(after, 0, "'전송중'인 사진이 남은 채 발행 레이어를 열었다")
        self.assertEqual(settled, 1)

    def test_normalize_post_url(self):
        from naver_editor import normalize_post_url
        self.assertEqual(normalize_post_url("https://blog.naver.com/abc_1/223456789012?x=1"), "https://blog.naver.com/abc_1/223456789012")
        self.assertEqual(normalize_post_url("https://blog.naver.com/PostView.naver?blogId=abc&logNo=223456789012"), "https://blog.naver.com/abc/223456789012")
        self.assertIsNone(normalize_post_url("https://blog.naver.com/abc"))
        self.assertIsNone(normalize_post_url(None))

    # ------------------------------------------------------------ 제목
    def test_title_retried_when_late_popup_steals_focus(self):
        # 늦게 뜬 '작성 중인 글' 팝업이 입력을 가로채도 팝업을 닫고 제목을 다시 넣는다
        from naver_editor import JS_READ_TEXT, S

        async def body(ed: NaverEditor, page):
            await ed.open_write_page()
            await ed.dismiss_draft_popup()          # 이때는 아직 팝업이 없다
            await ed.set_title("늦은 팝업 제목")
            f = await ed.frame()
            return await self._state(ed), await f.evaluate(JS_READ_TEXT, S["title_para"])

        st, title = self._run(self._with_editor("?latedraft=1", body))
        self.assertEqual(st["draft"], "cancel")
        self.assertIn("늦은 팝업 제목", title)

    # ------------------------------------------------------------ 캡차 판별
    def test_hidden_captcha_frame_is_not_a_captcha(self):
        # 실제 네이버처럼 0x0 ncaptcha 프레임이 늘 있어도 글쓰기는 열려야 한다(2026-09-11 실측 오판)
        async def body(ed: NaverEditor, page):
            await ed.open_write_page()
            return await ed.detect_captcha()

        self.assertFalse(self._run(self._with_editor("", body)))

    def test_visible_captcha_still_stops(self):
        from naver_editor import CaptchaDetected

        async def body(ed: NaverEditor, page):
            with self.assertRaises(CaptchaDetected):
                await ed.open_write_page()
            return True

        self.assertTrue(self._run(self._with_editor("?captcha=1", body)))

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

    def test_reads_category_list_and_leaves_the_layer_as_it_found_it(self):
        """앱 드롭다운 채우기 — 목록만 읽고 카테고리를 바꾸지 않는다."""
        async def body(ed: NaverEditor, page):
            await ed.open_write_page()
            await ed.dismiss_draft_popup()
            await ed.open_publish_layer()
            items = await ed.read_categories()
            self.assertEqual(items, [{"id": "24", "name": "임플란트 칼럼"}, {"id": "7", "name": "공지"}])
            frame = await ed.frame()
            expanded = await frame.evaluate(
                "() => document.querySelector('[data-click-area=\"tpb*i.category\"]').getAttribute('aria-expanded')")
            self.assertEqual(expanded, "false")  # 우리가 열었으면 다시 닫는다
            return await self._state(ed)

        st = self._run(self._with_editor("", body))
        self.assertEqual(st["category"], "기본")   # 목록만 읽었으므로 선택은 그대로
        self.assertIsNone(st["published"])

    def test_saves_a_draft_without_publishing(self):
        async def body(ed: NaverEditor, page):
            await ed.open_write_page()
            await ed.dismiss_draft_popup()
            await ed.set_title("임시저장 글")
            out = await ed.save_draft()
            self.assertTrue(out.ok)
            return await self._state(ed)

        st = self._run(self._with_editor("", body))
        self.assertIsNone(st["published"])
        self.assertEqual(st["saved"], 1)

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

    def test_landing_check_requires_matching_clickable_anchor(self):
        from naver_editor import EditorError
        async def body(ed, page):
            await ed.open_write_page()
            f = await ed.frame()
            await f.evaluate('''() => {
                const a = document.createElement('a');
                a.href = 'https://example.com/info?utm_content=one';
                a.textContent = '안내';
                document.querySelector('.se-component.se-text').appendChild(a);
            }''')
            await ed.verify_links(['https://example.com/info?utm_content=one'])
            with self.assertRaises(EditorError):
                await ed.verify_links(['https://example.com/info?utm_content=other'])
        self._run(self._with_editor('', body))


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
                "--once", "--max-per-blog", "1", "--headless", "true", "--profiles-dir", self.tmp, "--log-dir", self.tmp, "--min-gap", "0", "--max-gap", "0"]
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
            from journal import Journal
            args.journal = Journal(Path(self.tmp) / 'test-journal.sqlite3')
            client = ServerClient(args.server)
            client.login(args.email, args.password)
            async with async_playwright() as pw:
                pool = agent.BrowserPool(pw, Path(args.profiles_dir), headless=True, window_pos=None)
                try:
                    await agent.run_once(client, pool, args)
                finally:
                    await pool.close()
                    client.close()
                    args.journal.close()

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
