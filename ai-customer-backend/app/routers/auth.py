"""认证路由 /auth/*。

- POST /auth/login  登录验证 → 返回 JWT Token + 用户信息
- POST /auth/logout 登出（黑名单 Token 写入 Redis）
- GET  /auth/me     获取当前登录用户信息
- POST /auth/register 注册新用户 (P0 便捷接口，生产可关闭)
"""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserInfo
from app.schemas.common import ApiResponse
from app.services.auth_service import AuthService
from app.services.deps import get_auth_service, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["认证"])
_security = HTTPBearer(auto_error=False)


@router.post("/login", response_model=ApiResponse, summary="用户登录")
async def login(
    req: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> ApiResponse:
    """登录验证 → 返回 JWT Token + 用户信息。"""
    token_resp: TokenResponse = await auth_service.login(req.username, req.password)
    return ApiResponse.success(data=token_resp.model_dump(mode="json"))


@router.post("/logout", response_model=ApiResponse, summary="登出")
async def logout(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> ApiResponse:
    """登出：将 Token 加入 Redis 黑名单。"""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else ""
    if token:
        try:
            await auth_service.blacklist_token(token)
        except Exception as e:
            logger.warning("Blacklist token failed: %s", e)
    return ApiResponse.success(message="已退出登录")


@router.get("/me", response_model=ApiResponse, summary="获取当前用户")
async def me(
    user: User = Depends(get_current_user),
) -> ApiResponse:
    """获取当前登录用户信息。"""
    user_info = UserInfo(
        user_id=user.id,
        username=user.username,
        role=user.role,
        status=user.status,
        created_at=user.created_at,
    )
    return ApiResponse.success(data=user_info.model_dump(mode="json"))


@router.post("/register", response_model=ApiResponse, summary="注册用户")
async def register(
    req: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> ApiResponse:
    """注册新用户（P0 便捷接口）。"""
    user = await auth_service.register(req.username, req.password, req.role)
    return ApiResponse.success(
        data={"user_id": user.id, "username": user.username, "role": user.role},
        message="注册成功",
    )
