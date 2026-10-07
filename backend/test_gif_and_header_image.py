"""움직이는 GIF 와 머리 사진이 **실제 바이트로** 살아남는지.

프레임 수를 세어 확인한다. 이 두 길에는 테스트가 아예 없었다 — prepare_job_images 는
0건이었고, _with_header 의 사진 분기는 가짜 DB 가 None 을 돌려줘 한 번도 실행되지 않았다
(2026-10-07). GIF 는 다시 인코딩하면 첫 장면만 남아 멈춘 그림이 되므로, '파일이 만들어졌다'
가 아니라 '프레임이 그대로다'를 봐야 한다.
"""
import asyncio
import base64
import io
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ['MEDIA_DIR'] = _TMP
os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///./test-unused.db')
os.environ.setdefault('DATABASE_URL_SYNC', 'sqlite:///./test-unused.db')

from PIL import Image
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.api.campaign import JobBlock, _with_header
from app.models.campaign import Blog, Draft, PublishJob
from app.models.media_pool import ImageVariant, PoolImage
from app.services import campaign_jobs

FRAMES = 4


def animated_gif(frames: int = FRAMES) -> bytes:
    imgs = [Image.new("RGB", (120, 90), (i * 50 % 255, 80, 160)) for i in range(frames)]
    buffer = io.BytesIO()
    imgs[0].save(buffer, format="GIF", save_all=True, append_images=imgs[1:], duration=120, loop=0)
    return buffer.getvalue()


def still_jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (400, 300), (200, 100, 50)).save(buffer, format="JPEG")
    return buffer.getvalue()


def read(data: bytes):
    image = Image.open(io.BytesIO(data))
    return image.format, getattr(image, "n_frames", 1), getattr(image, "is_animated", False)


class ImageBytesTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.engine = create_async_engine('sqlite+aiosqlite:///' + str(Path(self.dir.name) / 't.db'))
        async with self.engine.begin() as conn:
            for table in (Blog.__table__, PublishJob.__table__, Draft.__table__,
                          PoolImage.__table__, ImageVariant.__table__):
                await conn.run_sync(lambda sync, t=table: t.create(sync))
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self):
        await self.engine.dispose()
        self.dir.cleanup()

    async def _pool_image(self, db, image_id, data, ctype):
        db.add(PoolImage(id=image_id, user_id='u', content_type=ctype, data=data, filename='x'))
        await db.commit()

    async def test_an_animated_gif_keeps_every_frame_through_the_photo_pool(self):
        """원고 자동화(사진 풀) 경로. 여기가 JPEG 로 눌러 버려 재생이 멈췄다."""
        raw = animated_gif()
        async with self.sessions() as db:
            await self._pool_image(db, 'p1', raw, 'image/gif')
            job = PublishJob(id='j1', user_id='u', campaign_id='c', draft_id='d',
                             blog_ref_id='b', scheduled_at=datetime.utcnow())
            db.add(job)
            await db.commit()
            draft = Draft(id='d', user_id='u', campaign_id='c', title='t', body='b',
                          image_plan=[{"slot": 0, "after_paragraph": 0, "pool_image_id": "p1"}])
            out = await campaign_jobs.prepare_job_images(db, job, draft)
            await db.commit()
        path = Path(out[0]['path'])
        self.assertEqual(path.suffix, '.gif')
        self.assertEqual(read(path.read_bytes()), ('GIF', FRAMES, True))
        # 같은 파일을 그대로 보내면 네이버 중복사진 판정의 첫 층(파일 해시)에 걸린다.
        self.assertNotEqual(path.read_bytes(), raw)
        self.assertTrue(campaign_jobs.image_as_data_url(str(path)).startswith('data:image/gif;base64,'))

    async def test_a_still_photo_still_goes_through_the_uniquifier(self):
        """GIF 분기를 넣었다고 보통 사진이 유니크화를 건너뛰면 안 된다."""
        async with self.sessions() as db:
            await self._pool_image(db, 'p2', still_jpeg(), 'image/jpeg')
            job = PublishJob(id='j2', user_id='u', campaign_id='c', draft_id='d2',
                             blog_ref_id='b', scheduled_at=datetime.utcnow())
            db.add(job)
            await db.commit()
            draft = Draft(id='d2', user_id='u', campaign_id='c', title='t', body='b',
                          image_plan=[{"slot": 0, "after_paragraph": 0, "pool_image_id": "p2"}])
            out = await campaign_jobs.prepare_job_images(db, job, draft)
            await db.commit()
            variants = (await db.execute(__import__('sqlalchemy').select(ImageVariant))).scalars().all()
        self.assertEqual(Path(out[0]['path']).suffix, '.jpg')
        self.assertIsNotNone(out[0]['phash'])
        self.assertEqual(len(variants), 1, "변형 기록이 남아야 다음 글이 '가장 먼 변형'을 고를 수 있다")

    async def test_a_gif_header_photo_still_moves(self):
        """글 맨 위 고정 사진도 같은 규칙을 탄다 — 순서는 첫 문장 → 사진 → 링크 카드."""
        async with self.sessions() as db:
            await self._pool_image(db, 'h1', animated_gif(), 'image/gif')
            blog = Blog(id='b', user_id='u', client_id='c', blog_id='x',
                        header_text='오늘 위례해오름한의원에서는', header_image_id='h1',
                        header_link_url='https://clinic.example.com/reserve')
            out = await _with_header(db, [JobBlock(type="text", content="본문입니다.")], blog, None)
        self.assertEqual([b.type for b in out], ['text', 'image', 'text', 'text'])
        self.assertEqual([b.content for b in out if b.type == 'text'],
                         ['오늘 위례해오름한의원에서는', 'https://clinic.example.com/reserve', '본문입니다.'])
        payload = [b for b in out if b.type == 'image'][0].image
        self.assertTrue(payload.startswith('data:image/gif;base64,'))
        self.assertEqual(read(base64.b64decode(payload.split('base64,')[1])), ('GIF', FRAMES, True))


if __name__ == '__main__':
    unittest.main()
