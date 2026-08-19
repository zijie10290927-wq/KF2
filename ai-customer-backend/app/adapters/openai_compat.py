"""OpenAI 兼容端点 — /api/v1/openai。

职责：反向暴露 OpenAI 兼容的 /v1/chat/completions 端点，
使 Dify / FastGPT / Chatwoot 等支持 OpenAI API 的系统可直接对接。

核心接口：
- POST /openai/chat/completions   OpenAI 兼容对话接口（支持流式与非流式）

鉴权：X-API-Key 头或 Authorization: Bearer {key}，比对 OPENAI_COMPAT_API_KEY
"""

import logging
import time
import uuid
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from app.adapters.response_adapter import (
    collect_stream_response,
    make_openai_chunk,
    sse_data_line,
    sse_done_line,
)
from app.config.database import AsyncSessionLocal
from app.config.settings import settings
from app.schemas.webhook import OpenAIChatRequest
from app.services.chat_service import ChatService
from app.services.config_service import ConfigService
from app.services.intent_service import IntentService
from app.services.llm_service import LLMService
from app.services.memory_service import MemoryService
from app.services.rag_service import RAGService
from app.schemas.chat import SSEEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/openai", tags=["渠道适配-OpenAI兼容"])


def _extract_api_key(
    x_api_key: Optional[str], authorization: Optional[str]
) -> str:
    """从请求头提取 API Key。

    Args:
        x_api_key: X-API-Key 头。
        authorization: Authorization 头。

    Returns:
        str: API Key；不存在返回空字符串。
    """
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def _verify_api_key(api_key: str) -> bool:
    """验证 API Key。

    Args:
        api_key: 待验证的 key。

    Returns:
        bool: 是否合法。
    """
    expected = settings.OPENAI_COMPAT_API_KEY
    if not expected:
        logger.warning("OPENAI_COMPAT_API_KEY not configured, skip verification")
        return True
    if not api_key:
        return False
    # 简单字符串比较（key 一般足够长，时序攻击风险低）
    return api_key == expected


async def _build_chat_service() -> ChatService:
    """构建独立 ChatService（独立 session + 完整依赖链）。"""
    db = AsyncSessionLocal()
    config_service = ConfigService(db)
    llm_service = LLMService(config_service=config_service)
    intent_service = IntentService(llm_service=llm_service)
    rag_service = RAGService(
        db=db, config_service=config_service, llm_service=llm_service
    )
    memory_service = MemoryService(db)
    return ChatService(
        db=db,
        intent_service=intent_service,
        rag_service=rag_service,
        llm_service=llm_service,
        memory_service=memory_service,
        config_service=config_service,
    )


