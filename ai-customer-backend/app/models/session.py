"""ChatSession — chat_sessions 表：对话会话。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.config.database import Base


class ChatSession(Base):
    """对话会话表：每个用户可拥有多个会话。"""

    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(256), default="新对话", nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("active", "closed", "transferred", name="session_status"),
        default="active",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_user_id", "user_id"),
        Index("idx_session_id", "session_id", unique=True),
    )
