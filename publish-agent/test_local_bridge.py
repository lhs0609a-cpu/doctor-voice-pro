"""홈페이지 자동 연결 창구 — 우리 홈페이지만, 이 PC 안에서만, 코드만 받는다."""
import http.client
import json
import os
import unittest
from unittest import mock

import local_bridge

SITE = 'https://doctor-voice-pro-ghwi.vercel.app'


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.pairs = []
        self.saved_ports = local_bridge.PORTS
        local_bridge.PORTS = (0,)   # 테스트에서는 비어 있는 아무 포트나

        def pair(code):
            self.pairs.append(code)
            return (code == 'GOODCODE', '연결됨' if code == 'GOODCODE' else '코드가 틀렸습니다', {'email': 'a@naver.com'})

        self.bridge = local_bridge.LocalBridge(
            status=lambda: {'app': 'doctorvoice-launcher', 'version': '9.9.9', 'paired': False}, pair=pair)
        self.port = self.bridge.start()

    def tearDown(self):
        self.bridge.stop()
        local_bridge.PORTS = self.saved_ports

    def call(self, method, path, body=None, origin=SITE, host=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        headers = {'Host': host or f'127.0.0.1:{self.port}'}
        if origin:
            headers['Origin'] = origin
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers['Content-Type'] = 'application/json'
        conn.request(method, path, body=data, headers=headers)
        res = conn.getresponse()
        raw = res.read()
        conn.close()
        return res, (json.loads(raw) if raw else None)

    def test_our_site_can_see_the_launcher(self):
        res, body = self.call('GET', '/status')
        self.assertEqual(res.status, 200)
        self.assertEqual(body['app'], 'doctorvoice-launcher')
        self.assertEqual(res.getheader('Access-Control-Allow-Origin'), SITE)
        self.assertEqual(res.getheader('Access-Control-Allow-Private-Network'), 'true')

    def test_our_site_can_hand_over_a_code(self):
        res, body = self.call('POST', '/pair', {'code': 'GOODCODE'})
        self.assertEqual(res.status, 200)
        self.assertTrue(body['ok'])
        self.assertEqual(body['email'], 'a@naver.com')
        self.assertEqual(self.pairs, ['GOODCODE'])

    def test_bad_code_is_reported_not_swallowed(self):
        res, body = self.call('POST', '/pair', {'code': 'WRONG'})
        self.assertEqual(res.status, 409)
        self.assertFalse(body['ok'])

    def test_other_sites_are_refused(self):
        for origin in ('https://evil.example.com', None,
                       'https://doctor-voice-pro-ghwi.vercel.app.evil.com',
                       'https://evil-doctor-voice-pro.vercel.app',   # 앞에 뭘 붙여도 우리 주소가 아니다
                       'https://doctor-voice-pro-ghwi.vercel.app.kr',
                       'http://doctor-voice-pro-ghwi-git-main.vercel.app'):  # 미리보기는 https 만
            res, _ = self.call('POST', '/pair', {'code': 'GOODCODE'}, origin=origin)
            self.assertEqual(res.status, 403, origin)
        self.assertEqual(self.pairs, [])

    def test_vercel_preview_deployments_are_allowed(self):
        # 배포마다 주소가 바뀌어도 연결이 끊기면 안 된다.
        for origin in ('https://doctor-voice-pro-ghwi-git-feature-one-stop-wizard-team.vercel.app',
                       'https://doctor-voice-pro-ghwi-a1b2c3d4.vercel.app'):
            res, body = self.call('GET', '/status', origin=origin)
            self.assertEqual(res.status, 200, origin)
            # 크롬은 보낸 Origin 과 글자까지 같아야 응답을 읽는다.
            self.assertEqual(res.getheader('Access-Control-Allow-Origin'), origin)
            self.assertEqual(body['app'], 'doctorvoice-launcher')

    def test_custom_domain_can_be_opened_without_rebuilding(self):
        origin = 'https://app.doctorvoice.kr'
        res, _ = self.call('GET', '/status', origin=origin)
        self.assertEqual(res.status, 403)
        with mock.patch.dict(os.environ, {local_bridge.EXTRA_ORIGINS_ENV: f'{origin}, https://other.example'}):
            res, _ = self.call('GET', '/status', origin=origin)
            self.assertEqual(res.status, 200)
            self.assertEqual(res.getheader('Access-Control-Allow-Origin'), origin)

    def test_dns_rebinding_host_is_refused(self):
        res, _ = self.call('GET', '/status', host='attacker.example.com')
        self.assertEqual(res.status, 403)

    def test_preflight_allows_our_site_and_private_network(self):
        res, _ = self.call('OPTIONS', '/pair')
        self.assertEqual(res.status, 204)
        self.assertEqual(res.getheader('Access-Control-Allow-Origin'), SITE)
        self.assertIn('POST', res.getheader('Access-Control-Allow-Methods'))
        self.assertEqual(res.getheader('Access-Control-Allow-Private-Network'), 'true')

    def test_missing_or_huge_body_is_refused(self):
        res, _ = self.call('POST', '/pair', {})
        self.assertEqual(res.status, 400)
        res, _ = self.call('POST', '/pair', {'code': 'x' * 5000})
        self.assertEqual(res.status, 400)


if __name__ == '__main__':
    unittest.main()
