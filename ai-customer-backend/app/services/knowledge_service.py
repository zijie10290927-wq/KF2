"""KnowledgeService — 知识库文档处理流水线。

完整串联：上传 → MinIO 落盘 → 解析 → 清洗 → 分块 → 向量化 → Milvus+MySQL 入库。

设计要点：
1. 长任务使用独立 AsyncSession，避免主会话提前关闭（异步上下文泄漏）。
2. 期间更新 doc.status: uploading → processing → indexed / failed。
3. 大文件解析与向量化应在后台任务中执行，禁止在 API 请求线程内同步阻塞。
4. 删除文档需联动清理 MinIO + Milvus + MySQL chunks + MySQL doc。
"""

import logging
import re
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import AsyncSessionLocal
from app.config.milvus import milvus_client
from app.config.minio import minio_client
from app.config.settings import settings
from app.models import KnowledgeChunk, KnowledgeDoc
from app.services.rag_service import embedding_client
from app.utils.document_parser import parse_auto

if TYPE_CHECKING:  # pragma: no cover
    from app.services.config_service import ConfigService
    from app.schemas.knowledge import DocFilterParams

logger = logging.getLogger(__name__)


class KnowledgeService:
    """知识库文档处理流水线服务。"""

    def __init__(
        self,
        db: AsyncSession,
        config_service: "Optional[ConfigService]" = None,
    ) -> None:
        """初始化 KnowledgeService。

        Args:
            db: 当前请求的 AsyncSession（仅用于查询/快速操作，长任务用独立 session）。
            config_service: 配置服务，用于读取 chunk_size / overlap 等动态配置。
        """
        self.db = db
        self.config_service = config_service

    # ------------------------------------------------------------------ #
    # 上传入口：创建 doc 记录 + 落 MinIO + 触发后台处理
    # ------------------------------------------------------------------ #
    async def upload_document(
        self,
        file_bytes: bytes,
        filename: str,
        file_size: Optional[int],
        category: Optional[str] = None,
        chunk_size: Optional[int] = None,
        overlap: Optional[int] = None,
    ) -> KnowledgeDoc:
        """上传文档入口：创建 doc 元数据 + 立即落 MinIO，返回 status=uploading 的 doc。

        Args:
            file_bytes: 文件二进制内容。
            filename: 原始文件名（用于推断扩展名）。
            file_size: 文件字节数（允许为空）。
            category: 知识分类标签（可选）。
            chunk_size: 分块大小；None 时从 ConfigService 读取。
            overlap: 分块重叠；None 时从 ConfigService 读取。

        Returns:
            KnowledgeDoc: 已创建的文档元数据，status=uploading。
        """
        # 1. 读取默认分块参数
        cs = chunk_size or await self._resolve_chunk_size()
        ov = overlap or await self._resolve_chunk_overlap()

        # 2. 解析扩展名与 file_type
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
        file_type = ext if ext in ("pdf", "docx", "doc", "txt", "md", "markdown") else "txt"

        # 3. 生成 doc_id 与 MinIO 路径
        doc_id = str(uuid.uuid4())
        object_name = self._build_minio_path(filename, ext)

        # 4. 创建 doc 记录（status=uploading）
        doc = KnowledgeDoc(
            doc_id=doc_id,
            filename=filename,
            file_path=object_name,
            file_type=file_type,
            file_size=file_size or len(file_bytes),
            category=category,
            chunk_size=cs,
            overlap=ov,
            chunk_count=0,
            status="uploading",
        )
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)

        # 5. 立即上传原始文件到 MinIO（轻量 IO，可与请求同步）
        try:
            minio_client.put_object_bytes(
                bucket=settings.MINIO_BUCKET,
                object_name=object_name,
                data=file_bytes,
                length=len(file_bytes),
                content_type=self._guess_content_type(ext),
            )
        except Exception as e:
            # MinIO 失败：标记 failed，但不抛错（用户可重试 reindex）
            logger.error("Upload to MinIO failed for doc %s: %s", doc_id, e)
            await self._mark_failed(doc_id, f"MinIO 上传失败: {e}")
            raise

        return doc

    # ------------------------------------------------------------------ #
    # 核心流水线：异步处理
    # ------------------------------------------------------------------ #
    async def process_document_from_minio(self, doc_id: str) -> None:
        """从 MinIO 拉取已上传文件并触发处理流水线（供 BackgroundTasks 调用）。

        Args:
            doc_id: 文档 ID。

        Returns:
            None: 文件读取失败会标记 doc.status=failed。
        """
        doc = await self.get_document(doc_id)
        if doc is None:
            logger.error("process_from_minio: doc not found %s", doc_id)
            return

        file_bytes = minio_client.get_object_bytes(
            settings.MINIO_BUCKET, doc.file_path
        )
        if not file_bytes:
            await self._mark_failed(doc_id, "从 MinIO 读取文件失败")
            return

        await self.process_document(doc_id, file_bytes, doc.filename)

    async def reindex_from_minio(self, doc_id: str) -> None:
        """从 MinIO 拉取已上传文件并触发重建索引（供 BackgroundTasks 调用）。

        Args:
            doc_id: 文档 ID。

        Returns:
            None
        """
        doc = await self.get_document(doc_id)
        if doc is None:
            logger.error("reindex_from_minio: doc not found %s", doc_id)
            return

        file_bytes = minio_client.get_object_bytes(
            settings.MINIO_BUCKET, doc.file_path
        )
        if not file_bytes:
            await self._mark_failed(doc_id, "从 MinIO 读取文件失败")
            return

        await self.reindex(doc_id, file_bytes, doc.filename)

    async def process_document(
        self,
        doc_id: str,
        file_bytes: bytes,
        filename: str,
    ) -> None:
        """文档处理流水线（应在 BackgroundTasks 中调用）。

        7 步流程：
            1. status=processing
            2. 解析文档为 raw_text
            3. 清洗文本
            4. RecursiveCharacterTextSplitter 分块
            5. 估算 token 数
            6. 批量向量化
            7. Milvus 入库 + MySQL chunks 入库 + status=indexed

        Args:
            doc_id: 文档 ID。
            file_bytes: 文件二进制内容。
            filename: 原始文件名（用于推断扩展名）。

        Returns:
            None: 任意步骤失败都会写入 status=failed + error_msg。
        """
        # 使用独立 AsyncSession，避免主会话关闭导致写入失败
        async with AsyncSessionLocal() as session:
            try:
                # Step 1: 标记 processing
                await self._update_status(session, doc_id, "processing")
                await session.commit()

                # 读取 doc 元数据（chunk_size / overlap / file_path / category）
                doc = await self._get_doc(session, doc_id)
                if doc is None:
                    raise ValueError(f"Doc not found: {doc_id}")

                # Step 2: 解析文档
                raw_text = parse_auto(file_bytes, filename)
                if not raw_text.strip():
                    raise ValueError("文档解析后内容为空")

                # Step 3: 清洗文本
                clean_text = self._clean_text(raw_text)

                # Step 4: 分块
                chunks = self._split_text(
                    clean_text,
                    chunk_size=doc.chunk_size or settings.RAG_CHUNK_SIZE,
                    overlap=doc.overlap or settings.RAG_CHUNK_OVERLAP,
                )
                if not chunks:
                    raise ValueError("分块结果为空")

                logger.info(
                    "Doc %s split into %d chunks (size=%d overlap=%d)",
                    doc_id, len(chunks), doc.chunk_size, doc.overlap,
                )

                # Step 5 + 6: 估算 token + 批量向量化
                chunk_meta: list[dict] = []
                for idx, text in enumerate(chunks):
                    chunk_meta.append({
                        "chunk_id": str(uuid.uuid4()),
                        "chunk_index": idx,
                        "content": text,
                        "token_count": self._estimate_tokens(text),
                    })

                # 批量 embedding（按批次，避免单次请求过大）
                embeddings = await self._batch_embed_safe(
                    [m["content"] for m in chunk_meta]
                )
                if len(embeddings) != len(chunk_meta):
                    raise ValueError(
                        f"Embedding 数量不匹配: {len(embeddings)} != {len(chunk_meta)}"
                    )

                # Step 7: Milvus 入库 + MySQL chunks 入库
                await self._insert_to_milvus(doc_id, doc.category, chunk_meta, embeddings)

                # 写入 MySQL chunks
                for m in chunk_meta:
                    session.add(
                        KnowledgeChunk(
                            chunk_id=m["chunk_id"],
                            doc_id=doc_id,
                            chunk_index=m["chunk_index"],
                            content=m["content"],
                            token_count=m["token_count"],
                            extra_metadata={
                                "category": doc.category,
                                "filename": doc.filename,
                            },
                        )
                    )

                # 更新 doc 状态
                doc.chunk_count = len(chunks)
                doc.status = "indexed"
                doc.error_msg = None
                await session.commit()

                logger.info("Doc %s indexed successfully (%d chunks)", doc_id, len(chunks))

            except Exception as e:
                logger.exception("Process document failed: doc_id=%s", doc_id)
                await session.rollback()
                await self._mark_failed(doc_id, str(e))

    # ------------------------------------------------------------------ #
    # 查询接口
    # ------------------------------------------------------------------ #
    async def get_document(self, doc_id: str) -> Optional[KnowledgeDoc]:
        """根据 doc_id 查询单条文档。

        Args:
            doc_id: 文档 ID。

        Returns:
            Optional[KnowledgeDoc]: 文档对象；不存在返回 None。
        """
        stmt = select(KnowledgeDoc).where(KnowledgeDoc.doc_id == doc_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_documents(
        self,
        page: int = 1,
        page_size: int = 10,
        status_filter: Optional[str] = None,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> dict:
        """分页查询文档列表。

        Args:
            page: 页码（从 1 开始）。
            page_size: 每页条数。
            status_filter: 状态过滤（uploading/processing/indexed/failed）。
            category: 分类过滤。
            keyword: 文件名关键词模糊匹配。

        Returns:
            dict: {list: [KnowledgeDoc, ...], total: int, page: int, page_size: int}
        """
        stmt = select(KnowledgeDoc)
        count_stmt = select(func.count(KnowledgeDoc.id))

        if status_filter:
            stmt = stmt.where(KnowledgeDoc.status == status_filter)
            count_stmt = count_stmt.where(KnowledgeDoc.status == status_filter)
        if category:
            stmt = stmt.where(KnowledgeDoc.category == category)
            count_stmt = count_stmt.where(KnowledgeDoc.category == category)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(KnowledgeDoc.filename.like(like))
            count_stmt = count_stmt.where(KnowledgeDoc.filename.like(like))

        # 总数
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # 分页
        stmt = stmt.order_by(KnowledgeDoc.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size)
        result = await self.db.execute(stmt)
        docs = list(result.scalars().all())

        return {
            "list": docs,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    # ------------------------------------------------------------------ #
    # 删除与重建索引
    # ------------------------------------------------------------------ #
    async def delete_document(self, doc_id: str) -> bool:
        """删除文档：联动清理 MinIO + Milvus + MySQL chunks + MySQL doc。

        Args:
            doc_id: 文档 ID。

        Returns:
            bool: 是否找到并删除了文档。
        """
        doc = await self.get_document(doc_id)
        if doc is None:
            return False

        # 1. 删 MinIO 原文件
        try:
            minio_client.delete_object(settings.MINIO_BUCKET, doc.file_path)
        except Exception as e:  # pragma: no cover
            logger.warning("Delete MinIO object failed: %s", e)

        # 2. 删 Milvus 向量（按 doc_id 过滤）
        try:
            client = milvus_client.get_client()
            if client is not None:
                client.delete(
                    collection_name=settings.MILVUS_COLLECTION,
                    filter=f'doc_id == "{doc_id}"',
                )
        except Exception as e:  # pragma: no cover
            logger.warning("Delete Milvus chunks failed: %s", e)

        # 3. 删 MySQL chunks
        await self.db.execute(
            delete(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc_id)
        )
        # 4. 删 MySQL doc
        await self.db.execute(
            delete(KnowledgeDoc).where(KnowledgeDoc.doc_id == doc_id)
        )
        await self.db.commit()
        return True

    async def reindex(
        self,
        doc_id: str,
        file_bytes: bytes,
        filename: str,
    ) -> None:
        """重建索引：先清空旧 chunks 与 Milvus 记录，再走流水线。

        Args:
            doc_id: 文档 ID。
            file_bytes: 文件二进制内容。
            filename: 原始文件名。

        Returns:
            None
        """
        # 1. 清旧 chunks（保留 doc 元数据，重置 chunk_count 与 status）
        await self.db.execute(
            delete(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc_id)
        )
        # 清 Milvus 旧记录
        try:
            client = milvus_client.get_client()
            if client is not None:
                client.delete(
                    collection_name=settings.MILVUS_COLLECTION,
                    filter=f'doc_id == "{doc_id}"',
                )
        except Exception as e:  # pragma: no cover
            logger.warning("Clear Milvus for reindex failed: %s", e)

        # 重置 doc 状态
        doc = await self.get_document(doc_id)
        if doc is not None:
            doc.chunk_count = 0
            doc.status = "uploading"
            doc.error_msg = None
        await self.db.commit()

        # 2. 走处理流水线
        await self.process_document(doc_id, file_bytes, filename)

    # ------------------------------------------------------------------ #
    # 内部工具
    # ------------------------------------------------------------------ #
    async def _resolve_chunk_size(self) -> int:
        """从 ConfigService 读取 rag_chunk_size，失败则用 settings 默认值。

        Returns:
            int: 分块大小（字符数）。
        """
        if self.config_service is not None:
            return await self.config_service.get_int(
                "rag_chunk_size", settings.RAG_CHUNK_SIZE
            )
        return settings.RAG_CHUNK_SIZE

    async def _resolve_chunk_overlap(self) -> int:
        """从 ConfigService 读取 rag_chunk_overlap，失败则用 settings 默认值。

        Returns:
            int: 分块重叠字符数。
        """
        if self.config_service is not None:
            return await self.config_service.get_int(
                "rag_chunk_overlap", settings.RAG_CHUNK_OVERLAP
            )
        return settings.RAG_CHUNK_OVERLAP

    @staticmethod
    def _build_minio_path(filename: str, ext: str) -> str:
        """构造 MinIO 对象路径：knowledge/yyyy/MM/dd/{uuid}.{ext}。

        Args:
            filename: 原始文件名（仅用于日志，不参与路径）。
            ext: 扩展名（不含点）。

        Returns:
            str: MinIO object_name。
        """
        now = datetime.now()
        return f"knowledge/{now.strftime('%Y/%m/%d')}/{uuid.uuid4().hex}.{ext}"

    @staticmethod
    def _guess_content_type(ext: str) -> str:
        """根据扩展名猜测 MIME 类型。

        Args:
            ext: 扩展名（小写，不含点）。

        Returns:
            str: MIME 类型字符串。
        """
        mapping = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "doc": "application/msword",
            "txt": "text/plain",
            "md": "text/markdown",
            "markdown": "text/markdown",
        }
        return mapping.get(ext, "application/octet-stream")

    @staticmethod
    def _clean_text(raw_text: str) -> str:
        """清洗文本：去多余空行、控制字符、连续空格、页眉页脚噪声。

        Args:
            raw_text: 解析后的原始文本。

        Returns:
            str: 清洗后的文本。
        """
        # 去除控制字符（保留 \n \t）
        text = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]", "", raw_text)
        # 多个空行压缩为单个
        text = re.sub(r"\n{3,}", "\n\n", text)
        # 行尾空格
        text = re.sub(r"[ \t]+\n", "\n", text)
        # 连续空格压缩
        text = re.sub(r"[ ]{2,}", " ", text)
        return text.strip()

    @staticmethod
    def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
        """使用 RecursiveCharacterTextSplitter 递归分块。

        Args:
            text: 待分块文本。
            chunk_size: 单块最大字符数。
            overlap: 块间重叠字符数。

        Returns:
            list[str]: 分块结果列表。
        """
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "langchain-text-splitters 未安装，请执行 `pip install langchain-text-splitters`"
            ) from e

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            separators=["\n\n", "\n", "。", "！", "？", "；", " ", ""],
            keep_separator=True,
        )
        return splitter.split_text(text)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """粗略估算 token 数（4 字符 ≈ 1 token，下限 1）。

        Args:
            text: 文本内容。

        Returns:
            int: token 估计值。
        """
        return max(1, len(text) // 4)

    async def _batch_embed_safe(
        self, texts: list[str], batch_size: int = 16
    ) -> list[list[float]]:
        """分批调用 embedding_client.batch_embed，避免单次请求过大。

        Args:
            texts: 待向量化的文本列表。
            batch_size: 单批最大文本数。

        Returns:
            list[list[float]]: 与 texts 顺序一致的向量列表。
        """
        all_vectors: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            vectors = await embedding_client.batch_embed(batch)
            all_vectors.extend(vectors)
        return all_vectors

    async def _insert_to_milvus(
        self,
        doc_id: str,
        category: Optional[str],
        chunk_meta: list[dict],
        embeddings: list[list[float]],
    ) -> None:
        """将 chunks 与向量写入 Milvus。

        Args:
            doc_id: 文档 ID。
            category: 文档分类。
            chunk_meta: chunk 元数据列表（含 chunk_id / content）。
            embeddings: 与 chunk_meta 顺序一致的向量列表。

        Returns:
            None: Milvus 不可用时仅告警，不阻塞 MySQL 入库。
        """
        client = milvus_client.get_client()
        if client is None:
            logger.warning("Milvus unavailable, skip vector insert (doc=%s)", doc_id)
            return

        records = []
        for m, vec in zip(chunk_meta, embeddings):
            records.append(
                {
                    "chunk_id": m["chunk_id"],
                    "doc_id": doc_id,
                    "content": m["content"][:8000],  # Milvus content 上限 8192
                    "embedding": vec,
                    "category": category or "",
                }
            )

        try:
            client.insert(
                collection_name=settings.MILVUS_COLLECTION,
                data=records,
            )
            logger.info("Milvus inserted %d vectors for doc %s", len(records), doc_id)
        except Exception as e:
            logger.error("Milvus insert failed (doc=%s): %s", doc_id, e)
            # 不抛错：MySQL chunks 仍可入库（关键词检索可用），向量检索自动降级

    @staticmethod
    async def _get_doc(session: AsyncSession, doc_id: str) -> Optional[KnowledgeDoc]:
        """在指定 session 中查询 doc。

        Args:
            session: AsyncSession 实例。
            doc_id: 文档 ID。

        Returns:
            Optional[KnowledgeDoc]
        """
        stmt = select(KnowledgeDoc).where(KnowledgeDoc.doc_id == doc_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def _update_status(
        session: AsyncSession, doc_id: str, status: str
    ) -> None:
        """更新文档状态（不提交，由调用方控制事务）。

        Args:
            session: AsyncSession 实例。
            doc_id: 文档 ID。
            status: 目标状态。

        Returns:
            None
        """
        stmt = select(KnowledgeDoc).where(KnowledgeDoc.doc_id == doc_id)
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()
        if doc is not None:
            doc.status = status

    @staticmethod
    async def _mark_failed(doc_id: str, error_msg: str) -> None:
        """将文档标记为 failed 并写入 error_msg（使用独立 session）。

        Args:
            doc_id: 文档 ID。
            error_msg: 失败原因。

        Returns:
            None
        """
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(KnowledgeDoc).where(KnowledgeDoc.doc_id == doc_id)
                result = await session.execute(stmt)
                doc = result.scalar_one_or_none()
                if doc is not None:
                    doc.status = "failed"
                    doc.error_msg = error_msg[:1000]  # 截断防止超长
                    await session.commit()
        except Exception as e:  # pragma: no cover
            logger.error("Mark doc %s failed error: %s", doc_id, e)
