"""ZhiboAdapter — 智齿科技客服平台适配器。

职责：
1. 接收智齿 Webhook 消息（event=message.receive）
2. 验证 X-Sobot-Signature HMAC-SHA256 签名（含时间戳防重放）
3. 调用智齿 Open API 推送回复、转人工、关闭会话等

签名验证规则：
    Header: X-Sobot-Signature = "sha256=" + HMAC-SHA256(secret, timestamp + "." + body)
    Header: X-Sobot-Timestamp  = unix_timestamp_ms
    校验：1. 时间戳偏差 ≤ 300 秒  2. HMAC 比对（hmac.compare_digest 防时序攻击）

智齿 Webhook 消息格式：
    {
      "event": "message.receive",
      "timestamp": 1700000000000,
      "data": {
        "conversation": {"id": "conv_abc123", "type": "online", ...},
        "sender":       {"id": "visitor_u001", "name": "张三", ...},
        "message":      {"id": "msg_xyz789", "type": "text", "content": "..."},
        "extra":        {...}
      }
    }
"""

import hashlib
import hmac
import json
import logging
import time
from typing import Any, Optional

import httpx

from app.adapters.base import BaseAdapter
from app.config.settings import settings
from app.exceptions import AdapterAuthError, AdapterSendError

logger = logging.getLogger(__name__)

# 允许的时间戳偏差（秒）：±300 秒防重放
_TIMESTAMP_TOLERANCE_SECONDS = 300

# 智齿消息类型 → 中文标签
MSG_TYPE_LABELS = {
    "text": "文本",
    "image": "图片",
    "file": "文件",
    "audio": "语音",
    "video": "视频",
    "rich": "富文本",
}


