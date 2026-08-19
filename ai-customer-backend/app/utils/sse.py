"""SSE 响应构建工具。

SSE 事件格式：`event: {type}\ndata: {json}\n\n`（必须以双换行结尾）。
"""

import json
import logging
from typing import AsyncGenerator

from app.schemas.chat import SSEEvent

logger = logging.getLogger(__name__)


def sse_pack(event: SSEEvent) -> bytes:
    """将 SSEEvent 序列化为 SSE 协议帧。

    输出格式：
        event: answer
        data: {"type":"answer","content":"你好"}

    注意：必须以 ``\\n\\n`` 结尾，否则前端无法正确分割事件。
    """
    payload = event.model_dump(exclude_none=True)
    data_line = json.dumps(payload, ensure_ascii=False)
    frame = f"event: {event.type}\ndata: {data_line}\n\n"
    return frame.encode("utf-8")


def sse_pack_raw(event_type: str, data: dict) -> bytes:
    """直接按 type + dict 序列化（避免频繁构造 SSEEvent）。"""
    data_line = json.dumps(data, ensure_ascii=False)
    frame = f"event: {event_type}\ndata: {data_line}\n\n"
    return frame.encode("utf-8")


async def sse_stream(async_iter: AsyncGenerator[SSEEvent, None]) -> AsyncGenerator[bytes, None]:
    """包装异步生成器，逐 pack 流式输出。"""
    try:
        async for event in async_iter:
            yield sse_pack(event)
    except Exception as e:  # pragma: no cover
        logger.exception("SSE stream wrapper failed: %s", e)
        err = SSEEvent(type="error", message="流式生成异常，请稍后重试")
        yield sse_pack(err)


def make_answer_event(content: str) -> SSEEvent:
    return SSEEvent(type="answer", content=content)


def make_source_event(sources: list[dict]) -> SSEEvent:
    return SSEEvent(type="source", sources=sources)  # type: ignore[arg-type]


def make_fallback_event(data: dict) -> SSEEvent:
    return SSEEvent(type="fallback", data=data)


def make_done_event(message_id: str | None = None) -> SSEEvent:
    return SSEEvent(type="done", data={"message_id": message_id} if message_id else None)


def make_error_event(message: str) -> SSEEvent:
    return SSEEvent(type="error", message=message)
