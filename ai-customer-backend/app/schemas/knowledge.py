"""知识库 DTO。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DocUploadResponse(BaseModel):
    """上传响应。"""

    doc_id: str
    filename: str
    chunk_count: int = 0
    status: str = "uploading"


class DocListItem(BaseModel):
    """文档列表项。"""

    doc_id: str
    filename: str
    file_type: str
    file_size: Optional[int] = None
    category: Optional[str] = None
    chunk_count: int = 0
    status: str
    error_msg: Optional[str] = None
    created_at: datetime


class DocFilterParams(BaseModel):
    """筛选参数。"""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)
    status: Optional[str] = None
    category: Optional[str] = None
    keyword: Optional[str] = None
