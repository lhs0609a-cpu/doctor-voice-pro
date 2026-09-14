"""홈페이지 ↔ 실행기 자동 연결 계약 — 1회용 코드 → 기기 키 → 로그인 토큰."""
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import campaign as api
from app.core.security import decode_token
from app.models.campaign import AgentDevice, AgentPairCode, AgentSession
from app.models.user import User


class PairingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine('sqlite+aiosqlite:///' + str(Path(self.tmp.name) / 'pair.db'))
        async with self.engine.begin() as conn:
            for table in (AgentSession.__table__, AgentPairCode.__table__, AgentDevice.__table__):
                await conn.run_sync(lambda sync, t=table: t.create(sync))
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.user = 'u'
        app = FastAPI()
        app.include_router(api.router)

        async def db_override():
            async with self.sessions() as db:
                yield db
        app.dependency_overrides[api.get_db] = db_override
        app.dependency_overrides[api.get_current_user] = lambda: User(id=self.user)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test')

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.engine.dispose()
        self.tmp.cleanup()

    async def pair(self, device_id='pc-1'):
        code = (await self.client.post('/agent/pair')).json()['code']
        claim = await self.client.post('/agent/pair/claim', json={'code': code, 'device_id': device_id, 'label': '원장님 PC'})
        return code, claim

    async def test_code_becomes_a_device_key_and_the_key_becomes_a_login_token(self):
        code, claim = await self.pair()
        self.assertEqual(len(code), 8)
        self.assertEqual(claim.status_code, 200, claim.text)
        secret = claim.json()['device_secret']
        token = await self.client.post('/agent/device-token', json={'device_id': 'pc-1', 'device_secret': secret})
        self.assertEqual(token.status_code, 200, token.text)
        self.assertEqual(decode_token(token.json()['access_token'])['sub'], 'u')

    async def test_code_works_only_once(self):
        code, _ = await self.pair()
        again = await self.client.post('/agent/pair/claim', json={'code': code, 'device_id': 'pc-2'})
        self.assertEqual(again.status_code, 400, again.text)

    async def test_expired_code_is_refused(self):
        code = (await self.client.post('/agent/pair')).json()['code']
        async with self.sessions() as db:
            row = await db.get(AgentPairCode, code)
            row.expires_at = datetime.utcnow() - timedelta(seconds=1)
            await db.commit()
        claim = await self.client.post('/agent/pair/claim', json={'code': code, 'device_id': 'pc-1'})
        self.assertEqual(claim.status_code, 400, claim.text)

    async def test_code_is_forgiving_about_case_and_dashes(self):
        code = (await self.client.post('/agent/pair')).json()['code']
        typed = f'{code[:4]}-{code[4:]}'.lower()
        claim = await self.client.post('/agent/pair/claim', json={'code': typed, 'device_id': 'pc-1'})
        self.assertEqual(claim.status_code, 200, claim.text)

    async def test_key_is_stored_only_as_a_hash(self):
        _, claim = await self.pair()
        async with self.sessions() as db:
            device = await db.get(AgentDevice, 'pc-1')
        self.assertNotEqual(device.secret_hash, claim.json()['device_secret'])
        self.assertEqual(len(device.secret_hash), 64)

    async def test_wrong_key_gets_no_token(self):
        await self.pair()
        token = await self.client.post('/agent/device-token', json={'device_id': 'pc-1', 'device_secret': 'guess'})
        self.assertEqual(token.status_code, 401, token.text)

    async def test_revoked_device_gets_no_token_and_its_light_goes_off(self):
        _, claim = await self.pair()
        await self.client.post('/agent/heartbeat', json={'device_id': 'pc-1', 'version': '1.4.0', 'running': True})
        revoke = await self.client.delete('/agent/devices/pc-1')
        self.assertEqual(revoke.status_code, 200, revoke.text)
        token = await self.client.post('/agent/device-token',
                                       json={'device_id': 'pc-1', 'device_secret': claim.json()['device_secret']})
        self.assertEqual(token.status_code, 401, token.text)
        self.assertFalse((await self.client.get('/agent/status')).json()['online'])

    async def test_repairing_replaces_the_old_key(self):
        _, first = await self.pair()
        _, second = await self.pair()
        old = await self.client.post('/agent/device-token',
                                     json={'device_id': 'pc-1', 'device_secret': first.json()['device_secret']})
        new = await self.client.post('/agent/device-token',
                                     json={'device_id': 'pc-1', 'device_secret': second.json()['device_secret']})
        self.assertEqual((old.status_code, new.status_code), (401, 200))

    async def test_pc_moving_to_another_account_drops_the_old_light(self):
        await self.pair()
        await self.client.post('/agent/heartbeat', json={'device_id': 'pc-1', 'version': '1.4.0'})
        self.user = 'other'
        _, claim = await self.pair()
        self.assertEqual(claim.status_code, 200, claim.text)
        beat = await self.client.post('/agent/heartbeat', json={'device_id': 'pc-1', 'version': '1.4.0'})
        self.assertEqual(beat.status_code, 200, beat.text)   # 예전 계정 기록이 남아 있으면 403 이었다

    async def test_cannot_revoke_someone_elses_device(self):
        await self.pair()
        self.user = 'intruder'
        revoke = await self.client.delete('/agent/devices/pc-1')
        self.assertEqual(revoke.status_code, 404, revoke.text)


if __name__ == '__main__':
    unittest.main()
