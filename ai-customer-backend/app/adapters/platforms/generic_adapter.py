"""GenericAdapter — 通用兜底适配器。

适用于：
1. 尚未开发专用适配器的平台（七鱼/Udesk/Zendesk 等预留）
2. 自定义 Webhook 对接
3. 内部系统调用

特性：
- 签名规则：HMAC-SHA256(WEBHOOK_HMAC_SECRET, body)
- 消息格式：扁平 JSON {session_id, user_id, message, callback_url, channel}
- 回复方式：通过请求中指定的 callback_url 回调推送结果
"""

import hashlib
import hmac
import json
import logging
import uuid
from typing import Any, Optional

import httpx

from app.adapters.base import BaseAdapter
from app.config.settings import settings
from app.exceptions import AdapterAuthError, AdapterSendError

logger = logging.getLogger(__name__)


class GenericAdapter(BaseAdapter):
    """通用兜底适配器。

    请求体格式（扁平 JSON）：
        {
          "session_id": "ext_xxx",          // 必填，外部会话 ID
          "user_id": "user_xxx",            // 可选
          "user_name": "张三",              // 可选
          "message": "怎么生成水墨画？",     // 必填，用户消息
          "callback_url": "https://...",   // 可选，回复回调 URL
          "channel": "web",                 // 可选，渠道类型
          "message_id": "msg_xxx"           // 可选，消息 ID（防重复）
        }

    签名头：X-Webhook-Signature = HMAC-SHA256(WEBHOOK_HMAC_SECRET, body)
    """

    platform_name = "generic"
    display_name = "通用接入"

    # ------------------------------------------------------------------ #
    # 签名验证
    # ------------------------------------------------------------------ #
    def verify_signature(self, headers: dict, raw_body: bytes) -> bool:
        """验证通用 Webhook 签名：HMAC-SHA256(WEBHOOK_HMAC_SECRET, body)。

        Args:
            headers: HTTP 请求头。
            raw_body: 原始请求体字节。

        Returns:
            bool: 签名是否合法。
        """
        secret = settings.WEBHOOK_HMAC_SECRET
        if not secret:
            logger.warning("WEBHOOK_HMAC_SECRET not configured, skip verification")
            return True

        lower_headers = {k.lower(): v for k, v in headers.items()}
        signature = lower_headers.get("x-webhook-signature", "")
        if not signature:
            logger.warning("Missing X-Webhook-Signature header")
            return False

        expected = hmac.new(
            secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(signature, expected)

    # ------------------------------------------------------------------ #
    # 消息解析
    # ------------------------------------------------------------------ #
    def parse_incoming(self, raw_body: bytes) -> dict:
        """解析扁平 JSON 请求体为统一格式。

        Args:
            raw_body: 原始请求体字节。

        Returns:
            dict: 统一格式。

        Raises:
            AdapterAuthError: JSON 解析失败或缺少必填字段。
        """
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise AdapterAuthError(f"解析 Webhook 体失败: {e}") from e

        if not isinstance(payload, dict):
            raise AdapterAuthError("Webhook body 必须为 JSON 对象")

        # 兼容多种字段命名
        session_id = (
            payload.get("session_id")
            or payload.get("external_session_id")
            or payload.get("conversation_id")
        )
        if not session_id:
            raise AdapterAuthError("Webhook 缺少 session_id 字段")

        message = payload.get("message") or payload.get("content") or ""
        if not message:
            return {"skip": True, "reason": "empty message"}

        return {
            "skip": False,
            "external_session_id": session_id,
            "external_user_id": payload.get("user_id") or payload.get("external_user_id"),
            "external_user_name": payload.get("user_name") or payload.get("external_user_name"),
            "message": message,
            "message_id": payload.get("message_id") or str(uuid.uuid4()),
            "channel_type": payload.get("channel") or payload.get("channel_type") or "web",
            "metadata": {
                "callback_url": payload.get("callback_url"),
                "extra": payload.get("extra") or payload.get("metadata") or {},
            },
        }

    # ------------------------------------------------------------------ #
    # 回复推送
    # ------------------------------------------------------------------ #
    async def send_reply(
        self,
        external_session_id: str,
        content: str,
        sources: Optional[list[dict]] = None,
        fallback: Optional[dict] = None,
        **kwargs: Any,
    ) -> None:
        """通过 callback_url 回调推送结果。

        Args:
            external_session_id: 外部会话 ID。
            content: 回复正文（Markdown 文本）。
            sources: 引用来源列表。
            fallback: 兜底配置 dict。
            **kwargs: callback_url（覆盖 metadata 中的回调地址）。

        Raises:
            AdapterSendError: 无 callback_url 或推送失败。
        """
        callback_url = kwargs.get("callback_url")
        if not callback_url:
            raise AdapterSendError(
                "GenericAdapter.send_reply 需要 callback_url 参数"
            )

        final_content = self.build_final_content(content, sources, fallback)
        payload = {
            "session_id": external_session_id,
            "content": final_content,
            "content_type": "markdown" if self._has_markdown(final_content) else "text",
            "sources": sources or [],
            "fallback": fallback or {},
            "timestamp": int(__import__("time").time() * 1000),
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(callback_url, json=payload)
            if resp.status_code >= 400:
                raise AdapterSendError(
                    f"Generic callback HTTP {resp.status_code}: {resp.text[:200]}"
                )
        except httpx.HTTPError as e:
            raise AdapterSendError(f"Generic callback 网络异常: {e}") from e

    # ------------------------------------------------------------------ #
    # 内部辅助
    # ------------------------------------------------------------------ #
    @staticmethod
    def _has_markdown(text: str) -> bool:
        """简单判断文本是否含 Markdown 语法。

        Args:
            text: 待判断文本。

        Returns:
            bool: 是否含 Markdown 语法。
        """
        if not text:
            return False
        markers = ("**", "##", "- ", "* ", "```", "|", "\n> ")
        return any(m in text for m in markers)
