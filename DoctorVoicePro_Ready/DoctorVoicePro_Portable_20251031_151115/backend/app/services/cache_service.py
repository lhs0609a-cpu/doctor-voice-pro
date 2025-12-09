"""
Redis 캐싱 서비스
프로필, API 응답 등을 캐싱하여 성능 향상
"""

import json
import redis.asyncio as aioredis
from typing import Optional, Any
from datetime import timedelta
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Redis 기반 캐싱 서비스"""

    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.default_ttl = 3600  # 1 hour in seconds

    async def connect(self):
        """Redis 연결"""
        try:
            self.redis = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
            await self.redis.ping()
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis = None

    async def disconnect(self):
        """Redis 연결 종료"""
        if self.redis:
            await self.redis.close()
            logger.info("Redis disconnected")

    async def get(self, key: str) -> Optional[Any]:
        """캐시에서 값 가져오기"""
        if not self.redis:
            return None

        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None

    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None
    ) -> bool:
        """캐시에 값 저장"""
        if not self.redis:
            return False

        try:
            ttl = ttl or self.default_ttl
            serialized_value = json.dumps(value)
            await self.redis.set(key, serialized_value, ex=ttl)
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """캐시에서 값 삭제"""
        if not self.redis:
            return False

        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """패턴에 매칭되는 모든 키 삭제"""
        if not self.redis:
            return 0

        try:
            keys = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                return await self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache delete pattern error for pattern {pattern}: {e}")
            return 0

    async def exists(self, key: str) -> bool:
        """키 존재 여부 확인"""
        if not self.redis:
            return False

        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False

    async def expire(self, key: str, seconds: int) -> bool:
        """키의 만료 시간 설정"""
        if not self.redis:
            return False

        try:
            return await self.redis.expire(key, seconds)
        except Exception as e:
            logger.error(f"Cache expire error for key {key}: {e}")
            return False

    # Specialized cache methods

    async def get_user_profile(self, user_id: str) -> Optional[dict]:
        """사용자 프로필 캐시 조회"""
        return await self.get(f"profile:{user_id}")

    async def set_user_profile(
        self, user_id: str, profile: dict, ttl: int = 1800
    ) -> bool:
        """사용자 프로필 캐시 저장 (기본 30분)"""
        return await self.set(f"profile:{user_id}", profile, ttl)

    async def invalidate_user_profile(self, user_id: str) -> bool:
        """사용자 프로필 캐시 무효화"""
        return await self.delete(f"profile:{user_id}")

    async def get_post(self, post_id: str) -> Optional[dict]:
        """포스트 캐시 조회"""
        return await self.get(f"post:{post_id}")

    async def set_post(
        self, post_id: str, post: dict, ttl: int = 600
    ) -> bool:
        """포스트 캐시 저장 (기본 10분)"""
        return await self.set(f"post:{post_id}", post, ttl)

    async def invalidate_post(self, post_id: str) -> bool:
        """포스트 캐시 무효화"""
        return await self.delete(f"post:{post_id}")

    async def invalidate_user_posts(self, user_id: str) -> int:
        """사용자의 모든 포스트 캐시 무효화"""
        return await self.delete_pattern(f"posts:{user_id}:*")

    async def get_user_posts_list(
        self, user_id: str, page: int, page_size: int
    ) -> Optional[dict]:
        """사용자 포스트 목록 캐시 조회"""
        return await self.get(f"posts:{user_id}:{page}:{page_size}")

    async def set_user_posts_list(
        self, user_id: str, page: int, page_size: int, posts: dict, ttl: int = 300
    ) -> bool:
        """사용자 포스트 목록 캐시 저장 (기본 5분)"""
        return await self.set(f"posts:{user_id}:{page}:{page_size}", posts, ttl)

    async def get_analytics(self, post_id: str) -> Optional[dict]:
        """분석 데이터 캐시 조회"""
        return await self.get(f"analytics:{post_id}")

    async def set_analytics(
        self, post_id: str, analytics: dict, ttl: int = 900
    ) -> bool:
        """분석 데이터 캐시 저장 (기본 15분)"""
        return await self.set(f"analytics:{post_id}", analytics, ttl)

    async def increment_view_count(self, post_id: str) -> Optional[int]:
        """포스트 조회수 증가"""
        if not self.redis:
            return None

        try:
            key = f"views:{post_id}"
            count = await self.redis.incr(key)
            # 조회수는 24시간 동안 유지
            if count == 1:
                await self.redis.expire(key, 86400)
            return count
        except Exception as e:
            logger.error(f"Increment view count error for post {post_id}: {e}")
            return None


# Global cache service instance
cache_service = CacheService()
