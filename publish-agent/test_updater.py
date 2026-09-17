import hashlib
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import httpx

import updater

GOOD_URL = 'https://doctor-voice-pro-ghwi.vercel.app/downloads/DoctorVoiceAutopilotSetup.exe'


def manifest(**overrides):
    payload = {'version': '9.9.9', 'url': GOOD_URL, 'sha256': 'a' * 64}
    payload.update(overrides)
    return payload


def client_returning(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


class VersionTests(unittest.TestCase):
    def test_compares_numerically_not_alphabetically(self):
        self.assertTrue(updater.is_newer('1.10.0', '1.9.0'))
        self.assertFalse(updater.is_newer('1.0.0', '1.0.0'))
        self.assertFalse(updater.is_newer('0.9.9', '1.0.0'))
        self.assertTrue(updater.is_newer('1.0.1', '1.0'))

    def test_rejects_junk_versions(self):
        for text in ('', 'v1.0', '1.0.0-beta', '1.0.0.0.1', '../1.0'):
            with self.assertRaises(ValueError):
                updater.version_tuple(text)


class ManifestTests(unittest.TestCase):
    def test_accepts_newer_signed_manifest(self):
        self.assertEqual(updater.read_manifest(manifest(), '1.0.0'),
                         {'version': '9.9.9', 'url': GOOD_URL, 'sha256': 'a' * 64})

    def test_ignores_same_or_older_version(self):
        self.assertIsNone(updater.read_manifest(manifest(version='1.0.0'), '1.0.0'))
        self.assertIsNone(updater.read_manifest(manifest(version='0.1.0'), '1.0.0'))

    def test_rejects_untrusted_or_plain_http_download(self):
        for url in ('http://doctor-voice-pro-ghwi.vercel.app/x.exe', 'https://evil.example.com/x.exe',
                    'https://doctor-voice-pro-ghwi.vercel.app.evil.com/x.exe', 'file:///C:/x.exe', ''):
            self.assertIsNone(updater.read_manifest(manifest(url=url), '1.0.0'), url)

    def test_rejects_missing_or_malformed_hash(self):
        for digest in ('', 'a' * 63, 'z' * 64, None, 12345):
            self.assertIsNone(updater.read_manifest(manifest(sha256=digest), '1.0.0'), digest)

    def test_ignores_broken_payloads(self):
        for payload in (None, [], 'text', {}, {'version': '9.9.9'}):
            self.assertIsNone(updater.read_manifest(payload, '1.0.0'))


class FetchTests(unittest.TestCase):
    def test_network_failure_is_not_an_error(self):
        def boom(request):
            raise httpx.ConnectError('offline', request=request)
        with client_returning(boom) as client:
            self.assertIsNone(updater.fetch(updater.MANIFEST_URL, client=client, local='1.0.0'))

    def test_server_error_and_bad_json_are_not_errors(self):
        with client_returning(lambda request: httpx.Response(500)) as client:
            self.assertIsNone(updater.fetch(updater.MANIFEST_URL, client=client, local='1.0.0'))
        with client_returning(lambda request: httpx.Response(200, text='<html>')) as client:
            self.assertIsNone(updater.fetch(updater.MANIFEST_URL, client=client, local='1.0.0'))

    def test_reads_new_version(self):
        with client_returning(lambda request: httpx.Response(200, json=manifest())) as client:
            self.assertEqual(updater.fetch(updater.MANIFEST_URL, client=client, local='1.0.0')['version'], '9.9.9')


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())

    def test_keeps_file_that_matches_hash(self):
        body = b'installer bytes'
        update = manifest(sha256=hashlib.sha256(body).hexdigest())
        with client_returning(lambda request: httpx.Response(200, content=body)) as client:
            saved = updater.download(update, self.folder, client=client)
        self.assertEqual(saved.read_bytes(), body)
        self.assertIn('9.9.9', saved.name)

    def test_deletes_file_whose_hash_does_not_match(self):
        with client_returning(lambda request: httpx.Response(200, content=b'tampered')) as client:
            with self.assertRaises(ValueError):
                updater.download(manifest(), self.folder, client=client)
        self.assertEqual(list(self.folder.glob('*.exe')), [])

    def test_leaves_nothing_behind_when_download_fails(self):
        with client_returning(lambda request: httpx.Response(404)) as client:
            with self.assertRaises(httpx.HTTPError):
                updater.download(manifest(), self.folder, client=client)
        self.assertEqual(list(self.folder.glob('*.exe')), [])


class ManifestFileTests(unittest.TestCase):
    def test_published_manifest_matches_what_the_updater_accepts(self):
        published = Path(__file__).resolve().parent.parent / 'frontend' / 'public' / 'downloads' / 'launcher-version.json'
        if not published.is_file():
            self.skipTest('아직 빌드하지 않았습니다')
        payload = json.loads(published.read_text(encoding='utf-8'))
        # 배포본이 소스보다 앞설 수는 없다 — 그러면 아무도 못 받는 버전을 내보낸 것이다.
        # 소스가 앞서는 것(아직 빌드하지 않은 다음 버전)은 정상이다.
        self.assertFalse(updater.is_newer(payload.get('version'), updater.VERSION),
                         f"배포된 매니페스트({payload.get('version')})가 소스({updater.VERSION})보다 높습니다")
        self.assertIsNotNone(updater.read_manifest(payload, '0.0.1'))


class StrayCopyTests(unittest.TestCase):
    """내려받아 풀어 둔 옛 복사본을 알아보고 설치본으로 넘긴다."""

    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.installed = self.folder / 'Installed' / updater.APP_EXE
        self.installed.parent.mkdir()
        self.installed.write_bytes(b'exe')
        self.stray = self.folder / 'Downloads' / updater.APP_EXE
        self.stray.parent.mkdir()
        self.stray.write_bytes(b'old exe')

    def run_as(self, running, installed):
        with mock.patch.object(updater, 'installed_build', return_value=True), \
             mock.patch.object(updater, 'installed_exe', return_value=installed):
            return updater.stray_copy(running)

    def test_old_copy_is_sent_to_the_installed_one(self):
        self.assertEqual(self.run_as(self.stray, self.installed), self.installed)

    def test_the_installed_one_is_left_alone(self):
        self.assertIsNone(self.run_as(self.installed, self.installed))

    def test_same_path_written_differently_is_not_a_stray_copy(self):
        # 윈도우는 대소문자를 가리지 않는다 — 글자만 비교하면 멀쩡한 설치본을 쫓아낸다.
        disguised = Path(str(self.installed).upper())
        self.assertIsNone(self.run_as(disguised, self.installed))

    def test_without_an_install_nothing_happens(self):
        # 설치하지 않고 압축만 풀어 쓰는 사람의 실행기를 가로채면 안 된다.
        self.assertIsNone(self.run_as(self.stray, None))

    def test_development_run_is_never_touched(self):
        with mock.patch.object(updater, 'installed_build', return_value=False), \
             mock.patch.object(updater, 'installed_exe', return_value=self.installed):
            self.assertIsNone(updater.stray_copy(self.stray))


if __name__ == "__main__":
    unittest.main()
