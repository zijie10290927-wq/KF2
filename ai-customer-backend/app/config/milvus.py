"""Milvus Client 连接与集合管理。

Milvus 连接池：客户端应在应用启动时初始化并复用，禁止在每次检索时重新创建连接。
"""

import logging
from typing import Any, Optional

from app.config.settings import settings

logger = logging.getLogger(__name__)


class MilvusClientWrapper:
    """Milvus 客户端单例封装：延迟初始化 + 集合自动建表建索引。"""

    def __init__(self) -> None:
        self._client: Any = None
        self._connected: bool = False

    @property
    def client(self) -> Any:
        """获取底层 MilvusClient（未初始化时抛错）。"""
        if self._client is None:
            raise RuntimeError("Milvus client not initialized. Call connect() first.")
        return self._client

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> None:
        """建立 Milvus 连接：优先连接独立服务器，失败则降级到 milvus-lite 嵌入模式。"""
        if self._connected and self._client is not None:
            return

        # 1. 优先尝试连接独立 Milvus 服务器
        try:
            from pymilvus import MilvusClient

            uri = f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
            self._client = MilvusClient(uri=uri, timeout=5)
            self._connected = True
            logger.info("Milvus connected (server): %s", uri)
            return
        except Exception as e:
            logger.warning("Milvus server connect failed, trying embedded mode: %s", e)

        # 2. 降级到 milvus-lite 嵌入模式（本地文件存储，无需独立服务）
        try:
            from pymilvus import MilvusClient
            import os

            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data", "milvus_lite.db"
            )
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            self._client = MilvusClient(uri=db_path)
            self._connected = True
            logger.info("Milvus connected (embedded lite): %s", db_path)
        except Exception as e:  # pragma: no cover
            logger.error("Milvus embedded connect failed: %s", e)
            self._client = None
            self._connected = False

    def ensure_collection(self) -> None:
        """检查 knowledge_embeddings 集合是否存在，不存在则按 schema 创建 + 建索引。"""
        if self._client is None:
            logger.warning("Milvus client None, skip ensure_collection")
            return

        collection = settings.MILVUS_COLLECTION
        try:
            from pymilvus import DataType

            if self._client.has_collection(collection):
                logger.info("Milvus collection '%s' exists", collection)
                return

            schema = self._client.create_schema(
                auto_id=False, enable_dynamic_field=False
            )
            schema.add_field("chunk_id", DataType.VARCHAR, max_length=36, is_primary=True)
            schema.add_field("doc_id", DataType.VARCHAR, max_length=36)
            schema.add_field("content", DataType.VARCHAR, max_length=8192)
            schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=settings.EMBEDDING_DIM)
            schema.add_field("category", DataType.VARCHAR, max_length=64)

            index_params = self._client.prepare_index_params()
            index_params.add_index(
                field_name="embedding",
                index_type="IVF_FLAT",
                metric_type="COSINE",
                params={"nlist": 128},
            )

            self._client.create_collection(
                collection_name=collection,
                schema=schema,
                index_params=index_params,
            )
            logger.info("Milvus collection '%s' created", collection)
        except Exception as e:  # pragma: no cover
            logger.error("Milvus ensure_collection failed: %s", e)

    def get_client(self) -> Optional[Any]:
        """返回 MilvusClient 单例（可能为 None）。"""
        return self._client

    async def close(self) -> None:
        """关闭连接（应用关闭时调用）。"""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:  # pragma: no cover
                pass
            self._client = None
            self._connected = False
            logger.info("Milvus connection closed")


# 全局单例
milvus_client = MilvusClientWrapper()
