"""KnowledgeDoc — knowledge_docs 表：知识库文档元数据。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Enum, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.config.database import Base


class KnowledgeDoc(Base):
    """知识库文档元数据表。"""

    __tablename__ = "knowledge_docs"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    doc_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    chunk_size: Mapped[int] = mapped_column(Integer, default=512, nullable=False)
    overlap: Mapped[int] = mapped_column(Integer, default=64, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("uploading", "processing", "indexed", "failed", name="doc_status"),
        default="uploading",
        nullable=False,
        index=True,
    )
    error_msg: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_status", "status"),
    )
