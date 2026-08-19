"""FastAPI 应用入口。

职责：
1. 日志配置
2. Lifespan：启动时初始化 Milvus/MinIO/DB，关闭时释放连接
3. CORS 中间件 + 业务中间件注册
4. 路由挂载（/api/v1 前缀）
5. 健康检查端点
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings
from app.config.database import async_engine, Base
from app.config.milvus import milvus_client
from app.config.minio import minio_client
from app.config.redis import ping_redis
from app.middleware import register_middlewares
from app.routers import (
    admin_channel_router,
    admin_chat_logs_router,
    admin_config_router,
    admin_knowledge_router,
    admin_users_router,
    auth_router,
    chat_router,
    openai_compat_router,
    webhook_router,
    widget_router,
)

# ---------------------------------------------------------------------- #
# 日志配置
# ---------------------------------------------------------------------- #
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------- #
# Lifespan：启动 / 关闭钩子
# ---------------------------------------------------------------------- #
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化资源，关闭时释放。"""
    logger.info("==== Starting AI Customer Agent (env=%s) ====", settings.APP_ENV)

    # 1. Redis 连通性检查（非阻塞，失败仅告警）
    redis_ok = await ping_redis()
    logger.info("Redis ping: %s", "OK" if redis_ok else "FAILED (will degrade)")

    # 2. Milvus 初始化（延迟连接 + 集合检查）
    try:
        milvus_client.connect()
        milvus_client.ensure_collection()
        logger.info("Milvus ready: %s", milvus_client.is_connected)
    except Exception as e:
        logger.warning("Milvus init failed (RAG will degrade): %s", e)

    # 3. MinIO 初始化
    try:
        minio_client.ensure_bucket()
        logger.info("MinIO ready")
    except Exception as e:
        logger.warning("MinIO init failed: %s", e)

    # 4. DB 表自动创建（开发环境；生产用 alembic migrate）
    if settings.APP_ENV == "development":
        try:
            async with async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("DB tables ensured (create_all)")
        except Exception as e:
            logger.warning("DB create_all failed (use alembic migrate): %s", e)

    # 5. 初始化默认 admin 账号（幂等：仅当不存在时创建）
    #    默认账号: admin / admin123   (⚠️ 生产环境务必修改或禁用)
    try:
        from app.config.database import AsyncSessionLocal
        from app.services.auth_service import AuthService
        async with AsyncSessionLocal() as init_db:
            init_auth = AuthService(init_db)
            exists = await init_auth.get_user_by_username("admin")
            if exists is None:
                await init_auth.register("admin", "admin123", role="admin")
                logger.info("Default admin account created: admin / admin123 (⚠️ CHANGE IN PROD)")
            else:
                logger.info("Admin account exists, skip init")
            # 同时创建一个普通用户用于 C 端演示
            demo_exists = await init_auth.get_user_by_username("demo")
            if demo_exists is None:
                await init_auth.register("demo", "demo123", role="user")
                logger.info("Demo user account created: demo / demo123")
    except Exception as e:
        logger.warning("Init default users failed (DB unavailable?): %s", e)

    logger.info("==== Application ready ====")
    yield

    # 关闭：释放连接
    logger.info("==== Shutting down ====")
    try:
        await milvus_client.close()
    except Exception:  # pragma: no cover
        pass
    try:
        await async_engine.dispose()
    except Exception:  # pragma: no cover
        pass
    logger.info("==== Shutdown complete ====")


# ---------------------------------------------------------------------- #
# FastAPI 应用
# ---------------------------------------------------------------------- #
app = FastAPI(
    title="AI 出图产品智能客服 Agent",
    description="基于 FastAPI + Vue3 的全栈 AI 智能客服系统 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS 中间件（最外层）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-Response-Time-ms"],
)

# 业务中间件 + 异常处理
register_middlewares(app)

# 路由挂载
app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(chat_router, prefix=settings.API_PREFIX)
app.include_router(admin_knowledge_router, prefix=settings.API_PREFIX)
app.include_router(admin_config_router, prefix=settings.API_PREFIX)
app.include_router(admin_chat_logs_router, prefix=settings.API_PREFIX)
app.include_router(admin_users_router, prefix=settings.API_PREFIX)
# 渠道适配层路由（Section 11）
app.include_router(admin_channel_router, prefix=settings.API_PREFIX)
app.include_router(webhook_router, prefix=settings.API_PREFIX)
app.include_router(openai_compat_router, prefix=settings.API_PREFIX)
app.include_router(widget_router, prefix=settings.API_PREFIX)


# ---------------------------------------------------------------------- #
# 健康检查
# ---------------------------------------------------------------------- #
@app.get("/health", tags=["系统"], summary="健康检查")
async def health() -> dict:
    """健康检查端点（无需认证）。"""
    return {
        "status": "ok",
        "env": settings.APP_ENV,
        "version": "1.0.0",
        "milvus": milvus_client.is_connected,
    }


@app.get("/", tags=["系统"], summary="根路径")
async def root() -> dict:
    """根路径重定向信息。"""
    return {
        "name": "AI Customer Agent API",
        "docs": "/docs",
        "health": "/health",
    }
