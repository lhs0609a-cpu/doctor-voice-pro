import unittest
from urllib.parse import urlparse, parse_qs
from app.services.landing_links import for_draft, append_cta, validate_url


class LandingTests(unittest.TestCase):
    def test_destination_unchanged_without_tracking(self):
        url = 'https://example.com/book?a=1&a=2#faq'
        self.assertEqual(for_draft({'landing_url': url}, 'c', 'd')['url'], url)

    def test_tracking_preserves_existing_values_fragment_and_identifies_draft(self):
        link = for_draft({'landing_url': 'https://example.com/book?a=1&utm_source=custom#faq', 'landing_tracking': True}, 'campaign', 'draft')
        parsed = urlparse(link['url'])
        self.assertEqual((parsed.hostname, parsed.path, parsed.fragment), ('example.com', '/book', 'faq'))
        query = parse_qs(parsed.query)
        self.assertEqual(query['utm_source'], ['custom'])
        self.assertEqual(query['utm_content'], ['draft'])
        self.assertEqual(query['a'], ['1'])

    def test_unsafe_urls_rejected(self):
        for url in ('javascript:alert(1)', 'http://example.com', 'https://user:pass@example.com', 'https://example.com/\nhello'):
            with self.assertRaises(ValueError):
                validate_url(url)

    def test_natural_cta_appended_once_with_exact_destination(self):
        landing = for_draft({'landing_url': 'https://example.com/info'}, 'c', 'd')
        body = append_cta('본문 내용', '진료 과정이 궁금하다면 아래 안내에서 필요한 내용을 확인할 수 있습니다.', landing)
        self.assertEqual(body.count(landing['url']), 1)
        self.assertTrue(body.endswith(landing['url']))

    def test_model_cannot_add_arbitrary_link(self):
        with self.assertRaises(ValueError):
            append_cta('본문 https://wrong.example', '추가 안내는 아래 페이지에서 확인할 수 있습니다.',
                       for_draft({'landing_url': 'https://example.com'}, 'c', 'd'))


if __name__ == '__main__':
    unittest.main()
