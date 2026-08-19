"""对话记录管理路由 /admin/chat/*（需 admin 角色）。

- GET /admin/chat/logs                 分页对话记录（按 session_id/日期/意图过滤）
- GET /admin/chat/logs/{session_id}    指定会话的完整对话详情
- GET /admin/chat/sessions            会话列表（含用户名/状态/消息数）
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.exceptions import NotFoundError
from app.models import ChatMessage, ChatSession, User
from app.schemas.admin import ChatLogItem
from app.schemas.common import ApiResponse
from app.services.deps import get_admin_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/chat", tags=["B端-对话记录"])


@router.get("/logs", response_model=ApiResponse, summary="分页对话记录")
async def list_chat_logs(
    session_id: Optional[str] = Query(None),
    intent: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """按 session_id/日期/意图分页查询对话消息记录。"""
    stmt = select(ChatMessage)
    count_stmt = select(func.count(ChatMessage.id))

    if session_id:
        stmt = stmt.where(ChatMessage.session_id == session_id)
        count_stmt = count_stmt.where(ChatMessage.session_id == session_id)
    if intent:
        stmt = stmt.where(ChatMessage.intent == intent)
        count_stmt = count_stmt.where(ChatMessage.intent == intent)
    if start_date:
        stmt = stmt.where(ChatMessage.created_at >= start_date)
        count_stmt = count_stmt.where(ChatMessage.created_at >= start_date)
    if end_date:
        stmt = stmt.where(ChatMessage.created_at <= end_date)
        count_stmt = count_stmt.where(ChatMessage.created_at <= end_date)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(ChatMessage.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size)
    result = await db.execute(stmt)
    messages = list(result.scalars().all())

    data = [
        ChatLogItem(
            message_id=m.message_id,
            session_id=m.session_id,
            role=m.role,
            content=m.content,
            intent=m.intent,
            sources=m.sources,
            model_used=m.model_used,
            created_at=m.created_at,
        ).model_dump(mode="json")
        for m in messages
    ]
    return ApiResponse.success(
        data={
            "list": data,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/logs/{session_id}", response_model=ApiResponse, summary="会话完整对话")
async def get_session_logs(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """获取指定会话的完整对话记录（按时间正序）。"""
    # 先校验会话是否存在
    sess = await db.execute(
        select(ChatSession).where(ChatSession.session_id == session_id)
    )
    session = sess.scalar_one_or_none()
    if session is None:
        raise NotFoundError("会话不存在")

    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    result = await db.execute(stmt)
    messages = list(result.scalars().all())

    data = [
        ChatLogItem(
            message_id=m.message_id,
            session_id=m.session_id,
            role=m.role,
            content=m.content,
            intent=m.intent,
            sources=m.sources,
            model_used=m.model_used,
            created_at=m.created_at,
        ).model_dump(mode="json")
        for m in messages
    ]
    return ApiResponse.success(
        data={
            "session_id": session_id,
            "title": session.title,
            "status": session.status,
            "messages": data,
        }
    )


@router.get("/sessions", response_model=ApiResponse, summary="会话列表")
async def list_sessions(
    user_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None, description="active/closed/transferred"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """会话列表（联表查询用户名 + 消息数）。"""
    stmt = select(ChatSession, User.username).join(User, ChatSession.user_id == User.id, isouter=True)
    count_stmt = select(func.count(ChatSession.id))

    if user_id:
        stmt = stmt.where(ChatSession.user_id == user_id)
        count_stmt = count_stmt.where(ChatSession.user_id == user_id)
    if status:
        stmt = stmt.where(ChatSession.status == status)
        count_stmt = count_stmt.where(ChatSession.status == status)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(ChatSession.updated_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size)
    result = await db.execute(stmt)
    rows = result.all()

    data = [
        {
            "session_id": s.session_id,
            "user_id": s.user_id,
            "username": username or "",
            "title": s.title,
            "status": s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s, username in rows
    ]
    return ApiResponse.success(
        data={"list": data, "total": total, "page": page, "page_size": page_size}
    )
