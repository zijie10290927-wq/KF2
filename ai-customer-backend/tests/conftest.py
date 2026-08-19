"""pytest 全局 fixture。

测试环境策略（对应《代码审查标准与流程规范》测试要求）：
- DB: 内存 SQLite（aiosqlite + StaticPool），每测试自动建表/清表，不污染开发数据
- Redis: 强制降级 fakeredis（内存模式），不依赖真实 Redis 服务
- LLM: 走 mock 分支（占位符 Key 自动触发），不产生真实 API 调用
"""

import os

# 必须在导入 app 模块之前设置：环境变量优先级高于 .env
os.environ["DB_TYPE"] = "sqlite"
os.environ["APP_ENV"] = "test"
os.environ["LLM_API_KEY"] = ""  # 空 Key → mock 模式

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# 导入 Base 与全部 ORM 模型（确保 metadata 完整）
from app.config.database import Base
import app.models  # noqa: F401


def _dedup_index_names() -> None:
    """去除跨表重名索引。

    已知问题：ChatMessage 与 ChatSession 均定义了名为 idx_session_id 的索引
    （MySQL 索引名按表作用域，无冲突；SQLite 索引名全局作用域，create_all 报错）。
    此处为测试侧规避，模型侧问题已记入代码审查报告。
    """
    seen: set[str] = set()
    for table in Base.metadata.tables.values():
        for idx in list(table.indexes):
            if idx.name in seen:
                table.indexes.discard(idx)
            else:
                seen.add(idx.name)


_dedup_index_names()


@pytest.fixture(scope="session")
def test_engine():
    """内存 SQLite 异步引擎（StaticPool 保证多连接共享同一内存库）。"""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield engine
    # 引擎关闭交由垃圾回收（Windows 下关闭可能挂起）


@pytest.fixture
async def db_session(test_engine) -> AsyncSession:
    """独立测试会话：每测试建表 → yield → 清表，保证测试隔离。"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
    async with factory() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
def fake_redis():
    """强制 Redis 降级 fakeredis（内存模式），所有测试不依赖真实 Redis。"""
    from app.config.redis import redis_client

    redis_client._degraded = True
    yield
    redis_client._degraded = False


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """预置一个普通用户，返回 ORM 对象。"""
    from app.models import User
    from app.services.auth_service import AuthService

    user = User(
        username="testuser",
        password_hash=AuthService.hash_password("Test@12345"),
        role="user",
        status=1,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_session_row(db_session: AsyncSession, test_user):
    """预置一个聊天会话（含 FK 用户），返回 session_id 字符串。"""
    import uuid

    from app.models import ChatSession

    session_id = str(uuid.uuid4())
    db_session.add(
        ChatSession(session_id=session_id, user_id=test_user.id, title="测试会话")
    )
    await db_session.commit()
    return session_id
