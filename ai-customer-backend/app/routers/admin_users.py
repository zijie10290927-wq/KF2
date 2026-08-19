"""用户管理路由 /admin/users/*（需 admin 角色）。

- GET    /admin/users                          分页用户列表
- GET    /admin/users/{user_id}                用户详情
- PATCH  /admin/users/{user_id}/status         启用/禁用用户
- PATCH  /admin/users/{user_id}/role           修改用户角色
- POST   /admin/users/{user_id}/reset-password 管理员重置密码
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.exceptions import NotFoundError, PermissionDeniedError
from app.models import User
from app.schemas.common import ApiResponse
from app.services.deps import get_admin_user
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/users", tags=["B端-用户管理"])


class UserOut(BaseModel):
    """用户输出 DTO（不含密码）。"""

    id: int
    username: str
    role: str
    status: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


def _user_to_out(u: User) -> dict:
    """User ORM → 输出字典。

    Args:
        u: User ORM 对象。

    Returns:
        dict: UserOut 兼容字典。
    """
    return UserOut(
        id=u.id,
        username=u.username,
        role=u.role,
        status=u.status,
        created_at=u.created_at.isoformat() if u.created_at else None,
        updated_at=u.updated_at.isoformat() if u.updated_at else None,
    ).model_dump(mode="json")


@router.get("", response_model=ApiResponse, summary="分页用户列表")
async def list_users(
    keyword: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """分页查询用户列表（支持关键词/角色/状态过滤）。"""
    stmt = select(User)
    count_stmt = select(func.count(User.id))

    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(User.username.like(like))
        count_stmt = count_stmt.where(User.username.like(like))
    if role:
        stmt = stmt.where(User.role == role)
        count_stmt = count_stmt.where(User.role == role)
    if status is not None:
        stmt = stmt.where(User.status == status)
        count_stmt = count_stmt.where(User.status == status)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    users = list(result.scalars().all())

    return ApiResponse.success(
        data={
            "list": [_user_to_out(u) for u in users],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/{user_id}", response_model=ApiResponse, summary="用户详情")
async def get_user(
    user_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """获取用户详情。"""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    u = result.scalar_one_or_none()
    if u is None:
        raise NotFoundError("用户不存在")
    return ApiResponse.success(data=_user_to_out(u))


class StatusUpdate(BaseModel):
    """状态更新请求体。"""

    status: int  # 1:正常 0:禁用


@router.patch("/{user_id}/status", response_model=ApiResponse, summary="启用/禁用用户")
async def update_user_status(
    user_id: int = Path(..., ge=1),
    payload: StatusUpdate = ...,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """启用或禁用用户。"""
    if user_id == user.id:
        return ApiResponse.error(message="不能修改自己的状态")

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    u = result.scalar_one_or_none()
    if u is None:
        raise NotFoundError("用户不存在")

    if payload.status not in (0, 1):
        return ApiResponse.error(message="status 只能为 0 或 1")

    u.status = payload.status
    await db.commit()
    await db.refresh(u)
    return ApiResponse.success(data=_user_to_out(u), message="状态已更新")


class RoleUpdate(BaseModel):
    """角色更新请求体。"""

    role: str  # admin / user


@router.patch("/{user_id}/role", response_model=ApiResponse, summary="修改用户角色")
async def update_user_role(
    user_id: int = Path(..., ge=1),
    payload: RoleUpdate = ...,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """修改用户角色（admin ↔ user）。"""
    if user_id == user.id:
        return ApiResponse.error(message="不能修改自己的角色")

    if payload.role not in ("admin", "user"):
        return ApiResponse.error(message="role 只能为 admin 或 user")

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    u = result.scalar_one_or_none()
    if u is None:
        raise NotFoundError("用户不存在")

    u.role = payload.role
    await db.commit()
    await db.refresh(u)
    return ApiResponse.success(data=_user_to_out(u), message="角色已更新")


class ResetPassword(BaseModel):
    """重置密码请求体。"""

    new_password: str


@router.post(
    "/{user_id}/reset-password",
    response_model=ApiResponse,
    summary="管理员重置用户密码",
)
async def reset_password(
    user_id: int = Path(..., ge=1),
    payload: ResetPassword = ...,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """管理员重置用户密码（BCrypt 哈希存储）。"""
    if len(payload.new_password) < 6:
        return ApiResponse.error(message="密码长度至少 6 位")

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    u = result.scalar_one_or_none()
    if u is None:
        raise NotFoundError("用户不存在")

    u.password_hash = AuthService.hash_password(payload.new_password)
    await db.commit()
    return ApiResponse.success(message="密码已重置")
