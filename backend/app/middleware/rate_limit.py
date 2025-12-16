"""
Rate Limiting Middleware
API 요청 제한을 통한 서비스 보호
"""

import time
from typing import Callable, Dict, Tuple
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate Limiting 미들웨어

    IP 주소와 사용자 ID 기반으로 요청 제한
    - 익명 사용자: IP 기반
    - 인증된 사용자: User ID 기반

    기본 제한:
    - 일반 엔드포인트: 100 requests/minute
    - AI 생성 엔드포인트: 10 requests/minute
    - 인증 엔드포인트: 20 requests/minute
    """

    def __init__(
        self,
        app,
        default_limit: int = 100,
        window_size: int = 60,  # seconds
    ):
        super().__init__(app)
        self.default_limit = default_limit
        self.window_size = window_size

        # In-memory storage for request counts
        # Format: {key: [(timestamp, count), ...]}
        self.request_counts: Dict[str, list] = {}

        # Different limits for different endpoints
        self.endpoint_limits = {
            "/api/v1/posts/": (10, 60),  # 10 requests per minute for post creation
            "/api/v1/posts/.*/rewrite": (5, 60),  # 5 requests per minute for rewrite
            "/api/v1/auth/login": (20, 60),  # 20 requests per minute for login
            "/api/v1/auth/register": (10, 60),  # 10 requests per minute for register
        }

    def get_client_identifier(self, request: Request) -> str:
        """클라이언트 식별자 생성"""
        # Try to get user ID from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"user:{user_id}"

        # Fallback to IP address
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        return f"ip:{client_ip}"

    def get_rate_limit_for_path(self, path: str) -> Tuple[int, int]:
        """경로에 따른 Rate Limit 설정 반환"""
        import re

        for pattern, (limit, window) in self.endpoint_limits.items():
            if re.match(pattern, path):
                return limit, window

        return self.default_limit, self.window_size

    def is_rate_limited(
        self, identifier: str, limit: int, window: int
    ) -> Tuple[bool, int, int]:
        """
        Rate Limit 체크

        Returns:
            (is_limited, remaining_requests, reset_time)
        """
        current_time = time.time()
        window_start = current_time - window

        # Clean old entries
        if identifier in self.request_counts:
            self.request_counts[identifier] = [
                (ts, count)
                for ts, count in self.request_counts[identifier]
                if ts > window_start
            ]
        else:
            self.request_counts[identifier] = []

        # Count requests in current window
        total_requests = sum(
            count for _, count in self.request_counts[identifier]
        )

        # Calculate remaining and reset time
        remaining = max(0, limit - total_requests)
        reset_time = int(window_start + window) if self.request_counts[identifier] else int(current_time + window)

        # Check if limited
        is_limited = total_requests >= limit

        if not is_limited:
            # Add current request
            self.request_counts[identifier].append((current_time, 1))

        return is_limited, remaining, reset_time

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """요청 처리 및 Rate Limiting 적용"""

        # Skip rate limiting for health check and docs
        if request.url.path in ["/", "/health", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)

        # Get client identifier
        identifier = self.get_client_identifier(request)

        # Get rate limit for this path
        limit, window = self.get_rate_limit_for_path(request.url.path)

        # Check rate limit
        is_limited, remaining, reset_time = self.is_rate_limited(
            identifier, limit, window
        )

        # Add rate limit headers
        response_headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_time),
        }

        if is_limited:
            logger.warning(
                f"Rate limit exceeded for {identifier} on {request.url.path}"
            )

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요.",
                    "retry_after": reset_time - int(time.time()),
                },
                headers={
                    **response_headers,
                    "Retry-After": str(reset_time - int(time.time())),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        for header, value in response_headers.items():
            response.headers[header] = value

        return response


class RedisRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Redis 기반 Rate Limiting 미들웨어 (더 확장 가능)

    프로덕션 환경에서는 이 버전을 사용하는 것을 권장
    """

    def __init__(
        self,
        app,
        redis_client,
        default_limit: int = 100,
        window_size: int = 60,
    ):
        super().__init__(app)
        self.redis = redis_client
        self.default_limit = default_limit
        self.window_size = window_size

        self.endpoint_limits = {
            "/api/v1/posts/": (10, 60),
            "/api/v1/posts/.*/rewrite": (5, 60),
            "/api/v1/auth/login": (20, 60),
            "/api/v1/auth/register": (10, 60),
        }

    def get_client_identifier(self, request: Request) -> str:
        """클라이언트 식별자 생성"""
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"rate_limit:user:{user_id}"

        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        return f"rate_limit:ip:{client_ip}"

    def get_rate_limit_for_path(self, path: str) -> Tuple[int, int]:
        """경로에 따른 Rate Limit 설정 반환"""
        import re

        for pattern, (limit, window) in self.endpoint_limits.items():
            if re.match(pattern, path):
                return limit, window

        return self.default_limit, self.window_size

    async def is_rate_limited(
        self, identifier: str, limit: int, window: int
    ) -> Tuple[bool, int, int]:
        """Redis 기반 Rate Limit 체크"""
        if not self.redis:
            return False, limit, int(time.time() + window)

        try:
            current_time = int(time.time())
            key = f"{identifier}:{current_time // window}"

            # Increment counter
            count = await self.redis.incr(key)

            # Set expiration on first request
            if count == 1:
                await self.redis.expire(key, window * 2)

            # Calculate remaining and reset time
            remaining = max(0, limit - count)
            reset_time = (current_time // window + 1) * window

            is_limited = count > limit

            return is_limited, remaining, reset_time

        except Exception as e:
            logger.error(f"Redis rate limit error: {e}")
            # Fail open - don't block on error
            return False, limit, int(time.time() + window)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """요청 처리 및 Rate Limiting 적용"""

        # Skip rate limiting for health check and docs
        if request.url.path in ["/", "/health", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)

        identifier = self.get_client_identifier(request)
        limit, window = self.get_rate_limit_for_path(request.url.path)

        is_limited, remaining, reset_time = await self.is_rate_limited(
            identifier, limit, window
        )

        response_headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_time),
        }

        if is_limited:
            logger.warning(
                f"Rate limit exceeded for {identifier} on {request.url.path}"
            )

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요.",
                    "retry_after": reset_time - int(time.time()),
                },
                headers={
                    **response_headers,
                    "Retry-After": str(reset_time - int(time.time())),
                },
            )

        response = await call_next(request)

        for header, value in response_headers.items():
            response.headers[header] = value

        return response
