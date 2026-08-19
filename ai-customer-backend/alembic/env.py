"""Alembic 环境配置（异步版）。

使用 SQLAlchemy 2.0 异步引擎执行迁移。
"""

import asyncio
import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# 加载应用配置（settings 会读取 .env）
from app.config.settings import settings
from app.config.database import Base
# 导入全部 ORM 模型，确保 metadata 注册
from app.models import (  # noqa: F401
    User, ChatSession, ChatMessage, KnowledgeDoc, KnowledgeChunk,
    ModelConfig, SystemConfig, ChannelSession,
)

# Alembic 配置
config = context.config

# 从 settings 覆盖数据库 URL
config.set_main_option("sqlalchemy.url", settings.async_database_url)

# 日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

# 目标 metadata（用于 autogenerate）
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：生成 SQL 脚本而不连接数据库。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """在给定连接上执行迁移。"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """异步模式：使用 async_engine 执行迁移。"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """在线模式入口：调度异步迁移。"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
