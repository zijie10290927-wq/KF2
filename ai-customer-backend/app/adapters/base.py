"""BaseAdapter — 渠道适配器抽象基类。

职责：
1. 定义所有平台适配器的统一消息收发契约
2. 提供引用来源与兜底话术的通用格式化方法
3. 子类只需实现三个抽象方法：verify_signature / parse_incoming / send_reply

设计要点：
- 子类通过 platform_name 唯一标识，用于路由分发与工厂注册
- parse_incoming 返回统一内部格式 dict，屏蔽各平台消息差异
- send_reply 接收 Markdown 文本，由适配器内部转换为平台原生格式
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseAdapter(ABC):
    """渠道适配器基类，所有平台适配器继承此类。

    类属性：
        platform_name: 平台唯一标识（zhibo/qiyu/udesk/chatwoot/generic）
        display_name: 后台展示名称
    """

    platform_name: str = "generic"
    display_name: str = "通用接入"

    @abstractmethod
    def verify_signature(self, headers: dict, raw_body: bytes) -> bool:
        """验证平台 Webhook 签名（防伪造）。

        Args:
            headers: HTTP 请求头字典（大小写不敏感读取）。
            raw_body: 原始请求体字节（用于 HMAC 计算）。

        Returns:
            bool: 签名是否合法。
        """
        ...

    @abstractmethod
    def parse_incoming(self, raw_body: bytes) -> dict:
        """解析平台消息为统一内部格式。

        Args:
            raw_body: 原始请求体字节。

        Returns:
            dict: 统一格式，字段如下：
                - skip (bool): 是否跳过非消息事件
                - external_session_id (str): 平台会话 ID
                - external_user_id (str | None): 平台用户 ID
                - external_user_name (str | None): 平台用户名
                - message (str): 用户消息文本
                - message_id (str): 平台消息 ID（用于幂等去重）
                - channel_type (str): 渠道类型（web/app/wechat 等）
                - metadata (dict): 平台透传的额外信息
        """
        ...

    @abstractmethod
    async def send_reply(
        self,
        external_session_id: str,
        content: str,
        sources: Optional[list[dict]] = None,
        fallback: Optional[dict] = None,
        **kwargs: Any,
    ) -> None:
        """将 Agent 回复推送回平台。

        Args:
            external_session_id: 平台会话 ID。
            content: 回复正文（Markdown 文本）。
            sources: 引用来源列表，每项含 title/score/snippet 字段。
            fallback: 兜底配置 dict，含 show_transfer/show_phone/phone 字段。
            **kwargs: 平台特有扩展参数（如 callback_url）。

        Raises:
            AdapterSendError: 推送失败时抛出。
        """
        ...

    # ------------------------------------------------------------------ #
    # 通用辅助方法（子类可覆写以适配平台原生 UI）
    # ------------------------------------------------------------------ #
    def format_sources(self, sources: list[dict]) -> str:
        """将引用来源格式化为文本附加在回答末尾。

        Args:
            sources: 引用来源列表，每项含 title/score 字段。

        Returns:
            str: 格式化后的 Markdown 文本；空列表返回空字符串。
        """
        if not sources:
            return ""
        lines = ["\n\n---\n📎 参考来源："]
        for s in sources[:3]:
            title = s.get("title", "未知")
            score = s.get("score", 0)
            try:
                score_pct = f"{float(score):.0%}"
            except (TypeError, ValueError):
                score_pct = str(score)
            lines.append(f"• {title}（相关度 {score_pct}）")
        return "\n".join(lines)

    def format_fallback(self, fallback: dict) -> str:
        """将兜底配置转为文本提示。

        Args:
            fallback: 兜底配置 dict，含 show_transfer/show_phone/phone 字段。

        Returns:
            str: 多行提示文本；无任何提示项返回空字符串。
        """
        if not fallback:
            return ""
        parts = []
        if fallback.get("show_transfer"):
            parts.append("如需进一步帮助，请输入「转人工」")
        if fallback.get("show_phone"):
            phone = fallback.get("phone", "")
            if phone:
                parts.append(f"或拨打客服电话：{phone}")
        return "\n".join(parts)

    def build_final_content(
        self,
        content: str,
        sources: Optional[list[dict]] = None,
        fallback: Optional[dict] = None,
    ) -> str:
        """组装最终回复文本：回答 + 引用来源 + 兜底提示。

        Args:
            content: AI 回答正文。
            sources: 引用来源列表。
            fallback: 兜底配置 dict。

        Returns:
            str: 拼接后的完整回复文本。
        """
        parts = [content or ""]
        if sources:
            src_text = self.format_sources(sources)
            if src_text:
                parts.append(src_text)
        if fallback:
            fb_text = self.format_fallback(fallback)
            if fb_text:
                parts.append(fb_text)
        return "\n".join(p for p in parts if p)

    # ------------------------------------------------------------------ #
    # 可选能力探测（子类按需覆写）
    # ------------------------------------------------------------------ #
    async def transfer_to_human(
        self, external_session_id: str, reason: str = "", **kwargs: Any
    ) -> bool:
        """触发平台转人工。

        Args:
            external_session_id: 平台会话 ID。
            reason: 转人工原因。

        Returns:
            bool: True 表示成功；False 表示平台不支持或失败。
        """
        return False

    async def send_typing_indicator(self, external_session_id: str) -> None:
        """发送"正在输入"状态（提升用户体验）。

        默认空实现，子类按需覆写。
        """
        return None

    async def close_session(self, external_session_id: str) -> bool:
        """关闭/结束平台会话。

        Args:
            external_session_id: 平台会话 ID。

        Returns:
            bool: True 表示成功；False 表示平台不支持或失败。
        """
        return False

    async def mark_read(self, external_session_id: str, message_id: str) -> bool:
        """标记消息已读。

        Args:
            external_session_id: 平台会话 ID。
            message_id: 消息 ID。

        Returns:
            bool: True 表示成功；False 表示平台不支持或失败。
        """
        return False
