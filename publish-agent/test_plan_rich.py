"""서식 블록 → 타이핑 계획. 브라우저 없이 도는 순수 로직 검사.

여기서 지키려는 것: 글쓴이가 잡아 둔 서식과 순서가 동작 목록에서도 그대로일 것,
소제목·인용구·목록이 끝나면 본문으로 되돌아올 것(안 그러면 다음 문단까지 소제목이 된다).
"""
import unittest

from plan import Op, has_formatting, merge_text_ops, plan_rich_blocks


def _text(t, **style):
    return {"t": t, **style}


class RichPlanTests(unittest.TestCase):
    def kinds(self, ops):
        return [o.kind for o in ops]

    def test_span_formatting_rides_along(self):
        ops = plan_rich_blocks([{"type": "text", "spans": [
            _text("가려움이 "), _text("2주 이상", b=True), _text(" 이어지면", i=True, u=True)]}])
        self.assertEqual([o.payload for o in ops], ["가려움이 ", "2주 이상", " 이어지면"])
        self.assertIsNone(ops[0].attrs)
        self.assertEqual(ops[1].attrs, {"b": True})
        self.assertEqual(ops[2].attrs, {"i": True, "u": True})

    def test_color_and_size_ride_along(self):
        ops = plan_rich_blocks([{"type": "text", "spans": [_text("보습", color="#c00000", size=15.0)]}])
        self.assertEqual(ops[0].attrs, {"color": "#c00000", "size": 15.0})

    def test_different_formatting_is_never_merged(self):
        ops = merge_text_ops(plan_rich_blocks([{"type": "text", "spans": [
            _text("아주 "), _text("중요", b=True), _text("합니다")]}]))
        self.assertEqual([o.payload for o in ops], ["아주 ", "중요", "합니다"])

    def test_same_formatting_is_merged(self):
        ops = merge_text_ops(plan_rich_blocks([{"type": "text", "spans": [
            _text("한 문장", b=True), _text("이 쪼개져 있다", b=True)]}]))
        self.assertEqual([o.payload for o in ops], ["한 문장이 쪼개져 있다"])

    def test_heading_returns_to_body_afterwards(self):
        ops = plan_rich_blocks([{"type": "heading", "level": 2, "spans": [_text("진료 전 확인할 것")]}])
        self.assertEqual(ops[0], Op("para", attrs={"kind": "heading", "level": 2}))
        self.assertEqual(ops[-1], Op("para", attrs={"kind": "text"}))

    def test_quote_returns_to_body_afterwards(self):
        ops = plan_rich_blocks([{"type": "quote", "spans": [_text("가장 많이 묻는 질문")]}])
        self.assertEqual(ops[0].attrs, {"kind": "quote"})
        self.assertEqual(ops[-1].attrs, {"kind": "text"})

    def test_list_items_are_separated_by_one_enter(self):
        ops = plan_rich_blocks([{"type": "list", "ordered": True, "items": [
            [_text("아침 보습")], [_text("저녁 보습")]]}])
        self.assertEqual(ops[0].attrs, {"kind": "list", "ordered": True})
        self.assertEqual(self.kinds(ops), ["para", "text", "enter", "text", "para"])

    def test_table_carries_its_cells(self):
        rows = [[[_text("단계", b=True)], [_text("할 일", b=True)]], [[_text("1일차")], [_text("보습")]]]
        ops = plan_rich_blocks([{"type": "table", "header": True, "rows": rows}])
        self.assertEqual(ops[0].kind, "table")
        self.assertTrue(ops[0].attrs["header"])
        self.assertEqual(ops[0].attrs["rows"], rows)

    def test_paragraphs_get_a_blank_line_photos_get_one_line(self):
        ops = plan_rich_blocks([
            {"type": "text", "spans": [_text("첫 문단")]},
            {"type": "text", "spans": [_text("둘째 문단")]},
            {"type": "image", "image": "data:image/jpeg;base64,AA"},
            {"type": "text", "spans": [_text("사진 뒤 문단")]},
        ])
        self.assertEqual(self.kinds(ops),
                         ["text", "enter", "enter", "text", "enter", "image", "enter", "text"])

    def test_document_order_survives(self):
        ops = plan_rich_blocks([
            {"type": "heading", "level": 1, "spans": [_text("제목")]},
            {"type": "text", "spans": [_text("본문")]},
            {"type": "table", "header": False, "rows": [[[_text("한 칸")]]]},
            {"type": "image", "image": "data:image/jpeg;base64,AA"},
        ])
        self.assertEqual([o.kind for o in ops if o.kind in ("text", "table", "image")],
                         ["text", "text", "table", "image"])

    def test_empty_blocks_are_skipped(self):
        self.assertEqual(plan_rich_blocks([{"type": "text", "spans": []},
                                           {"type": "table", "rows": []},
                                           {"type": "list", "items": []}]), [])

    def test_plain_blocks_are_not_treated_as_formatted(self):
        self.assertFalse(has_formatting([{"type": "text", "content": "글"},
                                         {"type": "image", "image": "data:,"}]))
        self.assertTrue(has_formatting([{"type": "table", "rows": [[[_text("칸")]]]}]))
        self.assertTrue(has_formatting([{"type": "text", "spans": [_text("글")]}]))


if __name__ == "__main__":
    unittest.main()
