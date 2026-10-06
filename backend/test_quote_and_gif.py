"""AI 가 쓴 원고의 인용구, 그리고 사진 풀 경로의 움직이는 GIF.

둘 다 '워드 경로는 되는데 원고 자동화 경로만 안 되던' 것이다(2026-10-07 사용자 요청).
1) 줄 전체가 따옴표인 줄은 블로그 인용구로 세운다 — 워드와 같은 규칙을 쓴다.
2) 움직이는 GIF 는 다시 인코딩하지 않는다. JPEG 로 누르면 첫 장면만 남아 멈춘 그림이 된다.
"""
import unittest
from pathlib import Path
import tempfile

from app.api.campaign import _assemble_blocks
from app.models.campaign import Draft
from app.services import campaign_jobs, docx_import


class QuotedLineTests(unittest.TestCase):
    def test_a_fully_quoted_line_is_recognised(self):
        self.assertEqual(docx_import.quoted_line_text('"키가 작은 게 아니라 늦는 겁니다"'),
                         "키가 작은 게 아니라 늦는 겁니다")
        self.assertEqual(docx_import.quoted_line_text('“초경 후에도 늦지 않습니다.”'),
                         "초경 후에도 늦지 않습니다.")

    def test_a_quote_inside_a_sentence_is_left_alone(self):
        """문장 안의 대화 따옴표까지 인용구로 세우면 글이 망가진다."""
        self.assertIsNone(docx_import.quoted_line_text('어머니가 "늦되는 아이"라고 하셨습니다.'))
        self.assertIsNone(docx_import.quoted_line_text('따옴표가 없는 평범한 줄입니다.'))


class AssembleQuoteTests(unittest.IsolatedAsyncioTestCase):
    async def blocks(self, body):
        draft = Draft(id="d", user_id="u", campaign_id="c", title="t", body=body, blocks=None)
        return await _assemble_blocks(None, draft, [], include_images=False)

    async def test_a_quoted_line_becomes_a_blog_quote(self):
        out = await self.blocks('앞 문단입니다.\n\n"키가 작은 게 아니라 늦는 겁니다"\n\n뒤 문단입니다.')
        self.assertEqual([(b.type, b.content) for b in out], [
            ("text", "앞 문단입니다."),
            ("quote", "키가 작은 게 아니라 늦는 겁니다"),       # 따옴표는 뗀다 — 두 번 인용한 꼴이 된다
            ("text", "뒤 문단입니다."),
        ])

    async def test_the_quote_carries_spans_so_formatting_survives(self):
        out = await self.blocks('"한 줄 인용"')
        self.assertEqual(out[0].spans, [{"t": "한 줄 인용"}])

    async def test_ordinary_paragraphs_still_merge_into_one_block(self):
        out = await self.blocks("첫 문단.\n\n둘째 문단.")
        self.assertEqual([(b.type, b.content) for b in out], [("text", "첫 문단.\n\n둘째 문단.")])


class GifDataUrlTests(unittest.TestCase):
    def test_a_gif_keeps_its_own_mime(self):
        """실행기는 data URL 의 형식을 그대로 믿고 그 확장자로 파일을 만든다(ext_for_mime).
        여기서 jpeg 로 못 박으면 GIF 를 올려도 네이버에는 jpg 로 올라가 움직임이 죽는다."""
        with tempfile.TemporaryDirectory() as tmp:
            for suffix, expected in ((".gif", "image/gif"), (".png", "image/png"),
                                     (".jpg", "image/jpeg")):
                path = Path(tmp) / ("x" + suffix)
                path.write_bytes(b"\x00\x01")
                url = campaign_jobs.image_as_data_url(str(path))
                self.assertTrue(url.startswith(f"data:{expected};base64,"), (suffix, url[:30]))


if __name__ == "__main__":
    unittest.main()
