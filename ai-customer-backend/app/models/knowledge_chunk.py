"""KnowledgeChunk — knowledge_chunks 表：知识分块。"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.config.database import Base


class KnowledgeChunk(Base):
    """知识分块表：与 Milvus 中的向量记录一一对应。"""

    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    chunk_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    doc_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("knowledge_docs.doc_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    extra_metadata: Mapped[Optional[Any]] = mapped_column("extra_metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_doc_id", "doc_id"),
    )
