"""워드 업로드 → 발행 실행기까지, 서식이 살아서 도착하는지.

parse 자체는 test_docx_import.py 가 본다. 여기서는 붙인 자리만 본다:
업로드가 블록을 원고에 저장하는지, 문서 안 사진이 사진 풀로 가는지,
그리고 클레임이 실행기 능력(rich_text_v1)에 따라 서식을 붙이거나 눌러서 보내는지.
"""
import copy
import unittest

import httpx
from fastapi import FastAPI

from test_docx_import import _doc_with_everything
from test_publish_protocol import DatabaseCase

from app.api import campaign as api
from app.models.campaign import AutopilotPolicy, Blog, Campaign, CampaignKeyword, Client, Draft, PublishJob
from app.models.media_pool import PoolImage
from app.models.publish_queue import QueuedPost, ScheduleMark
from app.models.user import User


class DocxUploadTests(DatabaseCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with self.engine.begin() as conn:
            for table in (Blog.__table__, Draft.__table__, Campaign.__table__,
                          CampaignKeyword.__table__, Client.__table__, PoolImage.__table__, AutopilotPolicy.__table__, ScheduleMark.__table__, QueuedPost.__table__):
                await conn.run_sync(lambda sync, t=table: t.create(sync))
        async with self.sessions() as db:
            db.add(Client(id='client', user_id='u', name='clinic'))
            db.add(Campaign(id='c', user_id='u', client_id='client', name='test', blog_ids=['b']))
            db.add(Blog(id='b', user_id='u', client_id='client', blog_id='testblog', status='active'))
            db.add(CampaignKeyword(id='k', campaign_id='c', user_id='u', keyword='아토피'))
            await db.commit()

        app = FastAPI()
        app.include_router(api.router)

        async def db_override():
            async with self.sessions() as db:
                yield db

        app.dependency_overrides[api.get_db] = db_override
        app.dependency_overrides[api.get_current_user] = lambda: User(id='u')
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test')

    async def asyncTearDown(self):
        await self.client.aclose()
        await super().asyncTearDown()

    async def upload(self, name: str = '아토피.docx') -> dict:
        response = await self.client.post(
            '/campaigns/c/drafts/upload',
            files={'files': (name, _doc_with_everything(),
                             'application/vnd.openxmlformats-officedocument.wordprocessingml.document')},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()[0]

    async def claim(self, draft_id: str, capabilities=(), job: str = 'j0') -> dict:
        async with self.sessions() as db:
            row = await db.get(PublishJob, job)
            row.draft_id = draft_id
            await db.commit()
        response = await self.client.post('/agent/claim', json={
            'blog_ref_id': 'b', 'protocol_version': 2, 'capabilities': list(capabilities)})
        self.assertEqual(response.status_code, 200, response.text)
        claimed = response.json()
        self.assertEqual(len(claimed), 1, response.text)
        return claimed[0]

    async def test_upload_keeps_the_document_order_and_shape(self):
        draft = await self.upload()
        async with self.sessions() as db:
            row = await db.get(Draft, draft['id'])
            kinds = [b['type'] for b in row.blocks]
        self.assertEqual(kinds, ['text', 'heading', 'text', 'quote', 'list', 'table', 'image', 'text'])
        self.assertEqual(draft['title'], '아토피 초기 증상 확인법')

    async def test_upload_moves_document_photos_into_the_pool(self):
        draft = await self.upload()
        async with self.sessions() as db:
            row = await db.get(Draft, draft['id'])
            image = next(b for b in row.blocks if b['type'] == 'image')
            self.assertNotIn('image', image)         # 바이트를 원고에 담지 않는다
            pool = await db.get(PoolImage, image['pool_image_id'])
        self.assertIsNotNone(pool)
        self.assertEqual(pool.content_type, 'image/jpeg')
        self.assertTrue(pool.data)

    async def test_upload_reports_what_it_read(self):
        draft = await self.upload()
        self.assertEqual(draft['checks']['import'],
                         {'source': 'docx', 'images': 1, 'tables': 1, 'headings': 1, 'warnings': []})

    async def test_table_survives_in_the_plain_text_too(self):
        draft = await self.upload()
        async with self.sessions() as db:
            row = await db.get(Draft, draft['id'])
        self.assertIn('1일차 | 보습제 바르기', row.body)
        self.assertGreater(row.char_count, 0)

    async def test_broken_word_file_is_rejected(self):
        response = await self.client.post(
            '/campaigns/c/drafts/upload',
            files={'files': ('깨진.docx', b'not a docx at all', 'application/octet-stream')})
        self.assertEqual(response.status_code, 400)
        self.assertIn('워드 파일을 읽지 못했습니다', response.json()['detail'])

    async def test_uploaded_manuscript_can_be_scheduled(self):
        """워드로 올린 완성 원고도 예약 대상이다(변형의 원본만 빠진다)."""
        draft = await self.upload()
        response = await self.client.post('/campaigns/c/schedule/preview', json={
            'start_date': '2026-10-01', 'days': 3, 'draft_ids': [draft['id']]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([i['draft_id'] for i in response.json()['assigned']], [draft['id']])

    async def test_a_manuscript_with_variants_stays_out_of_the_schedule(self):
        draft = await self.upload()
        async with self.sessions() as db:
            db.add(Draft(id='v1', user_id='u', client_id='client', campaign_id='c', source='variant',
                         parent_draft_id=draft['id'], title='변형', body='변형 본문', status='ready'))
            await db.commit()
        response = await self.client.post('/campaigns/c/schedule/preview', json={
            'start_date': '2026-10-01', 'days': 3, 'draft_ids': [draft['id']]})
        self.assertEqual(response.status_code, 400, response.text)   # 원본만 고르면 예약할 것이 없다

    async def test_editing_the_body_drops_the_word_formatting(self):
        """고친 글이 이긴다 — 블록을 남겨 두면 발행이 그것을 먼저 보고 수정이 사라진다."""
        draft = await self.upload()
        response = await self.client.put(f'/drafts/{draft["id"]}', json={'body': '다시 쓴 본문입니다.'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn('import', response.json()['checks'])
        async with self.sessions() as db:
            row = await db.get(Draft, draft['id'])
        self.assertIsNone(row.blocks)

    async def test_new_launcher_gets_the_formatting(self):
        draft = await self.upload()
        claimed = await self.claim(draft['id'], capabilities=['rich_text_v1'])
        kinds = [b['type'] for b in claimed['blocks']]
        self.assertEqual(kinds, ['text', 'heading', 'text', 'quote', 'list', 'table', 'image', 'text'])
        heading = claimed['blocks'][1]
        self.assertEqual(heading['level'], 2)
        self.assertTrue(any(s.get('b') for s in claimed['blocks'][0]['spans']))
        self.assertTrue(claimed['blocks'][5]['header'])
        self.assertTrue(claimed['blocks'][6]['image'].startswith('data:image/jpeg;base64,'))

    async def test_point_settings_persist_and_preview_keeps_word_content(self):
        draft = await self.upload()
        settings = {'enabled':True,'phrases':['진료 전 확인할 것'],'text_color':'#0078cb'}
        saved = await self.client.put('/campaigns/c/formatting',json=settings)
        self.assertEqual(saved.status_code,200,saved.text)
        loaded = await self.client.get('/campaigns/c/formatting')
        self.assertEqual(saved.json(),loaded.json())
        preview = await self.client.post(f'/drafts/{draft["id"]}/formatting-preview',json=settings)
        self.assertEqual(preview.status_code,200,preview.text)
        self.assertEqual(preview.json()['blocks'][6], {'type':'image'})
        self.assertTrue(any(b['type']=='quote' for b in preview.json()['blocks']))
        invalid = await self.client.put('/campaigns/c/formatting',json={'text_color':'red;display:none'})
        self.assertEqual(invalid.status_code,422)

    async def test_point_style_capability_preserves_inline_styles(self):
        draft = await self.upload()
        claimed = await self.claim(draft['id'],capabilities=['point_styles_v1'])
        self.assertTrue(any(s.get('b') for s in claimed['blocks'][0]['spans']))
        self.assertEqual(claimed['blocks'][3]['type'],'quote')

    async def test_old_client_cannot_silently_drop_requested_points(self):
        draft = await self.upload()
        async with self.sessions() as db:
            row = await db.get(Draft,draft['id'])
            row.checks = {**row.checks,'formatting':{'enabled':True}}
            job = await db.get(PublishJob,'j0')
            job.draft_id = row.id
            await db.commit()
        response = await self.client.post('/agent/claim',json={'blog_ref_id':'b','protocol_version':2,'capabilities':[]})
        self.assertEqual(response.status_code,426,response.text)
        async with self.sessions() as db:
            job = await db.get(PublishJob,'j0')
            self.assertEqual(job.status,'queued')
            self.assertIsNone(job.lock_token)

    async def test_old_launcher_gets_plain_text_but_keeps_the_photo(self):
        draft = await self.upload()
        claimed = await self.claim(draft['id'])
        kinds = [b['type'] for b in claimed['blocks']]
        self.assertEqual(kinds, ['text', 'image', 'text'])
        self.assertNotIn('spans', claimed['blocks'][0])
        self.assertIn('1일차 | 보습제 바르기', claimed['blocks'][0]['content'])
        self.assertIn('1일차 | 보습제 바르기', claimed['content'])

    async def test_photo_can_be_left_out(self):
        draft = await self.upload()
        async with self.sessions() as db:
            row = await db.get(PublishJob, 'j0')
            row.draft_id = draft['id']
            await db.commit()
        response = await self.client.post('/agent/claim', json={
            'blog_ref_id': 'b', 'protocol_version': 2, 'include_images': False,
            'capabilities': ['rich_text_v1']})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn('image', [b['type'] for b in response.json()[0]['blocks']])

    async def test_missing_photo_stops_the_publish(self):
        draft = await self.upload()
        async with self.sessions() as db:
            row = await db.get(Draft, draft['id'])
            # 제자리에서 고치면 SQLAlchemy 가 JSON 변경을 못 본다(옛 값과 같은 객체라서).
            blocks = copy.deepcopy(row.blocks)
            for block in blocks:
                if block['type'] == 'image':
                    block['pool_image_id'] = 'gone'
            row.blocks = blocks
            job = await db.get(PublishJob, 'j0')
            job.draft_id = draft['id']
            await db.commit()
        response = await self.client.post('/agent/claim', json={
            'blog_ref_id': 'b', 'protocol_version': 2, 'capabilities': ['rich_text_v1']})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), [])       # 사진 없이 발행하지 않는다


if __name__ == '__main__':
    unittest.main()
