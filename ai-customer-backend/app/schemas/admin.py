"""管理后台 DTO。"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.chat import SourceItem


class ModelConfigCreate(BaseModel):
    """模型配置新增。"""

    model_name: str = Field(..., max_length=64)
    api_base: str = Field(..., max_length=256)
    api_key: str = Field(..., min_length=1, max_length=256)
    temperature: Decimal = Field(default=Decimal("0.70"), ge=0, le=1)
    max_tokens: int = Field(default=2048, ge=1, le=32768)
    enabled: bool = True
    is_default: bool = False


class ModelConfigUpdate(BaseModel):
    """模型配置更新。"""

    model_name: Optional[str] = Field(default=None, max_length=64)
    api_base: Optional[str] = Field(default=None, max_length=256)
    api_key: Optional[str] = Field(default=None, max_length=256)
    temperature: Optional[Decimal] = Field(default=None, ge=0, le=1)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=32768)
    enabled: Optional[bool] = None
    is_default: Optional[bool] = None


class ModelConfigOut(BaseModel):
    """模型配置输出（不含 API Key）。"""

    id: int
    model_name: str
    api_base: str
    temperature: Decimal
    max_tokens: int
    enabled: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime


class FallbackMessageUpdate(BaseModel):
    """兜底话术更新。"""

    message: Optional[str] = None
    show_transfer_button: Optional[bool] = None
    show_phone: Optional[bool] = None
    phone_number: Optional[str] = None


class FallbackConfig(BaseModel):
    """兜底配置。"""

    fallback_message: str
    show_transfer_button: bool = True
    show_phone: bool = True
    phone_number: str = ""


class ChatLogFilter(BaseModel):
    """对话记录筛选。"""

    session_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    intent: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ChatLogItem(BaseModel):
    """对话记录条目。"""

    message_id: str
    session_id: str
    role: str
    content: str
    intent: Optional[str] = None
    sources: Optional[list[SourceItem]] = None
    model_used: Optional[str] = None
    created_at: datetime
