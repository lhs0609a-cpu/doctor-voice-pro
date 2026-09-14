"""최종 발행 뒤 '글쓰기 화면을 벗어났다'(성공 신호) 판정. python -m pytest test_publish_detect.py -q"""
import unittest

from naver_editor import left_editor

WRITE = "https://blog.naver.com/platonmarketing?Redirect=Write&categoryNo=19"


class LeftEditorTests(unittest.TestCase):
    def test_write_page_address_is_not_a_move(self):
        # 2026-09-11 실제 네이버: 클릭 전후 바깥 주소가 이 글쓰기 주소 그대로였는데 '이동'으로 판정됐다
        self.assertFalse(left_editor(WRITE, WRITE))
        self.assertFalse(left_editor("", WRITE))
        self.assertFalse(left_editor(WRITE, "https://blog.naver.com/PostWriteForm.naver?blogId=x"))
        self.assertFalse(left_editor(WRITE, "https://blog.naver.com/GoBlogWrite.naver"))

    def test_real_moves_count(self):
        self.assertTrue(left_editor(WRITE, "https://blog.naver.com/platonmarketing/223456789012"))
        self.assertTrue(left_editor(WRITE, "https://blog.naver.com/PostList.naver?blogId=platonmarketing"))

    def test_other_sites_are_not_success(self):
        self.assertFalse(left_editor(WRITE, "https://nid.naver.com/nidlogin.login"))


if __name__ == "__main__":
    unittest.main()
