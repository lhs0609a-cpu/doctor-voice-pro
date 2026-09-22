"""예약 목록 행 → 시각. 브라우저 없이 도는 부분만 따로 본다.

네이버는 같은 목록 안에서도 날짜를 여러 모양으로 적고, 올해 글은 연도를 생략한다.
셀렉터가 아니라 이 규칙이 예약 목록 읽기의 진짜 본체다.
"""
import unittest
from datetime import datetime

from naver_editor import parse_reservation_rows

NOW = datetime(2026, 9, 22, 12, 0)


def row(text, title=""):
    return {"text": text, "title": title}


class ParseReservationRowsTest(unittest.TestCase):
    def at(self, text, title="", now=NOW):
        rows = parse_reservation_rows([row(text, title)], now)
        return rows[0]["at"] if rows else None

    def test_reads_every_date_shape_naver_uses(self):
        self.assertEqual(self.at("2026. 9. 23. 14:30 아토피"), datetime(2026, 9, 23, 14, 30))
        self.assertEqual(self.at("2026-09-23 14:30"), datetime(2026, 9, 23, 14, 30))
        self.assertEqual(self.at("9월 23일 14시 30분"), datetime(2026, 9, 23, 14, 30))
        self.assertEqual(self.at("2026.09.23 오후 2:30"), datetime(2026, 9, 23, 14, 30))
        self.assertEqual(self.at("9월 23일 오전 12:05"), datetime(2026, 9, 23, 0, 5))

    def test_missing_year_means_the_date_that_is_still_ahead(self):
        """연말에 본 '1월 3일'은 내년이다. 예약 목록에 지난 글만 남는 일은 없다."""
        self.assertEqual(self.at("1월 3일 오전 9:00"), datetime(2027, 1, 3, 9, 0))
        self.assertEqual(self.at("9월 25일 09:00"), datetime(2026, 9, 25, 9, 0))
        # 바로 며칠 전 글은 올해 그대로 둔다(서버가 과거 자리를 걸러 낸다)
        self.assertEqual(self.at("9월 20일 09:00"), datetime(2026, 9, 20, 9, 0))

    def test_takes_the_title_from_the_row_when_the_link_is_empty(self):
        rows = parse_reservation_rows([row("2026. 9. 23. 14:30 · 아토피 초기 증상")], NOW)
        self.assertEqual(rows[0]["title"], "아토피 초기 증상")

    def test_skips_rows_without_a_time_and_impossible_clocks(self):
        self.assertEqual(parse_reservation_rows([row("제목만 있는 줄")], NOW), [])
        self.assertEqual(parse_reservation_rows([row("2026. 9. 23. 25:99")], NOW), [])
        self.assertEqual(parse_reservation_rows([row("2026. 2. 30. 10:00")], NOW), [])

    def test_same_slot_twice_counts_once(self):
        """같은 자리가 목록에 두 번 보여도 자리는 하나다(요약줄이 함께 잡히는 경우)."""
        rows = parse_reservation_rows([row("2026. 9. 23. 14:30 아토피"),
                                       row("2026. 9. 23. 14:30 아토피 · 예약")], NOW)
        self.assertEqual(len(rows), 1)

    def test_rows_come_back_in_time_order(self):
        rows = parse_reservation_rows([row("2026. 9. 26. 09:10"), row("2026. 9. 23. 14:30")], NOW)
        self.assertEqual([r["at"] for r in rows],
                         [datetime(2026, 9, 23, 14, 30), datetime(2026, 9, 26, 9, 10)])


if __name__ == "__main__":
    unittest.main()
