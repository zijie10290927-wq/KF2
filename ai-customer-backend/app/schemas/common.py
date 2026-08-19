"""统一响应模型 + 公共 DTO。"""

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel


T = TypeVar("T")


class ApiResponse(BaseModel):
    """统一响应契约：{code, message, data}。"""

    code: int = 0
    message: str = "success"
    data: Optional[Any] = None

    @classmethod
    def success(cls, data: Any = None, message: str = "success") -> "ApiResponse":
        return cls(code=0, message=message, data=data)

    @classmethod
    def error(cls, message: str, code: int = -1, data: Any = None) -> "ApiResponse":
        return cls(code=code, message=message, data=data)


class PageResponse(BaseModel, Generic[T]):
    """分页响应。"""

    code: int = 0
    message: str = "success"
    data: Optional[list[T]] = None
    total: int = 0
    page: int = 1
    page_size: int = 10
