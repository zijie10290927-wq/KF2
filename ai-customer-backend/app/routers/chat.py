"""C 端对话接口 /chat/*。

- POST /chat/stream                                  SSE 流式对话
- POST /chat/sessions                                创建新会话
- GET  /chat/sessions/{session_id}/messages          分页获取会话消息历史
- GET  /chat/sessions                                获取当前用户会话列表
- DELETE /chat/sessions/{session_id}                 删除会话
- POST /chat/transfer-human                          申请转人工客服
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.exceptions import NotFoundError
from app.models import ChatMessage, ChatSession, User
from app.schemas.chat import (
    ChatMessageDTO,
    ChatSessionDTO,
    StreamChatRequest,
    TransferHumanRequest,
    TransferHumanResponse,
)
from app.schemas.common import ApiResponse
from app.services.chat_service import ChatService
from app.services.config_service import ConfigService
from app.services.deps import get_chat_service, get_config_service, get_current_user
from app.services.memory_service import MemoryService
from app.utils.sse import sse_stream

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["C端对话"])


class CreateSessionReq(BaseModel):
    """创建会话请求体（前端以 JSON body 方式发送）。"""
    title: str = "新对话"


@router.post("/stream", summary="流式对话 (SSE)")
async def stream_chat(
    req: StreamChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """发送消息，SSE 流式返回回答。

    SSE 事件类型：source / answer / fallback / done / error
    每个事件格式：``event: {type}\\ndata: {json}\\n\\n``
    """
    # 历史转为 dict 列表
    history = [{"role": h.role, "content": h.content} for h in req.history]

    async def event_generator():
        async for event in chat_service.handle_message_stream(
            session_id=req.session_id,
            message=req.message,
            history=history,
            user_id=user.id,
        ):
            yield event

    return StreamingResponse(
        sse_stream(event_generator()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 禁用缓冲
        },
    )


@router.post("/sessions", response_model=ApiResponse, summary="创建新会话")
async def create_session(
    req: CreateSessionReq = Body(default_factory=CreateSessionReq),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApiResponse:
    """创建新会话，返回 {session_id, title, created_at}。
    兼容两种请求格式：
    - 前端新写法：JSON body { title?: string }
    - 历史 query param 写法：?title=xxx（若 body 缺省但 query 有值仍接受）
    """
    session_id = str(uuid.uuid4())
    session = ChatSession(
        session_id=session_id,
        user_id=user.id,
        title=req.title or "新对话",
        status="active",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    dto = ChatSessionDTO(
        session_id=session.session_id,
        title=session.title,
        status=session.status,
        created_at=session.created_at,
    )
    return ApiResponse.success(data=dto.model_dump(mode="json"))


@router.get("/sessions", response_model=ApiResponse, summary="会话列表")
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApiResponse:
    """获取当前用户的所有会话。"""
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    result = await db.execute(stmt)
    sessions = result.scalars().all()
    data = [
        ChatSessionDTO(
            session_id=s.session_id,
            title=s.title,
            status=s.status,
            created_at=s.created_at,
        ).model_dump(mode="json")
        for s in sessions
    ]
    return ApiResponse.success(data=data)


@router.get("/sessions/{session_id}/messages", response_model=ApiResponse, summary="分页消息历史")
async def get_messages(
    session_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApiResponse:
    """分页获取会话消息历史。"""
    # 校验会话归属
    await _ensure_session_owner(db, session_id, user.id)

    offset = (page - 1) * page_size
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()
    data = [
        ChatMessageDTO(
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

    # 总数
    from sqlalchemy import func

    count_stmt = select(func.count(ChatMessage.id)).where(ChatMessage.session_id == session_id)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    return ApiResponse.success(data={"list": data, "total": total, "page": page, "page_size": page_size})


@router.delete("/sessions/{session_id}", response_model=ApiResponse, summary="删除会话")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApiResponse:
    """删除会话（级联删除消息）。"""
    await _ensure_session_owner(db, session_id, user.id)
    stmt = delete(ChatSession).where(ChatSession.session_id == session_id)
    await db.execute(stmt)
    await db.commit()
    return ApiResponse.success(message="会话已删除")


@router.post("/transfer-human", response_model=ApiResponse, summary="转人工客服")
async def transfer_human(
    req: TransferHumanRequest,
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_current_user),
) -> ApiResponse:
    """申请转人工客服。"""
    fallback = await config_service.get_fallback_message()
    resp = TransferHumanResponse(
        transfer_status="ok",
        human_service_url="",
        phone=fallback.phone_number,
        message="已为您转接人工客服，请稍候",
    )
    return ApiResponse.success(data=resp.model_dump(mode="json"))


# ---------------------------------------------------------------------- #
# 辅助
# ---------------------------------------------------------------------- #
async def _ensure_session_owner(db: AsyncSession, session_id: str, user_id: int) -> ChatSession:
    """校验会话存在且属于当前用户。"""
    stmt = select(ChatSession).where(
        ChatSession.session_id == session_id,
        ChatSession.user_id == user_id,
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    if session is None:
        raise NotFoundError("会话不存在或无权访问")
    return session
