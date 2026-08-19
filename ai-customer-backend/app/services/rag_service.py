"""RAGService — RAG 知识库检索服务。

知识库语义检索 + 上下文拼接 + 可选混合检索 / Query 改写 / Re-ranking。
"""

import hashlib
import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.milvus import milvus_client
from app.config.settings import settings
from app.models import KnowledgeChunk, KnowledgeDoc

if TYPE_CHECKING:  # pragma: no cover
    from app.services.config_service import ConfigService
    from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


# -------- Mock Embedding：确定性伪随机向量 --------
def _mock_embed_single(text: str, dim: int) -> list[float]:
    """基于 MD5 哈希种子生成确定性单位向量（mock 向量）。

    相同文本返回相同向量（可检索），向量归一化到 L2=1，便于 COSINE 距离计算。
    """
    seed = hashlib.md5(text.encode("utf-8")).digest()
    # 使用 8 个 uint32 作为基础种子
    seed_ints = [int.from_bytes(seed[i : i + 4], "little", signed=False) for i in range(0, 16, 4)]
    vec: list[float] = []
    state = seed_ints.copy()
    for i in range(dim):
        # xorshift32 变体
        s = state[i % len(state)]
        s ^= s << 13
        s ^= s >> 17
        s ^= s << 5
        state[i % len(state)] = s & 0xFFFFFFFF
        # 映射到 (-1, 1)
        v = (s & 0xFFFFFFFF) / 0xFFFFFFFF * 2.0 - 1.0
        # 叠加字符权重（让相似文本产生相似向量）
        if i < len(text):
            v += ord(text[i]) / 65536.0
        vec.append(v)
    # L2 归一化
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


@dataclass
class RetrievalResult:
    """单条检索结果。"""

    chunk_id: str
    doc_id: str
    content: str
    score: float
    category: Optional[str] = None
    source: str = "vector"  # vector / keyword / fused


class EmbeddingClient:
    """Embedding 客户端：调用 OpenAI 兼容的 embedding 接口。

    降级策略：
    - 当 API Key 为占位符 / 长度不足 / 调用失败时，
      自动切换到本地 mock 向量化（确定性伪随机向量），保证 Milvus、RAG、
      知识库上传流水线都能正常运行。
    """

    def __init__(self) -> None:
        self._client: Any = None
        self._force_mock: bool = False

    def _should_mock(self) -> bool:
        key = (settings.EMBEDDING_API_KEY or "").strip().lower()
        bad = ("sk-your-", "your-api-key", "please-change", "sk-xxxxxxxx", "sk-test")
        return self._force_mock or any(p in key for p in bad) or len(key) < 10

    async def _get_client(self) -> Any:
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=settings.EMBEDDING_API_KEY or "empty",
                base_url=settings.EMBEDDING_API_BASE,
            )
        return self._client

    async def embed(self, text: str) -> list[float]:
        """单条文本向量化。API Key 无效或调用失败时走 mock。"""
        if self._should_mock():
            if not self._force_mock:
                logger.info("Embedding use mock mode (placeholder API key detected)")
            return _mock_embed_single(text, settings.EMBEDDING_DIM)
        try:
            client = await self._get_client()
            resp = await client.embeddings.create(
                input=text,
                model=settings.EMBEDDING_MODEL,
                dimensions=settings.EMBEDDING_DIM,
            )
            return list(resp.data[0].embedding)
        except Exception as e:
            logger.error("Embedding failed: %s — fallback to mock", e)
            self._force_mock = True
            return _mock_embed_single(text, settings.EMBEDDING_DIM)

    async def batch_embed(self, texts: list[str]) -> list[list[float]]:
        """批量向量化。"""
        if not texts:
            return []
        if self._should_mock():
            if not self._force_mock:
                logger.info("Embedding batch use mock mode (placeholder API key detected)")
            return [_mock_embed_single(t, settings.EMBEDDING_DIM) for t in texts]
        try:
            client = await self._get_client()
            resp = await client.embeddings.create(
                input=texts,
                model=settings.EMBEDDING_MODEL,
                dimensions=settings.EMBEDDING_DIM,
            )
            sorted_data = sorted(resp.data, key=lambda x: x.index)
            return [list(d.embedding) for d in sorted_data]
        except Exception as e:
            logger.error("Batch embedding failed: %s — fallback to mock", e)
            self._force_mock = True
            return [_mock_embed_single(t, settings.EMBEDDING_DIM) for t in texts]


