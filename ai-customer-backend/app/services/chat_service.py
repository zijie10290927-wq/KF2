"""ChatService — 对话编排服务 (核心调度)。

串联：意图识别 → RAG 检索 → LLM 生成 → 兜底引导 → 记忆存储 的完整编排。

关键：在 finally 块中执行 Redis+MySQL 双写时，使用独立的 AsyncSession，
避免主会话提前关闭导致写入失败（异步上下文泄漏）。
"""

import logging
import uuid
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import AsyncSessionLocal
from app.config.settings import settings
from app.schemas.chat import SSEEvent, SourceItem
from app.services.config_service import ConfigService
from app.services.intent_service import IntentResult, IntentService
from app.services.llm_service import LLMService
from app.services.memory_service import MemoryService
from app.services.rag_service import RAGService
from app.utils.sse import (
    make_answer_event,
    make_done_event,
    make_error_event,
    make_fallback_event,
    make_source_event,
)

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """你是一个AI出图产品的智能客服助手。请根据以下知识库内容回答用户问题。
如果知识库内容不足以回答，请基于你的知识给出合理回答，但要注明"仅供参考"。
回答要简洁、专业、友好，使用 Markdown 格式。

【知识库内容】
{context}
【结束】
"""

AMBIGUOUS_PROMPT = """您好！我不太确定您的问题。您是想咨询AI出图产品的相关问题吗？
您可以尝试这样提问：
• "如何生成一张水墨风格的山水画？"
• "图片分辨率最高支持多少？"
• "提示词怎么写效果更好？"
如果以上都不是您想问的，您可以转人工客服或拨打 {phone}。"""


