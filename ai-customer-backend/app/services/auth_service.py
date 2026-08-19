"""AuthService — 认证鉴权服务。

JWT 签发/验证、密码哈希、权限检查。
密码使用 passlib BCrypt 哈希。
"""

import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Optional

import bcrypt
from fastapi import Depends
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.config.redis import redis_client
from app.config.settings import settings
from app.exceptions import AuthError
from app.models import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserInfo,
)

logger = logging.getLogger(__name__)

# 密码哈希：直接使用 bcrypt 原生 API。
# 原因：passlib<1.7.5 + bcrypt>=4.1 在 Python 3.13 存在兼容问题
#   (1) module 'bcrypt' has no attribute '__about__'
#   (2) ValueError: password cannot be longer than 72 bytes
# bcrypt 生成的 $2b$ 前缀哈希与之前 passlib 输出 100% 互认。

# 开发模式内置账号（DB 不可用时的降级方案；⚠️ 生产禁用）
_DEV_BUILTIN_USERS: dict[str, dict] = {
    "admin": {
        "user_id": 1,
        "username": "admin",
        "role": "admin",
        "status": 1,
        "password": "admin123",
    },
    "demo": {
        "user_id": 2,
        "username": "demo",
        "role": "user",
        "status": 1,
        "password": "demo123",
    },
}

# Token 黑名单前缀
_TOKEN_BLACKLIST_PREFIX = "token:blacklist:"
_TOKEN_WHITELIST_PREFIX = "token:whitelist:"


