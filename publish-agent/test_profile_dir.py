"""브라우저 프로필은 '로그인한 계정'의 것이다.

네이버는 로그인 아이디와 블로그 주소가 다를 수 있다(lhs0609c 로 로그인, 블로그는
platonmarketing). 프로필을 주소로 잡아 두면 주소를 맞추는 순간 빈 폴더로 갈아타
로그인이 통째로 날아간다 — 2026-09-23 실제로 그랬고, 실행기가 아무 일도 못 했다.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent import BrowserPool


class ProfileDirTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.pool = BrowserPool(None, Path(self.folder.name), headless=True, window_pos=None)

    def tearDown(self):
        self.folder.cleanup()

    def test_an_existing_login_is_carried_over_to_the_account_folder(self):
        old = Path(self.folder.name) / 'platonmarketing'
        (old / 'Default').mkdir(parents=True)
        (old / 'Default' / 'Cookies').write_bytes(b'session')
        self.pool.remember_profile('lhs0609c', 'platonmarketing')
        moved = self.pool.profile_dir('lhs0609c')
        self.assertEqual(moved.name, 'lhs0609c')
        self.assertEqual((moved / 'Default' / 'Cookies').read_bytes(), b'session')
        self.assertFalse(old.exists())

    def test_the_account_folder_wins_when_both_exist(self):
        """이미 계정 폴더가 있으면 그게 진짜다 — 옛 폴더로 덮어쓰면 최신 로그인을 잃는다."""
        for name, mark in (('lhs0609c', b'new'), ('platonmarketing', b'old')):
            box = Path(self.folder.name) / name / 'Default'
            box.mkdir(parents=True)
            (box / 'Cookies').write_bytes(mark)
        self.pool.remember_profile('lhs0609c', 'platonmarketing')
        kept = self.pool.profile_dir('lhs0609c')
        self.assertEqual((kept / 'Default' / 'Cookies').read_bytes(), b'new')

    def test_a_first_run_just_names_the_folder(self):
        fresh = self.pool.profile_dir('newaccount')
        self.assertEqual(fresh, Path(self.folder.name) / 'newaccount')
        self.assertFalse(fresh.exists())        # 만드는 것은 브라우저를 띄울 때다

    def test_an_alias_equal_to_the_key_is_not_remembered(self):
        self.pool.remember_profile('same', 'same', '')
        self.assertEqual(self.pool.legacy['same'], [])


if __name__ == '__main__':
    unittest.main()
