"""네이버 없이 도는 테스트.

    python test_dryrun_offline.py

- plan.py: 예약 분 10분 내림, 블록→타이핑 계획, data URL 디코드, 모바일 포맷 멱등성
- server_client.py: 로컬 가짜 서버(http.server)에 대한 요청 경로/메서드/본문/헤더 모양, 401 재로그인
- agent.run_job: 대역 에디터로 '예약 설정 실패 → 발행 클릭 금지', dry-run 은 발행 클릭 없음
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
import threading
import time
import unittest
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from plan import (  # noqa: E402
    Op,
    decode_data_url,
    ext_for_mime,
    floor_minute,
    merge_text_ops,
    mobile_format,
    nospace_len,
    split_paragraphs,
    PARA_MAX_CHARS,
    PARA_MIN_CHARS,
    NUMBERS_PER_PARAGRAPH,
    parse_schedule,
    pick_emphasize,
    plan_blocks,
    plan_text,
    schedule_is_safe,
)
from server_client import ServerClient, ServerError  # noqa: E402

JPEG_1PX = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
)
DATA_URL = "data:image/jpeg;base64," + base64.b64encode(JPEG_1PX).decode()


# ================================================================ plan.py
class TestSchedule(unittest.TestCase):
    def test_floor_minute(self):
        self.assertEqual(floor_minute(datetime(2026, 9, 10, 14, 37, 22)).minute, 30)
        self.assertEqual(floor_minute(datetime(2026, 9, 10, 14, 0)).minute, 0)
        self.assertEqual(floor_minute(datetime(2026, 9, 10, 14, 59)).minute, 50)
        self.assertEqual(floor_minute(datetime(2026, 9, 10, 14, 9)).minute, 0)
        self.assertEqual(floor_minute(datetime(2026, 9, 10, 14, 37, 22)).second, 0)

    def test_parse_schedule_formats(self):
        self.assertEqual(parse_schedule("2026-09-10T14:37"), datetime(2026, 9, 10, 14, 30))
        self.assertEqual(parse_schedule("2026-09-10T14:37:15"), datetime(2026, 9, 10, 14, 30))
        self.assertEqual(parse_schedule("2026-09-10T14:37+09:00"), datetime(2026, 9, 10, 14, 30))
        self.assertEqual(parse_schedule("2026-09-10T05:37Z"), datetime(2026, 9, 10, 14, 30))
        self.assertEqual(parse_schedule("2026-09-09T23:37-06:00"), datetime(2026, 9, 10, 14, 30))
        with self.assertRaises(ValueError):
            parse_schedule("")
        with self.assertRaises(ValueError):
            parse_schedule("내일 오후")

    def test_schedule_safety_margin(self):
        now = datetime(2026, 9, 10, 14, 0)
        self.assertFalse(schedule_is_safe(datetime(2026, 9, 10, 14, 10), now)[0])
        self.assertFalse(schedule_is_safe(datetime(2026, 9, 10, 13, 0), now)[0])
        self.assertFalse(schedule_is_safe(datetime(2026, 9, 10, 14, 15), now)[0])
        self.assertTrue(schedule_is_safe(datetime(2026, 9, 10, 14, 20), now)[0])


class TestTypingPlan(unittest.TestCase):
    def test_plain_lines_and_enters(self):
        ops = plan_text("가\n나", [])
        self.assertEqual(ops, [Op("text", "가"), Op("enter"), Op("text", "나")])

    def test_bold_once_per_paragraph(self):
        ops = plan_text("임플란트 상담은 임플란트 전문.\n\n임플란트 다시.", ["임플란트"])
        bolds = [o for o in ops if o.kind == "bold"]
        self.assertEqual(len(bolds), 2)  # 문단 1에서 1회, 빈 줄 뒤 문단 2에서 1회
        self.assertEqual(ops[0], Op("bold", "임플란트"))
        # 같은 문단의 두 번째 '임플란트'는 굵게 하지 않는다 — 앞 문장에 그대로 남아 있어야 한다.
        self.assertEqual("".join(o.payload for o in ops if o.kind == "text" and o.payload),
                         " 상담은 임플란트 전문. 다시.")

    def test_longest_keyword_first(self):
        ops = plan_text("치과 임플란트 치과", ["치과", "치과 임플란트"])
        self.assertEqual(ops[0], Op("bold", "치과 임플란트"))

    def test_blocks_interleave(self):
        blocks = [
            {"type": "text", "content": "첫 문장입니다."},
            {"type": "image", "image": DATA_URL},
            {"type": "text", "content": "둘째 문장입니다."},
            {"type": "text", "content": "셋째 문장입니다."},
        ]
        kinds = [o.kind for o in plan_blocks(blocks, [])]
        # 글 → Enter → 이미지 → Enter → 글 → Enter,Enter(빈 줄) → 글
        self.assertEqual(kinds, ["text", "enter", "image", "enter", "text", "enter", "enter", "text"])

    def test_image_first_block(self):
        ops = plan_blocks([{"type": "image", "image": DATA_URL}, {"type": "text", "content": "본문."}], [])
        self.assertEqual([o.kind for o in ops], ["image", "enter", "text"])
        self.assertEqual(ops[0].payload, DATA_URL)

    def test_empty_blocks_skipped(self):
        ops = plan_blocks([{"type": "text", "content": ""}, {"type": "image"}, {"type": "text", "content": "본문."}], [])
        self.assertEqual([o.kind for o in ops], ["text"])

    def test_merge_text_ops(self):
        merged = merge_text_ops([Op("text", "a"), Op("text", "b"), Op("enter"), Op("text", "c")])
        self.assertEqual(merged, [Op("text", "ab"), Op("enter"), Op("text", "c")])

    def test_every_break_is_a_blank_line(self):
        """줄바꿈이 한 칸·두 칸으로 섞이지 않는다(2026-09-29 고객 지적).

        예전에는 '한 줄 한 문장, 두 문장마다 빈 줄'이라 문단 안은 1줄, 문단 사이는 2줄이었다."""
        raw = "첫 문장입니다. 둘째 문장입니다. 셋째 문장입니다. 넷째 문장입니다."
        once = mobile_format(raw)
        self.assertNotIn("\n", once.replace("\n\n", ""), "빈 줄이 아닌 줄바꿈이 남아 있다")
        self.assertEqual(mobile_format(once), once, "다시 걸어도 결과가 같아야 한다")

    def test_a_paragraph_is_35_to_50_characters_without_spaces(self):
        raw = ("상담을 시작하면 열 분 중 예닐곱 분이 이 질문부터 하십니다. 프리사이스가 제일 좋은 겁니까. "
               "속성연장술은 옛날 방식 아닙니까. 레이튼은 왜 안 하십니까. 충분히 이해합니다.")
        paras = mobile_format(raw).split("\n\n")
        for para in paras:
            self.assertLessEqual(nospace_len(para), PARA_MAX_CHARS, para)
        # 마지막 문단만 35자에 못 미칠 수 있다(남은 문장을 버리지 않는다)
        for para in paras[:-1]:
            self.assertGreaterEqual(nospace_len(para), PARA_MIN_CHARS, para)

    def test_a_long_sentence_is_never_cut_in_the_middle(self):
        """'. 찍은 기준으로 문단나눔' — 50자를 넘겨도 마침표에서만 끊는다."""
        long = "뼈 안에 무엇이 어떻게 들어가는지, 그 결과 다리의 축이 어디로 지나가는지를 함께 보는 일입니다."
        self.assertEqual(mobile_format(long), long, "문장 중간을 끊으면 안 된다")

    def test_the_manuscripts_own_paragraphs_are_kept(self):
        """원고가 빈 줄로 나눠 둔 화제 경계를 넘어 문장을 이어 붙이지 않는다."""
        raw = "짧은 도입입니다.\n\n여기부터는 다른 이야기입니다."
        self.assertEqual(mobile_format(raw), "짧은 도입입니다.\n\n여기부터는 다른 이야기입니다.")

    def test_a_quoted_line_becomes_a_subheading(self):
        paras = split_paragraphs('"무엇을 보고 판단하는가"\n\n기계는 도구입니다.')
        self.assertEqual(paras[0], {"kind": "heading", "text": "무엇을 보고 판단하는가"})
        self.assertEqual(paras[1]["kind"], "text")

    def test_a_quote_inside_a_sentence_is_not_a_subheading(self):
        """문장 속 인용까지 소제목으로 올리면 본문이 제목투성이가 된다."""
        raw = '그래서 "어느 것이 제일 좋습니까"는 답이 없는 질문입니다.'
        self.assertEqual(split_paragraphs(raw)[0]["kind"], "text")

    def test_a_short_line_without_punctuation_is_still_a_subheading(self):
        """따옴표가 없어도 서버가 소제목으로 보는 모양(짧은 한 줄)은 소제목이다."""
        self.assertEqual(split_paragraphs("이 질문에 바로 답하면 손해입니다")[0]["kind"], "heading")

    def test_a_subheading_becomes_a_naver_quote_without_its_quotes(self):
        """2026-09-30 고객 확정: 따옴표 줄은 **인용구**로 세운다(처음엔 굵은 글씨로 했다)."""
        ops = merge_text_ops(plan_blocks(
            [{"type": "text", "content": '"무엇을 보고 판단하는가"\n\n기계는 도구입니다.'}], []))
        self.assertEqual(ops[0], Op("quote", "무엇을 보고 판단하는가"))
        self.assertEqual(ops[1:3], [Op("enter"), Op("enter")])
        self.assertEqual(ops[3], Op("text", "기계는 도구입니다."))

    def test_numbers_with_units_are_emphasised(self):
        """'숫자나, 중요한 부분 강조 표시'(2026-09-29 고객 요청). 조사가 붙어도 숫자만 칠한다."""
        ops = plan_text("수술 후 3개월이면 재수술률은 2% 미만입니다.", [])
        self.assertEqual([o.payload for o in ops if o.kind == "bold"], ["3개월", "2%"])

    def test_number_emphasis_is_capped_per_paragraph(self):
        """문단마다 두 개까지. 더 칠하면 강조가 아니라 배경이 된다."""
        ops = plan_text("1일 2회 3주 4개월 5cm 를 지킵니다.", [])
        self.assertEqual(len([o for o in ops if o.kind == "bold"]), NUMBERS_PER_PARAGRAPH)

    def test_a_keyword_and_a_number_can_share_a_paragraph(self):
        ops = plan_text("임플란트는 3개월이면 자리를 잡습니다.", ["임플란트"])
        self.assertEqual([o.payload for o in ops if o.kind == "bold"], ["임플란트", "3개월"])

    def test_plain_numbers_without_a_unit_are_left_alone(self):
        ops = plan_text("자료 3 을 봅니다.", [])
        self.assertEqual([o.payload for o in ops if o.kind == "bold"], [])

    def test_pick_emphasize(self):
        self.assertEqual(pick_emphasize(["#임플란트", "치", "  교정 ", "임플란트", 3]), ["임플란트", "교정"])


class TestDataUrl(unittest.TestCase):
    def test_decode_jpeg(self):
        mime, data = decode_data_url(DATA_URL)
        self.assertEqual(mime, "image/jpeg")
        self.assertEqual(data, JPEG_1PX)
        self.assertEqual(data[:2], b"\xff\xd8")

    def test_missing_padding_and_whitespace(self):
        body = base64.b64encode(b"hello world").decode().rstrip("=")
        self.assertEqual(decode_data_url("data:text/plain;base64," + body[:6] + "\n" + body[6:])[1], b"hello world")

    def test_non_base64(self):
        self.assertEqual(decode_data_url("data:text/plain,a%20b")[1], b"a b")

    def test_invalid(self):
        with self.assertRaises(ValueError):
            decode_data_url("http://x/y.jpg")

    def test_ext(self):
        self.assertEqual(ext_for_mime("image/png"), "png")
        self.assertEqual(ext_for_mime("image/jpeg"), "jpg")
        self.assertEqual(ext_for_mime("weird/thing"), "jpg")


# ================================================================ server_client.py (가짜 서버)
class FakeState:
    def __init__(self):
        self.requests = []
        self.logins = 0
        self.expire_once = False
        self.blog_id = "platonmarketing"          # 요약/잡의 네이버 블로그 ID
        self.schedule = "2026-09-10T14:30"        # 클레임 잡의 예약 시각
        self.queue_jobs = []                      # 발행 큐(확장 대체 경로)
        self.categories = []
        self.beats = []                           # 실행기 하트비트(웹 신호등)


class FakeHandler(BaseHTTPRequestHandler):
    state: FakeState

    def log_message(self, *a):  # 조용히
        pass

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"null") if n else None

    def _send(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _route(self, method):
        st = self.state
        body = self._body() if method == "POST" else None
        st.requests.append({"method": method, "path": self.path, "auth": self.headers.get("Authorization"), "body": body})
        p = self.path
        if p == "/api/v1/auth/login" and method == "POST":
            if body.get("password") == "wrong":
                return self._send(401, {"detail": "이메일 또는 비밀번호가 올바르지 않습니다"})
            st.logins += 1
            return self._send(200, {"access_token": f"tok-{st.logins}", "token_type": "bearer"})
        if not (self.headers.get("Authorization") or "").startswith("Bearer tok-"):
            return self._send(401, {"detail": "Not authenticated"})
        if st.expire_once and self.headers.get("Authorization") == "Bearer tok-1":
            st.expire_once = False
            return self._send(401, {"detail": "token expired"})
        if p == "/api/v1/campaign/agent/summary":
            return self._send(200, [{"blog_ref_id": "b1", "naver_blog_id": st.blog_id, "label": "메인", "status": "active",
                                     "status_reason": None, "pending": 2, "next_at": "2026-09-10T14:30", "login_id": "lhs0609c"}])
        if p == "/api/v1/campaign/agent/blogs/b1/credential":
            return self._send(200, {"login_id": "lhs0609c", "login_pw": "pw!", "naver_blog_id": st.blog_id})
        if p == "/api/v1/campaign/agent/claim" and method == "POST":
            return self._send(200, [{
                "id": "j1", "lock_token": "L1", "title": "제목", "content": "본문.",
                "blocks": [{"type": "text", "content": "본문."}, {"type": "image", "image": DATA_URL}],
                "tags": ["임플란트"], "emphasize": ["임플란트"], "finalAction": "schedule",
                "schedule": {"datetime": st.schedule},
                "options": {"openType": "public", "search": True, "category": "24"},
                "expectedBlogId": st.blog_id, "blog_ref_id": "b1", "draft_id": "d1",
            }])
        if p == "/api/v1/campaign/agent/jobs/j1/result" and method == "POST":
            if body.get("lock_token") == "OTHER":
                return self._send(409, {"detail": "다른 실행기가 잡은 건입니다(잠금 불일치)"})
            return self._send(200, {"success": True, "status": "published" if body.get("ok") else ("uncertain" if body.get("uncertain") else "failed")})
        if p == "/api/v1/campaign/agent/jobs/j1/checkpoint" and method == "POST":
            return self._send(200, {"success": True, "lease_seconds": 120})
        if p == "/api/v1/campaign/blogs/b1/status" and method == "POST":
            return self._send(200, {"success": True, "status": body.get("status")})
        if p == "/api/v1/campaign/agent/heartbeat" and method == "POST":
            st.beats.append(body)
            return self._send(200, {"online": True, "running": body.get("running"), "version": body.get("version"), "devices": []})
        if p.startswith("/api/v1/publish/queue/jobs") and method == "GET":
            return self._send(200, st.queue_jobs)
        if p.startswith("/api/v1/publish/queue/") and p.endswith("/result") and method == "POST":
            return self._send(200, {"success": True})
        if p == "/api/v1/publish/categories":
            if method == "POST":
                st.categories = body.get("categories") or []
                return self._send(200, {"categories": st.categories})
            return self._send(200, {"categories": st.categories})
        return self._send(404, {"detail": f"no route {method} {p}"})

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")


class TestServerClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = FakeState()
        FakeHandler.state = cls.state
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        self.state.requests.clear()
        self.state.logins = 0
        self.state.expire_once = False
        self.c = ServerClient(self.base, timeout=5)

    def tearDown(self):
        self.c.close()

    def test_login_and_bearer(self):
        tok = self.c.login("a@b.c", "pw")
        self.assertEqual(tok, "tok-1")
        req = self.state.requests[-1]
        self.assertEqual((req["method"], req["path"]), ("POST", "/api/v1/auth/login"))
        self.assertEqual(req["body"], {"email": "a@b.c", "password": "pw"})
        self.c.summary()
        self.assertEqual(self.state.requests[-1]["auth"], "Bearer tok-1")

    def test_token_is_replaced_before_it_expires(self):
        """만료를 기다렸다 401 을 맞지 않는다 — 기록에 '토큰 만료'가 줄줄이 남던 이유였다."""
        self.c.login('a@b.c', 'pw')
        self.c.summary()
        self.assertEqual(self.state.requests[-1]['auth'], 'Bearer tok-1')
        self.c.token_until = time.monotonic() + 10      # 곧 만료된다고 보게 만든다
        self.c.summary()
        self.assertEqual(self.state.requests[-1]['auth'], 'Bearer tok-2')   # 미리 갈아끼웠다
        self.assertEqual(self.state.logins, 2)
        self.assertFalse(any(r['path'].endswith('/summary') and r['auth'] == 'Bearer tok-1'
                             for r in self.state.requests[-2:]))

    def test_fresh_token_is_not_renewed_every_call(self):
        self.c.login('a@b.c', 'pw')
        for _ in range(3):
            self.c.summary()
        self.assertEqual(self.state.logins, 1)          # 멀쩡한 토큰을 두고 다시 받지 않는다

    def test_login_failure(self):
        with self.assertRaises(ServerError) as cm:
            self.c.login("a@b.c", "wrong")
        self.assertEqual(cm.exception.status, 401)
        self.assertIn("올바르지", cm.exception.detail)

    def test_summary_and_credential_shapes(self):
        self.c.login("a@b.c", "pw")
        s = self.c.summary()
        self.assertEqual(s[0]["blog_ref_id"], "b1")
        self.assertEqual(self.state.requests[-1]["method"], "GET")
        cred = self.c.credential("b1")
        self.assertEqual(cred["login_pw"], "pw!")
        self.assertEqual(self.state.requests[-1]["path"], "/api/v1/campaign/agent/blogs/b1/credential")

    def test_claim_body(self):
        self.c.login("a@b.c", "pw")
        jobs = self.c.claim("b1", limit=3, include_images=False)
        self.assertEqual(self.state.requests[-1]["body"], {"blog_ref_id": "b1", "limit": 3, "include_images": False, "mode": "live", "protocol_version": 2, "capabilities": ["landing_links_v1", "point_styles_v1"]})
        self.assertEqual(jobs[0]["lock_token"], "L1")
        self.assertEqual(jobs[0]["blocks"][1]["type"], "image")

    def test_report_result_body(self):
        self.c.login("a@b.c", "pw")
        r = self.c.report_result("j1", "L1", ok=True, url="https://blog.naver.com/platonmarketing/1")
        self.assertEqual(r["status"], "published")
        self.assertEqual(self.state.requests[-1]["body"], {
            "lock_token": "L1", "ok": True, "uncertain": False, "message": None,
            "url": "https://blog.naver.com/platonmarketing/1", "need_login": False, "captcha": False,
            "release": False, "receipt_id": None, "drafted": False,
        })

    def test_a_saved_draft_says_so(self):
        """임시저장까지만 했다는 것을 서버가 알아야 공개 확인(RSS)을 태우지 않는다."""
        self.c.login("a@b.c", "pw")
        self.c.report_result("j1", "L1", ok=True, drafted=True)
        self.assertTrue(self.state.requests[-1]["body"]["drafted"])
        self.c.report_result("j1", "L1", ok=False, uncertain=False, message="dry-run")
        b = self.state.requests[-1]["body"]
        self.assertEqual((b["ok"], b["uncertain"], b["message"]), (False, False, "dry-run"))
        r = self.c.report_result("j1", "L1", ok=False, captcha=True, message="캡차")
        self.assertEqual(self.state.requests[-1]["body"]["captcha"], True)

    def test_lock_mismatch_raises(self):
        self.c.login("a@b.c", "pw")
        with self.assertRaises(ServerError) as cm:
            self.c.report_result("j1", "OTHER", ok=True)
        self.assertEqual(cm.exception.status, 409)

    def test_blog_status_body(self):
        self.c.login("a@b.c", "pw")
        self.c.set_blog_status("b1", "captcha", "이유")
        req = self.state.requests[-1]
        self.assertEqual(req["path"], "/api/v1/campaign/blogs/b1/status")
        self.assertEqual(req["body"], {"status": "captcha", "reason": "이유"})

    def test_queue_fetch_targets_one_blog(self):
        self.c.login("a@b.c", "pw")
        self.state.queue_jobs = [{"id": "q1", "title": "제목", "blocks": [], "tags": [], "emphasize": [],
                                  "finalAction": "schedule", "schedule": {"datetime": "2026-09-10T14:30"}, "options": {}}]
        jobs = self.c.queue_jobs(limit=2, blog_ref_id="b1")
        self.assertEqual(jobs[0]["id"], "q1")
        path = self.state.requests[-1]["path"]
        self.assertIn("limit=2", path)
        self.assertIn("blog_ref_id=b1", path)
        self.assertIn("claim_unassigned=false", path)
        self.c.queue_jobs(blog_ref_id="b1", claim_unassigned=True)
        self.assertIn("claim_unassigned=true", self.state.requests[-1]["path"])

    def test_heartbeat_reports_version_and_running_state(self):
        self.c.login("a@b.c", "pw")
        out = self.c.heartbeat(device_id="pc-1", version="9.9.9", running=True, label="원장님 PC", note="대기 3건")
        self.assertTrue(out["online"])
        self.assertEqual(self.state.beats[-1], {
            "device_id": "pc-1", "version": "9.9.9", "running": True, "label": "원장님 PC", "note": "대기 3건",
        })
        self.c.heartbeat(device_id="pc-1", version="9.9.9", running=False)
        self.assertEqual(self.state.beats[-1]["label"], None)
        self.assertFalse(self.state.beats[-1]["running"])

    def test_queue_result_and_categories_bodies(self):
        self.c.login("a@b.c", "pw")
        self.c.queue_result("q1", ok=False, message="x" * 900)
        req = self.state.requests[-1]
        self.assertEqual(req["path"], "/api/v1/publish/queue/q1/result")
        self.assertFalse(req["body"]["ok"])
        self.assertEqual(len(req["body"]["message"]), 500)
        self.c.put_categories([{"id": "24", "name": "칼럼"}])
        self.assertEqual(self.state.requests[-1]["body"], {"categories": [{"id": "24", "name": "칼럼"}]})
        self.assertEqual(self.c.categories()["categories"], [{"id": "24", "name": "칼럼"}])

    def test_relogin_on_401(self):
        self.c.login("a@b.c", "pw")
        self.state.expire_once = True
        s = self.c.summary()
        self.assertEqual(s[0]["blog_ref_id"], "b1")
        paths = [r["path"] for r in self.state.requests]
        self.assertEqual(paths, ["/api/v1/auth/login", "/api/v1/campaign/agent/summary", "/api/v1/auth/login", "/api/v1/campaign/agent/summary"])
        self.assertEqual(self.c.token, "tok-2")


# ================================================================ agent.run_job (대역 에디터)
class FakeEditor:
    """NaverEditor 와 같은 메서드 이름. 호출 순서만 기록하고, 설정에 따라 특정 단계에서 예외를 던진다."""

    def __init__(self, *, fail_at: str = "", blog_id: str = "platonmarketing"):
        self.calls = []
        self.fail_at = fail_at
        self.blog_id = blog_id
        self.publish_url = None
        self.counts = None            # None 이면 '예약 건수를 못 읽는 화면'

    def _rec(self, name, *a):
        self.calls.append(name)
        if name == self.fail_at:
            from naver_editor import CaptchaDetected, EditorError, LoginRequired, ScheduleError

            raise {"set_schedule": ScheduleError, "open_write_page": LoginRequired, "publish": CaptchaDetected}.get(name, EditorError)(f"{name} 실패")

    async def open_write_page(self): self._rec("open_write_page")
    async def dismiss_draft_popup(self): self._rec("dismiss_draft_popup")
    async def read_blog_id(self): self._rec("read_blog_id"); return self.blog_id
    async def set_title(self, t): self._rec("set_title")
    async def insert_body_blocks(self, b, e, *, reformat=True): self._rec("insert_body_blocks"); self.reformat = reformat; return sum(1 for x in b if x.get("type") == "image")
    async def open_publish_layer(self): self._rec("open_publish_layer")
    async def set_open_type(self, t): self._rec("set_open_type")
    async def set_search_allow(self, a): self._rec("set_search_allow")
    async def set_category(self, c): self._rec("set_category")
    async def set_tags(self, t): self._rec("set_tags"); return len(t)
    async def set_schedule(self, dt): self._rec("set_schedule"); self.dt = dt
    async def set_publish_now(self): self._rec("set_publish_now")
    async def verify_links(self, urls): self._rec('verify_links')
    async def read_categories(self): self._rec("read_categories"); return [{"id": "24", "name": "칼럼"}]

    async def save_draft(self, dry_run=False):
        from naver_editor import PublishOutcome

        self._rec("save_draft")
        return PublishOutcome(ok=True, message="임시저장")

    async def reserve_count(self, *, reopen=False):
        self._rec("reserve_count")
        counts = getattr(self, "counts", None)
        if counts is None:
            return None
        return counts.pop(0) if counts else None

    async def publish(self, dry_run=False):
        from naver_editor import PublishOutcome

        self._rec("publish")
        return PublishOutcome(ok=True, url=self.publish_url, message="발행 레이어 닫힘")


def _job(**over):
    j = {
        "id": "j1", "lock_token": "L1", "title": "제목", "content": "본문.",
        "blocks": [{"type": "text", "content": "본문."}], "tags": ["a"], "emphasize": [],
        "finalAction": "schedule", "schedule": {"datetime": "2026-09-10T14:37"},
        "options": {"openType": "public", "search": True, "category": None},
        "expectedBlogId": "platonmarketing", "blog_ref_id": "b1", "draft_id": "d1",
    }
    j.update(over)
    return j


NOW = datetime(2026, 9, 10, 9, 0)


class TestRunJob(unittest.TestCase):
    def run_job(self, editor, job, dry_run=False):
        import agent

        return asyncio.run(agent.run_job(editor, job, dry_run=dry_run, now=NOW))

    def test_happy_path_order_and_minute_floor(self):
        ed = FakeEditor()
        r = self.run_job(ed, _job())
        self.assertTrue(r.ok)
        self.assertEqual(ed.dt, datetime(2026, 9, 10, 14, 30))
        self.assertLess(ed.calls.index("set_schedule"), ed.calls.index("publish"))
        self.assertLess(ed.calls.index("set_category"), ed.calls.index("set_schedule"))
        # 발행이 마지막 '쓰는' 동작이다. 그 뒤에는 예약이 실제로 걸렸는지 읽어 보기만 한다.
        self.assertEqual([c for c in ed.calls if c != "reserve_count"][-1], "publish")

    def test_schedule_failure_never_publishes(self):
        ed = FakeEditor(fail_at="set_schedule")
        r = self.run_job(ed, _job())
        self.assertFalse(r.ok)
        self.assertFalse(r.uncertain)
        self.assertIn("예약설정 실패", r.message)
        self.assertNotIn("publish", ed.calls)

    def test_missing_landing_link_never_publishes(self):
        editor = FakeEditor(fail_at='verify_links')
        result = self.run_job(editor, _job(options={'requiredLinks': ['https://example.com']}))
        self.assertFalse(result.ok)
        self.assertNotIn('publish', editor.calls)

    def test_valid_landing_link_is_verified_before_publish(self):
        editor = FakeEditor()
        result = self.run_job(editor, _job(options={'requiredLinks': ['https://example.com']}))
        self.assertTrue(result.ok)
        self.assertLess(editor.calls.index('verify_links'), editor.calls.index('publish'))

    def test_dry_run_never_publishes(self):
        ed = FakeEditor()
        r = self.run_job(ed, _job(), dry_run=True)
        self.assertEqual((r.ok, r.uncertain, r.message), (False, False, "dry-run"))
        self.assertIn("set_schedule", ed.calls)
        self.assertNotIn("publish", ed.calls)

    def test_imminent_schedule_rejected_before_touching_editor(self):
        ed = FakeEditor()
        r = self.run_job(ed, _job(schedule={"datetime": "2026-09-10T09:10"}))
        self.assertFalse(r.ok)
        self.assertEqual(ed.calls, [])

    def test_blog_mismatch_stops_before_typing(self):
        ed = FakeEditor(blog_id="someoneelse")
        r = self.run_job(ed, _job())
        self.assertFalse(r.ok)
        self.assertIn("다릅니다", r.message)
        self.assertNotIn("set_title", ed.calls)

    def test_login_required_flag(self):
        r = self.run_job(FakeEditor(fail_at="open_write_page"), _job())
        self.assertTrue(r.need_login)
        self.assertFalse(r.ok)

    def test_unknown_blog_stops_before_typing(self):
        for actual, expected in [("", "platonmarketing"), ("platonmarketing", "")]:
            with self.subTest(actual=actual, expected=expected):
                ed = FakeEditor(blog_id=actual)
                r = self.run_job(ed, _job(expectedBlogId=expected))
                self.assertFalse(r.ok)
                self.assertNotIn("set_title", ed.calls)
                self.assertNotIn("publish", ed.calls)

    def test_a_reservation_that_did_not_register_is_not_reported_as_success(self):
        """발행 창이 닫혔어도 네이버 예약 건수가 늘지 않았으면 성공이 아니다.

        2026-09-28 실측: 두 건이 '예약 등록 후 페이지 이동'으로 성공 보고됐는데 블로그에는
        새 글도 예약도 없었다. 창이 닫혔다는 것만으로 성공이라고 하면 사용자는 예약이 걸린 줄 안다."""
        editor = FakeEditor()
        editor.counts = [2, 2]                      # 발행 전 2건 → 발행 후에도 2건
        out = self.run_job(editor, _job())
        self.assertFalse(out.ok)
        self.assertTrue(out.uncertain)
        self.assertIn("예약 건수가 늘지 않았습니다", out.message)

    def test_a_reservation_that_registered_is_a_success(self):
        editor = FakeEditor()
        editor.counts = [2, 3]
        out = self.run_job(editor, _job())
        self.assertTrue(out.ok)
        self.assertIsNone(out.receipt_id)

    def test_a_reservation_never_borrows_another_posts_number(self):
        """예약한 글은 아직 주소가 없다. 화면에 보이는 글 번호는 이미 올라가 있던 남의 글이다."""
        editor = FakeEditor()
        editor.publish_url = "https://blog.naver.com/platonmarketing/224423860380"
        out = self.run_job(editor, _job())
        self.assertTrue(out.ok)
        self.assertIsNone(out.receipt_id)
        self.assertIsNone(out.url)

    def test_immediate_publish_still_reports_its_own_number(self):
        editor = FakeEditor()
        editor.publish_url = "https://blog.naver.com/platonmarketing/224423860380"
        out = self.run_job(editor, _job(finalAction="publish"))
        self.assertTrue(out.ok)
        self.assertEqual(out.receipt_id, "224423860380")

    def test_missing_publish_response_is_uncertain(self):
        class NoResponseEditor(FakeEditor):
            async def publish(self):
                self._rec("publish")
                return None

        ed = NoResponseEditor()
        r = self.run_job(ed, _job())
        self.assertIn("publish", ed.calls)
        self.assertFalse(r.ok)
        self.assertTrue(r.uncertain)

    def test_uncertainty_overrides_success_flag(self):
        from naver_editor import PublishOutcome

        class AmbiguousEditor(FakeEditor):
            async def publish(self):
                return PublishOutcome(ok=True, uncertain=True, message="결과 대조 필요")

        r = self.run_job(AmbiguousEditor(), _job())
        self.assertFalse(r.ok)
        self.assertTrue(r.uncertain)

    def test_typed_errors_after_publish_remain_uncertain(self):
        from naver_editor import BlogMismatch, LoginRequired, ScheduleError

        for error_type in (BlogMismatch, LoginRequired, ScheduleError):
            with self.subTest(error=error_type.__name__):
                class InterruptedEditor(FakeEditor):
                    async def publish(self):
                        self._rec("publish")
                        raise error_type("발행 중 연결 중단")

                r = self.run_job(InterruptedEditor(), _job())
                self.assertFalse(r.ok)
                self.assertTrue(r.uncertain)

    def test_captcha_after_publish_click_is_uncertain(self):
        r = self.run_job(FakeEditor(fail_at="publish"), _job())
        self.assertTrue(r.uncertain)
        self.assertTrue(r.captcha)

    def test_generic_error_before_publish_is_plain_failure(self):
        r = self.run_job(FakeEditor(fail_at="insert_body_blocks"), _job())
        self.assertFalse(r.ok)
        self.assertFalse(r.uncertain)

    def test_word_original_is_typed_without_remobile_formatting(self):
        """서버가 reformat=False 로 내리면(워드 업로드) 글쓴이 줄바꿈을 다시 자르지 않는다."""
        ed = FakeEditor()
        self.run_job(ed, _job(options={"openType": "public", "search": True, "category": None, "reformat": False}))
        self.assertFalse(ed.reformat)
        plain = FakeEditor()
        self.run_job(plain, _job())
        self.assertTrue(plain.reformat)      # 옛 서버·생성 원고는 그대로 재정렬

    def test_non_schedule_action_refused(self):
        ed = FakeEditor()
        r = self.run_job(ed, _job(finalAction="publishNow"))
        self.assertFalse(r.ok)
        self.assertEqual(ed.calls, [])


class TestFinalActions(unittest.TestCase):
    """확장이 하던 즉시발행·임시저장을 실행기가 대신한다."""

    def run_job(self, editor, job, dry_run=False):
        import agent

        return asyncio.run(agent.run_job(editor, job, dry_run=dry_run, now=NOW))

    def test_immediate_publish_turns_the_now_radio_on_and_never_schedules(self):
        editor = FakeEditor()
        result = self.run_job(editor, _job(finalAction="publish", schedule=None))
        self.assertTrue(result.ok)
        self.assertIn("set_publish_now", editor.calls)
        self.assertNotIn("set_schedule", editor.calls)
        self.assertLess(editor.calls.index("set_publish_now"), editor.calls.index("publish"))

    def test_draft_saves_without_opening_the_publish_layer(self):
        editor = FakeEditor()
        result = self.run_job(editor, _job(finalAction="draft", schedule=None))
        self.assertTrue(result.ok)
        self.assertIn("save_draft", editor.calls)
        for step in ("open_publish_layer", "set_schedule", "publish"):
            self.assertNotIn(step, editor.calls)

    def test_draft_still_checks_the_logged_in_blog(self):
        editor = FakeEditor(blog_id="someoneelse")
        result = self.run_job(editor, _job(finalAction="draft", schedule=None))
        self.assertFalse(result.ok)
        self.assertNotIn("save_draft", editor.calls)

    def test_dry_run_clicks_neither_publish_nor_save(self):
        for action in ("publish", "draft"):
            editor = FakeEditor()
            result = self.run_job(editor, _job(finalAction=action, schedule=None), dry_run=True)
            self.assertEqual(result.message, "dry-run")
            self.assertNotIn("publish", editor.calls)
            self.assertNotIn("save_draft", editor.calls)


class FakeQueueClient:
    """process_queue_jobs 가 쓰는 서버 호출만 흉내낸다."""

    def __init__(self, jobs, *, categories=None):
        self.pending = list(jobs)
        self.results = []
        self.fetches = []
        self.saved_categories = categories if categories is not None else []
        self.put_calls = 0

    def queue_jobs(self, *, limit=1, blog_ref_id=None, claim_unassigned=False):
        self.fetches.append({"limit": limit, "blog_ref_id": blog_ref_id, "claim_unassigned": claim_unassigned})
        return [self.pending.pop(0)] if self.pending else []

    def queue_result(self, post_id, *, ok, message=None):
        self.results.append({"id": post_id, "ok": ok, "message": message})
        return {"success": True}

    def categories(self):
        return {"categories": self.saved_categories}

    def put_blog_categories(self, blog_ref_id, categories):
        self.blog_categories = (blog_ref_id, categories)
        return {"saved": len(categories)}

    def put_categories(self, categories):
        self.put_calls += 1
        self.saved_categories = categories
        return {"categories": categories}


def _queue_args(**over):
    values = dict(dry_run=False, max_per_blog=5, min_gap=0, max_gap=0, stop_event=None)
    values.update(over)
    return argparse.Namespace(**values)


BLOG = {"blog_ref_id": "b1", "naver_blog_id": "platonmarketing", "label": "메인"}


class TestQueueJobs(unittest.TestCase):
    """대량 발행 큐를 실행기가 가져와 등록한다(확장 SUBMIT_BATCH 대체)."""

    def run_queue(self, client, editor, args=None, claim_unassigned=False):
        import agent

        return asyncio.run(agent.process_queue_jobs(client, editor, BLOG, args or _queue_args(),
                                                    claim_unassigned=claim_unassigned))

    def test_publishes_each_job_against_the_expected_blog_and_reports_back(self):
        client = FakeQueueClient([_queue_job("q1"), _queue_job("q2")])
        editor = FakeEditor()
        done = self.run_queue(client, editor)
        self.assertEqual(done, 2)
        self.assertEqual([r["id"] for r in client.results], ["q1", "q2"])
        self.assertTrue(all(r["ok"] for r in client.results))
        self.assertEqual(client.fetches[0]["blog_ref_id"], "b1")

    def test_uncertain_result_is_reported_as_not_ok_and_flagged(self):
        from naver_editor import PublishOutcome

        class AmbiguousEditor(FakeEditor):
            async def publish(self, dry_run=False):
                self._rec("publish")
                return PublishOutcome(ok=True, uncertain=True, message="결과 대조 필요")

        client = FakeQueueClient([_queue_job("q1")])
        self.run_queue(client, AmbiguousEditor())
        self.assertFalse(client.results[0]["ok"])
        self.assertIn("확인 필요", client.results[0]["message"])

    def test_captcha_stops_the_blog_after_reporting_the_current_job(self):
        client = FakeQueueClient([_queue_job("q1"), _queue_job("q2")])
        done = self.run_queue(client, FakeEditor(fail_at="publish"))
        self.assertEqual(done, 1)
        self.assertEqual(len(client.results), 1)
        self.assertEqual(len(client.pending), 1)

    def test_dry_run_never_touches_the_queue(self):
        client = FakeQueueClient([_queue_job("q1")])
        done = self.run_queue(client, FakeEditor(), _queue_args(dry_run=True))
        self.assertEqual((done, client.fetches, client.results), (0, [], []))

    def test_unassigned_jobs_are_only_claimed_when_told_to(self):
        client = FakeQueueClient([])
        self.run_queue(client, FakeEditor(), claim_unassigned=True)
        self.assertTrue(client.fetches[0]["claim_unassigned"])
        client = FakeQueueClient([])
        self.run_queue(client, FakeEditor())
        self.assertFalse(client.fetches[0]["claim_unassigned"])

    def test_stops_at_the_per_blog_limit(self):
        client = FakeQueueClient([_queue_job(f"q{i}") for i in range(5)])
        done = self.run_queue(client, FakeEditor(), _queue_args(max_per_blog=2))
        self.assertEqual(done, 2)
        self.assertEqual(len(client.pending), 3)


class TestCategorySync(unittest.TestCase):
    """앱 카테고리 드롭다운 채우기(확장 SYNC_CATEGORIES 대체)."""

    def sync(self, client, editor, blog=None):
        import agent

        return asyncio.run(agent.sync_categories(client, editor, blog))

    def test_reads_and_stores_categories_when_the_cache_is_empty(self):
        client = FakeQueueClient([])
        editor = FakeEditor()
        self.assertEqual(self.sync(client, editor), 1)
        self.assertEqual(client.saved_categories, [{"id": "24", "name": "칼럼"}])
        self.assertEqual(editor.calls[-1], "open_write_page")  # 레이어를 연 채로 두지 않는다

    def test_skips_when_the_server_already_has_them(self):
        client = FakeQueueClient([], categories=[{"id": "24", "name": "칼럼"}])
        editor = FakeEditor()
        self.assertEqual(self.sync(client, editor), 0)
        self.assertNotIn("read_categories", editor.calls)

    def test_a_blog_gets_its_own_list_even_when_another_blog_filled_the_cache(self):
        """카테고리 목록은 블로그마다 다르다.

        예전에는 사용자 단위로 한 벌만 두어서, 먼저 읽은 블로그의 목록이 영구히 남고 다른
        블로그는 남의 카테고리를 골라 두게 됐다. 실행기는 못 찾은 카테고리로는 올리지 않으므로
        그 블로그의 발행이 통째로 막힌다(2026-09-28)."""
        client = FakeQueueClient([], categories=[{"id": "24", "name": "칼럼"}])
        editor = FakeEditor()
        blog = {"blog_ref_id": "ref-2", "wants_categories": True}
        self.assertEqual(self.sync(client, editor, blog), 1)
        self.assertEqual(client.blog_categories, ("ref-2", [{"id": "24", "name": "칼럼"}]))

    def test_a_blog_that_already_reported_is_not_asked_again(self):
        client = FakeQueueClient([], categories=[{"id": "24", "name": "칼럼"}])
        editor = FakeEditor()
        self.assertEqual(self.sync(client, editor, {"blog_ref_id": "ref-2", "wants_categories": False}), 0)
        self.assertNotIn("read_categories", editor.calls)

    def test_editor_failure_never_blocks_publishing(self):
        client = FakeQueueClient([])
        self.assertEqual(self.sync(client, FakeEditor(fail_at="open_publish_layer")), 0)


def _queue_job(job_id, **over):
    # 큐 경로는 실제 시계로 예약 안전성을 본다 → 고정 날짜를 쓰면 그 시각이 지나는 순간 깨진다.
    import agent

    ahead = (agent.now_kst_naive() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
    job = _job(id=job_id, schedule={"datetime": ahead})
    job.pop("lock_token", None)
    job.pop("expectedBlogId", None)
    job.update(over)
    return job


class TestSelectBlogs(unittest.TestCase):
    def test_filters(self):
        import agent

        s = [
            {"blog_ref_id": "b1", "naver_blog_id": "aaa", "label": "메인", "status": "active", "pending": 2},
            {"blog_ref_id": "b2", "naver_blog_id": "bbb", "label": "서브", "status": "active", "pending": 0},
            {"blog_ref_id": "b3", "naver_blog_id": "ccc", "label": "셋", "status": "paused", "pending": 4},
            {"blog_ref_id": "b4", "naver_blog_id": "ddd", "label": "넷", "status": "login_required", "pending": 1},
        ]
        self.assertEqual([b["blog_ref_id"] for b in agent.select_blogs(s, None)], ["b1", "b4"])
        self.assertEqual([b["blog_ref_id"] for b in agent.select_blogs(s, "서브")], ["b2"])
        self.assertEqual([b["blog_ref_id"] for b in agent.select_blogs(s, "CCC")], ["b3"])
        self.assertEqual(agent.select_blogs(s, "없음"), [])

    def test_the_first_cycle_visits_every_blog_so_chrome_opens(self):
        """켜자마자 크롬 창이 열려야 로그인을 할 수 있다(2026-09-30 신고).

        네이버 로그인은 실행기가 연 크롬 창에서만 할 수 있는데, 예전에는 대기 글이 있어야만
        그 창이 열렸다. 그래서 첫 예약은 반드시 실패하고, 그 실패로 열린 창에 로그인해야
        두 번째부터 됐다 — "무조건 처음 1회 실패 발생합니다"."""
        import agent

        s = [
            {"blog_ref_id": "b1", "naver_blog_id": "aaa", "label": "메인", "status": "active", "pending": 0},
            {"blog_ref_id": "b2", "naver_blog_id": "bbb", "label": "서브", "status": "login_required", "pending": 0},
            {"blog_ref_id": "b3", "naver_blog_id": "ccc", "label": "셋", "status": "disabled", "pending": 0},
        ]
        # 평소에는 막힌 블로그(로그인 필요)만 들른다 — 멀쩡한 블로그는 올릴 것이 없으면 열지 않는다.
        self.assertEqual([b["blog_ref_id"] for b in agent.select_blogs(s, None)], ["b2"])
        first = [b["blog_ref_id"] for b in agent.select_blogs(s, None, first_run=True)]
        self.assertEqual(first, ["b1", "b2"], "첫 바퀴는 멀쩡한 블로그도 들러 크롬을 열어 둔다")
        self.assertNotIn("b3", first, "사용 안 함 블로그까지 열지는 않는다")

    def test_the_first_cycle_still_honours_a_named_blog(self):
        import agent

        s = [{"blog_ref_id": "b1", "naver_blog_id": "aaa", "label": "메인", "status": "active", "pending": 0},
             {"blog_ref_id": "b2", "naver_blog_id": "bbb", "label": "서브", "status": "active", "pending": 0}]
        self.assertEqual([b["blog_ref_id"] for b in agent.select_blogs(s, "서브", first_run=True)], ["b2"])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class ProxyOptionTests(unittest.TestCase):
    """블로그별 고정 프록시 주소를 Playwright 옵션으로 옮기는 규칙."""

    def test_plain_host_port(self):
        from agent import _proxy_option
        self.assertEqual(_proxy_option('123.45.67.89:8080'),
                         {'server': 'http://123.45.67.89:8080'})

    def test_credentials_are_moved_out_of_the_address(self):
        # 주소에 계정을 박아 두면 크롬이 인증 창을 띄우고 실행기가 거기서 멈춘다.
        from agent import _proxy_option
        self.assertEqual(_proxy_option('http://user:pw@10.0.0.1:3128'),
                         {'server': 'http://10.0.0.1:3128', 'username': 'user', 'password': 'pw'})

    def test_socks_and_escaped_password(self):
        from agent import _proxy_option
        self.assertEqual(_proxy_option('socks5://u%40a:p%3Aw@h.example:1080'),
                         {'server': 'socks5://h.example:1080', 'username': 'u@a', 'password': 'p:w'})
