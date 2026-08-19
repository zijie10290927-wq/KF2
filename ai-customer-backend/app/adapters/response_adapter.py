"""ResponseAdapter — SSE 事件 → 平台响应格式转换器。

职责：
1. 将 Agent SSE 事件流（answer/source/fallback/done/error）合并为纯文本回答
2. 提供给 Webhook 适配器使用，便于一次性 send_reply 推送
3. 提供 OpenAI 兼容 SSE chunk 格式转换

设计要点：
- 仅做事件收集与格式转换，不调用任何业务服务
- 与 ChatService.handle_message_stream 解耦
"""

import logging
import time
import uuid
from typing import Any, AsyncGenerator, Optional

from app.schemas.chat import SSEEvent, SourceItem

logger = logging.getLogger(__name__)


class CollectedResponse:
    """收集后的完整响应。"""

    def __init__(self) -> None:
        self.answer: str = ""
        self.sources: list[dict] = []
        self.fallback: Optional[dict] = None
        self.message_id: Optional[str] = None
        self.error: Optional[str] = None
        self.intent: Optional[str] = None

    def to_dict(self) -> dict:
        """转为 dict 供调用方使用。

        Returns:
            dict: 包含 answer/sources/fallback/message_id/error 字段。
        """
        return {
            "answer": self.answer,
            "sources": self.sources,
            "fallback": self.fallback,
            "message_id": self.message_id,
            "error": self.error,
            "intent": self.intent,
        }


async def collect_stream_response(
    stream: AsyncGenerator[SSEEvent, None],
) -> CollectedResponse:
    """收集 SSE 事件流为完整响应对象。

    Args:
        stream: SSEEvent 异步生成器（来自 ChatService.handle_message_stream）。

    Returns:
        CollectedResponse: 收集后的完整响应。
    """
    collected = CollectedResponse()
    try:
        async for event in stream:
            if event.type == "answer" and event.content:
                collected.answer += event.content
            elif event.type == "source" and event.sources:
                collected.sources = [
                    s.model_dump() if isinstance(s, SourceItem) else s
                    for s in event.sources
                ]
            elif event.type == "fallback" and event.data:
                collected.fallback = event.data
            elif event.type == "done" and event.data:
                collected.message_id = event.data.get("message_id")
            elif event.type == "error" and event.message:
                collected.error = event.message
    except Exception as e:
        logger.error("Collect stream response failed: %s", e)
        collected.error = str(e)
    return collected


def make_openai_chunk(
    content: str,
    model: str = "ai-customer-agent",
    completion_id: Optional[str] = None,
    finish_reason: Optional[str] = None,
) -> dict:
    """构造 OpenAI 兼容 SSE chunk。

    Args:
        content: 当前 chunk 内容。
        model: 模型名（默认 ai-customer-agent）。
        completion_id: 补全 ID；不传自动生成。
        finish_reason: 结束原因（null / stop）。

    Returns:
        dict: OpenAI chat.completion.chunk 对象。
    """
    return {
        "id": completion_id or f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"content": content} if content else {},
                "finish_reason": finish_reason,
            }
        ],
    }


def make_openai_completion(
    answer: str,
    model: str = "ai-customer-agent",
    completion_id: Optional[str] = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> dict:
    """构造 OpenAI 兼容非流式响应。

    Args:
        answer: 完整回答文本。
        model: 模型名。
        completion_id: 补全 ID。
        prompt_tokens: prompt token 数（可选）。
        completion_tokens: 补全 token 数（可选）。

    Returns:
        dict: OpenAI chat.completion 对象。
    """
    return {
        "id": completion_id or f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def sse_data_line(data: Any) -> str:
    """构造 SSE data 行（OpenAI 风格：data: {json}\\n\\n）。

    Args:
        data: 可序列化对象。

    Returns:
        str: SSE 文本块。
    """
    import json

    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def sse_done_line() -> str:
    """构造 OpenAI SSE 结束标记。"""
    return "data: [DONE]\n\n"
