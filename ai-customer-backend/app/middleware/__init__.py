"""全局异常处理与中间件注册。"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions import AppException
from app.middleware.auth import AuthMiddleware
from app.middleware.logging_mw import RequestLogMiddleware
from app.middleware.rate_limiter import RateLimitMiddleware

logger = logging.getLogger(__name__)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """自定义业务异常处理。"""
    logger.warning("AppException: %s (code=%d) path=%s", exc.message, exc.code, request.url.path)
    http_status = _http_status_from_code(exc.code)
    return JSONResponse(
        status_code=http_status,
        content={"code": exc.code, "message": exc.message, "data": None},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """请求参数校验失败 → 400。"""
    logger.warning("ValidationError: %s path=%s", exc.errors(), request.url.path)
    return JSONResponse(
        status_code=400,
        content={
            "code": 400,
            "message": "请求参数校验失败",
            "data": {"errors": exc.errors()},
        },
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """HTTP 异常处理。"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": str(exc.detail), "data": None},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """未捕获异常兜底。"""
    logger.exception("Unhandled exception path=%s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务内部错误，请稍后重试",
            "data": None,
        },
    )


def _http_status_from_code(code: int) -> int:
    """业务码 → HTTP 状态码映射。"""
    if code in (401, 403, 404, 429):
        return code
    if 400 <= code < 500:
        return 400
    return 500


def register_middlewares(app: FastAPI) -> None:
    """注册全部中间件。

    Starlette 中间件执行顺序：后添加的越靠外（请求阶段越先执行）。
    添加顺序：RequestLog → RateLimit → Auth
    请求阶段执行顺序（外→内）：Auth → RateLimit → RequestLog → CORS → handler
    这样 Auth 先设置 request.state.user，RateLimit 才能按 user_id 限流。
    """
    # CORS 在 main.py 中通过 add_middleware 注册（最外层）
    app.add_middleware(RequestLogMiddleware)  # 最内
    app.add_middleware(RateLimitMiddleware)   # 中间
    app.add_middleware(AuthMiddleware)        # 最外（最先执行请求阶段）

    # 异常处理器
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
