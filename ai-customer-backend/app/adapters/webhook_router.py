"""Webhook 统一路由 — /api/v1/webhook。

职责：
1. 接收第三方平台 Webhook 推送（智齿/七鱼/Udesk/Chatwoot/generic）
2. 验签 + 解析 + 防重复
3. 映射/创建内部会话
4. 立即返回 202，异步处理（background_tasks 调用 ChatService）

核心接口：
- POST /webhook/{platform}   统一 Webhook 接收入口
- GET  /webhook/health       健康检查（启用状态 + 已注册平台列表）

设计要点：
- 防重采用内存缓存 _processed_messages（message_id → 处理时间戳），TTL 5 分钟
- 异步处理用 BackgroundTasks，避免阻塞 Webhook 响应
- ChatService 通过 AsyncSessionLocal + 完整依赖链构建，独立于请求 DB session
"""

import logging
import time
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Request, Response
from fastapi.responses import JSONResponse

from app.adapters.platforms import get_adapter, list_adapters
from app.adapters.response_adapter import collect_stream_response
from app.adapters.session_mapper import session_mapper
from app.config.database import AsyncSessionLocal
from app.config.settings import settings
from app.exceptions import AdapterAuthError
from app.schemas.webhook import WebhookAck, WebhookHealth
from app.services.chat_service import ChatService
from app.services.config_service import ConfigService
from app.services.intent_service import IntentService
from app.services.llm_service import LLMService
from app.services.memory_service import MemoryService
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["渠道适配-Webhook"])

# 防重复：message_id -> 处理时间戳
_processed_messages: dict[str, float] = {}
_PROCESSED_TTL_SECONDS = 300  # 5 分钟


def _is_duplicate(message_id: str) -> bool:
    """检查 message_id 是否已处理过（含过期清理）。"""
    if not message_id:
        return False
    now = time.time()
    # 顺便清理过期项（每 100 次调用清理一次）
    if len(_processed_messages) > 1000:
        expired = [k for k, t in _processed_messages.items() if now - t > _PROCESSED_TTL_SECONDS]
        for k in expired:
            _processed_messages.pop(k, None)
    if message_id in _processed_messages:
        return True
    _processed_messages[message_id] = now
    return False


@router.get("/health", response_model=WebhookHealth, summary="Webhook 健康检查")
async def webhook_health() -> WebhookHealth:
    """返回 Webhook 启用状态 + 已注册平台列表。"""
    return WebhookHealth(enabled=settings.WEBHOOK_ENABLED, platforms=list_adapters())


@router.post("/{platform}", status_code=202, summary="统一 Webhook 接收入口")
async def receive_webhook(
    platform: str,
    request: Request,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    """接收第三方平台 Webhook 推送。

    处理流程（9 步）：
      Step 0: 检查 WEBHOOK_ENABLED，未启用返回 503
      Step 1: get_adapter(platform) 获取适配器（未注册 → 404）
      Step 2: 读取 raw_body
      Step 3: adapter.verify_signature()（失败 → 403）
      Step 4: adapter.parse_incoming()（异常 → 400）
      Step 5: parsed.skip=True → 返回 {"status": "ignored"}
      Step 6: 防重复检查（message_id）
      Step 7: session_mapper.get_or_create() 映射/创建内部会话
      Step 8: background_tasks.add_task(_process_and_reply, ...) 异步处理
      Step 9: 立即返回 202 {"status":"accepted", platform, internal_session_id}
    """
    # Step 0: 启用检查
    if not settings.WEBHOOK_ENABLED:
        return JSONResponse(
            status_code=503,
            content={"code": 503, "message": "Webhook 功能未启用", "data": None},
        )

    # Step 1: 获取适配器
    adapter = get_adapter(platform)
    if adapter is None:
        return JSONResponse(
            status_code=404,
            content={"code": 404, "message": f"未注册的平台: {platform}", "data": None},
        )

    # Step 2: 读取 raw_body
    raw_body = await request.body()

    # Step 3: 签名验证
    try:
        headers = {k: v for k, v in request.headers.items()}
        if not adapter.verify_signature(headers, raw_body):
            return JSONResponse(
                status_code=403,
                content={"code": 403, "message": "签名验证失败", "data": None},
            )
    except Exception as e:
        logger.warning("Verify signature failed (platform=%s): %s", platform, e, exc_info=True)
        return JSONResponse(
            status_code=403,
            content={"code": 403, "message": "签名验证失败", "data": None},
        )

    # Step 4: 解析消息
    try:
        parsed = adapter.parse_incoming(raw_body)
    except AdapterAuthError as e:
        return JSONResponse(
            status_code=400,
            content={"code": 400, "message": str(e), "data": None},
        )
    except Exception as e:
        logger.warning("Parse incoming failed (platform=%s): %s", platform, e, exc_info=True)
        return JSONResponse(
            status_code=400,
            content={"code": 400, "message": "消息解析失败，请检查推送格式", "data": None},
        )

    # Step 5: 跳过非消息事件
    if parsed.get("skip"):
        return JSONResponse(
            status_code=200,
            content={
                "code": 0,
                "message": "ignored",
                "data": {"status": "ignored", "reason": parsed.get("reason", "non-message event")},
            },
        )

    message_id = parsed.get("message_id") or str(uuid.uuid4())

    # Step 6: 防重复
    if _is_duplicate(message_id):
        return JSONResponse(
            status_code=200,
            content={
                "code": 0,
                "message": "duplicate",
                "data": {"status": "duplicate", "msg_id": message_id},
            },
        )

    # Step 7: 会话映射
    try:
        internal_session_id = await session_mapper.get_or_create(
            platform=adapter.platform_name,
            external_session_id=parsed["external_session_id"],
            external_user_id=parsed.get("external_user_id"),
            external_user_name=parsed.get("external_user_name"),
            channel_type=parsed.get("channel_type"),
            metadata=parsed.get("metadata"),
        )
    except Exception as e:
        logger.error("Session mapper failed: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": "会话映射失败，请稍后重试", "data": None},
        )

    # Step 8: 异步处理
    background_tasks.add_task(
        _process_and_reply,
        adapter=adapter,
        platform=adapter.platform_name,
        external_session_id=parsed["external_session_id"],
        internal_session_id=internal_session_id,
        message=parsed["message"],
        metadata=parsed.get("metadata") or {},
    )

    # Step 9: 立即返回 202
    ack = WebhookAck(
        msg_id=message_id,
        status="accepted",
        platform=adapter.platform_name,
        internal_session_id=internal_session_id,
    )
    return JSONResponse(
        status_code=202,
        content={
            "code": 0,
            "message": "accepted",
            "data": ack.model_dump(),
        },
    )


