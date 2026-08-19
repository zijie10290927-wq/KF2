"""SQLAlchemy 2.0 异步引擎与会话工厂。

全异步强制：所有数据库操作必须使用 AsyncSession，严禁混用同步代码阻塞事件循环。
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.config.settings import settings

# 异步引擎：根据数据库类型选择不同配置
if settings.DB_TYPE == "sqlite":
    # SQLite：启用 WAL 模式 + busy_timeout，解决并发请求文件锁竞争导致的 25s 阻塞
    async_engine = create_async_engine(
        settings.async_database_url,
        echo=settings.APP_ENV == "development" and settings.LOG_LEVEL == "DEBUG",
        future=True,
        connect_args={
            "timeout": 30,          # busy_timeout: 锁等待最多 30s（而非立即报 locked）
            "check_same_thread": False,
        },
    )

    # 启动时通过事件监听器设置 WAL 模式和 busy_timeout
    from sqlalchemy import event

    @event.listens_for(async_engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")       # WAL: 读写不互斥
        cursor.execute("PRAGMA busy_timeout=30000")      # 锁等待 30s
        cursor.execute("PRAGMA synchronous=NORMAL")      # WAL 下 NORMAL 足够安全
        cursor.close()
else:
    # MySQL 连接池：大小 20，最大溢出 40，自动回收 1h。
    async_engine = create_async_engine(
        settings.async_database_url,
        pool_size=20,
        max_overflow=40,
        pool_pre_ping=False,
        pool_recycle=3600,
        echo=settings.APP_ENV == "development" and settings.LOG_LEVEL == "DEBUG",
        future=True,
    )

# 异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# ORM 基类
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入：yield 一个独立 AsyncSession，请求结束自动关闭。

    使用方式：`db: AsyncSession = Depends(get_db)`
    """
    async with AsyncSessionLocal() as db:
        try:
            yield db
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()
