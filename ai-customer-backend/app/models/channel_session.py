"""ChannelSession — channel_sessions 表：外部平台 ↔ 内部会话映射。"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.config.database import Base


class ChannelSession(Base):
    """渠道会话映射表：第三方平台会话与内部 session_id 的双向映射。"""

    __tablename__ = "channel_sessions"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    external_session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    external_user_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    external_user_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    internal_session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    channel_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    extra_metadata: Mapped[Optional[Any]] = mapped_column("extra_metadata", JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_platform", "platform"),
        Index("idx_internal_session_id", "internal_session_id"),
        UniqueConstraint("platform", "external_session_id", name="uk_platform_session"),
    )
