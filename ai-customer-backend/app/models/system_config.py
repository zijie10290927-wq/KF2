"""SystemConfig — system_configs 表：KV 系统配置。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.config.database import Base


class SystemConfig(Base):
    """系统配置 KV 表：兜底话术 / RAG 参数 / 意图阈值等。"""

    __tablename__ = "system_configs"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    config_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    config_value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("uk_config_key", "config_key", unique=True),
    )


# 预置核心配置项
DEFAULT_SYSTEM_CONFIGS = {
    "fallback_message": (
        "抱歉，我暂时无法回答该问题。您可以选择转接人工客服或拨打 400-xxx-xxxx 咨询。"
    ),
    "show_transfer_button": "true",
    "show_phone": "true",
    "phone_number": "400-xxx-xxxx",
    "rag_top_k": "5",
    "rag_score_threshold": "0.60",
    "rag_chunk_size": "512",
    "rag_chunk_overlap": "64",
    "rag_hybrid_search": "true",
    "rag_query_rewrite": "true",
    "intent_confidence_high": "0.85",
    "intent_confidence_low": "0.60",
    # ===== 渠道适配层 (Section 11) =====
    "webhook_enabled": "true",
    "openai_compat_enabled": "true",
    "widget_enabled": "true",
    "zhibo_enabled": "false",
    "zhibo_api_base": "https://api.sobot.com",
    "chatwoot_enabled": "false",
}
