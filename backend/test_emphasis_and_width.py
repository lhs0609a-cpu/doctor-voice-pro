"""강조는 포인트에만, 사진은 본문 폭에 맞게.

2026-09-23 실측: 워드 원고가 제목에 쓴 색+굵게가 참고문헌의 저자·학회 이름에도 붙어 와서
글이 알록달록해졌다. 그리고 움직이는 GIF 가 400×225 라 본문 칸(≈700px) 절반만 채웠다.
"""
import io
import unittest

from PIL import Image

from app.services.image_widen import BLOG_WIDTH, widen
from app.services.point_formatting import trim_stray_emphasis

BODY = {'color': '#222b2f'}
MARK = {'b': True, 'color': '#1a9e8f'}


def span(text, **style):
    return {'t': text, **style}


def block(*spans):
    return {'type': 'text', 'spans': list(spans)}


def styles(result_block):
    return [(s['t'], s.get('b'), s.get('color')) for s in result_block['spans']]


class EmphasisTest(unittest.TestCase):
    def test_a_reference_line_keeps_its_words_and_loses_its_colours(self):
        cite = block(span('김남익', **MARK),
                     span(', 「복합 성장운동 프로그램이 키 성장에 미치는 영향」, ', **BODY),
                     span('한국발육발달학회', **MARK),
                     span(', 2021', **BODY))
        out = trim_stray_emphasis([cite])[0]
        self.assertEqual(''.join(s['t'] for s in out['spans']),
                         ''.join(s['t'] for s in cite['spans']))
        self.assertTrue(all(s.get('color') == '#222b2f' and not s.get('b') for s in out['spans']))

    def test_a_heading_is_left_alone(self):
        """문단 전체가 한 서식이면 제목이다 — 제목까지 지우면 글이 밋밋해진다."""
        head = block(span('운동도 자극이 실려야 남습니다', **MARK))
        self.assertEqual(trim_stray_emphasis([head])[0], head)

    def test_a_paragraph_keeps_one_point_not_three(self):
        para = block(span('동래구 중앙대로에 ', **BODY), span('키네스 부산점', **MARK),
                     span('이 있습니다. 같은 프로그램으로 함께하실 수 있습니다. ', **BODY),
                     span('성장책임보증제', **MARK), span('를 운영합니다.', **BODY))
        out = trim_stray_emphasis([para])[0]
        self.assertEqual([s for s in styles(out) if s[1]], [('키네스 부산점', True, '#1a9e8f')])

    def test_plain_word_documents_are_untouched(self):
        """서식을 적어 두지 않은 원고는 그대로 지나간다."""
        plain = [{'type': 'text', 'content': '안녕하세요. 오늘은 성장 이야기입니다.'}]
        self.assertEqual(trim_stray_emphasis(plain), plain)


def gif(width, height, frames=3) -> bytes:
    # 장면이 서로 달라야 한다 — 똑같은 장면은 Pillow 가 한 장으로 합쳐 버린다.
    images = [Image.new('RGB', (width, height), (30 * i, 90, 200 - 30 * i)).convert('P')
              for i in range(frames)]
    buf = io.BytesIO()
    images[0].save(buf, 'GIF', save_all=True, append_images=images[1:], duration=80, loop=0)
    return buf.getvalue()


class WidenTest(unittest.TestCase):
    def test_a_small_animation_is_widened_and_still_moves(self):
        data, kind = widen(gif(400, 225), 'image/gif')
        self.assertEqual(kind, 'image/gif')
        im = Image.open(io.BytesIO(data))
        self.assertGreaterEqual(im.width, BLOG_WIDTH)
        self.assertEqual(im.height, im.width * 225 // 400)   # 비율 그대로
        self.assertTrue(im.is_animated)
        self.assertEqual(im.n_frames, 3)

    def test_a_photo_that_already_fills_the_column_is_returned_untouched(self):
        buf = io.BytesIO()
        Image.new('RGB', (900, 600), 'white').save(buf, 'JPEG')
        data, kind = widen(buf.getvalue(), 'image/jpeg')
        self.assertEqual(data, buf.getvalue())
        self.assertEqual(kind, 'image/jpeg')

    def test_a_tiny_icon_is_left_small_rather_than_smeared(self):
        """세 배 넘게 늘리면 뭉개진다 — 작은 그림은 작은 채로 두는 편이 낫다."""
        buf = io.BytesIO()
        Image.new('RGB', (80, 80), 'white').save(buf, 'PNG')
        data, _ = widen(buf.getvalue(), 'image/png')
        self.assertEqual(Image.open(io.BytesIO(data)).width, 80)

    def test_a_broken_file_is_passed_through_instead_of_failing_the_post(self):
        self.assertEqual(widen(b'not an image', 'image/png'), (b'not an image', 'image/png'))


if __name__ == '__main__':
    unittest.main()
