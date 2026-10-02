"""홈페이지에서 **다른 아이디로 로그인**했을 때 그 계정 전용 창으로 넘기는 길(2026-10-01 요구).

"다른 아이디로 로그인하면 로컬에이전트도 그 아이디에 맞춰서 연동되어서
100개 아이디가 있으면 로컬에이전트도 100개가 되어야지"

핵심은 **코드를 쓰지 않고 넘기는 것**이다. 이 창이 코드를 먼저 써 버리면 새 창은 쓸 코드가
없어 사람이 브라우저에서 한 번 더 승인해야 한다. 계정을 함께 받으면 그 전에 알 수 있다.
"""
import types
import unittest
from unittest import mock

import desktop
from desktop import Desktop


def stand_in(email='a@naver.com'):
    """tkinter 창 없이 bridge_pair 만 돌려 보는 대역."""
    fake = types.SimpleNamespace(
        paired_email=email, server_url='https://example.com', device_id='dev-1',
        sibling_opened={}, adopted=[])
    fake.SIBLING_COOLDOWN = Desktop.SIBLING_COOLDOWN
    fake.may_switch_to = types.MethodType(Desktop.may_switch_to, fake)
    fake.open_sibling = types.MethodType(Desktop.open_sibling, fake)
    fake.bridge_pair = types.MethodType(Desktop.bridge_pair, fake)
    fake.adopt_pairing = lambda secret, mail, client: fake.adopted.append((secret, mail))
    return fake


class HandoffTests(unittest.TestCase):
    def test_another_account_gets_its_own_window_with_the_code(self):
        fake = stand_in()
        with mock.patch.object(desktop.subprocess, 'Popen') as popen:
            ok, message, extra = fake.bridge_pair('GOODCODE', 'b@naver.com')
        self.assertFalse(ok, '이 창이 연결된 것은 아니다')
        self.assertTrue(extra['spawned'], '그 계정 전용 창을 띄웠다')
        command = popen.call_args[0][0]
        self.assertIn('--account', command)
        self.assertIn('b@naver.com', command)
        self.assertIn('--pair-code', command)
        self.assertIn('GOODCODE', command, '코드를 함께 넘겨야 새 창이 스스로 연결한다')
        self.assertEqual(fake.adopted, [], '이 창이 남의 계정 코드를 써 버리면 안 된다')

    def test_the_window_opens_once_even_if_the_site_keeps_asking(self):
        """홈페이지는 주기적으로 연결을 청한다. 상한이 없으면 창이 겹쳐 열린다."""
        fake = stand_in()
        with mock.patch.object(desktop.subprocess, 'Popen') as popen:
            for _ in range(5):
                fake.bridge_pair('GOODCODE', 'b@naver.com')
        self.assertEqual(popen.call_count, 1)

    def test_my_own_account_connects_here(self):
        fake = stand_in()
        client = mock.MagicMock()
        client.pair_claim.return_value = {'device_secret': 'sec', 'email': 'a@naver.com'}
        client.device_login.return_value = {'email': 'a@naver.com'}
        with mock.patch.object(desktop, 'ServerClient', return_value=client), \
             mock.patch.object(desktop.subprocess, 'Popen') as popen:
            ok, message, extra = fake.bridge_pair('GOODCODE', 'a@naver.com')
        self.assertTrue(ok, message)
        self.assertEqual(fake.adopted, [('sec', 'a@naver.com')])
        popen.assert_not_called()

    def test_a_window_with_no_account_yet_takes_the_code(self):
        """처음 켠 창은 아직 주인이 없다 — 누가 로그인했든 그 계정으로 붙는다."""
        fake = stand_in(email='')
        client = mock.MagicMock()
        client.pair_claim.return_value = {'device_secret': 'sec', 'email': 'c@naver.com'}
        client.device_login.return_value = {'email': 'c@naver.com'}
        with mock.patch.object(desktop, 'ServerClient', return_value=client):
            ok, _message, _extra = fake.bridge_pair('GOODCODE', 'c@naver.com')
        self.assertTrue(ok)
        self.assertEqual(fake.adopted, [('sec', 'c@naver.com')])


if __name__ == '__main__':
    unittest.main()
