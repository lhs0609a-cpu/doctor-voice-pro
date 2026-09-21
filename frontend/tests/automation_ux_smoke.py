"""Browser UX checks against a running local Next server; every API is mocked."""
import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright, expect

BASE = os.environ.get('UX_BASE_URL', 'http://127.0.0.1:8317')
OUTPUT = Path(__file__).resolve().parents[2] / 'docs' / 'ux-preview'


async def main():
    OUTPUT.mkdir(exist_ok=True)
    client = {'id': 'hospital', 'name': '서울봄의원', 'diseases': ['습진'], 'treatments': [], 'regions': ['서울'],
        'blogs': [{'id': 'blog', 'blog_id': 'springclinic', 'label': '병원 블로그', 'status': 'active'}], 'briefs': []}
    campaign = {'id': 'campaign', 'client_id': 'hospital', 'client_name': client['name'], 'name': '서울봄 자동 운영',
        'blog_ids': ['blog'], 'collection_id': 'photos', 'settings': {}, 'stats': {}, 'status': 'draft', 'step': 1}
    config = dict(daily_posts=2, buffer_days=3, image_count=3, target_chars=2000, min_score=85,
        max_rewrites=2, daily_generation_limit=6, landing_url='', landing_label='자세한 안내 확인하기', landing_purpose='', landing_tracking=False)
    keywords = [
        {'id': 'k1', 'keyword': '습진 초기증상', 'source': 'related', 'scope': 'national', 'monthly_mobile': 880,
         'monthly_pc': 120, 'total_volume': 1000, 'competition': 'mid', 'verdict': 'possible',
         'verdict_reason': '병원 블로그 진입 여지가 있습니다', 'in_sheet': False, 'selected': True,
         'passes_filter': True, 'has_draft': False, 'my_blog_id': 'springclinic', 'my_verdict': 'likely',
         'my_probability': 0.78},
        {'id': 'k2', 'keyword': '습진 연고 종류', 'source': 'related', 'scope': 'national', 'monthly_mobile': 420,
         'monthly_pc': 60, 'total_volume': 480, 'competition': 'high', 'verdict': 'avoid',
         'verdict_reason': '병원 블로그가 전혀 노출되지 않습니다', 'in_sheet': False, 'selected': False,
         'passes_filter': True, 'has_draft': False, 'my_verdict': None, 'my_probability': None},
    ]
    state = {'empty': False, 'enabled': False, 'config': config, 'starts': 0, 'fail': False, 'bulk': None,
             'hunt': None, 'keywords': keywords}

    async def route(request_route):
        request = request_route.request
        url = urlparse(request.url)
        if '/api/' not in url.path:
            if request.url.startswith(BASE):
                await request_route.continue_()
            else:
                await request_route.abort()
            return
        path, method = url.path, request.method
        response = {}
        if path.endswith('/automation') and method == 'POST':
            body = request.post_data_json
            assert body['max_keywords'] == 30 and body['discover_keywords'] and body['auto_schedule']
            assert body['quality']['landing_url'] == 'https://example.com/bulk'
            state['bulk'] = {'id': 'bulk-task', 'type': 'automation_pipeline', 'status': 'running', 'progress': 0,
                             'total': 4, 'message': '키워드 찾는 중', 'result': {'requested': 30}}
            response = state['bulk']
        elif path.endswith('/bulk-task/cancel'):
            state['bulk']['status'] = 'cancelled'
            response = {'success': True}
        elif path.endswith('/tasks/bulk-task'):
            response = state['bulk']
        elif path.endswith('/autopilot'):
            if method == 'PUT':
                if state['fail']:
                    await request_route.fulfill(status=400, json={'detail': {'issues': ['사진 세트를 연결하세요']}})
                    return
                body = request.post_data_json
                state['enabled'] = body.pop('enabled')
                state['config'] = body
                state['starts'] += 1
            response = {'enabled': state['enabled'], 'config': state['config'], 'message': '예약 재고를 확인합니다', 'reserved_today': 2,
                        'next_run_at': None, 'task': None}
        elif path.endswith('/clients'):
            if method == 'POST':
                client.update(request.post_data_json)
                client['blogs'] = []
                response = client
            else:
                response = [] if state['empty'] else [client]
        elif path.endswith('/blogs') and method == 'POST':
            blog = {**request.post_data_json, 'id': 'blog', 'status': 'active'}
            client['blogs'] = [blog]
            response = blog
        elif path.endswith('/campaigns'):
            if method == 'POST':
                state['empty'] = False
                campaign['name'] = request.post_data_json['name']
                response = campaign
            else:
                response = [] if state['empty'] else [campaign]
        elif path.endswith('/clients/hospital'):
            response = client
        elif path.endswith('/campaigns/campaign'):
            if method == 'PATCH':
                campaign.update(request.post_data_json)
            response = campaign
        elif path.endswith('/keywords/hunt') and method == 'POST':
            state['hunt'] = {'id': 'hunt-task', 'type': 'keyword_hunt', 'status': 'running', 'progress': 1,
                             'total': 200, 'message': '통검 자리 확인 12/200', 'result': {}}
            response = state['hunt']
        elif path.endswith('/tasks/hunt-task'):
            response = state['hunt']
        elif path.endswith('/keywords'):
            response = state['keywords']
        elif path.endswith('/jobs'):
            response = [{'id': str(i), 'title': title, 'status': status, 'scheduled_at': '2026-09-15T10:00:00'} for i, (title, status) in enumerate([
                ('습진 관리 안내', 'published'), ('피부 상담 전 알아둘 점', 'submitted'), ('진료 과정 안내', 'uncertain')])]
        elif path.endswith('/tasks'):
            response = [state['bulk']] if state['bulk'] else []
        await request_route.fulfill(json=response)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1440, 'height': 1100})
        await context.route('**/*', route)
        await context.add_init_script("localStorage.setItem('access_token','fake-test-token'); localStorage.setItem('user', JSON.stringify({id:'u',name:'테스트',email:'test@example.invalid'}));")
        page = await context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        await page.goto(BASE + '/dashboard/one-stop')
        await expect(page.get_by_role('button', name='30개 글 자동 작성·예약 시작')).to_be_enabled()
        await page.get_by_role('button', name='50개', exact=True).click()
        await expect(page.get_by_label('총 몇 개의 글을 준비할까요?')).to_have_value('50')
        await page.get_by_role('button', name='30개', exact=True).click()
        await page.get_by_label('랜딩 URL (선택)', exact=True).fill('https://example.com/bulk')
        await page.screenshot(path=str(OUTPUT / 'automation-bulk.png'), full_page=True)
        await page.get_by_role('button', name='30개 글 자동 작성·예약 시작').click()
        await expect(page.get_by_text('대량 작업 진행 중', exact=True)).to_be_visible()
        await page.reload()
        await expect(page.get_by_text('대량 작업 진행 중', exact=True)).to_be_visible()
        await page.get_by_role('button', name='새 원고 준비 중단', exact=True).click()
        await expect(page.get_by_text('새 원고 준비가 중단되었습니다.', exact=True)).to_be_visible()
        await page.get_by_role('button', name='매일 자동 운영', exact=True).click()
        await expect(page.get_by_role('button', name='자동 운영 시작', exact=True)).to_be_enabled()
        await expect(page.get_by_text('확인이 필요한 항목이 있습니다')).to_be_visible()
        await page.get_by_label('글에서 안내할 랜딩페이지 URL').fill('https://example.com/guide')
        await page.get_by_role('button', name='자동 운영 시작', exact=True).click()
        await expect(page.get_by_text('자동 운영이 켜져 있습니다')).to_be_visible()
        assert state['starts'] == 1 and state['config']['landing_url'] == 'https://example.com/guide'
        await page.evaluate('window.scrollTo(0, 0)')
        await page.screenshot(path=str(OUTPUT / 'automation-desktop.png'), full_page=True)
        await page.reload()
        await page.get_by_role('button', name='매일 자동 운영', exact=True).click()
        await expect(page.get_by_text('자동 운영이 켜져 있습니다')).to_be_visible()
        await page.get_by_role('button', name='일시정지', exact=True).click()
        await expect(page.get_by_role('button', name='자동 운영 시작', exact=True)).to_be_visible()
        await page.set_viewport_size({'width': 390, 'height': 844})
        await page.screenshot(path=str(OUTPUT / 'automation-mobile.png'), full_page=True)
        assert await page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile horizontal overflow'
        state['empty'] = True
        await page.reload()
        await page.get_by_label('병원 이름').fill('서울봄의원')
        await page.get_by_label('진료 항목', exact=True).fill('습진, 여드름')
        await page.get_by_label('네이버 블로그 ID').fill('springclinic')
        await page.screenshot(path=str(OUTPUT / 'automation-first-setup.png'), full_page=True)
        await page.get_by_role('button', name='저장하고 발행 기준 정하기').click()
        await page.get_by_role('button', name='매일 자동 운영', exact=True).click()
        await expect(page.get_by_role('button', name='자동 운영 시작', exact=True)).to_be_enabled()
        assert state['starts'] == 2, 'Setup must not start publication'
        state['fail'] = True
        await page.get_by_role('button', name='자동 운영 시작', exact=True).click()
        await expect(page.get_by_role('alert').filter(has_text='사진 세트를 연결하세요')).to_be_visible()
        await page.wait_for_timeout(5500)
        await expect(page.get_by_role('alert').filter(has_text='사진 세트를 연결하세요')).to_be_visible()
        assert not errors, errors
        await browser.close()
    print('PASS: bulk presets, one-click start, reload recovery, cancellation, recurring start/pause, mobile, onboarding, validation; no page errors')


if __name__ == '__main__':
    asyncio.run(main())