class ZhiboAdapter(BaseAdapter):
    """智齿科技适配器。"""

    platform_name = "zhibo"
    display_name = "智齿科技"

    # 智齿 API 基础路径
    API_BASE: str = settings.ZHIBO_API_BASE or "https://api.sobot.com"

    # 消息类型映射（content_type 智齿侧字段）
    MSG_TYPE_MAP: dict[str, str] = {
        "text": "text",
        "markdown": "markdown",
    }

    # ------------------------------------------------------------------ #
    # 签名验证
    # ------------------------------------------------------------------ #
    def verify_signature(self, headers: dict, raw_body: bytes) -> bool:
        """验证智齿签名：sha256=HMAC-SHA256(secret, timestamp + "." + body)。

        Args:
            headers: HTTP 请求头。
            raw_body: 原始请求体字节。

        Returns:
            bool: 签名是否合法。
        """
        secret = settings.ZHIBO_WEBHOOK_SECRET
        if not secret:
            # 未配置 secret 时直接放行（开发阶段）
            logger.warning("ZHIBO_WEBHOOK_SECRET not configured, skip verification")
            return True

        # 大小写不敏感读取 header
        lower_headers = {k.lower(): v for k, v in headers.items()}
        signature = lower_headers.get("x-sobot-signature", "")
        timestamp_str = lower_headers.get("x-sobot-timestamp", "")

        if not signature or not timestamp_str:
            logger.warning("Missing X-Sobot-Signature or X-Sobot-Timestamp header")
            return False

        # 1. 时间戳偏差检查
        try:
            ts = int(timestamp_str)
            # 兼容毫秒与秒
            if ts > 10**12:
                ts = ts // 1000
            now = int(time.time())
            if abs(now - ts) > _TIMESTAMP_TOLERANCE_SECONDS:
                logger.warning("Zhibo timestamp out of tolerance: ts=%s now=%s", ts, now)
                return False
        except (TypeError, ValueError):
            logger.warning("Invalid X-Sobot-Timestamp: %s", timestamp_str)
            return False

        # 2. HMAC 比对（防时序攻击）
        body_str = raw_body.decode("utf-8", errors="replace")
        expected_sig = "sha256=" + hmac.new(
            secret.encode("utf-8"),
            f"{timestamp_str}.{body_str}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(signature, expected_sig)

    # ------------------------------------------------------------------ #
    # 消息解析
    # ------------------------------------------------------------------ #
    def parse_incoming(self, raw_body: bytes) -> dict:
        """解析智齿 message.receive 事件为统一格式。

        Args:
            raw_body: 原始请求体字节。

        Returns:
            dict: 统一格式（详见 BaseAdapter.parse_incoming 文档）。

        Raises:
            AdapterAuthError: JSON 解析失败或字段缺失。
        """
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            logger.warning("Parse zhibo webhook body failed: %s", e)
            raise AdapterAuthError("Webhook body 必须为合法的 UTF-8 JSON") from e

        event = payload.get("event") or payload.get("type") or ""
        # 非消息事件标记跳过
        if event and event != "message.receive":
            return {"skip": True, "event": event}

        data = payload.get("data") or {}
        conversation = data.get("conversation") or {}
        sender = data.get("sender") or {}
        message = data.get("message") or {}
        extra = data.get("extra") or {}

        msg_id = message.get("id") or ""
        conv_id = conversation.get("id") or ""
        if not conv_id:
            raise AdapterAuthError("智齿 Webhook 缺少 conversation.id")

        msg_type = message.get("type", "text")
        content = message.get("content", "")

        # 非文本消息降级为提示文本
        if msg_type != "text" and not content:
            label = MSG_TYPE_LABELS.get(msg_type, msg_type)
            content = f"[收到一条{label}消息，暂不支持解析，请联系人工客服]"

        return {
            "skip": False,
            "external_session_id": conv_id,
            "external_user_id": sender.get("id"),
            "external_user_name": sender.get("name"),
            "message": content,
            "message_id": msg_id,
            "channel_type": conversation.get("channel") or conversation.get("type") or "web",
            "metadata": {
                "event": event,
                "conversation_type": conversation.get("type"),
                "sender_type": sender.get("type"),
                "sender_phone": sender.get("phone"),
                "page_url": extra.get("page_url"),
                "custom_fields": extra.get("custom_fields"),
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
        """调用智齿 Open API 推送回复。

        Args:
            external_session_id: 智齿 conversation.id。
            content: 回复正文（Markdown 文本）。
            sources: 引用来源列表。
            fallback: 兜底配置 dict。
            **kwargs: 扩展参数（msg_type）。

        Raises:
            AdapterSendError: 推送失败。
        """
        msg_type = kwargs.get("msg_type", "text")
        final_content = self._build_final_content(content, sources, fallback)
        content_type = "markdown" if self._has_markdown(final_content) else "text"

        payload = {
            "conversation_id": external_session_id,
            "content": final_content,
            "content_type": content_type,
            "msg_type": self.MSG_TYPE_MAP.get(msg_type, "text"),
        }

        url = f"{self.API_BASE}/api/open/v1/message/send"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload, headers=self._auth_headers())
            if resp.status_code >= 400:
                raise AdapterSendError(
                    f"智齿 send_reply HTTP {resp.status_code}: {resp.text[:200]}"
                )
            data = resp.json() if resp.text else {}
            if data.get("code") not in (0, "0", 200, "200"):
                raise AdapterSendError(
                    f"智齿 send_reply 业务错误: code={data.get('code')} msg={data.get('message')}"
                )
        except httpx.HTTPError as e:
            raise AdapterSendError(f"智齿 send_reply 网络异常: {e}") from e

    # ------------------------------------------------------------------ #
    # 转人工 / 关闭会话 / 已读
    # ------------------------------------------------------------------ #
    async def transfer_to_human(
        self,
        external_session_id: str,
        reason: str = "",
        **kwargs: Any,
    ) -> bool:
        """调用智齿 API 触发转人工。

        Args:
            external_session_id: 智齿 conversation.id。
            reason: 转人工原因。
            **kwargs: skill_group_id（技能组 ID，可选）。

        Returns:
            bool: True 表示成功。
        """
        skill_group_id = kwargs.get("skill_group_id")
        payload: dict[str, Any] = {
            "conversation_id": external_session_id,
            "reason": reason,
        }
        if skill_group_id:
            payload["skill_group_id"] = skill_group_id

        url = f"{self.API_BASE}/api/open/v1/conversation/transfer"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload, headers=self._auth_headers())
            if resp.status_code >= 400:
                logger.error("Zhibo transfer HTTP %s: %s", resp.status_code, resp.text[:200])
                return False
            data = resp.json() if resp.text else {}
            return data.get("code") in (0, "0", 200, "200")
        except httpx.HTTPError as e:
            logger.error("Zhibo transfer failed: %s", e)
            return False

    async def close_session(self, external_session_id: str) -> bool:
        """关闭智齿会话。

        Args:
            external_session_id: 智齿 conversation.id。

        Returns:
            bool: True 表示成功。
        """
        url = f"{self.API_BASE}/api/open/v1/conversation/close"
        payload = {"conversation_id": external_session_id}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload, headers=self._auth_headers())
            if resp.status_code >= 400:
                logger.error("Zhibo close_session HTTP %s", resp.status_code)
                return False
            data = resp.json() if resp.text else {}
            return data.get("code") in (0, "0", 200, "200")
        except httpx.HTTPError as e:
            logger.error("Zhibo close_session failed: %s", e)
            return False

    async def send_typing_indicator(self, external_session_id: str) -> None:
        """发送"正在输入"状态。"""
        url = f"{self.API_BASE}/api/open/v1/message/typing"
        payload = {"conversation_id": external_session_id, "status": "typing"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(url, json=payload, headers=self._auth_headers())
        except httpx.HTTPError as e:
            logger.debug("Zhibo typing indicator failed: %s", e)

    async def mark_read(self, external_session_id: str, message_id: str) -> bool:
        """标记消息已读。"""
        url = f"{self.API_BASE}/api/open/v1/message/read"
        payload = {"conversation_id": external_session_id, "message_id": message_id}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload, headers=self._auth_headers())
            return resp.status_code < 400
        except httpx.HTTPError as e:
            logger.debug("Zhibo mark_read failed: %s", e)
            return False

    # ------------------------------------------------------------------ #
    # 内部辅助
    # ------------------------------------------------------------------ #
    def _auth_headers(self) -> dict:
        """构建智齿 API 认证头。

        Returns:
            dict: 含 Bearer Token + X-App-Key 的请求头。
        """
        token = settings.ZHIBO_API_TOKEN
        app_key = settings.ZHIBO_APP_KEY
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if app_key:
            headers["X-App-Key"] = app_key
        return headers

    def _build_final_content(
        self,
        content: str,
        sources: Optional[list[dict]],
        fallback: Optional[dict],
    ) -> str:
        """组装最终回复文本（回答 + 引用来源 + 兜底提示）。"""
        return self.build_final_content(content, sources, fallback)

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

    @staticmethod
    def _type_label(msg_type: str) -> str:
        """消息类型中文标签。

        Args:
            msg_type: 消息类型字符串。

        Returns:
            str: 中文标签；未知返回原值。
        """
        return MSG_TYPE_LABELS.get(msg_type, msg_type)