@router.post("/chat/completions", summary="OpenAI 兼容对话接口")
async def openai_chat_completions(
    req: OpenAIChatRequest,
    request: Request,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    authorization: Optional[str] = Header(default=None),
):
    """OpenAI 兼容对话接口。

    流程：
    1. 验证 API Key（X-API-Key 或 Authorization: Bearer）
    2. 提取最后一条 user 消息作为输入
    3. 从 req.metadata.session_id 复用或生成新 session_id
    4. stream=True → SSE 流式返回 OpenAI chunk
       stream=False → 一次性返回 OpenAI chat.completion
    """
    # Step 1: 启用检查 + 鉴权
    if not settings.OPENAI_COMPAT_ENABLED:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=503,
            content={
                "error": {"message": "OpenAI 兼容端点未启用", "type": "service_unavailable"},
            },
        )

    api_key = _extract_api_key(x_api_key, authorization)
    if not _verify_api_key(api_key):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "message": "Invalid API key",
                    "type": "invalid_request_error",
                    "code": "invalid_api_key",
                }
            },
        )

    # Step 2: 提取最后一条 user 消息
    user_message = ""
    history: list[dict] = []
    for msg in req.messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if not content:
            continue
        if role == "user":
            user_message = content
        history.append({"role": role, "content": content})

    if not user_message:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=400,
            content={
                "error": {"message": "messages 中无 user 消息", "type": "invalid_request_error"},
            },
        )

    # Step 3: 解析 session_id
    session_id: Optional[str] = None
    if req.metadata and isinstance(req.metadata, dict):
        session_id = req.metadata.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    model_name = req.model or "ai-customer-agent"

    # Step 4: 分流处理
    chat_service = await _build_chat_service()
    try:
        if req.stream:
            return StreamingResponse(
                _stream_openai_format(
                    chat_service=chat_service,
                    session_id=session_id,
                    message=user_message,
                    history=history[:-1] if len(history) > 1 else [],
                    completion_id=completion_id,
                    created=created,
                    model_name=model_name,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            # 非流式：收集后一次性返回
            stream = chat_service.handle_message_stream(
                session_id=session_id,
                message=user_message,
                history=history[:-1] if len(history) > 1 else [],
            )
            collected = await collect_stream_response(stream)
            answer = collected.answer or collected.error or ""

            from app.adapters.response_adapter import make_openai_completion

            completion = make_openai_completion(
                answer=answer,
                model=model_name,
                completion_id=completion_id,
                completion_tokens=len(answer) // 4,  # 粗略估算
            )
            return completion
    finally:
        # 关闭独立 db session
        try:
            await chat_service.db.close()
        except Exception:  # pragma: no cover
            pass


async def _stream_openai_format(
    chat_service: ChatService,
    session_id: str,
    message: str,
    history: list[dict],
    completion_id: str,
    created: int,
    model_name: str,
) -> AsyncGenerator[str, None]:
    """将 ChatService SSE 事件流转为 OpenAI 兼容 chunk。

    Args:
        chat_service: ChatService 实例。
        session_id: 内部会话 ID。
        message: 用户消息。
        history: 历史消息列表（不含当前消息）。
        completion_id: 补全 ID。
        created: 创建时间戳。
        model_name: 模型名。

    Yields:
        str: OpenAI SSE 格式文本块。
    """
    try:
        async for event in chat_service.handle_message_stream(
            session_id=session_id,
            message=message,
            history=history,
        ):
            if event.type == "answer" and event.content:
                chunk = make_openai_chunk(
                    content=event.content,
                    model=model_name,
                    completion_id=completion_id,
                )
                yield sse_data_line(chunk)
            elif event.type == "fallback" and event.data:
                # fallback 拼接为文本（OpenAI 协议无 fallback 字段）
                fb = event.data
                fb_text = ""
                if fb.get("show_transfer"):
                    fb_text += "\n\n如需进一步帮助，请输入「转人工」"
                if fb.get("show_phone"):
                    fb_text += f"\n或拨打客服电话：{fb.get('phone', '')}"
                if fb_text:
                    chunk = make_openai_chunk(
                        content=fb_text,
                        model=model_name,
                        completion_id=completion_id,
                    )
                    yield sse_data_line(chunk)
            elif event.type == "error" and event.message:
                # 错误也以 chunk 形式输出（保持流式语义）
                chunk = make_openai_chunk(
                    content=f"\n\n[error: {event.message}]",
                    model=model_name,
                    completion_id=completion_id,
                )
                yield sse_data_line(chunk)
            # source/done 事件对 OpenAI 协议无意义，跳过
        # 结束标记
        end_chunk = make_openai_chunk(
            content="",
            model=model_name,
            completion_id=completion_id,
            finish_reason="stop",
        )
        yield sse_data_line(end_chunk)
        yield sse_done_line()
    except Exception as e:
        logger.exception("OpenAI stream failed: %s", e)
        err_chunk = make_openai_chunk(
            content="\n\n[生成回答时出错，请稍后重试]",
            model=model_name,
            completion_id=completion_id,
        )
        yield sse_data_line(err_chunk)
        yield sse_done_line()
