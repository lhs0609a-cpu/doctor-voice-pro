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
