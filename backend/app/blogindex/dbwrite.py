"""
격리된 짧은 쓰기 트랜잭션.

운영(SQLite, 1 vCPU)에서 경쟁자 3명을 동시에 채점하면 세션 하나가 `database is locked` 를
한 번 맞는 순간 그 세션의 연결이 무효화되고("Can't reconnect until invalid transaction is
rolled back") 이후 캐시 저장·표본 적재·스냅샷까지 전부 실패한 뒤 90초 타임아웃으로 끝났다(실측).

그래서 캐시성 쓰기는 분석 세션을 쓰지 않고, 매번 자기 세션을 열어 짧게 커밋하고 닫는다.
잠금이면 잠깐 쉬고 다시 시도하고, 끝내 실패해도 예외를 밖으로 내지 않는다(캐시는 없어도 된다).
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Awaitable, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

WriteFn = Callable[[AsyncSession], Awaitable[None]]


async def isolated_write(fn: WriteFn, *, what: str = "write", retries: int = 3) -> bool:
    """fn(session) 을 자기 세션에서 실행하고 커밋. 성공하면 True."""
    from app.db.database import AsyncSessionLocal

    last: Optional[Exception] = None
    for attempt in range(retries):
        try:
            async with AsyncSessionLocal() as s:
                try:
                    await fn(s)
                    await s.commit()
                    return True
                except Exception as e:  # noqa: BLE001
                    last = e
                    try:
                        await s.rollback()
                    except Exception:  # noqa: BLE001
                        pass
                    msg = str(e).lower()
                    if "locked" in msg or "busy" in msg or "invalid transaction" in msg:
                        await asyncio.sleep(0.3 * (attempt + 1) + random.random() * 0.3)
                        continue
                    break
        except Exception as e:  # noqa: BLE001
            last = e
            await asyncio.sleep(0.3)
    logger.warning("[dbwrite] %s 실패: %s", what, last)
    return False
