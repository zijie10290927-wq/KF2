"""Pydantic 请求/响应 DTO 层。"""

from app.schemas.common import ApiResponse, PageResponse
from app.schemas.chat import (
    ChatMessageDTO,
    ChatMessageItem,
    ChatSessionDTO,
    SSEEvent,
    SourceItem,
    StreamChatRequest,
    TransferHumanRequest,
    TransferHumanResponse,
)
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserInfo
from app.schemas.knowledge import DocFilterParams, DocListItem, DocUploadResponse
from app.schemas.admin import (
    ChatLogFilter,
    ChatLogItem,
    FallbackConfig,
    FallbackMessageUpdate,
    ModelConfigCreate,
    ModelConfigOut,
    ModelConfigUpdate,
)
from app.schemas.webhook import WebhookAck

__all__ = [
    "ApiResponse",
    "PageResponse",
    # chat
    "ChatMessageDTO",
    "ChatMessageItem",
    "ChatSessionDTO",
    "SSEEvent",
    "SourceItem",
    "StreamChatRequest",
    "TransferHumanRequest",
    "TransferHumanResponse",
    # auth
    "LoginRequest",
    "RegisterRequest",
    "TokenResponse",
    "UserInfo",
    # knowledge
    "DocFilterParams",
    "DocListItem",
    "DocUploadResponse",
    # admin
    "ChatLogFilter",
    "ChatLogItem",
    "FallbackConfig",
    "FallbackMessageUpdate",
    "ModelConfigCreate",
    "ModelConfigOut",
    "ModelConfigUpdate",
    # webhook
    "WebhookAck",
]
