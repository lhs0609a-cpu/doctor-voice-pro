"""Connection states are mocked; no account login or publication occurs."""
import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright, expect

BASE = os.environ.get('UX_BASE_URL', 'http://127.0.0.1:8318').rstrip('/')
OUT = Path(__file__).resolve().parents[2] / 'docs' / 'ux-preview'


async def main():
    state = {'mode': 'offline'}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1440, 'height': 1000})
        await context.add_init_script("localStorage.setItem('access_token','fake'); localStorage.setItem('user',JSON.stringify({id:'u',email:'demo@example.invalid'}));")
        async def route(r):
            url = r.request.url
            if '/agent/status' in url:
                if state['mode'] == 'error':
                    await r.fulfill(status=503, json={'detail': 'unavailable'})
                else:
                    await r.fulfill(json={'online': state['mode'] in ('idle', 'running'), 'running': state['mode'] == 'running', 'devices': [], 'version': '1.4.1'})
            elif '/api/' in url:
                await r.fulfill(json=[])
            elif url.startswith(BASE):
                await r.continue_()
            else:
                await r.abort()
        await context.route('**/*', route)
        page = await context.new_page()
        page.set_default_navigation_timeout(180000)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        for mode, text in [('offline', '실행기 창이 열려 있어도 계정 연결이 필요해요'), ('error', '연결 상태를 확인하지 못했어요'), ('idle', '연결 완료! 실행기에서 시작 버튼을 눌러 주세요'), ('running', '실행기가 자동 발행을 처리하고 있어요')]:
            state['mode'] = mode
            await page.goto(BASE + '/dashboard/launcher')
            await expect(page.get_by_text(text, exact=True)).to_be_visible(timeout=60000)
            await expect(page.get_by_text('실행기 꺼짐', exact=True)).to_have_count(0)
            if mode == 'offline':
                await page.get_by_role('button', name='지금 이 계정과 연결하기', exact=True).click()
                await expect(page.get_by_role('alert').filter(has_text='옛 ZIP 실행기를 닫고')).to_be_visible()
                await page.get_by_text('이미 실행기를 켰는데 연결이 안 돼요', exact=True).click()
                await expect(page.get_by_text('demo@example.invalid', exact=False).last).to_be_visible()
                OUT.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(OUT / 'launcher-connection-guide.png'), full_page=True)
                await page.set_viewport_size({'width': 390, 'height': 844})
                assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                await page.screenshot(path=str(OUT / 'launcher-connection-mobile.png'), full_page=True)
                await page.set_viewport_size({'width': 1440, 'height': 1000})
        assert not errors, errors
        await browser.close()
    print('PASS: offline, server error, idle, running, mobile overflow; no page errors')


if __name__ == '__main__':
    asyncio.run(main())
