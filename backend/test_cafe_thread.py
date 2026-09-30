"""카페 스레드 검수 — 광고 티가 나는 것들을 결정적으로 잡는다(2026-09-30 소잠한의원 요청).

"본문은 질문형식, 댓글 6개 중 댓글 2 부분만 특정 병원 정보 언급"

지시만으로는 지켜지지 않는다. 모델은 시키면 대체로 하지만 가끔 흘리고, 그 '가끔'이 광고
티를 낸다. 그래서 생성과 별개로 확인한다.
"""
import unittest

from app.services.cafe_thread import check_thread, clinic_aliases

CLIENT = {"name": "소잠한의원", "short_name": "소잠", "brand_keyword": "선릉역한의원",
          "forbidden_words": ["최고"], "facts": "누적 진료 27000건 이상."}


def thread(**over):
    base = {
        "title": "지루성피부염 어떻게들 관리하세요?",
        "body": "두 달째 두피가 가렵고 각질이 심합니다.\n\n다들 어떻게 하셨는지 궁금해요.",
        "promo_index": 2,
        "comment_count": 4,
        "comments": [
            {"seq": 1, "persona": "같은 고민", "body": "저도 그래요 ㅠㅠ 고생 많으시겠어요"},
            {"seq": 2, "persona": "다녀온 사람", "body": "저는 소잠한의원 갔어요. 상담은 편했습니다"},
            {"seq": 3, "persona": "궁금이", "body": "거기 어떠셨어요? 오래 다니셨나요"},
            {"seq": 4, "persona": "경험자", "body": "저는 샴푸부터 바꿨어요"},
        ],
    }
    base.update(over)
    return base


class AliasTests(unittest.TestCase):
    def test_every_way_of_naming_the_clinic_counts(self):
        self.assertEqual(clinic_aliases(CLIENT), ["소잠한의원", "소잠", "선릉역한의원"])


class ThreadCheckTests(unittest.TestCase):
    def test_a_clean_thread_passes(self):
        result = check_thread(thread(), CLIENT)
        self.assertTrue(result["ok"], result["issues"])

    def test_the_clinic_name_leaking_into_another_comment_is_caught(self):
        """가장 중요한 검사. 하나라도 새면 그 글은 광고로 읽힌다."""
        bad = thread()
        bad["comments"][3]["body"] = "저도 선릉역한의원 가볼까 해요"
        issues = check_thread(bad, CLIENT)["issues"]
        self.assertTrue(any("4번 댓글" in i and "선릉역한의원" in i for i in issues), issues)

    def test_a_short_alias_is_caught_too(self):
        bad = thread()
        bad["comments"][0]["body"] = "소잠 좋다던데요"
        self.assertFalse(check_thread(bad, CLIENT)["ok"])

    def test_the_promo_comment_must_actually_name_the_clinic(self):
        bad = thread()
        bad["comments"][1]["body"] = "저는 한의원 다녀왔어요"
        issues = check_thread(bad, CLIENT)["issues"]
        self.assertTrue(any("2번 댓글에 병원 이름이 없습니다" in i for i in issues), issues)

    def test_the_question_post_must_not_know_the_clinic(self):
        """묻는 사람이 이미 병원을 알고 있으면 질문이 아니라 광고다."""
        bad = thread(body="소잠한의원 가보신 분 계신가요?")
        self.assertFalse(check_thread(bad, CLIENT)["ok"])

    def test_a_post_that_is_not_a_question_is_caught(self):
        bad = thread(title="두피 관리 후기입니다", body="두 달 관리한 기록을 남깁니다.")
        issues = check_thread(bad, CLIENT)["issues"]
        self.assertTrue(any("질문처럼" in i for i in issues), issues)

    def test_links_and_phone_numbers_and_prices_are_refused(self):
        for text, word in (("https://blog.naver.com/x 참고하세요", "링크"),
                           ("02-1234-5678 로 전화했어요", "전화"),
                           ("한 번에 150,000원 들었어요", "가격")):
            with self.subTest(word):
                bad = thread()
                bad["comments"][2]["body"] = text
                self.assertFalse(check_thread(bad, CLIENT)["ok"], text)

    def test_the_comment_count_must_match(self):
        bad = thread(comment_count=6)
        issues = check_thread(bad, CLIENT)["issues"]
        self.assertTrue(any("6개여야" in i for i in issues), issues)

    def test_clinic_forbidden_words_still_apply(self):
        bad = thread()
        bad["comments"][0]["body"] = "여기가 최고예요"
        self.assertTrue(any("금칙어" in i for i in check_thread(bad, CLIENT)["issues"]))

    def test_invented_clinic_numbers_still_apply(self):
        bad = thread()
        bad["comments"][1]["body"] = "소잠한의원 갔어요. 누적 5만건 이상 봤다더라고요"
        self.assertTrue(any("실적 숫자" in i for i in check_thread(bad, CLIENT)["issues"]))



