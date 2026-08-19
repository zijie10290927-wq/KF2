"""ChatMessage — chat_messages 表：对话消息。"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.config.database import Base


class ChatMessage(Base):
    """对话消息表：用户消息 + AI 回答均存于此。"""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chat_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        Enum("user", "assistant", "system", name="message_role"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    sources: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )

    __table_args__ = (
        Index("idx_session_id", "session_id"),
        Index("idx_created_at", "created_at"),
    )
