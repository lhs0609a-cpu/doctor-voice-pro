"""사람이 로그인하는 동안 실행기가 로그인 페이지를 다시 열지 않는지. python -m pytest test_login_wait.py -q"""
import asyncio
import unittest

import agent


class _Ctx:
    def __init__(self, cookies):
        self._cookies = cookies

    async def cookies(self, _url):
        return self._cookies


class _Page:
    def __init__(self, url, cookies):
        self.url = url
        self.context = _Ctx(cookies)


class _Editor:
    def __init__(self, url, cookies):
        self.page = _Page(url, cookies)
        self.opened = 0

    async def open_write_page(self):
        self.opened += 1


class _Client:
    def __init__(self):
        self.statuses = []

    def set_blog_status(self, ref, status, reason):
        self.statuses.append(status)

    def credential(self, ref):
        return {}


BLOG = {"blog_ref_id": "b1", "naver_blog_id": "testblog"}


class LoginWaitTests(unittest.TestCase):
    def test_does_not_reload_while_person_is_logging_in(self):
        ed = _Editor("https://nid.naver.com/nidlogin.login?url=x", [])
        ok, reason = asyncio.run(agent.ensure_login(ed, _Client(), BLOG))
        self.assertFalse(ok)
        self.assertEqual(ed.opened, 0, "입력 중인 로그인 페이지를 새로 열면 안 된다")
        self.assertIn("기다리는 중", reason)

    def test_continues_once_login_cookie_exists(self):
        ed = _Editor("https://nid.naver.com/nidlogin.login?url=x", [{"name": "NID_AUT", "value": "v"}])
        ok, _ = asyncio.run(agent.ensure_login(ed, _Client(), BLOG))
        self.assertTrue(ok)
        self.assertEqual(ed.opened, 1)

    def test_normal_page_opens_write_page(self):
        ed = _Editor("https://blog.naver.com/testblog", [])
        ok, _ = asyncio.run(agent.ensure_login(ed, _Client(), BLOG))
        self.assertTrue(ok)
        self.assertEqual(ed.opened, 1)


if __name__ == "__main__":
    unittest.main()


class _ClosedPage(_Page):
    """사람이 닫아 버린 창. 주소는 마지막 것을 그대로 들고 있다."""

    def is_closed(self):
        return True


class _OpenPage(_Page):
    def is_closed(self):
        return False


class ClosedWindowTests(unittest.TestCase):
    """사람이 크롬 창을 닫으면 **다시 연다**.

    2026-10-23 실측: pgandplt 89건을 올린 뒤 창이 닫혔는데, page.url 이 마지막 주소
    (nid.naver.com)를 그대로 들고 있어 실행기가 '아직 로그인하는 중'으로 보고 25분 동안
    기다리기만 했다. 창은 없는데 로그는 멀쩡해 보여서 사람이 알아채기 어렵다.
    """

    def test_a_closed_window_is_reopened_instead_of_waited_on(self):
        ed = _Editor("https://nid.naver.com/nidlogin.login?url=x", [])
        ed.page = _ClosedPage(ed.page.url, [])
        ok, _ = asyncio.run(agent.ensure_login(ed, _Client(), BLOG))
        self.assertTrue(ok)
        self.assertEqual(ed.opened, 1, "닫힌 창을 두고 기다리면 영영 멈춘다")

    def test_an_open_login_window_is_still_left_alone(self):
        ed = _Editor("https://nid.naver.com/nidlogin.login?url=x", [])
        ed.page = _OpenPage(ed.page.url, [])
        ok, reason = asyncio.run(agent.ensure_login(ed, _Client(), BLOG))
        self.assertFalse(ok)
        self.assertEqual(ed.opened, 0, "입력 중인 로그인 페이지는 건드리지 않는다")
        self.assertIn("기다리는 중", reason)
