"""
프록시 관리 서비스
- 프록시 로테이션
- 헬스체크
- 실패 관리
"""

import uuid
import aiohttp
import asyncio
import random
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.viral_common import ProxyServer, ProxyType


class ProxyManagerService:
    """프록시 관리 서비스"""

    # 프록시 테스트 URL
    TEST_URL = "https://www.naver.com"
    TEST_TIMEOUT = 10

    async def add_proxy(
        self,
        db: AsyncSession,
        user_id: str,
        proxy_type: ProxyType,
        host: str,
        port: int,
        username: Optional[str] = None,
        password: Optional[str] = None,
        name: Optional[str] = None,
        country: Optional[str] = None,
        region: Optional[str] = None
    ) -> ProxyServer:
        """프록시 추가"""
        proxy = ProxyServer(
            id=str(uuid.uuid4()),
            user_id=user_id,
            proxy_type=proxy_type.value,
            host=host,
            port=port,
            username=username,
            password=password,
            name=name or f"{host}:{port}",
            country=country,
            region=region
        )
        db.add(proxy)
        await db.commit()
        await db.refresh(proxy)
        return proxy

    async def get_proxies(
        self,
        db: AsyncSession,
        user_id: str,
        proxy_type: Optional[ProxyType] = None,
        is_active: Optional[bool] = None
    ) -> List[ProxyServer]:
        """프록시 목록 조회"""
        query = select(ProxyServer).where(ProxyServer.user_id == user_id)

        if proxy_type:
            query = query.where(ProxyServer.proxy_type == proxy_type.value)

        if is_active is not None:
            query = query.where(ProxyServer.is_active == is_active)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_next_proxy(
        self,
        db: AsyncSession,
        user_id: str,
        proxy_type: Optional[ProxyType] = None,
        exclude_ids: Optional[List[str]] = None
    ) -> Optional[ProxyServer]:
        """다음 사용 가능한 프록시 (로테이션)"""
        query = select(ProxyServer).where(
            and_(
                ProxyServer.user_id == user_id,
                ProxyServer.is_active == True,
                ProxyServer.is_healthy == True
            )
        )

        if proxy_type:
            query = query.where(ProxyServer.proxy_type == proxy_type.value)

        if exclude_ids:
            query = query.where(ProxyServer.id.notin_(exclude_ids))

        result = await db.execute(query)
        proxies = list(result.scalars().all())

        if not proxies:
            return None

        # 마지막 사용 시간 기준 정렬 (가장 오래된 것 우선)
        proxies.sort(key=lambda x: x.last_used_at or datetime.min)

        # 상위 3개 중 랜덤 선택
        top_proxies = proxies[:min(3, len(proxies))]
        selected = random.choice(top_proxies)

        # 사용 기록 업데이트
        selected.last_used_at = datetime.utcnow()
        selected.usage_count += 1
        await db.commit()

        return selected

    def get_proxy_url(self, proxy: ProxyServer) -> str:
        """프록시 URL 생성"""
        if proxy.username and proxy.password:
            return f"{proxy.proxy_type}://{proxy.username}:{proxy.password}@{proxy.host}:{proxy.port}"
        return f"{proxy.proxy_type}://{proxy.host}:{proxy.port}"

    async def test_proxy(
        self,
        db: AsyncSession,
        proxy_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """프록시 테스트"""
        result = await db.execute(
            select(ProxyServer).where(
                and_(
                    ProxyServer.id == proxy_id,
                    ProxyServer.user_id == user_id
                )
            )
        )
        proxy = result.scalar_one_or_none()

        if not proxy:
            return {"success": False, "error": "Proxy not found"}

        return await self._check_proxy_health(db, proxy)

    async def _check_proxy_health(
        self,
        db: AsyncSession,
        proxy: ProxyServer
    ) -> Dict[str, Any]:
        """프록시 헬스체크"""
        proxy_url = self.get_proxy_url(proxy)
        start_time = datetime.utcnow()

        try:
            connector = aiohttp.TCPConnector(ssl=False)
            timeout = aiohttp.ClientTimeout(total=self.TEST_TIMEOUT)

            async with aiohttp.ClientSession(
                connector=connector,
                timeout=timeout
            ) as session:
                async with session.get(
                    self.TEST_URL,
                    proxy=proxy_url
                ) as resp:
                    elapsed = (datetime.utcnow() - start_time).total_seconds()

                    if resp.status == 200:
                        proxy.is_healthy = True
                        proxy.last_check_at = datetime.utcnow()
                        proxy.response_time_ms = int(elapsed * 1000)
                        proxy.fail_count = 0

                        # 성공률 계산
                        proxy.success_count += 1
                        total = proxy.success_count + proxy.fail_count
                        proxy.success_rate = proxy.success_count / total if total > 0 else 1.0

                        await db.commit()

                        return {
                            "success": True,
                            "response_time_ms": proxy.response_time_ms,
                            "status_code": resp.status
                        }
                    else:
                        raise Exception(f"HTTP {resp.status}")

        except Exception as e:
            proxy.is_healthy = False
            proxy.last_check_at = datetime.utcnow()
            proxy.fail_count += 1
            proxy.last_error = str(e)

            # 5회 이상 실패 시 비활성화
            if proxy.fail_count >= 5:
                proxy.is_active = False

            # 성공률 업데이트
            total = proxy.success_count + proxy.fail_count
            proxy.success_rate = proxy.success_count / total if total > 0 else 0

            await db.commit()

            return {
                "success": False,
                "error": str(e)
            }

    async def check_all_proxies(
        self,
        db: AsyncSession,
        user_id: str
    ) -> Dict[str, Any]:
        """모든 프록시 헬스체크"""
        proxies = await self.get_proxies(db, user_id, is_active=True)

        results = {
            "total": len(proxies),
            "healthy": 0,
            "unhealthy": 0,
            "details": []
        }

        for proxy in proxies:
            check_result = await self._check_proxy_health(db, proxy)
            results["details"].append({
                "proxy_id": proxy.id,
                "name": proxy.name,
                **check_result
            })

            if check_result["success"]:
                results["healthy"] += 1
            else:
                results["unhealthy"] += 1

            # 동시 요청 방지 딜레이
            await asyncio.sleep(0.5)

        return results

    async def update_proxy(
        self,
        db: AsyncSession,
        proxy_id: str,
        user_id: str,
        **updates
    ) -> Optional[ProxyServer]:
        """프록시 업데이트"""
        result = await db.execute(
            select(ProxyServer).where(
                and_(
                    ProxyServer.id == proxy_id,
                    ProxyServer.user_id == user_id
                )
            )
        )
        proxy = result.scalar_one_or_none()

        if proxy:
            for key, value in updates.items():
                if hasattr(proxy, key):
                    setattr(proxy, key, value)
            proxy.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(proxy)

        return proxy

    async def delete_proxy(
        self,
        db: AsyncSession,
        proxy_id: str,
        user_id: str
    ) -> bool:
        """프록시 삭제"""
        result = await db.execute(
            select(ProxyServer).where(
                and_(
                    ProxyServer.id == proxy_id,
                    ProxyServer.user_id == user_id
                )
            )
        )
        proxy = result.scalar_one_or_none()

        if proxy:
            await db.delete(proxy)
            await db.commit()
            return True
        return False

    async def record_proxy_failure(
        self,
        db: AsyncSession,
        proxy_id: str,
        error_message: str
    ):
        """프록시 실패 기록"""
        result = await db.execute(
            select(ProxyServer).where(ProxyServer.id == proxy_id)
        )
        proxy = result.scalar_one_or_none()

        if proxy:
            proxy.fail_count += 1
            proxy.last_error = error_message

            if proxy.fail_count >= 5:
                proxy.is_active = False
                proxy.is_healthy = False

            await db.commit()

    async def record_proxy_success(
        self,
        db: AsyncSession,
        proxy_id: str,
        response_time_ms: Optional[int] = None
    ):
        """프록시 성공 기록"""
        result = await db.execute(
            select(ProxyServer).where(ProxyServer.id == proxy_id)
        )
        proxy = result.scalar_one_or_none()

        if proxy:
            proxy.success_count += 1
            proxy.is_healthy = True
            proxy.last_used_at = datetime.utcnow()

            if response_time_ms:
                proxy.response_time_ms = response_time_ms

            # 성공률 업데이트
            total = proxy.success_count + proxy.fail_count
            proxy.success_rate = proxy.success_count / total if total > 0 else 1.0

            await db.commit()

    async def get_proxy_stats(
        self,
        db: AsyncSession,
        user_id: str
    ) -> Dict[str, Any]:
        """프록시 통계"""
        proxies = await self.get_proxies(db, user_id)

        total = len(proxies)
        active = sum(1 for p in proxies if p.is_active)
        healthy = sum(1 for p in proxies if p.is_healthy)

        avg_response_time = 0
        if proxies:
            response_times = [p.response_time_ms for p in proxies if p.response_time_ms]
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)

        avg_success_rate = 0
        if proxies:
            success_rates = [p.success_rate for p in proxies if p.success_rate is not None]
            if success_rates:
                avg_success_rate = sum(success_rates) / len(success_rates)

        total_usage = sum(p.usage_count for p in proxies)

        return {
            "total": total,
            "active": active,
            "healthy": healthy,
            "inactive": total - active,
            "avg_response_time_ms": round(avg_response_time, 2),
            "avg_success_rate": round(avg_success_rate * 100, 2),
            "total_usage": total_usage,
            "by_type": {
                "http": sum(1 for p in proxies if p.proxy_type == ProxyType.HTTP.value),
                "https": sum(1 for p in proxies if p.proxy_type == ProxyType.HTTPS.value),
                "socks5": sum(1 for p in proxies if p.proxy_type == ProxyType.SOCKS5.value)
            }
        }

    async def import_proxies(
        self,
        db: AsyncSession,
        user_id: str,
        proxy_list: str,
        proxy_type: ProxyType = ProxyType.HTTP
    ) -> Dict[str, Any]:
        """프록시 일괄 가져오기 (ip:port 또는 ip:port:user:pass 형식)"""
        lines = [line.strip() for line in proxy_list.split("\n") if line.strip()]
        imported = 0
        failed = 0
        errors = []

        for line in lines:
            try:
                parts = line.split(":")

                if len(parts) == 2:
                    host, port = parts
                    username, password = None, None
                elif len(parts) == 4:
                    host, port, username, password = parts
                else:
                    raise ValueError(f"Invalid format: {line}")

                await self.add_proxy(
                    db=db,
                    user_id=user_id,
                    proxy_type=proxy_type,
                    host=host,
                    port=int(port),
                    username=username,
                    password=password
                )
                imported += 1

            except Exception as e:
                failed += 1
                errors.append(f"{line}: {str(e)}")

        return {
            "imported": imported,
            "failed": failed,
            "errors": errors[:10]  # 처음 10개 에러만 반환
        }


# 싱글톤 인스턴스
proxy_manager = ProxyManagerService()
