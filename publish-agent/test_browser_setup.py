"""아무것도 안 깔린 PC 에서도 발행이 시작돼야 한다.

2026-09-27 확인: 설치 파일은 50MB 인데 Chromium 은 150MB 다. 번들에 .local-browsers
폴더가 없어서, 크롬이 없는 새 PC 에서는 브라우저를 띄우다 실패하고 발행이 시작조차
안 됐다. 개발용 PC 에는 크롬과 Playwright 브라우저가 이미 있어 드러나지 않았다.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import browser_setup as bs


class WhatIsAlreadyThere(unittest.TestCase):
    def test_a_pc_with_google_chrome_downloads_nothing(self):
        """대부분의 PC 가 여기서 끝난다. 150MB 를 괜히 받게 하면 안 된다."""
        with patch.object(bs, "system_chrome", return_value=Path("C:/chrome.exe")), \
             patch.object(bs, "install_chromium") as download:
            self.assertTrue(bs.prepare())
        download.assert_not_called()

    def test_a_previously_downloaded_chromium_counts(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "chromium-1234").mkdir()
            with patch.object(bs, "browsers_dir", return_value=Path(folder)), \
                 patch.object(bs, "system_chrome", return_value=None):
                self.assertTrue(bs.ready())

    def test_an_empty_browser_folder_is_not_ready(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(bs, "browsers_dir", return_value=Path(folder)), \
                 patch.object(bs, "system_chrome", return_value=None):
                self.assertFalse(bs.ready())

    def test_a_missing_browser_folder_is_not_ready(self):
        with patch.object(bs, "browsers_dir", return_value=Path("Z:/없는폴더")), \
             patch.object(bs, "system_chrome", return_value=None):
            self.assertFalse(bs.ready())


class TheNewPc(unittest.TestCase):
    def setUp(self):
        self.said = []

    def prepare(self):
        return bs.prepare(self.said.append)

    def test_a_bare_pc_downloads_the_browser_once(self):
        with patch.object(bs, "system_chrome", return_value=None), \
             patch.object(bs, "bundled_chromium", side_effect=[False, True]), \
             patch.object(bs, "_driver", return_value=["node.exe", "cli.js"]), \
             patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, b"")) as run:
            self.assertTrue(self.prepare())
        self.assertEqual(run.call_args[0][0][2:], ["install", "chromium"])
        self.assertTrue(any("내려받습니다" in m for m in self.said))

    def test_the_user_is_told_it_takes_a_while(self):
        """말없이 몇 분 멈춰 있으면 사람은 프로그램이 죽은 줄 안다."""
        with patch.object(bs, "system_chrome", return_value=None), \
             patch.object(bs, "bundled_chromium", side_effect=[False, True]), \
             patch.object(bs, "_driver", return_value=["node.exe", "cli.js"]), \
             patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, b"")):
            self.prepare()
        first = self.said[0]
        self.assertIn("150MB", first)
        self.assertIn("몇 분", first)

    def test_no_internet_does_not_crash_the_launcher(self):
        with patch.object(bs, "system_chrome", return_value=None), \
             patch.object(bs, "bundled_chromium", return_value=False), \
             patch.object(bs, "_driver", return_value=["node.exe", "cli.js"]), \
             patch("subprocess.run", side_effect=OSError("연결 실패")):
            self.assertFalse(self.prepare())
        self.assertTrue(any("내려받지 못했" in m for m in self.said))

    def test_a_slow_line_gives_up_instead_of_hanging_forever(self):
        with patch.object(bs, "system_chrome", return_value=None), \
             patch.object(bs, "bundled_chromium", return_value=False), \
             patch.object(bs, "_driver", return_value=["node.exe", "cli.js"]), \
             patch("subprocess.run", side_effect=subprocess.TimeoutExpired("x", 1)):
            self.assertFalse(self.prepare())
        self.assertTrue(any("오래 걸려" in m for m in self.said))

    def test_when_it_cannot_download_it_says_what_the_person_can_do(self):
        """막다른 길에 세워 두지 않는다 — 크롬을 깔면 된다고 알려 준다."""
        with patch.object(bs, "system_chrome", return_value=None), \
             patch.object(bs, "bundled_chromium", return_value=False), \
             patch.object(bs, "_driver", return_value=None):
            self.assertFalse(self.prepare())
        self.assertTrue(any("구글 크롬" in m for m in self.said))

    def test_a_download_that_reports_success_but_left_nothing_is_a_failure(self):
        with patch.object(bs, "system_chrome", return_value=None), \
             patch.object(bs, "bundled_chromium", return_value=False), \
             patch.object(bs, "_driver", return_value=["node.exe", "cli.js"]), \
             patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, b"")):
            self.assertFalse(self.prepare())


if __name__ == "__main__":
    unittest.main()