class ChatService:
    """对话编排服务：核心调度。"""

    def __init__(
        self,
        db: AsyncSession,
        intent_service: IntentService,
        rag_service: RAGService,
        llm_service: LLMService,
        memory_service: MemoryService,
        config_service: ConfigService,
    ) -> None:
        self.db = db
        self.intent_service = intent_service
        self.rag_service = rag_service
        self.llm_service = llm_service
        self.memory_service = memory_service
        self.config_service = config_service

    # ------------------------------------------------------------------ #
    # 主流程：流式对话
    # ------------------------------------------------------------------ #
    async def handle_message_stream(
        self,
        session_id: str,
        message: str,
        history: Optional[list[dict]] = None,
        user_id: Optional[int] = None,
    ) -> AsyncGenerator[SSEEvent, None]:
        """完整流式处理流程，yield SSEEvent。

        执行步骤：
        1. 意图识别
        2. 分支：off_topic → 兜底；ambiguous → 澄清；product_qa → 继续
        3. RAG 检索 + 上下文拼接
        4. 加载 Redis 短期历史
        5. 组装 Prompt
        6. SSE 下发 source 事件
        7. LLM 流式生成 → answer 事件
        8. SSE 下发 done 事件
        9. finally: 双写存储（独立 session，始终至少保存用户消息）
        """
        user_message_id = str(uuid.uuid4())
        assistant_message_id = str(uuid.uuid4())
        full_answer_parts: list[str] = []
        sources_for_persist: list[dict] = []
        intent_for_persist: Optional[str] = None
        model_used: Optional[str] = None
        error_occurred = False

        try:
            # Step 1: 意图识别
            intent_result = await self.intent_service.classify(message, history or [])
            intent_for_persist = intent_result.intent
            logger.info(
                "Intent: %s conf=%.2f source=%s (session=%s)",
                intent_result.intent,
                intent_result.confidence,
                intent_result.source,
                session_id,
            )

            # Step 2: 意图分支
            if intent_result.intent == "off_topic":
                fallback_cfg = await self.config_service.get_fallback_message()
                yield make_answer_event(fallback_cfg.fallback_message)
                full_answer_parts.append(fallback_cfg.fallback_message)
                yield make_fallback_event(
                    {
                        "show_transfer": fallback_cfg.show_transfer_button,
                        "show_phone": fallback_cfg.show_phone,
                        "phone": fallback_cfg.phone_number,
                    }
                )
                yield make_done_event(message_id=assistant_message_id)
                return

            if intent_result.intent == "ambiguous":
                fallback_cfg = await self.config_service.get_fallback_message()
                clarify = AMBIGUOUS_PROMPT.format(phone=fallback_cfg.phone_number)
                yield make_answer_event(clarify)
                full_answer_parts.append(clarify)
                yield make_done_event(message_id=assistant_message_id)
                return

            # product_qa 分支：继续完整 RAG + LLM 流程
            # Step 3: RAG 检索
            retrieval_results = await self.rag_service.retrieve(message)
            context = await self.rag_service.build_context(retrieval_results)

            # 准备 source 事件数据
            sources_for_event: list[SourceItem] = []
            for r in retrieval_results[:5]:
                sources_for_persist.append(
                    {
                        "title": f"知识片段-{r.chunk_id[:8]}",
                        "score": round(r.score, 4),
                        "snippet": r.content[:200],
                    }
                )
                sources_for_event.append(
                    SourceItem(
                        title=f"知识片段-{r.chunk_id[:8]}",
                        score=round(r.score, 4),
                        snippet=r.content[:200],
                    )
                )

            # Step 4: 加载 Redis 短期历史
            redis_history = await self.memory_service.get_history(session_id)

            # Step 5: 组装消息列表
            chat_messages: list[dict] = []
            for h in redis_history[-10:]:
                role = h.get("role", "user")
                content = h.get("content", "")
                if role in ("user", "assistant") and content:
                    chat_messages.append({"role": role, "content": content})
            chat_messages.append({"role": "user", "content": message})

            system_prompt = SYSTEM_PROMPT.format(context=context)

            # Step 6: 先下发 source 事件
            if sources_for_event:
                yield make_source_event([s.model_dump() for s in sources_for_event])

            # Step 7: LLM 流式生成 → answer 事件
            try:
                stream = await self.llm_service.generate(
                    messages=chat_messages,
                    system_prompt=system_prompt,
                    stream=True,
                )
                # 尝试获取 model_name（从 LLMService 缓存的配置中）
                try:
                    res = await self.llm_service.get_client()
                    # 兼容新版 3 元组返回 (client, cfg, use_mock) 和旧版 2 元组
                    if len(res) >= 2:
                        cfg = res[1]
                        model_used = cfg.get("model_name")
                except Exception:
                    pass

                async for token in stream:
                    if token:
                        full_answer_parts.append(token)
                        yield make_answer_event(token)
            except Exception as e:
                logger.error("LLM stream failed: %s", e)
                error_occurred = True
                yield make_error_event(f"生成回答时出错: {e}")
                # 即使出错，也保存已生成的部分回答（如果有）
                return

            # Step 8: done 事件
            yield make_done_event(message_id=assistant_message_id)

        except Exception as e:
            logger.exception("ChatService stream failed")
            error_occurred = True
            yield make_error_event(f"处理失败: {e}")

        finally:
            # Step 9: 双写存储（使用独立 AsyncSession 防止主会话关闭导致写入失败）
            # 始终保存用户消息 + AI 回答（即使出错，只要有已生成内容就保存）
            try:
                await self._persist_messages(
                    session_id=session_id,
                    user_message_id=user_message_id,
                    assistant_message_id=assistant_message_id,
                    user_message=message,
                    assistant_answer="".join(full_answer_parts),
                    intent=intent_for_persist,
                    sources=sources_for_persist if sources_for_persist else None,
                    model_used=model_used,
                )
            except Exception as e:
                logger.error("Persist messages failed: %s", e)

    # ------------------------------------------------------------------ #
    # 双写存储（独立 session）
    # ------------------------------------------------------------------ #
    async def _persist_messages(
        self,
        session_id: str,
        user_message_id: str,
        assistant_message_id: str,
        user_message: str,
        assistant_answer: str,
        intent: Optional[str],
        sources: Optional[list[dict]],
        model_used: Optional[str],
    ) -> None:
        """使用独立 AsyncSession 执行 Redis+MySQL 双写，避免主会话提前关闭。

        始终保存用户消息；AI 回答为空时跳过（但不影响用户消息持久化）。
        """
        async with AsyncSessionLocal() as new_db:
            memory = MemoryService(new_db)
            # 1. 用户消息（始终保存）
            await memory.save_message(
                session_id=session_id,
                role="user",
                content=user_message,
                message_id=user_message_id,
            )
            # 2. AI 回答（有内容才保存）
            if assistant_answer.strip():
                await memory.save_message(
                    session_id=session_id,
                    role="assistant",
                    content=assistant_answer,
                    message_id=assistant_message_id,
                    intent=intent,
                    sources=sources,
                    model_used=model_used,
                )

    # ------------------------------------------------------------------ #
    # 同步处理入口（供渠道适配层 P2 使用）
    # ------------------------------------------------------------------ #
    async def handle_message_sync(
        self,
        session_id: str,
        message: str,
        history: Optional[list[dict]] = None,
    ) -> dict:
        """非流式处理：收集所有 token 拼接为完整回答返回。

        供渠道适配层（Webhook / OpenAI 兼容端点）调用。
        """
        full_answer: list[str] = []
        sources: list[dict] = []
        fallback_data: Optional[dict] = None
        message_id: Optional[str] = None
        error_msg: Optional[str] = None

        async for event in self.handle_message_stream(
            session_id=session_id, message=message, history=history
        ):
            if event.type == "answer" and event.content:
                full_answer.append(event.content)
            elif event.type == "source" and event.sources:
                sources = [s.model_dump() if isinstance(s, SourceItem) else s for s in event.sources]
            elif event.type == "fallback" and event.data:
                fallback_data = event.data
            elif event.type == "done" and event.data:
                message_id = event.data.get("message_id")
            elif event.type == "error" and event.message:
                error_msg = event.message

        return {
            "answer": "".join(full_answer),
            "sources": sources,
            "fallback": fallback_data,
            "message_id": message_id,
            "error": error_msg,
        }
