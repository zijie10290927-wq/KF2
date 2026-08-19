"""ChatService 对话编排测试。

使用桩服务（Stub）隔离外部依赖，验证：
- 意图分支流转（off_topic / ambiguous / product_qa）
- SSE 事件序列正确性
- finally 双写持久化（用户消息 + AI 回答落入测试 DB）

持久化验证通过 monkeypatch 替换 chat_service 模块的 AsyncSessionLocal，
使其指向测试引擎，不污染开发数据库。
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.services.chat_service as chat_service_module
from app.models import ChatMessage
from app.services.chat_service import ChatService
from app.services.intent_service import IntentResult


# ---------------------------------------------------------------------- #
# 桩服务
# ---------------------------------------------------------------------- #
class StubIntentService:
    def __init__(self, intent: str):
        self._intent = intent

    async def classify(self, message, history=None):
        return IntentResult(intent=self._intent, confidence=0.9, source="rule")


class StubConfigService:
    async def get_fallback_message(self):
        return SimpleNamespace(
            fallback_message="抱歉，该问题超出服务范围，为您转接人工客服。",
            show_transfer_button=True,
            show_phone=True,
            phone_number="400-888-8888",
        )


class StubRagService:
    async def retrieve(self, message):
        return []

    async def build_context(self, results):
        return ""


class StubMemoryService:
    async def get_history(self, session_id):
        return []


class StubLLMService:
    async def get_client(self, model_name=None):
        return None, {"model_name": "mock-model"}, True

    async def generate(self, messages, system_prompt=None, stream=False, **kwargs):
        async def _gen():
            for tok in ["你好", "，", "这是测试回答"]:
                yield tok

        return _gen() if stream else "你好，这是测试回答"


def make_chat_service(db, intent: str) -> ChatService:
    return ChatService(
        db=db,
        intent_service=StubIntentService(intent),
        rag_service=StubRagService(),
        llm_service=StubLLMService(),
        memory_service=StubMemoryService(),
        config_service=StubConfigService(),
    )


async def collect_events(gen):
    return [e async for e in gen]


# ---------------------------------------------------------------------- #
# 分支测试
# ---------------------------------------------------------------------- #
class TestIntentBranches:
    async def test_off_topic_branch_events(self, db_session):
        """off_topic → answer + fallback + done 三事件序列。"""
        svc = make_chat_service(db_session, "off_topic")
        events = await collect_events(
            svc.handle_message_stream("sess-test", "今天天气如何")
        )
        types = [e.type for e in events]
        assert types == ["answer", "fallback", "done"]
        assert "转人工" in events[0].content or "人工" in events[0].content
        assert events[1].data["show_transfer"] is True

    async def test_ambiguous_branch_events(self, db_session):
        """ambiguous → answer + done（澄清引导，无 fallback 卡片）。"""
        svc = make_chat_service(db_session, "ambiguous")
        events = await collect_events(svc.handle_message_stream("sess-test", ""))
        types = [e.type for e in events]
        assert types == ["answer", "done"]
        assert "400-888-8888" in events[0].content  # 澄清话术含联系电话

    async def test_product_qa_branch_events(self, db_session):
        """product_qa → answer(流式) + done。"""
        svc = make_chat_service(db_session, "product_qa")
        events = await collect_events(
            svc.handle_message_stream("sess-test", "怎么生成水墨画")
        )
        types = [e.type for e in events]
        # 空检索结果 → 无 source 事件
        assert types == ["answer", "answer", "answer", "done"]
        assert events[0].content == "你好"


# ---------------------------------------------------------------------- #
# 持久化测试（finally 双写）
# ---------------------------------------------------------------------- #
class TestPersistence:
    async def test_messages_persisted_to_db(
        self, db_session, test_session_row, monkeypatch, test_engine
    ):
        """product_qa 完成后，用户消息 + AI 回答应双写落库。"""
        # 替换 chat_service 模块内的 AsyncSessionLocal → 测试引擎
        test_factory = async_sessionmaker(
            bind=test_engine, class_=AsyncSession, expire_on_commit=False
        )
        monkeypatch.setattr(
            chat_service_module, "AsyncSessionLocal", test_factory
        )

        svc = make_chat_service(db_session, "product_qa")
        events = await collect_events(
            svc.handle_message_stream(test_session_row, "怎么生成水墨画")
        )
        assert events[-1].type == "done"

        # 独立会话查询验证落库
        async with test_factory() as verify_db:
            rows = (
                (await verify_db.execute(select(ChatMessage)))
                .scalars()
                .all()
            )
            roles = sorted(r.role for r in rows)
            assert roles == ["assistant", "user"]
            user_msg = next(r for r in rows if r.role == "user")
            assert user_msg.content == "怎么生成水墨画"
            assistant_msg = next(r for r in rows if r.role == "assistant")
            assert assistant_msg.intent == "product_qa"  # 意图记录在 AI 消息上
            assert assistant_msg.model_used == "mock-model"

    async def test_user_message_saved_even_on_llm_failure(
        self, db_session, test_session_row, monkeypatch, test_engine
    ):
        """LLM 流式失败时，用户消息仍应保存（finally 保证）。"""

        class FailingLLMService(StubLLMService):
            async def generate(self, messages, system_prompt=None, stream=False, **kw):
                raise RuntimeError("simulated LLM outage")

        test_factory = async_sessionmaker(
            bind=test_engine, class_=AsyncSession, expire_on_commit=False
        )
        monkeypatch.setattr(chat_service_module, "AsyncSessionLocal", test_factory)

        svc = ChatService(
            db=db_session,
            intent_service=StubIntentService("product_qa"),
            rag_service=StubRagService(),
            llm_service=FailingLLMService(),
            memory_service=StubMemoryService(),
            config_service=StubConfigService(),
        )
        events = await collect_events(
            svc.handle_message_stream(test_session_row, "怎么生成水墨画")
        )
        # 应收到 error 事件，且消息不含底层异常细节（回归：异常泄露修复）
        error_events = [e for e in events if e.type == "error"]
        assert len(error_events) == 1
        assert "RuntimeError" not in error_events[0].message

        async with test_factory() as verify_db:
            rows = (await verify_db.execute(select(ChatMessage))).scalars().all()
            user_rows = [r for r in rows if r.role == "user"]
            assert len(user_rows) == 1  # 用户消息已保存
