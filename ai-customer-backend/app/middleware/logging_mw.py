"""请求日志中间件。

记录每个请求的 method、path、query、user_id、耗时 ms、HTTP 状态码。
INFO 级别日志，慢请求（>500ms）打 WARN。
SSE 流式响应特殊处理：不包装、不消耗 body，直接透传。
"""

import logging
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

_SLOW_REQUEST_THRESHOLD_MS = 500


class RequestLogMiddleware(BaseHTTPMiddleware):
    """请求日志中间件。"""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        start = time.perf_counter()
        method = request.method
        path = request.url.path
        query = str(request.url.query)

        # 跳过健康检查 / 静态资源 / 文档
        if path in ("/health", "/ping", "/favicon.ico", "/") or path.startswith("/docs") or path.startswith("/redoc"):
            return await call_next(request)

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1000
        status_code = response.status_code

        # 获取 user_id
        payload = getattr(request.state, "user", None)
        user_id = payload.get("user_id") if payload else None

        is_streaming = isinstance(response, StreamingResponse)
        stream_tag = " [STREAM]" if is_streaming else ""

        log_msg = (
            f"{method} {path}"
            f"{'?' + query if query else ''}"
            f" -> {status_code}"
            f"{stream_tag}"
            f" | user={user_id or '-'}"
            f" | {duration_ms:.1f}ms"
        )

        if duration_ms > _SLOW_REQUEST_THRESHOLD_MS:
            logger.warning("SLOW %s", log_msg)
        else:
            logger.info(log_msg)

        # 注入耗时到响应头（流式响应也安全，因为只设置 header）
        response.headers["X-Response-Time-ms"] = f"{duration_ms:.1f}"
        return response
