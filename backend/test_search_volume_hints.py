"""검색광고 keywordstool 호출 규칙 — 실 API 없이 요청 파라미터만 검증한다.

'습진 증상' 처럼 공백이 든 키워드를 그대로 보내면 검색광고가 400(11001)을 내고
같은 묶음 5개가 통째로 날아간다. 자동완성 씨앗은 대부분 공백을 포함하므로
이 규칙이 깨지면 발굴 후보의 상당수가 조용히 검색량 없이 남는다.
"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import search_volume_service as svs


def _fake_response(keywords):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"keywordList": [
        {"relKeyword": k.replace(" ", "").upper(), "monthlyPcQcCnt": 10,
         "monthlyMobileQcCnt": 100, "compIdx": "높음"} for k in keywords
    ]}
    return resp


class HintKeywordTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.sent = []

    def _client(self):
        """호출된 params 를 기록하는 httpx.AsyncClient 대역."""
        async def get(url, params=None, headers=None):
            self.sent.append(params)
            return _fake_response(params["hintKeywords"].split(","))

        client = MagicMock()
        client.get = AsyncMock(side_effect=get)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        return client

    async def _call(self, keywords):
        with patch.object(svs, "is_configured", return_value=True), \
             patch.object(svs, "_headers", return_value={}), \
             patch("httpx.AsyncClient", return_value=self._client()):
            return await svs._call_keywordstool(keywords)

    async def test_spaces_are_stripped_before_sending(self):
        await self._call(["습진 증상", "손 습진 치료", "건선"])
        hints = ",".join(p["hintKeywords"] for p in self.sent)
        self.assertNotIn(" ", hints)
        self.assertIn("습진증상", hints)
        self.assertIn("손습진치료", hints)

    async def test_spaced_keyword_still_matches_response(self):
        """공백을 지워 보내도 _normalize 규칙이 같아 원래 키워드에 도로 붙는다."""
        items = await self._call(["습진 증상"])
        self.assertEqual(svs._normalize(items[0]["relKeyword"]), svs._normalize("습진 증상"))

    async def test_calls_are_chunked_by_five(self):
        await self._call([f"키워드 {i}" for i in range(12)])
        self.assertEqual(len(self.sent), 3)
        for params in self.sent:
            self.assertLessEqual(len(params["hintKeywords"].split(",")), svs.MAX_HINTS_PER_CALL)


if __name__ == "__main__":
    unittest.main()