# 全局 embedding 单例
embedding_client = EmbeddingClient()


class RAGService:
    """RAG 检索服务。"""

    def __init__(
        self,
        db: AsyncSession,
        config_service: "Optional[ConfigService]" = None,
        llm_service: "Optional[LLMService]" = None,
    ) -> None:
        self.db = db
        self.config_service = config_service
        self.llm_service = llm_service

    # ------------------------------------------------------------------ #
    # 主检索入口
    # ------------------------------------------------------------------ #
    async def retrieve(
        self, query: str, top_k: Optional[int] = None
    ) -> list[RetrievalResult]:
        """主检索：Query 改写 → 向量化 → 混合检索 → RRF 融合 → 低分过滤 → Re-rank。"""
        if not query.strip():
            return []

        top_k = top_k or await self._get_top_k()
        threshold = await self._get_score_threshold()
        use_hybrid = await self._get_bool("rag_hybrid_search", True)
        use_rewrite = await self._get_bool("rag_query_rewrite", True)

        # 1. Query 改写（可选）
        queries = [query]
        if use_rewrite and self.llm_service is not None:
            try:
                rewritten = await self._rewrite_query(query)
                queries.extend(rewritten)
                # 去重保序
                seen = set()
                queries = [q for q in queries if not (q in seen or seen.add(q))]
            except Exception as e:
                logger.warning("Query rewrite failed: %s", e)

        # 2. 向量化主查询
        try:
            query_embedding = await embedding_client.embed(queries[0])
        except Exception as e:
            logger.error("Embed query failed: %s", e)
            return []

        # 3. 向量检索
        vector_results = await self._vector_search(query_embedding, top_k * 2)

        # 4. 关键词检索（可选混合）
        keyword_results: list[RetrievalResult] = []
        if use_hybrid:
            keyword_results = await self._keyword_search(query, top_k * 2)

        # 5. RRF 融合
        if use_hybrid and keyword_results:
            fused = self._rrf_fusion(vector_results, keyword_results, k=60)
        else:
            fused = vector_results

        # 6. 低分过滤
        filtered = [r for r in fused if r.score >= threshold]

        # 7. 截断到 top_k
        result = filtered[:top_k]

        # 8. Re-rank（P1 预留，当前直接返回）
        # result = await self._rerank(query, result, top_k)

        return result

    async def build_context(self, results: list[RetrievalResult]) -> str:
        """将检索结果拼接为 LLM 可读的上下文字符串。"""
        if not results:
            return "（暂无相关知识库内容）"
        parts: list[str] = []
        for idx, r in enumerate(results, 1):
            parts.append(f"[来源{idx}] {r.content}")
        return "\n\n".join(parts)

    # ------------------------------------------------------------------ #
    # 向量检索
    # ------------------------------------------------------------------ #
    async def _vector_search(
        self, query_embedding: list[float], top_k: int
    ) -> list[RetrievalResult]:
        """Milvus 向量检索，metric_type=COSINE。"""
        client = milvus_client.get_client()
        if client is None:
            logger.warning("Milvus unavailable, vector search skipped")
            return []
        try:
            results = client.search(
                collection_name=settings.MILVUS_COLLECTION,
                data=[query_embedding],
                limit=top_k,
                output_fields=["chunk_id", "doc_id", "content", "category"],
                search_params={"metric_type": "COSINE"},
            )
            # results 是 list[list[Hit]]，取第一个 query 的结果
            if not results:
                return []
            hits = results[0]
            out: list[RetrievalResult] = []
            for hit in hits:
                entity = hit.get("entity", {}) if isinstance(hit, dict) else {}
                score = hit.get("distance", 0.0) if isinstance(hit, dict) else getattr(hit, "distance", 0.0)
                # Milvus COSINE 距离可能需要转换为相似度
                score = float(score) if score <= 1.0 else 1.0 - float(score) / 100
                out.append(
                    RetrievalResult(
                        chunk_id=entity.get("chunk_id", ""),
                        doc_id=entity.get("doc_id", ""),
                        content=entity.get("content", ""),
                        score=score,
                        category=entity.get("category"),
                        source="vector",
                    )
                )
            return out
        except Exception as e:
            logger.error("Milvus search failed: %s", e)
            return []

    # ------------------------------------------------------------------ #
    # 关键词检索（MySQL LIKE 模糊匹配）
    # ------------------------------------------------------------------ #
    async def _keyword_search(
        self, query: str, top_k: int
    ) -> list[RetrievalResult]:
        """MySQL LIKE 模糊匹配（轻量级关键词检索）。"""
        # 提取关键词（简单分词：按空格 + 中文字符）
        keywords = [w.strip() for w in query.split() if w.strip()]
        if not keywords:
            # 中文：取前 8 个字符作为关键词
            keywords = [query[:8]]

        try:
            conditions = []
            for kw in keywords:
                conditions.append(KnowledgeChunk.content.like(f"%{kw}%"))
            stmt = (
                select(KnowledgeChunk)
                .where(or_(*conditions))
                .limit(top_k)
            )
            result = await self.db.execute(stmt)
            chunks = result.scalars().all()

            out: list[RetrievalResult] = []
            for chunk in chunks:
                # 简单评分：命中关键词数 / 总关键词数
                hit_count = sum(1 for kw in keywords if kw in chunk.content)
                score = hit_count / max(len(keywords), 1) * 0.8  # 关键词分上限 0.8
                out.append(
                    RetrievalResult(
                        chunk_id=chunk.chunk_id,
                        doc_id=chunk.doc_id,
                        content=chunk.content,
                        score=score,
                        source="keyword",
                    )
                )
            return out
        except Exception as e:
            logger.error("Keyword search failed: %s", e)
            return []

    # ------------------------------------------------------------------ #
    # RRF 融合
    # ------------------------------------------------------------------ #
    @staticmethod
    def _rrf_fusion(*result_lists: list[RetrievalResult], k: int = 60) -> list[RetrievalResult]:
        """RRF (Reciprocal Rank Fusion)：score = Σ 1/(k + rank)。"""
        scores: dict[str, float] = {}
        meta: dict[str, RetrievalResult] = {}
        for lst in result_lists:
            for rank, r in enumerate(lst, 1):
                key = r.chunk_id
                scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
                if key not in meta:
                    meta[key] = r

        fused: list[RetrievalResult] = []
        for chunk_id, score in scores.items():
            r = meta[chunk_id]
            fused.append(
                RetrievalResult(
                    chunk_id=chunk_id,
                    doc_id=r.doc_id,
                    content=r.content,
                    score=score,
                    category=r.category,
                    source="fused",
                )
            )
        fused.sort(key=lambda x: x.score, reverse=True)
        return fused

    # ------------------------------------------------------------------ #
    # Query 改写
    # ------------------------------------------------------------------ #
    async def _rewrite_query(self, query: str) -> list[str]:
        """LLM Query 改写：口语化 → 标准术语，返回 1~3 个改写版本。"""
        if self.llm_service is None:
            return []
        prompt = (
            "你是查询改写助手。请将用户的口语化问题改写为 1~3 个更利于检索的标准版本。\n"
            "要求：保留原意，使用更专业的术语，每行一个改写版本，不要编号和解释。\n\n"
            f"用户问题：{query}\n改写版本："
        )
        try:
            raw = await self.llm_service.generate(
                messages=[{"role": "user", "content": prompt}],
                stream=False,
                temperature=0.3,
                max_tokens=200,
            )
            lines = [ln.strip() for ln in (raw or "").splitlines() if ln.strip()]
            return lines[:3]
        except Exception as e:
            logger.warning("Query rewrite failed: %s", e)
            return []

    # ------------------------------------------------------------------ #
    # Re-rank（P1 预留）
    # ------------------------------------------------------------------ #
    async def _rerank(
        self, query: str, candidates: list[RetrievalResult], top_k: int
    ) -> list[RetrievalResult]:
        """BGE-Reranker-v2-m3 Cross-Encoder 重排序（P1 实现，当前直接返回）。"""
        return candidates[:top_k]

    # ------------------------------------------------------------------ #
    # 配置读取辅助
    # ------------------------------------------------------------------ #
    async def _get_top_k(self) -> int:
        if self.config_service:
            return await self.config_service.get_int("rag_top_k", settings.RAG_TOP_K)
        return settings.RAG_TOP_K

    async def _get_score_threshold(self) -> float:
        if self.config_service:
            return await self.config_service.get_float(
                "rag_score_threshold", settings.RAG_SCORE_THRESHOLD
            )
        return settings.RAG_SCORE_THRESHOLD

    async def _get_bool(self, key: str, default: bool) -> bool:
        if self.config_service:
            return await self.config_service.get_bool(key, default)
        return default
