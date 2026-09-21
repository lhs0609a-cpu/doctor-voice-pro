"""Browser check of Word upload, persisted formatting, preview and schedule request.

API responses are isolated fixtures. Real Naver editing is verified separately.
"""
import asyncio
import io
import os
from pathlib import Path
from urllib.parse import urlparse
from docx import Document
from playwright.async_api import async_playwright, expect

BASE=os.environ.get('UX_BASE_URL', 'http://127.0.0.1:8317').rstrip('/')
OUTPUT=Path(__file__).resolve().parents[2]/'output/naver-formatting-verification'

async def main():
    config=dict(enabled=False,bold=True,quote=True,color=True,background=True,text_color='#0078cb',background_color='#fff8b2',phrases=[])
    blog=dict(id='b',blog_id='fixture_blog',label='테스트 블로그',status='active',daily_limit=2)
    client=dict(id='h',name='테스트 병원',blogs=[blog],briefs=[],diseases=[],treatments=[],regions=[])
    campaign=dict(id='c',name='Word 예약',client_id='h',client_name='테스트 병원',blog_ids=['b'],settings={},stats={},step=3,status='draft')
    draft=dict(id='d',title='중요 포인트 테스트',source='upload',status='ready',char_count=200,checks={},tags=[],image_count_target=0,image_plan=[])
    state={'drafts':[],'saves':0,'scheduled':False}
    async def route(r):
        req=r.request; path=urlparse(req.url).path
        if '/api/' not in path:
            if req.url.startswith(BASE):await r.continue_()
            else:await r.abort()
            return
        response={}
        if path.endswith('/campaigns'):response=[campaign]
        elif path.endswith('/clients'):response=[client]
        elif path.endswith('/clients/h'):response=client
        elif path.endswith('/campaigns/c'):response=campaign
        elif path.endswith('/agent/status'):response={'online':False,'running':False,'devices':[]}
        elif path.endswith('/formatting'):
            if req.method=='PUT':config.update(req.post_data_json);state['saves']+=1
            response=config
        elif path.endswith('/drafts/upload'):
            assert b'word/document.xml' in req.post_data_buffer or b'PK' in req.post_data_buffer
            state['drafts']=[draft];response=[draft]
        elif path.endswith('/drafts'):response=state['drafts']
        elif path.endswith('/formatting-preview'):
            assert req.post_data_json['enabled']
            response={'title':draft['title'],'blocks':[{'type':'text','spans':[{'t':'핵심 기준','b':True},{'t':'과 일반 본문입니다.'}]},{'type':'quote','spans':[{'t':'핵심은 개인별 상태에 맞는 선택입니다.'}]}]}
        elif path.endswith('/schedule/preview') or path.endswith('/schedule/commit'):
            assert req.post_data_json['draft_ids']==['d']
            assert req.post_data_json['blog_ids']==['b']
            response={'total':1,'assigned':[{'draft_id':'d','title':draft['title'],'blog_ref_id':'b','blog_label':'테스트 블로그','scheduled_at':'2026-09-23T10:00:00'}],'unassigned':0,'calendar':[],'warnings':[]}
            if path.endswith('/commit'):state['scheduled']=True
        elif path.endswith('/autopilot'):
            response={'enabled':False,'config':dict(image_count=0,landing_url='',landing_purpose='',daily_posts=2)}
        elif any(path.endswith(suffix) for suffix in ('/keywords','/jobs','/tasks','/devices','/briefs','/collections')):response=[]
        await r.fulfill(json=response)
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True)
        context=await browser.new_context(viewport={'width':1440,'height':1100})
        await context.add_init_script("localStorage.setItem('access_token','fixture');localStorage.setItem('user',JSON.stringify({id:'u',name:'테스트',email:'test@example.invalid'}));")
        await context.route('**/*',route)
        page=await context.new_page();errors=[]
        page.set_default_timeout(120000)
        page.on('pageerror',lambda e:errors.append(e.stack or str(e)))
        await page.goto(BASE+'/dashboard/one-stop',timeout=120000)
        await page.get_by_text('Word 원고로 예약 발행',exact=True).click()
        doc=Document();doc.add_heading(draft['title'],level=1);doc.add_paragraph('핵심 기준과 일반 본문입니다.')
        data=io.BytesIO();doc.save(data)
        await page.get_by_label('예약할 Word 파일').set_input_files({'name':'서식.docx','mimeType':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','buffer':data.getvalue()})
        await expect(page.get_by_role('button',name='선택한 1개 원고 예약 설정')).to_be_enabled()
        await page.get_by_label('핵심 문구 자동 강조').check()
        await page.get_by_label('특히 강조할 문구',exact=False).fill('핵심 기준')
        await expect(page.get_by_text('설정 저장됨',exact=True)).to_be_visible()
        assert config['phrases']==['핵심 기준'] and config['enabled'] and state['saves']>0
        await page.get_by_role('button',name='강조 미리보기',exact=True).click()
        await expect(page.get_by_label('강조 미리보기',exact=True)).to_contain_text('핵심 기준')
        OUTPUT.mkdir(parents=True,exist_ok=True)
        await page.screenshot(path=str(OUTPUT/'homepage-word-formatting.png'),full_page=True)
        await page.reload()
        await page.get_by_text('Word 원고로 예약 발행',exact=True).click()
        await expect(page.get_by_label('핵심 문구 자동 강조')).to_be_checked()
        await expect(page.get_by_label('특히 강조할 문구',exact=False)).to_have_value('핵심 기준')
        await page.get_by_label('중요 포인트 테스트',exact=False).check()
        await page.get_by_role('button',name='선택한 1개 원고 예약 설정').click()
        await page.get_by_role('button',name='미리보기',exact=True).click()
        await expect(page.get_by_text('배정 미리보기',exact=True)).to_be_visible()
        await page.screenshot(path=str(OUTPUT/'homepage-word-schedule.png'),full_page=True)
        assert not state['scheduled'],'Preview must not create a reservation'
        await page.get_by_role('button',name='예약 걸기',exact=True).click()
        await page.get_by_role('alertdialog').get_by_role('button',name='예약 걸기',exact=True).click()
        await expect(page.get_by_text('예약을 저장했습니다.',exact=False)).to_be_visible()
        assert state['scheduled'],'Confirmation must submit the selected manuscript'
        assert not errors,errors
        await browser.close()
    print('PASS: Word upload, automatic save, reload persistence, styled preview, selected-only schedule preview and confirmation; API fixtures only, no real publication')

asyncio.run(main())