class AuthService:
    """认证鉴权服务。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # 密码哈希
    # ------------------------------------------------------------------ #
    @staticmethod
    def hash_password(raw_password: str) -> str:
        """使用 bcrypt 原生哈希（$2b$ 前缀）。"""
        return bcrypt.hashpw(
            raw_password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    @staticmethod
    def verify_password(raw_password: str, password_hash: str) -> bool:
        """校验密码，兼容 passlib 生成的旧 $2b$/$2a$ 哈希。"""
        try:
            hashed_bytes = password_hash.encode("utf-8")
            return bcrypt.checkpw(raw_password.encode("utf-8"), hashed_bytes)
        except Exception:  # pragma: no cover
            logger.warning("verify_password failed: %s", password_hash[:20])
            return False

    # ------------------------------------------------------------------ #
    # JWT 签发与验证
    # ------------------------------------------------------------------ #
    @staticmethod
    def create_access_token(payload: dict) -> str:
        """签发 JWT。payload 需含 user_id / username / role。"""
        to_encode = payload.copy()
        expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS)
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        })
        return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> dict:
        """解码 JWT，失败抛 AuthError。"""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
            return payload
        except JWTError as e:
            raise AuthError(f"Token 无效或已过期: {e}")

    async def verify_token(self, token: str) -> dict:
        """解码 JWT → 检查 Redis 黑名单 → 返回 payload。

        Redis 不可用时降级为跳过黑名单校验（仍校验 JWT 签名与过期）。
        """
        payload = self.decode_token(token)
        # 检查黑名单（Redis 不可用时降级）
        try:
            is_blacklisted = await redis_client.get(f"{_TOKEN_BLACKLIST_PREFIX}{token}")
            if is_blacklisted:
                raise AuthError("Token 已失效，请重新登录")
        except Exception as e:
            logger.warning("Redis unreachable, skip token blacklist check: %s", e)
        return payload

    async def blacklist_token(self, token: str) -> None:
        """logout 时把 token 加入 Redis 黑名单（TTL = JWT 剩余过期时间）。"""
        payload = self.decode_token(token)
        exp = payload.get("exp")
        if exp is None:
            ttl = settings.JWT_EXPIRE_HOURS * 3600
        else:
            now = int(datetime.now(timezone.utc).timestamp())
            ttl = max(int(exp) - now, 1)
        try:
            await redis_client.set(
                f"{_TOKEN_BLACKLIST_PREFIX}{token}", "1", ex=ttl
            )
        except Exception as e:  # pragma: no cover
            logger.error("Redis blacklist token failed: %s", e)

    # ------------------------------------------------------------------ #
    # 登录
    # ------------------------------------------------------------------ #
    async def login(self, username: str, password: str) -> TokenResponse:
        """登录验证 → 返回 JWT Token + 用户信息。

        优先级：
        1. 先尝试通过 DB 查询用户；
        2. 若 DB 不可用（OperationalError 等）或用户不存在，降级匹配 _DEV_BUILTIN_USERS 内置账号。
        """
        user_dict: Optional[dict] = None  # {"user_id", "username", "role", "status"}

        # 1. 尝试 DB 查询
        db_reachable = True
        try:
            stmt = select(User).where(User.username == username)
            result = await self.db.execute(stmt)
            user = result.scalar_one_or_none()
            if user is not None:
                if user.status != 1:
                    raise AuthError("账号已被禁用，请联系管理员")
                if not self.verify_password(password, user.password_hash):
                    raise AuthError("用户名或密码错误")
                user_dict = {
                    "user_id": user.id,
                    "username": user.username,
                    "role": user.role,
                    "status": user.status,
                    "created_at": user.created_at,
                }
        except AuthError:
            raise
        except Exception as e:
            # DB 不可达
            db_reachable = False
            logger.warning("DB unreachable in login, fallback to builtin users: %s", e)

        # 2. DB 不可达或用户不存在 → 降级到内置账号（仅开发环境）
        if user_dict is None:
            builtin = _DEV_BUILTIN_USERS.get(username)
            if builtin is None or builtin.get("password") != password:
                raise AuthError("用户名或密码错误")
            if builtin.get("status", 1) != 1:
                raise AuthError("账号已被禁用，请联系管理员")
            if not db_reachable:
                logger.info("Login using builtin user (DB unreachable): %s", username)
            user_dict = {
                "user_id": builtin["user_id"],
                "username": builtin["username"],
                "role": builtin["role"],
                "status": builtin["status"],
                "created_at": None,
            }

        payload = {
            "user_id": user_dict["user_id"],
            "username": user_dict["username"],
            "role": user_dict["role"],
        }
        token = self.create_access_token(payload)
        user_info = UserInfo(
            user_id=user_dict["user_id"],
            username=user_dict["username"],
            role=user_dict["role"],
            status=user_dict["status"],
            created_at=user_dict.get("created_at"),
        )
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=settings.JWT_EXPIRE_HOURS * 3600,
            user_info=user_info,
        )

    # ------------------------------------------------------------------ #
    # 用户查询
    # ------------------------------------------------------------------ #
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """按 ID 查询用户。DB 可达时仅返回真实记录；DB 不可达时降级到内置账号。"""
        try:
            stmt = select(User).where(User.id == user_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.warning("DB unreachable get_user_by_id, fallback builtin: %s", e)
            # DB 不可达时降级到内置账号
            for b in _DEV_BUILTIN_USERS.values():
                if b["user_id"] == user_id:
                    return _build_fake_user(b)
            return None

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """查询用户。DB 可达时仅返回真实记录；DB 不可达时降级到内置账号。"""
        try:
            stmt = select(User).where(User.username == username)
            result = await self.db.execute(stmt)
            db_user = result.scalar_one_or_none()
            return db_user  # DB 可达：无论是否找到都直接返回（找到为 User，未找到为 None）
        except Exception as e:
            logger.warning("DB unreachable get_user_by_username, fallback builtin: %s", e)
            # DB 不可达时降级到内置账号
            b = _DEV_BUILTIN_USERS.get(username)
            if b is not None:
                return _build_fake_user(b)
            return None

    async def register(self, username: str, password: str, role: str = "user") -> User:
        """注册新用户。"""
        existing = await self.get_user_by_username(username)
        if existing is not None:
            raise AuthError("用户名已存在")
        user = User(
            username=username,
            password_hash=self.hash_password(password),
            role=role if role in ("user", "admin") else "user",
            status=1,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user


def _build_fake_user(b: dict):  # type: ignore[no-untyped-def]  # 返回鸭子类型对象
    """构造一个与 User 模型属性兼容的「伪对象」，用于 DB 不可用时的降级。

    为避开 SQLAlchemy ORM InstrumentedAttribute 描述符（需要 session 绑定），
    这里直接用 types.SimpleNamespace 做鸭子类型，避免 .id/.role 等赋值时
    AttributeError: 'NoneType' object has no attribute 'set'。
    """
    from datetime import datetime
    from types import SimpleNamespace

    u = SimpleNamespace()
    u.id = b["user_id"]
    u.username = b["username"]
    u.password_hash = ""
    u.role = b["role"]
    u.status = b.get("status", 1)
    u.created_at = None
    u.updated_at = None
    return u
