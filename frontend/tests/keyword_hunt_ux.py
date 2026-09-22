"""Browser check of the keyword page: search, single delete, and bulk delete of a search result.

API responses are isolated fixtures. Nothing is published and no real keyword store is touched.
"""
import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright, expect

BASE = os.environ.get('UX_BASE_URL', 'http://127.0.0.1:8317').rstrip('/')
OUTPUT = Path(__file__).resolve().parents[2] / 'output/ux'


def keyword(kid, word, prob=0.5, intent=30, why='정보를 찾는 중', volume=120):
    return dict(id=kid, keyword=word, source='hunt', scope='region', monthly_mobile=volume, monthly_pc=20,
                total_volume=volume + 20, competition='mid', verdict='possible', selected=True,
                my_verdict='likely', my_probability=prob, category='대표', in_sheet=False,
                intent_score=intent, intent_reason=why)


async def main():
    blog = dict(id='b', blog_id='fixture_blog', label='테스트 블로그', status='active', daily_limit=2)
    client = dict(id='h', name='테스트 병원', blogs=[blog], briefs=[], diseases=['아토피'], treatments=[], regions=['서초'])
    campaign = dict(id='c', name='키워드', client_id='h', client_name='테스트 병원', blog_ids=['b'],
                    settings={}, stats={}, step=2, status='draft')
    # 검색칸은 후보가 20개를 넘을 때만 나온다 — 실제 목록처럼 채워 둔다.
    # 검색량은 '아토피에좋은음식'이 제일 큰데, 목록은 간절한 순이라 '서초아토피'가 위여야 한다.
    rows = [keyword('k1', '서초아토피', 0.9, intent=92, why='우리 지역을 찍어 찾는 중', volume=20),
            keyword('k2', '강남아토피', 0.9, intent=88, why='우리 지역을 찍어 찾는 중', volume=20),
            keyword('k3', '아토피에좋은음식', 0.9, intent=14, why='집에서 해결하려는 중', volume=9000)]
    rows += [keyword(f'f{i}', f'아토피후보{i}') for i in range(22)]
    state = {'deleted': [], 'cleared': 0}

    async def route(r):
        req = r.request
        path = urlparse(req.url).path
        if '/api/' not in path:
            if req.url.startswith(BASE):
                await r.continue_()
            else:
                await r.abort()
            return
        response = {}
        if req.method == 'DELETE' and path.endswith('/keywords'):
            state['cleared'] += 1
            rows.clear()
            response = {'removed': 25}
        elif req.method == 'DELETE' and '/keywords/' in path:
            kid = path.rsplit('/', 1)[-1]
            state['deleted'].append(kid)
            rows[:] = [k for k in rows if k['id'] != kid]
            response = {'success': True}
        elif path.endswith('/campaigns'):
            response = [campaign]
        elif path.endswith('/clients'):
            response = [client]
        elif path.endswith('/clients/h'):
            response = client
        elif path.endswith('/campaigns/c'):
            response = campaign
        elif path.endswith('/keywords'):
            response = list(rows)
        elif path.endswith('/keyword-categories'):
            response = {'categories': [{'key': 'symptom', 'label': '증상', 'default_ratio': 20}]}
        elif path.endswith('/agent/status'):
            response = {'online': False, 'running': False, 'devices': []}
        elif any(path.endswith(suffix) for suffix in ('/jobs', '/tasks', '/devices', '/drafts', '/briefs', '/collections')):
            response = []
        await r.fulfill(json=response)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1440, 'height': 1100})
        await context.add_init_script(
            "localStorage.setItem('access_token','fixture');"
            "localStorage.setItem('onboarding_completed','true');"
            "localStorage.setItem('tutorial_completed','true');"
            "localStorage.setItem('user',JSON.stringify({id:'u',name:'테스트',email:'test@example.invalid'}));")
        await context.route('**/*', route)
        page = await context.new_page()
        errors = []
        page.set_default_timeout(120000)
        page.on('pageerror', lambda e: errors.append(e.stack or str(e)))
        await page.goto(BASE + '/dashboard/keyword-hunt', timeout=120000)

        found = page.get_by_role('region', name='찾은 키워드')
        await expect(found).to_contain_text('서초아토피')
        # 검색량 9,000짜리 정보 키워드가 아니라, 간절한 검색이 맨 위여야 한다.
        first = found.get_by_role('listitem').first
        await expect(first).to_contain_text('서초아토피')
        await expect(first).to_contain_text('지금 찾는 중')
        await expect(found).to_contain_text('집에서 해결하려는 중')
        await page.get_by_role('button', name='서초아토피 지우기').click()
        await expect(found).not_to_contain_text('서초아토피')
        assert state['deleted'] == ['k1'], state['deleted']

        # 검색한 결과만 한꺼번에 지우기 — 300개를 하나씩 누르게 하지 않는다.
        await page.get_by_label('키워드 검색').fill('강남')
        await page.get_by_role('button', name='검색된 1개 지우기').click()
        await page.get_by_role('button', name='정말 1개 지우기').click()
        await expect(found).not_to_contain_text('강남아토피')
        assert state['deleted'] == ['k1', 'k2'], state['deleted']

        # 싹 비우기 — 새로 찾기 전에 판을 비운다(누적되지 않게)
        await page.get_by_label('키워드 검색').fill('')
        OUTPUT.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(OUTPUT / 'keyword-clear-all.png'), full_page=True)
        await page.get_by_role('button', name='키워드 전부 지우기', exact=True).click()
        await page.get_by_role('button', name='정말 23개 전부 지우기', exact=True).click()
        await expect(page.get_by_text('모은 후보', exact=True)).not_to_be_visible()
        assert state['cleared'] == 1, state

        assert not errors, errors
        await browser.close()
    print('PASS: urgency ordering, keyword search, single delete, filtered bulk delete and clear-all; API fixtures only')

asyncio.run(main())
