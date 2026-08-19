"""认证 DTO。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """登录请求。"""

    username: str = Field(..., min_length=1, max_length=64, description="用户名")
    password: str = Field(..., min_length=1, max_length=128, description="密码")


class RegisterRequest(BaseModel):
    """注册请求。

    安全约束：匿名注册端点仅允许创建普通用户；role 固定为 "user"，
    服务端（AuthService.register）会再次强制覆盖，双重防提权。
    """

    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    role: str = Field(default="user", pattern="^user$")


class UserInfo(BaseModel):
    """用户信息。"""

    user_id: int
    username: str
    role: str = "user"
    status: int = 1
    created_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    """登录响应。"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_info: UserInfo
