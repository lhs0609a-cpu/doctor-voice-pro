"""의료광고법 표현은 막지 않고 고친다.

2026-09-23 결정. 걸리면 원고를 통째로 세워 두던 것을 그만두고, 대안이 있으면 그 자리에서
바꾸고 대안이 없으면(가격·할인 같은 것) 그 문장을 덜어낸다. 무엇을 고쳤는지는 원고에 남긴다.
말을 바꾸면 조사가 어긋나므로('완치를' → '증상 개선를') 받침을 보고 조사도 맞춘다.
"""
import unittest

from app.services.campaign_writer import sanitize_blocks


def fix(body: str, title: str = "제목", blocks=None):
    return sanitize_blocks(blocks, title, body)


class AutoFixTest(unittest.TestCase):
    def test_a_phrase_with_an_alternative_is_swapped_in_place(self):
        _, body, _, changes = fix("완치를 보장합니다.")
        self.assertEqual(body, "증상 개선을 기대할 수 있습니다.")
        self.assertEqual([c["from"] for c in changes], ["완치", "보장합니다"])

    def test_particles_follow_the_new_word(self):
        """'완치를' 을 바꾸면 '증상 개선를' 이 된다 — 받침을 보고 조사를 고친다."""
        self.assertEqual(fix("완치가 목표입니다.")[1], "증상 개선이 목표입니다.")
        self.assertEqual(fix("완치는 어렵습니다.")[1], "증상 개선은 어렵습니다.")

    def test_a_latin_word_keeps_its_particle(self):
        self.assertEqual(fix("MRI를 찍습니다. 완치는 어렵습니다.")[1],
                         "MRI를 찍습니다. 증상 개선은 어렵습니다.")

    def test_a_price_sentence_is_removed_whole(self):
        """가격은 바꿔 쓸 말이 없다 — 반쪽 문장을 남기지 않고 그 문장을 통째로 덜어낸다."""
        _, body, _, changes = fix("검사비는 30,000원입니다. 꾸준히 관리하면 좋아집니다.")
        self.assertEqual(body, "꾸준히 관리하면 좋아집니다.")
        self.assertEqual(changes[0]["to"], "")
        self.assertEqual(changes[0]["category"], "가격_할인")

    def test_an_ordinary_manuscript_is_left_alone(self):
        text = "아이가 잘 자는데도 키가 크지 않는다면 성장판 검사를 받아 보세요."
        _, body, _, changes = fix(text)
        self.assertEqual(body, text)
        self.assertEqual(changes, [])

    def test_formatting_survives_the_fix(self):
        """서식은 건드리지 않는다 — 글자만 바꾼다."""
        blocks = [{"type": "text", "content": "완치를 보장합니다",
                   "spans": [{"t": "완치를 ", "b": True}, {"t": "보장합니다"}]}]
        _, _, out, _ = fix("", blocks=blocks)
        self.assertEqual(out[0]["spans"][0], {"t": "증상 개선을 ", "b": True})
        self.assertEqual(out[0]["content"], "증상 개선을 기대할 수 있습니다")

    def test_a_block_left_empty_is_dropped(self):
        blocks = [{"type": "text", "content": "이벤트 진행 중입니다.", "spans": [{"t": "이벤트 진행 중입니다."}]},
                  {"type": "text", "content": "본문입니다.", "spans": [{"t": "본문입니다."}]}]
        _, _, out, _ = fix("", blocks=blocks)
        self.assertEqual([b["content"] for b in out], ["본문입니다."])


if __name__ == "__main__":
    unittest.main()
