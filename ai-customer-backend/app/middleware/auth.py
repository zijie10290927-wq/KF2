"""JWT 认证中间件。

通过中间件实现，配置 exclude_paths（含 /auth/login, /docs, /api/v1/chat/** 等）。
成功：request.state.user = payload；失败：401。
"""

import fnmatch
import logging
import re

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config.database import AsyncSessionLocal
from app.config.settings import settings
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)


def _match_exclude(path: str, patterns: list[str]) -> bool:
    """路径匹配（支持 * 通配与 ** 跨段通配）。"""
    for p in patterns:
        if p.endswith("**"):
            prefix = p[:-2]
            if path.startswith(prefix):
                return True
        elif fnmatch.fnmatch(path, p):
            return True
        elif path == p:
            return True
    return False


class AuthMiddleware(BaseHTTPMiddleware):
    """JWT 认证中间件。"""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.exclude_paths = settings.auth_exclude_paths_list

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        path = request.url.path

        # 排除路径直接放行
        if _match_exclude(path, self.exclude_paths):
            return await call_next(request)

        # OPTIONS 预检放行
        if request.method == "OPTIONS":
            return await call_next(request)

        # 提取 Bearer Token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return self._unauthorized("请先登录")

        token = auth_header[7:].strip()
        if not token:
            return self._unauthorized("Token 为空")

        # 验证 Token（使用独立 session）
        try:
            async with AsyncSessionLocal() as db:
                auth_service = AuthService(db)
                payload = await auth_service.verify_token(token)
            # 注入到 request.state 供下游依赖使用
            request.state.user = payload
        except Exception as e:
            logger.warning("Auth failed: %s", e)
            return self._unauthorized(str(e) or "Token 无效")

        return await call_next(request)

    @staticmethod
    def _unauthorized(message: str) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"code": 401, "message": message, "data": None},
            headers={"WWW-Authenticate": "Bearer"},
        )