# ─────────────────────────── API 계약 ───────────────────────────
import os
os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///./test-unused.db')
os.environ.setdefault('DATABASE_URL_SYNC', 'sqlite:///./test-unused.db')
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import cafe_thread as api
from app.models.cafe_thread import CafeThread
from app.models.campaign import Client
from app.models.user import User

MADE = {
    "title": "지루성피부염 어떻게들 관리하세요?",
    "body": "두 달째 가렵습니다.\n\n다들 어떻게 하셨나요?",
    "comments": [
        {"seq": 1, "persona": "공감", "body": "저도 그래요"},
        {"seq": 2, "persona": "경험", "body": "저는 선릉역한의원 갔어요"},
        {"seq": 3, "persona": "질문", "body": "거기 어떠셨어요?"},
    ],
    "promo_index": 2,
    "comment_count": 3,
}


class ThreadApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine('sqlite+aiosqlite:///' + str(Path(self.tmp.name) / 'cafe.db'))
        async with self.engine.begin() as conn:
            for table in (CafeThread.__table__, Client.__table__):
                await conn.run_sync(lambda sync, t=table: t.create(sync))
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.sessions() as db:
            db.add(Client(id='c1', user_id='u', name='소잠한의원', short_name='소잠',
                          brand_keyword='선릉역한의원', forbidden_words=['최고']))
            await db.commit()
        app = FastAPI()
        app.include_router(api.router)

        async def db_override():
            async with self.sessions() as db:
                yield db
        app.dependency_overrides[api.get_db] = db_override
        app.dependency_overrides[api.get_current_user] = lambda: User(id='u')
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test')

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.engine.dispose()
        self.tmp.cleanup()

    async def _generate(self, made=None):
        with patch.object(api.service, 'generate_thread', AsyncMock(return_value=made or dict(MADE))):
            return await self.client.post('/cafe/threads/generate', json={
                'client_id': 'c1', 'topic': '지루성피부염', 'comment_count': 3, 'promo_index': 2})

    async def test_generate_saves_the_thread_with_its_checks(self):
        response = await self._generate()
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertTrue(data['checks']['ok'], data['checks'])
        self.assertEqual(len(data['comments']), 3)
        self.assertEqual(data['promo_index'], 2)

    async def test_editing_runs_the_checks_again(self):
        """고친 뒤에도 '통과'라고 적혀 있으면 그 표시는 거짓말이 된다."""
        thread_id = (await self._generate()).json()['id']
        edited = [dict(c) for c in MADE['comments']]
        edited[2]['body'] = '저도 선릉역한의원 가볼래요'     # 3번에 병원 이름이 샜다
        response = await self.client.put(f'/cafe/threads/{thread_id}', json={'comments': edited})
        self.assertEqual(response.status_code, 200, response.text)
        checks = response.json()['checks']
        self.assertFalse(checks['ok'])
        self.assertTrue(any('3번 댓글' in i for i in checks['issues']), checks['issues'])

    async def test_a_failing_thread_cannot_be_approved(self):
        thread_id = (await self._generate()).json()['id']
        broken = [dict(c) for c in MADE['comments']]
        broken[1]['body'] = '저는 그냥 한의원 갔어요'        # 2번에 병원 이름이 없다
        await self.client.put(f'/cafe/threads/{thread_id}', json={'comments': broken})
        refused = await self.client.put(f'/cafe/threads/{thread_id}', json={'approved': True})
        self.assertEqual(refused.status_code, 400, refused.text)

    async def test_a_clean_thread_can_be_approved(self):
        thread_id = (await self._generate()).json()['id']
        ok = await self.client.put(f'/cafe/threads/{thread_id}', json={'approved': True})
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertTrue(ok.json()['approved'])

    async def test_threads_are_listed_per_clinic(self):
        await self._generate()
        rows = (await self.client.get('/cafe/threads', params={'client_id': 'c1'})).json()
        self.assertEqual(len(rows), 1)
        self.assertEqual((await self.client.get('/cafe/threads', params={'client_id': 'other'})).json(), [])

    async def test_another_users_thread_is_not_reachable(self):
        thread_id = (await self._generate()).json()['id']
        async with self.sessions() as db:
            thread = await db.get(CafeThread, thread_id)
            thread.user_id = 'someone-else'
            await db.commit()
        self.assertEqual((await self.client.get(f'/cafe/threads/{thread_id}')).status_code, 404)

if __name__ == "__main__":
    unittest.main()
