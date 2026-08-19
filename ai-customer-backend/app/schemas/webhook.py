"""Webhook 请求/响应 DTO（渠道适配层）。

涵盖：
1. Webhook 立即响应（202 Accepted + ack body）
2. OpenAI 兼容端点请求/响应 DTO
3. 渠道会话消息 DTO（供管理后台使用）
"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------- #
# Webhook 立即响应
# ---------------------------------------------------------------------- #
class WebhookAck(BaseModel):
    """Webhook 立即响应（统一返回 202 + 此 body）。"""

    code: int = 0
    message: str = "accepted"
    msg_id: Optional[str] = None
    status: Optional[str] = "accepted"
    platform: Optional[str] = None
    internal_session_id: Optional[str] = None


class WebhookHealth(BaseModel):
    """Webhook 健康检查响应。"""

    enabled: bool
    platforms: List[dict] = Field(default_factory=list)


# ---------------------------------------------------------------------- #
# OpenAI 兼容端点 DTO
# ---------------------------------------------------------------------- #
class OpenAIChatRequest(BaseModel):
    """OpenAI 兼容对话请求。"""

    model: str = "ai-customer-agent"
    messages: List[dict] = Field(..., min_length=1)
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    # 扩展字段：用于透传 session_id 等
    metadata: Optional[dict] = None
    # 可选的用户标识（用于风控与日志）
    user: Optional[str] = None


class OpenAIMessage(BaseModel):
    """OpenAI 消息对象。"""

    role: str
    content: str


class OpenAIChoice(BaseModel):
    """OpenAI 选择项。"""

    index: int = 0
    message: Optional[OpenAIMessage] = None
    delta: Optional[dict] = None
    finish_reason: Optional[str] = None


class OpenAIUsage(BaseModel):
    """OpenAI 用量统计。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class OpenAIChatCompletion(BaseModel):
    """OpenAI 非流式响应。"""

    id: str
    object: str = "chat.completion"
    created: int
    model: str = "ai-customer-agent"
    choices: List[OpenAIChoice]
    usage: Optional[OpenAIUsage] = None


class OpenAIChatChunk(BaseModel):
    """OpenAI 流式 chunk。"""

    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str = "ai-customer-agent"
    choices: List[OpenAIChoice]


# ---------------------------------------------------------------------- #
# 渠道会话 DTO（管理后台）
# ---------------------------------------------------------------------- #
class ChannelSessionDTO(BaseModel):
    """渠道会话映射 DTO。"""

    id: int
    platform: str
    external_session_id: str
    external_user_id: Optional[str] = None
    external_user_name: Optional[str] = None
    internal_session_id: str
    channel_type: Optional[str] = None
    extra_metadata: Optional[Any] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChannelConfigDTO(BaseModel):
    """渠道配置 DTO（管理后台用）。"""

    platform: str
    display_name: str
    enabled: bool = False
    api_token: Optional[str] = None
    webhook_secret: Optional[str] = None
    app_key: Optional[str] = None
    api_base: Optional[str] = None
    remark: Optional[str] = None


class ChannelOverviewDTO(BaseModel):
    """渠道总览统计 DTO。"""

    today_messages: int = 0
    active_channels: int = 0
    avg_response_time_ms: int = 0
    transfer_rate: float = 0.0
    channels: List[dict] = Field(default_factory=list)


class WebhookLogDTO(BaseModel):
    """Webhook 日志 DTO（简化版，日志可走文件/DB）。"""

    id: int
    platform: str
    message_id: Optional[str] = None
    status: str
    raw_body: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
