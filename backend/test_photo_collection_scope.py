"""다른 병원 사진이 글에 실리지 않는다(2026-09-30 소잠한의원 실측).

"소잠한의원용 전후 사진 없고, 처음 보는 전후 사진 있음."

한 계정(대행사)이 여러 병원을 돌린다. 그런데 사진 후보를 고르는 곳만 병원 기본 사진 세트를
보지 않아서, 세트를 안 고른 캠페인이 **그 계정의 사진 전부**를 후보로 삼았다. 남의 병원
전후 사진이 그대로 올라간다 — 의료광고로도, 신뢰로도 가장 비싼 실패다.
"""
from pathlib import Path
import tempfile
import unittest

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.campaign import Campaign, Client, Draft
from app.models.media_pool import PoolCollection, PoolCollectionMember, PoolImage
from app.services import campaign_jobs


class Ctx:
    """job_worker.JobContext 대신 쓰는 최소 대역."""

    def __init__(self, db, user_id, payload):
        self.db, self.user_id, self.payload = db, user_id, payload
        self.job = None

    async def progress(self, *_args, **_kw):
        return None

    async def cancelled(self):
        return False


class CollectionScopeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine('sqlite+aiosqlite:///' + str(Path(self.tmp.name) / 'scope.db'))
        async with self.engine.begin() as conn:
            for table in (Campaign.__table__, Client.__table__, Draft.__table__,
                          PoolImage.__table__, PoolCollection.__table__, PoolCollectionMember.__table__):
                await conn.run_sync(lambda sync, t=table: t.create(sync))
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self):
        await self.engine.dispose()
        self.tmp.cleanup()

    async def _two_clinics(self, *, default_collection):
        async with self.sessions() as db:
            db.add(Client(id='sojam', user_id='u', name='소잠한의원',
                          default_collection_id='c-sojam' if default_collection else None))
            db.add(Client(id='other', user_id='u', name='다른병원'))
            db.add(Campaign(id='camp', user_id='u', client_id='sojam', name='소잠'))
            db.add(PoolCollection(id='c-sojam', user_id='u', name='소잠 사진'))
            db.add(PoolImage(id='p-sojam', user_id='u', data=b'x', active=True, scene='consult', tags=['상담']))
            db.add(PoolImage(id='p-other-beforeafter', user_id='u', data=b'x', active=True,
                             scene='patient', tags=['전후', '비교']))
            db.add(PoolCollectionMember(collection_id='c-sojam', pool_image_id='p-sojam', user_id='u'))
            await db.commit()

    async def test_the_clinic_default_set_is_used_when_the_campaign_has_none(self):
        """캠페인에 세트가 없어도 **그 병원 세트**를 쓴다. 전체 풀로 흘러가면 안 된다."""
        await self._two_clinics(default_collection=True)
        async with self.sessions() as db:
            ctx = Ctx(db, 'u', {'campaign_id': 'camp'})
            rows = await campaign_jobs._collection_photos(db, 'u', 'c-sojam')
            self.assertEqual([r.id for r in rows], ['p-sojam'])
            # 원고가 없어 배치는 0건이지만, 세트를 병원 기본값에서 찾아 캠페인에 적어 둬야 한다.
            await campaign_jobs.image_plan(ctx)
        async with self.sessions() as db:
            camp = await db.get(Campaign, 'camp')
            self.assertEqual(camp.collection_id, 'c-sojam', '병원 기본 세트가 캠페인에 자리잡아야 한다')

    async def test_without_any_set_a_multi_clinic_account_refuses_instead_of_mixing(self):
        """세트를 못 정했는데 병원이 여럿이면 멈춘다 — 남의 전후 사진을 올리느니 물어본다."""
        await self._two_clinics(default_collection=False)
        async with self.sessions() as db:
            ctx = Ctx(db, 'u', {'campaign_id': 'camp'})
            with self.assertRaises(ValueError) as caught:
                await campaign_jobs.image_plan(ctx)
            message = str(caught.exception)
            self.assertIn('사진 세트', message)
            self.assertIn('→', message, '무엇을 하면 되는지까지 적혀야 한다')

    async def test_a_set_never_leaks_another_clinics_photo(self):
        """세트로 좁히면 그 세트에 없는 사진은 후보가 되지 않는다."""
        await self._two_clinics(default_collection=True)
        async with self.sessions() as db:
            rows = await campaign_jobs._collection_photos(db, 'u', 'c-sojam')
        self.assertNotIn('p-other-beforeafter', [r.id for r in rows])


if __name__ == '__main__':
    unittest.main()
