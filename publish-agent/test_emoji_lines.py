"""이모지가 든 줄이 **이모지 하나만 남고 사라지던 것**.

2026-10-23 실물 측정(platonmarketing, 실제 네이버 글쓰기 화면, 발행 없음):

    보낸 줄                                             들어간 글자
    상담 0507-1434-3226 (평일 09~18시)                  그대로          ✅
    📞 상담 0507-1434-3226 (평일 09~18시) · …           '📞'            ❌
    👉 한도 범위 확인 · 상담료 0원                       '👉'            ❌
    상담 0507 📞 1434-3226 입니다                        '📞'            ❌ 앞글자까지 날아간다
    ※ 메디플라톤은 …  /  #병원대출 #의사대출             그대로          ✅

한 번에 보내면 네이버 편집기가 그 문단을 **이모지 하나로 덮어쓴다**. 그 줄을 다시 읽지
못해 'EditorError: 입력한 강조 문구가 본문에 표시되지 않았습니다' 로 원고가 통째로 떨어졌다
— pgandplt 원고 552편은 글마다 👉·📞 가 있어 **전부** 이 자리에서 멈췄다(P001·P002 실측).

이모지를 따로 떼어 보내면 줄 전체가 그대로 들어간다(같은 날 실측으로 확인).
"""
import unittest
from types import SimpleNamespace

from naver_editor import NaverEditor, _emoji_split


class SplitTests(unittest.TestCase):
    def test_emoji_is_taken_out_as_its_own_piece(self):
        self.assertEqual(_emoji_split('📞 상담 0507'), ['📞', ' 상담 0507'])
        self.assertEqual(_emoji_split('상담 0507 📞 1434'), ['상담 0507 ', '📞', ' 1434'])
        self.assertEqual(_emoji_split('👉 한도 확인 👈 지금'),
                         ['👉', ' 한도 확인 ', '👈', ' 지금'])

    def test_a_plain_line_is_sent_in_one_piece(self):
        """이모지가 없으면 지금까지와 똑같이 한 번에 보낸다 — 공연히 쪼개지 않는다."""
        self.assertEqual(_emoji_split('※ 메디플라톤은 제휴 금융기관의 상품을 안내합니다.'),
                         ['※ 메디플라톤은 제휴 금융기관의 상품을 안내합니다.'])
        self.assertEqual(_emoji_split('#병원대출 #의사대출 #닥터론'), ['#병원대출 #의사대출 #닥터론'])
        self.assertEqual(_emoji_split(''), [])

    def test_nothing_is_lost_or_reordered(self):
        for line in ('📞 상담 0507 📞 끝', '글자만', '📞', '앞👉뒤', '  📞  '):
            self.assertEqual(''.join(_emoji_split(line)), line, line)


class InsertTests(unittest.IsolatedAsyncioTestCase):
    def editor(self):
        sent = []

        class Keyboard:
            async def insert_text(self, text):
                sent.append(text)

        page = SimpleNamespace(keyboard=Keyboard())
        return NaverEditor.__new__(NaverEditor), page, sent

    async def test_the_emoji_goes_in_a_call_of_its_own(self):
        editor, page, sent = self.editor()
        editor.page = page
        await editor._insert('📞 상담 0507-1434-3226 (평일 09~18시)')
        self.assertEqual(sent, ['📞', ' 상담 0507-1434-3226 (평일 09~18시)'],
                         '이모지를 같이 보내면 그 줄이 이모지 하나로 바뀐다')

    async def test_a_plain_line_is_still_one_call(self):
        editor, page, sent = self.editor()
        editor.page = page
        await editor._insert('상담 0507-1434-3226 (평일 09~18시)')
        self.assertEqual(sent, ['상담 0507-1434-3226 (평일 09~18시)'])

    async def test_empty_text_sends_nothing(self):
        editor, page, sent = self.editor()
        editor.page = page
        await editor._insert('')
        self.assertEqual(sent, [])


if __name__ == '__main__':
    unittest.main()
