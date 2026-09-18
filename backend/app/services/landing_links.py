"""Campaign landing links: preserve destination, optional per-draft UTM, one CTA."""
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse


def validate_url(url):
    if not url:
        return ''
    if any(c.isspace() or ord(c) < 32 for c in url):
        raise ValueError('랜딩 URL에 공백이나 제어 문자를 넣을 수 없습니다')
    try:
        parsed = urlparse(url)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.port not in (None, 443) or len(url) > 1500):
            raise ValueError()
    except ValueError:
        raise ValueError('랜딩 URL은 로그인 정보가 없는 HTTPS 주소로 입력하세요')
    return url


def for_draft(config, campaign_id, draft_id):
    url = validate_url(config.get('landing_url', ''))
    if not url:
        return None
    if config.get('landing_tracking'):
        p = urlparse(url)
        query = parse_qsl(p.query, keep_blank_values=True)
        existing = {key for key, _ in query}
        for key, value in {'utm_source': 'naver', 'utm_medium': 'blog',
                           'utm_campaign': campaign_id, 'utm_content': draft_id}.items():
            if key not in existing:
                query.append((key, value))
        url = urlunparse(p._replace(query=urlencode(query)))
    return {'url': url, 'label': config.get('landing_label') or '자세한 안내 확인하기',
            'purpose': config.get('landing_purpose') or '관련 안내 확인'}


def append_cta(body, cta, landing):
    if not landing:
        return body
    if not isinstance(cta, str) or not 15 <= len(cta.strip()) <= 250:
        raise ValueError('랜딩페이지 연결 문장 형식이 올바르지 않습니다')
    # The model never chooses or rewrites the destination.
    import re
    if re.search(r'https?://|www\.', body + cta):
        raise ValueError('모델이 본문에 임의 링크를 넣었습니다')
    return body.rstrip() + '\n\n' + cta.strip() + '\n' + landing['label'] + '\n' + landing['url']
