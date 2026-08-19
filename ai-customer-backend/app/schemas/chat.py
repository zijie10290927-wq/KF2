"""对话相关 DTO。"""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ChatMessageItem(BaseModel):
    """消息单元（用于请求历史）。"""

    role: Literal["user", "assistant", "system"]
    content: str


class SourceItem(BaseModel):
    """引用来源。"""

    title: str
    score: float
    snippet: str = ""


class StreamChatRequest(BaseModel):
    """流式对话请求。"""

    session_id: str = Field(..., description="会话ID")
    message: str = Field(..., min_length=1, max_length=4096, description="用户消息")
    history: list[ChatMessageItem] = Field(default_factory=list, description="历史消息")


class SSEEvent(BaseModel):
    """SSE 事件序列化模型。"""

    type: Literal["answer", "source", "fallback", "done", "error"]
    content: Optional[str] = None
    sources: Optional[list[SourceItem]] = None
    data: Optional[dict[str, Any]] = None
    message: Optional[str] = None


class ChatSessionDTO(BaseModel):
    """会话信息。"""

    session_id: str
    title: str
    status: str = "active"
    created_at: datetime


class ChatMessageDTO(BaseModel):
    """消息详情。"""

    message_id: str
    session_id: str
    role: str
    content: str
    intent: Optional[str] = None
    sources: Optional[list[SourceItem]] = None
    model_used: Optional[str] = None
    created_at: datetime


class TransferHumanRequest(BaseModel):
    """转人工请求。"""

    session_id: str
    reason: str = ""


class TransferHumanResponse(BaseModel):
    """转人工响应。"""

    transfer_status: str = "ok"
    human_service_url: str = ""
    phone: str = ""
    message: str = "已为您转接人工客服"
