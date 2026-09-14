import unittest
from unittest.mock import AsyncMock, patch
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models.blog_outreach import OutreachSetting
from app.services import naver_search_credentials as keys, content_evidence


class SearchKeysTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with self.engine.begin() as conn:
            await conn.run_sync(OutreachSetting.__table__.create)
        self.db = async_sessionmaker(self.engine, expire_on_commit=False)()
        # Use a real Fernet key shared by save and read.
        key = Fernet.generate_key()
        self.crypto = Fernet(key)
        self.env = patch.dict('os.environ', {'ENCRYPTION_KEY': key.decode()})
        self.env.start()
        self.id_patch = patch.object(keys.settings, 'NAVER_CLIENT_ID', '')
        self.secret_patch = patch.object(keys.settings, 'NAVER_CLIENT_SECRET', '')
        self.id_patch.start(); self.secret_patch.start()
        self.db.add(OutreachSetting(user_id='owner', naver_client_id='saved-id',
                                   naver_client_secret_encrypted=self.crypto.encrypt(b'saved-secret').decode()))
        await self.db.commit()

    async def asyncTearDown(self):
        self.secret_patch.stop(); self.id_patch.stop(); self.env.stop()
        await self.db.close(); await self.engine.dispose()

    async def test_saved_pair_and_user_isolation(self):
        self.assertEqual(await keys.resolve(self.db, 'owner'), ('saved-id', 'saved-secret'))
        self.assertIsNone(await keys.resolve(self.db, 'other'))

    async def test_server_pair_fallback(self):
        with patch.object(keys.settings, 'NAVER_CLIENT_ID', 'server-id'), patch.object(keys.settings, 'NAVER_CLIENT_SECRET', 'server-secret'):
            self.assertEqual(await keys.resolve(self.db, 'other'), ('server-id', 'server-secret'))
            self.assertEqual(await keys.resolve(self.db, 'owner'), ('saved-id', 'saved-secret'))

    async def test_invalid_ciphertext_is_not_exposed(self):
        self.db.add(OutreachSetting(user_id='broken', naver_client_id='id', naver_client_secret_encrypted='invalid'))
        await self.db.commit()
        self.assertIsNone(await keys.resolve(self.db, 'broken'))

    async def test_evidence_search_uses_saved_keys(self):
        import httpx
        client = AsyncMock()
        client.get.return_value = httpx.Response(200, request=httpx.Request('GET', 'https://openapi.naver.com'),
            json={'items': [{'link': 'https://nhs.uk/a'}, {'link': 'https://nhs.uk/b'}]})
        async def source(_, url):
            return {'url': url, 'title': 'source', 'excerpt': 'evidence'}
        with patch.object(content_evidence.httpx, 'AsyncClient') as factory, patch.object(content_evidence, 'read_source', side_effect=source):
            factory.return_value.__aenter__.return_value = client
            sources = await content_evidence.collect('eczema', db=self.db, user_id='owner')
        self.assertEqual(len(sources), 2)
        self.assertEqual(client.get.call_args.kwargs['headers'], {'X-Naver-Client-Id': 'saved-id', 'X-Naver-Client-Secret': 'saved-secret'})


if __name__ == '__main__':
    unittest.main()
