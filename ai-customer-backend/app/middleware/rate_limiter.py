"""滑动窗口限流中间件。

策略：滑动窗口，默认 30 次/分钟/用户。
实现：Redis ZSet `rate_limit:{user_id}`，member=timestamp，score=timestamp。
每次请求 zremrangebyscore 清理过期 + zadd + zcard 比较，超限返回 429。
"""

import logging
import time

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config.redis import redis_client
from app.config.settings import settings

logger = logging.getLogger(__name__)

_RATE_LIMIT_PREFIX = "rate_limit:"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """滑动窗口限流（Redis ZSet）。"""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.max_requests = settings.RATE_LIMIT_MAX
        self.window = settings.RATE_LIMIT_WINDOW  # 秒

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        # 仅限 API 路径
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)

        # 从 request.state.user 获取 user_id（未登录用 IP）
        payload = getattr(request.state, "user", None)
        if payload and payload.get("user_id"):
            identity = f"user:{payload['user_id']}"
        else:
            client_ip = request.client.host if request.client else "unknown"
            identity = f"ip:{client_ip}"

        key = f"{_RATE_LIMIT_PREFIX}{identity}"
        now_ms = int(time.time() * 1000)
        window_start = now_ms - self.window * 1000

        try:
            pipe = redis_client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)  # 清理过期
            pipe.zadd(key, {str(now_ms): now_ms})  # 添加当前请求
            pipe.zcard(key)  # 统计当前窗口请求数
            pipe.expire(key, self.window)  # 设置过期
            results = await pipe.execute()
            current_count = results[2] if len(results) > 2 else 0
        except Exception as e:
            # Redis 故障时降级（放行请求，避免限流把服务搞挂）
            logger.warning("Rate limit redis failed: %s", e)
            return await call_next(request)

        if current_count > self.max_requests:
            logger.warning("Rate limit exceeded for %s: %d > %d", identity, current_count, self.max_requests)
            return JSONResponse(
                status_code=429,
                content={
                    "code": 429,
                    "message": "请求过于频繁，请稍后重试",
                    "data": None,
                },
                headers={
                    "Retry-After": str(self.window),
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # 注入剩余配额到响应头
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, self.max_requests - current_count)
        )
        return response
