"""Fetch bounded evidence from approved public medical publishers, never arbitrary URLs."""
import hashlib
from datetime import datetime
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from app.core.config import settings

PUBLISHERS = ('health.kdca.go.kr', 'kdca.go.kr', 'nhs.uk', 'medlineplus.gov', 'cancer.gov')
MAX_BYTES = 1_000_000


def allowed_url(url):
    try:
        p = urlparse(url)
        return (p.scheme == 'https' and not p.username and not p.password
                and p.port in (None, 443) and any(p.hostname == h or
                (p.hostname or '').endswith('.' + h) for h in PUBLISHERS))
    except ValueError:
        return False


async def read_source(client, url):
    for _ in range(4):
        if not allowed_url(url):
            raise ValueError('허용되지 않은 근거 자료 주소')
        async with client.stream('GET', url, follow_redirects=False) as response:
            if response.is_redirect:
                from urllib.parse import urljoin
                url = urljoin(url, response.headers.get('location', ''))
                continue
            response.raise_for_status()
            if 'text/html' not in response.headers.get('content-type', ''):
                raise ValueError('근거 자료가 HTML 문서가 아닙니다')
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > MAX_BYTES:
                    raise ValueError('근거 자료 크기 초과')
        soup = BeautifulSoup(bytes(data), 'html.parser')
        title = soup.title.get_text(' ', strip=True) if soup.title else ''
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'noscript']):
            tag.decompose()
        main = soup.select_one('article, main, #content, #contents') or soup.body
        text = main.get_text(' ', strip=True) if main else ''
        if len(text) < 300 or not title:
            raise ValueError('근거 자료 본문을 확인할 수 없습니다')
        return {'id': hashlib.sha256(url.encode()).hexdigest()[:16], 'url': url,
                'title': title[:250], 'excerpt': text[:12000],
                'retrieved_at': datetime.utcnow().isoformat(),
                'content_hash': hashlib.sha256(text.encode()).hexdigest()}
    raise ValueError('근거 자료 리디렉션 횟수 초과')


async def collect(query, *, db=None, user_id=None):
    if db is not None and user_id is not None:
        from app.services.naver_search_credentials import resolve
        keys = await resolve(db, user_id)
    else:
        keys = (settings.NAVER_CLIENT_ID, settings.NAVER_CLIENT_SECRET) if settings.NAVER_CLIENT_ID and settings.NAVER_CLIENT_SECRET else None
    if not keys:
        raise ValueError('공식 근거 검색을 위해 네이버 검색 API 키를 설정하세요')
    headers = {'X-Naver-Client-Id': keys[0], 'X-Naver-Client-Secret': keys[1]}
    sources, seen = [], set()
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        for domain in PUBLISHERS[:3]:
            response = await client.get('https://openapi.naver.com/v1/search/webkr.json',
                                        headers=headers, params={'query': f'{query} site:{domain}', 'display': 5})
            response.raise_for_status()
            for item in response.json().get('items', []):
                url = item.get('link', '')
                if url in seen or not allowed_url(url):
                    continue
                seen.add(url)
                try:
                    source = await read_source(client, url)
                except (httpx.HTTPError, ValueError):
                    continue
                if source['url'] not in {s['url'] for s in sources}:
                    sources.append(source)
                if len(sources) >= 2:
                    return sources
    if not sources:
        raise ValueError('주제에 맞는 공식 근거 본문을 확보하지 못했습니다')
    return sources
