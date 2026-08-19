"""ChannelAdminService — 渠道管理后台服务。

职责：
1. 渠道总览统计（今日消息数/活跃渠道/平均响应时间/转人工率）
2. 渠道配置 CRUD（基于 system_configs 表，前缀 channel:<platform>:*）
3. 启用/停用渠道
4. 渠道会话列表查询（含筛选 + 分页）
5. 渠道会话消息详情
6. Webhook 日志查询（简化版，从文件或内存读取）

设计要点：
- 渠道配置以 KV 形式存于 system_configs，key 命名规则：
  channel:{platform}:enabled / :api_token / :webhook_secret / :app_key / :api_base / :remark
- 加密字段（api_token / webhook_secret）使用 Fernet 加密
- 复用 ConfigService 读写 system_configs，避免重复实现缓存逻辑
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.platforms import list_adapters
from app.config.settings import settings
from app.models import ChatMessage
from app.models.channel_session import ChannelSession
from app.schemas.webhook import (
    ChannelConfigDTO,
    ChannelOverviewDTO,
    ChannelSessionDTO,
)
from app.services.config_service import ConfigService
from app.utils.crypto import decrypt_api_key, encrypt_api_key

logger = logging.getLogger(__name__)

# 渠道配置 key 前缀
_CHANNEL_CONFIG_PREFIX = "channel"

# 敏感字段列表（需加密存储）
_SENSITIVE_FIELDS = ("api_token", "webhook_secret")


class ChannelAdminService:
    """渠道管理后台服务。"""

    def __init__(self, db: AsyncSession) -> None:
        """初始化。

        Args:
            db: AsyncSession 实例。
        """
        self.db = db
        self.config_service = ConfigService(db)

    # ------------------------------------------------------------------ #
    # 渠道总览
    # ------------------------------------------------------------------ #
    async def get_overview(self) -> ChannelOverviewDTO:
        """获取渠道总览统计。

        Returns:
            ChannelOverviewDTO: 含今日消息数/活跃渠道/平均响应时间/转人工率。
        """
        # 今日范围
        today_start = datetime.combine(
            datetime.now().date(), datetime.min.time()
        )
        # 今日消息数（chat_messages 表）
        try:
            stmt = select(func.count(ChatMessage.id)).where(
                ChatMessage.created_at >= today_start
            )
            result = await self.db.execute(stmt)
            today_messages = result.scalar() or 0
        except Exception as e:
            logger.warning("Count today messages failed: %s", e)
            today_messages = 0

        # 活跃渠道数（channel_sessions 中 status=active 的不同 platform 数）
        try:
            stmt = (
                select(func.count(func.distinct(ChannelSession.platform)))
                .where(ChannelSession.status == "active")
            )
            result = await self.db.execute(stmt)
            active_channels = result.scalar() or 0
        except Exception as e:
            logger.warning("Count active channels failed: %s", e)
            active_channels = 0

        # 转人工率：assistant 消息中 intent=off_topic 占比（粗略近似）
        transfer_rate = 0.0
        try:
            total_stmt = select(func.count(ChatMessage.id)).where(
                ChatMessage.role == "assistant",
                ChatMessage.created_at >= today_start,
            )
            off_topic_stmt = select(func.count(ChatMessage.id)).where(
                ChatMessage.role == "assistant",
                ChatMessage.intent == "off_topic",
                ChatMessage.created_at >= today_start,
            )
            total_result = await self.db.execute(total_stmt)
            off_result = await self.db.execute(off_topic_stmt)
            total = total_result.scalar() or 0
            off_topic = off_result.scalar() or 0
            if total > 0:
                transfer_rate = round(off_topic / total, 4)
        except Exception as e:
            logger.warning("Calc transfer rate failed: %s", e)

        # 已注册适配器列表
        channels = list_adapters()
        # 每个适配器补充 enabled 状态
        for ch in channels:
            platform = ch["platform"]
            enabled_key = f"{_CHANNEL_CONFIG_PREFIX}:{platform}:enabled"
            enabled_val = await self.config_service.get(enabled_key, "false")
            ch["enabled"] = enabled_val.lower() in ("true", "1", "yes", "on")

        return ChannelOverviewDTO(
            today_messages=today_messages,
            active_channels=active_channels,
            avg_response_time_ms=0,  # 暂未采集响应时间
            transfer_rate=transfer_rate,
            channels=channels,
        )

    # ------------------------------------------------------------------ #
    # 渠道配置 CRUD
    # ------------------------------------------------------------------ #
    async def list_configs(self) -> list[ChannelConfigDTO]:
        """获取所有渠道配置。

        Returns:
            list[ChannelConfigDTO]: 渠道配置列表（含敏感字段掩码）。
        """
        result: list[ChannelConfigDTO] = []
        for ch in list_adapters():
            platform = ch["platform"]
            cfg = await self._load_config(platform)
            cfg.display_name = ch["display_name"]
            # 敏感字段掩码
            if cfg.api_token:
                cfg.api_token = self._mask_secret(cfg.api_token)
            if cfg.webhook_secret:
                cfg.webhook_secret = self._mask_secret(cfg.webhook_secret)
            result.append(cfg)
        return result

    async def save_config(self, config: ChannelConfigDTO) -> ChannelConfigDTO:
        """保存/更新渠道配置。

        Args:
            config: 渠道配置 DTO。

        Returns:
            ChannelConfigDTO: 保存后的配置（敏感字段已掩码）。
        """
        platform = config.platform
        # 加密敏感字段
        pairs: dict[str, str] = {
            "enabled": "true" if config.enabled else "false",
            "api_base": config.api_base or "",
            "app_key": config.app_key or "",
            "remark": config.remark or "",
        }
        # 仅当明文非空且非掩码时才更新密钥（避免掩码覆盖真实值）
        if config.api_token and not config.api_token.startswith("***"):
            pairs["api_token"] = encrypt_api_key(config.api_token)
        if config.webhook_secret and not config.webhook_secret.startswith("***"):
            pairs["webhook_secret"] = encrypt_api_key(config.webhook_secret)

        for key, value in pairs.items():
            full_key = f"{_CHANNEL_CONFIG_PREFIX}:{platform}:{key}"
            await self.config_service.set(full_key, value)

        # 返回掩码后的配置
        saved = await self._load_config(platform)
        saved.display_name = config.display_name
        if saved.api_token:
            saved.api_token = self._mask_secret(saved.api_token)
        if saved.webhook_secret:
            saved.webhook_secret = self._mask_secret(saved.webhook_secret)
        return saved

    async def toggle_status(self, platform: str, enabled: bool) -> bool:
        """启用/停用渠道。

        Args:
            platform: 平台标识。
            enabled: True 启用，False 禁用。

        Returns:
            bool: True 表示成功。
        """
        key = f"{_CHANNEL_CONFIG_PREFIX}:{platform}:enabled"
        await self.config_service.set(key, "true" if enabled else "false")
        return True

    async def test_connection(self, platform: str) -> dict:
        """测试渠道连接。

        Args:
            platform: 平台标识。

        Returns:
            dict: {success, message}。
        """
        from app.adapters.platforms import get_adapter

        adapter = get_adapter(platform)
        if adapter is None:
            return {"success": False, "message": f"未注册的平台: {platform}"}

        # 简单测试：检查必要配置项是否存在
        cfg = await self._load_config(platform)
        if not cfg.enabled:
            return {"success": False, "message": f"渠道 {platform} 未启用"}

        if platform == "zhibo":
            if not settings.ZHIBO_API_TOKEN and not cfg.api_token:
                return {"success": False, "message": "智齿 API Token 未配置"}
            return {
                "success": True,
                "message": f"智齿配置检查通过 (API_BASE={cfg.api_base or settings.ZHIBO_API_BASE})",
            }
        elif platform == "generic":
            return {
                "success": True,
                "message": "通用适配器无需额外配置（验证由 Webhook 触发）",
            }
        return {"success": True, "message": "适配器已加载"}

    # ------------------------------------------------------------------ #
    # 渠道会话查询
    # ------------------------------------------------------------------ #
    async def list_conversations(
        self,
        platform: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ChannelSession], int]:
        """分页查询渠道会话列表。

        Args:
            platform: 平台筛选（可选）。
            status: 状态筛选（可选）。
            keyword: 关键词（匹配 user_name / external_session_id）。
            page: 页码。
            page_size: 每页条数。

        Returns:
            tuple: (records, total)。
        """
        from sqlalchemy import or_

        base = select(ChannelSession)
        count_base = select(func.count(ChannelSession.id))

        if platform:
            base = base.where(ChannelSession.platform == platform)
            count_base = count_base.where(ChannelSession.platform == platform)
        if status:
            base = base.where(ChannelSession.status == status)
            count_base = count_base.where(ChannelSession.status == status)
        if keyword:
            like = f"%{keyword}%"
            cond = or_(
                ChannelSession.external_user_name.like(like),
                ChannelSession.external_session_id.like(like),
            )
            base = base.where(cond)
            count_base = count_base.where(cond)

        offset = (page - 1) * page_size
        base = base.order_by(ChannelSession.id.desc()).limit(page_size).offset(offset)

        result = await self.db.execute(base)
        records = list(result.scalars().all())
        count_result = await self.db.execute(count_base)
        total = count_result.scalar() or 0
        return records, total

    async def get_conversation_messages(
        self, session_id: str, limit: int = 100
    ) -> list[ChatMessage]:
        """查询会话消息详情。

        Args:
            session_id: 内部会话 ID。
            limit: 返回条数上限。

        Returns:
            list[ChatMessage]: 消息列表（按时间正序）。
        """
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------ #
    # Webhook 日志查询
    # ------------------------------------------------------------------ #
    async def list_webhook_logs(
        self,
        platform: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """查询 Webhook 日志（简化版，复用 channel_sessions 表作为日志来源）。

        Args:
            platform: 平台筛选。
            status: 状态筛选。
            page: 页码。
            page_size: 每页条数。

        Returns:
            tuple: (logs, total)。
        """
        records, total = await self.list_conversations(
            platform=platform, status=status, page=page, page_size=page_size
        )
        # 转为日志格式
        logs = []
        for r in records:
            logs.append(
                {
                    "id": r.id,
                    "platform": r.platform,
                    "message_id": r.external_session_id,
                    "status": r.status,
                    "raw_body": None,
                    "error": None,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
            )
        return logs, total

    # ------------------------------------------------------------------ #
    # 内部辅助
    # ------------------------------------------------------------------ #
    async def _load_config(self, platform: str) -> ChannelConfigDTO:
        """从 system_configs 加载渠道配置（解密敏感字段）。

        Args:
            platform: 平台标识。

        Returns:
            ChannelConfigDTO: 配置对象。
        """
        enabled = await self.config_service.get_bool(
            f"{_CHANNEL_CONFIG_PREFIX}:{platform}:enabled", False
        )
        api_base = await self.config_service.get(
            f"{_CHANNEL_CONFIG_PREFIX}:{platform}:api_base"
        )
        app_key = await self.config_service.get(
            f"{_CHANNEL_CONFIG_PREFIX}:{platform}:app_key"
        )
        remark = await self.config_service.get(
            f"{_CHANNEL_CONFIG_PREFIX}:{platform}:remark"
        )
        api_token_enc = await self.config_service.get(
            f"{_CHANNEL_CONFIG_PREFIX}:{platform}:api_token"
        )
        webhook_secret_enc = await self.config_service.get(
            f"{_CHANNEL_CONFIG_PREFIX}:{platform}:webhook_secret"
        )

        # 解密
        api_token = ""
        if api_token_enc:
            try:
                api_token = decrypt_api_key(api_token_enc)
            except Exception:  # pragma: no cover
                api_token = ""
        webhook_secret = ""
        if webhook_secret_enc:
            try:
                webhook_secret = decrypt_api_key(webhook_secret_enc)
            except Exception:  # pragma: no cover
                webhook_secret = ""

        return ChannelConfigDTO(
            platform=platform,
            display_name=platform,
            enabled=enabled,
            api_token=api_token,
            webhook_secret=webhook_secret,
            app_key=app_key,
            api_base=api_base,
            remark=remark,
        )

    @staticmethod
    def _mask_secret(secret: str) -> str:
        """敏感字段掩码。

        Args:
            secret: 明文密钥。

        Returns:
            str: 掩码后的字符串（保留首尾各 3 位）。
        """
        if not secret or len(secret) <= 6:
            return "***" if secret else ""
        return f"{secret[:3]}***{secret[-3:]}"
