"""服务依赖注入工厂：为路由层组装完整的 Service 依赖链。

遵循「FastAPI 路由必须使用 Depends 注入」铁律。
"""

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config.database import get_db
from app.exceptions import AuthError
from app.models import User
from app.services.auth_service import AuthService
from app.services.chat_service import ChatService
from app.services.config_service import ConfigService
from app.services.intent_service import IntentService
from app.services.knowledge_service import KnowledgeService
from app.services.llm_service import LLMService
from app.services.memory_service import MemoryService
from app.services.rag_service import RAGService


async def get_config_service(
    db: AsyncSession = Depends(get_db),
) -> ConfigService:
    return ConfigService(db)


async def get_auth_service(
    db: AsyncSession = Depends(get_db),
) -> AuthService:
    return AuthService(db)


async def get_memory_service(
    db: AsyncSession = Depends(get_db),
) -> MemoryService:
    return MemoryService(db)


async def get_llm_service(
    config_service: ConfigService = Depends(get_config_service),
) -> LLMService:
    return LLMService(config_service=config_service)


async def get_intent_service(
    llm_service: LLMService = Depends(get_llm_service),
) -> IntentService:
    return IntentService(llm_service=llm_service)


async def get_rag_service(
    db: AsyncSession = Depends(get_db),
    config_service: ConfigService = Depends(get_config_service),
    llm_service: LLMService = Depends(get_llm_service),
) -> RAGService:
    return RAGService(db=db, config_service=config_service, llm_service=llm_service)


async def get_chat_service(
    db: AsyncSession = Depends(get_db),
    intent_service: IntentService = Depends(get_intent_service),
    rag_service: RAGService = Depends(get_rag_service),
    llm_service: LLMService = Depends(get_llm_service),
    memory_service: MemoryService = Depends(get_memory_service),
    config_service: ConfigService = Depends(get_config_service),
) -> ChatService:
    """组装完整 ChatService 依赖链。"""
    return ChatService(
        db=db,
        intent_service=intent_service,
        rag_service=rag_service,
        llm_service=llm_service,
        memory_service=memory_service,
        config_service=config_service,
    )


async def get_knowledge_service(
    db: AsyncSession = Depends(get_db),
    config_service: ConfigService = Depends(get_config_service),
) -> KnowledgeService:
    """注入 KnowledgeService（含 ConfigService 用于读取分块参数）。"""
    return KnowledgeService(db=db, config_service=config_service)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
):  # type: ignore[no-untyped-def,return]  # 降级路径返回 SimpleNamespace duck typing
    """从 request.state.user 中提取 user_id 并查询 User 对象。

    JWT 中间件已将 payload 注入 request.state.user。
    路由中通过 ``user: User = Depends(get_current_user)`` 注入。
    DB 不可用时降级到 AuthService._DEV_BUILTIN_USERS 内置账号。
    """
    from app.services.auth_service import _DEV_BUILTIN_USERS, _build_fake_user

    payload = getattr(request.state, "user", None)
    if payload is None:
        raise AuthError("未登录或 Token 缺失")

    user_id = payload.get("user_id")
    if user_id is None:
        raise AuthError("Token 中缺少 user_id")

    try:
        stmt = select(User).where(User.id == int(user_id))
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if user is not None:
            if user.status != 1:
                raise AuthError("账号已被禁用")
            return user
    except Exception as e:
        # DB 不可达 → 降级到内置账号
        import logging
        logging.getLogger(__name__).warning("DB unreachable get_current_user, fallback builtin: %s", e)
        for b in _DEV_BUILTIN_USERS.values():
            if b["user_id"] == int(user_id):
                if b.get("status", 1) != 1:
                    raise AuthError("账号已被禁用") from e
                return _build_fake_user(b)
        raise AuthError("用户不存在") from e

    if user is None:
        # DB 可用但用户不存在 → 仍尝试匹配内置，兼容 DB 未初始化场景
        for b in _DEV_BUILTIN_USERS.values():
            if b["user_id"] == int(user_id):
                if b.get("status", 1) != 1:
                    raise AuthError("账号已被禁用")
                return _build_fake_user(b)
        raise AuthError("用户不存在")
    if user.status != 1:
        raise AuthError("账号已被禁用")
    return user


async def get_admin_user(
    user=Depends(get_current_user),  # type: ignore[no-untyped-def]
):  # type: ignore[no-untyped-def,return]
    """要求当前用户为管理员。"""
    if user.role != "admin":
        from app.exceptions import PermissionDeniedError

        raise PermissionDeniedError("需要管理员权限")
    return user