async def _process_and_reply(
    adapter,
    platform: str,
    external_session_id: str,
    internal_session_id: str,
    message: str,
    metadata: dict,
) -> None:
    """后台异步处理：调 ChatService + 推送回复（不阻塞 Webhook 响应）。

    Args:
        adapter: 平台适配器实例。
        platform: 平台名。
        external_session_id: 外部会话 ID。
        internal_session_id: 内部会话 ID。
        message: 用户消息文本。
        metadata: 平台透传的元信息（含 callback_url 等）。
    """
    start_ts = time.time()
    try:
        # 1. 发送"正在输入"
        try:
            await adapter.send_typing_indicator(external_session_id)
        except Exception as e:  # pragma: no cover
            logger.debug("send_typing_indicator failed: %s", e)

        # 2. 构建完整 ChatService 依赖链（独立 session）
        async with AsyncSessionLocal() as db:
            config_service = ConfigService(db)
            llm_service = LLMService(config_service=config_service)
            intent_service = IntentService(llm_service=llm_service)
            rag_service = RAGService(
                db=db, config_service=config_service, llm_service=llm_service
            )
            memory_service = MemoryService(db)
            chat_service = ChatService(
                db=db,
                intent_service=intent_service,
                rag_service=rag_service,
                llm_service=llm_service,
                memory_service=memory_service,
                config_service=config_service,
            )

            # 3. 调用 handle_message_stream 收集完整结果
            stream = chat_service.handle_message_stream(
                session_id=internal_session_id,
                message=message,
                history=[],
            )
            collected = await collect_stream_response(stream)

        # 4. 推送回复
        try:
            send_kwargs = {}
            # GenericAdapter 需要 callback_url
            if platform == "generic":
                callback_url = metadata.get("callback_url")
                if callback_url:
                    send_kwargs["callback_url"] = callback_url

            await adapter.send_reply(
                external_session_id=external_session_id,
                content=collected.answer or "",
                sources=collected.sources or None,
                fallback=collected.fallback,
                **send_kwargs,
            )
        except Exception as e:
            logger.error("send_reply failed (platform=%s): %s", platform, e)
            # 发送兜底错误消息
            try:
                await adapter.send_reply(
                    external_session_id=external_session_id,
                    content="抱歉，回复推送失败，请稍后重试或联系人工客服。",
                    sources=None,
                    fallback=None,
                    **({"callback_url": metadata.get("callback_url")} if platform == "generic" else {}),
                )
            except Exception:
                pass

        # 5. 若 fallback.show_transfer → 调用平台转人工
        if collected.fallback and collected.fallback.get("show_transfer"):
            try:
                transferred = await adapter.transfer_to_human(
                    external_session_id=external_session_id,
                    reason="用户问题触发兜底转人工",
                )
                if transferred:
                    logger.info(
                        "Transferred to human: platform=%s ext=%s",
                        platform,
                        external_session_id,
                    )
            except Exception as e:
                logger.warning("transfer_to_human failed: %s", e)

    except Exception as e:
        logger.exception(
            "Webhook _process_and_reply failed (platform=%s, ext=%s): %s",
            platform,
            external_session_id,
            e,
        )
    finally:
        elapsed_ms = int((time.time() - start_ts) * 1000)
        logger.info(
            "Webhook processed: platform=%s ext=%s elapsed=%dms",
            platform,
            external_session_id,
            elapsed_ms,
        )
