"""ModelConfig — model_configs 表：多模型配置。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.config.database import Base


class ModelConfig(Base):
    """多模型配置表：API Key 经 Fernet 加密存储。"""

    __tablename__ = "model_configs"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    api_base: Mapped[str] = mapped_column(String(256), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(String(512), nullable=False)
    temperature: Mapped[float] = mapped_column(Numeric(3, 2), default=0.70, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=2048, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("uk_model_name", "model_name", unique=True),
    )
