"""계정이 100개면 자리도 100개 — 계정끼리 같은 자리를 돌려쓰면 안 된다(2026-10-01 요구).

"다른 아이디로 로그인하면 로컬에이전트도 그 아이디에 맞춰서 연동되어서
100개 아이디가 있으면 로컬에이전트도 100개가 되어야지"

자리가 섞이면 크롬 로그인 세션이 섞여 **엉뚱한 계정의 블로그에 글이 올라간다**.
그래서 번호 자리(slotN, 상한 있음) 대신 계정 글자에서 만든 이름을 쓴다.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import accounts


class SlotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(accounts, 'root', lambda: Path(self.tmp.name))
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_a_hundred_accounts_get_a_hundred_different_slots(self):
        seats = {accounts.slot_for(f'clinic{n}@naver.com') for n in range(100)}
        self.assertEqual(len(seats), 100)

    def test_the_same_account_always_returns_to_its_own_slot(self):
        first = accounts.slot_for('a@naver.com')
        self.assertEqual(accounts.slot_for('a@naver.com'), first)
        self.assertEqual(accounts.slot_for('A@NAVER.COM'), first, '대소문자는 같은 계정이다')

    def test_an_account_that_already_has_a_numbered_slot_keeps_it(self):
        """옛 버전이 쓰던 slot1·slot2 자리는 그대로 둔다 — 다시 연결하지 않아도 되게."""
        accounts.save_index({'slot1': 'a@naver.com', 'slot2': 'b@naver.com'})
        self.assertEqual(accounts.slot_for('a@naver.com'), 'slot1')
        self.assertEqual(accounts.slot_for('b@naver.com'), 'slot2')
        self.assertNotIn(accounts.slot_for('c@naver.com'), ('slot1', 'slot2'))

    def test_the_site_can_see_every_account_this_pc_handles(self):
        accounts.save_index({'slot1': 'a@naver.com', 'acct0001': 'b@naver.com', 'slot3': ''})
        self.assertEqual(sorted(accounts.emails()), ['a@naver.com', 'b@naver.com'])

    def test_candidates_points_a_named_account_at_its_own_slot(self):
        accounts.save_index({'slot1': 'a@naver.com'})
        self.assertEqual(accounts.candidates('b@naver.com'),
                         [(accounts.slot_for('b@naver.com'), 'b@naver.com')])


if __name__ == '__main__':
    unittest.main()
