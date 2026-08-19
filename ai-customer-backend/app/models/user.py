"""User — users 表：用户账号。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Enum, Index, Integer, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.config.database import Base


class User(Base):
    """用户表：管理员 + C 端用户。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("user", "admin", name="user_role"), default="user", nullable=False
    )
    status: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False, comment="1:正常 0:禁用")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_username", "username"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User(id={self.id}, username={self.username!r}, role={self.role!r})>"
