"""SessionMapper — 外部平台会话 ↔ 内部 session_id 双向映射器。

职责：
1. 主入口 get_or_create：先查 active 映射，命中返回已有 internal_session_id；
   未命中则生成新 UUID + 插入 ChannelSession + commit
2. close_session：关闭会话映射（status='closed'）
3. get_by_internal_id：根据内部 session_id 反查外部平台信息

实现要点：
- 使用 AsyncSessionLocal 独立 session，避免主会话生命周期影响
- select().where(platform=..., external_session_id=..., status='active') 查询
- UniqueConstraint(platform, external_session_id) 保证同一平台同一外部会话仅一条 active
"""

import logging
import uuid
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import AsyncSessionLocal
from app.models.channel_session import ChannelSession

logger = logging.getLogger(__name__)


class SessionMapper:
    """外部平台会话 ↔ 内部 session_id 映射管理。"""

    def __init__(self, db: Optional[AsyncSession] = None) -> None:
        """初始化映射器。

        Args:
            db: 可选的 AsyncSession；不传则每次操作创建独立 session。
        """
        self.db = db

    async def get_or_create(
        self,
        platform: str,
        external_session_id: str,
        external_user_id: Optional[str] = None,
        external_user_name: Optional[str] = None,
        channel_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """获取或创建会话映射。

        Args:
            platform: 平台标识（zhibo/qiyu/udesk/chatwoot/generic）。
            external_session_id: 平台侧会话 ID。
            external_user_id: 平台侧用户 ID（可选）。
            external_user_name: 平台侧用户名（可选）。
            channel_type: 渠道类型（web/app/wechat/douyin 等）。
            metadata: 平台透传的额外信息。

        Returns:
            str: 内部 session_id（UUID 格式）。
        """
        if self.db is not None:
            return await self._get_or_create_with_db(
                self.db,
                platform,
                external_session_id,
                external_user_id,
                external_user_name,
                channel_type,
                metadata,
            )
        # 无注入 session，创建独立 session
        async with AsyncSessionLocal() as db:
            return await self._get_or_create_with_db(
                db,
                platform,
                external_session_id,
                external_user_id,
                external_user_name,
                channel_type,
                metadata,
            )

    async def _get_or_create_with_db(
        self,
        db: AsyncSession,
        platform: str,
        external_session_id: str,
        external_user_id: Optional[str],
        external_user_name: Optional[str],
        channel_type: Optional[str],
        metadata: Optional[dict],
    ) -> str:
        """在指定 session 中执行映射查询/创建。"""
        # 1. 查询 active 映射
        stmt = (
            select(ChannelSession)
            .where(
                ChannelSession.platform == platform,
                ChannelSession.external_session_id == external_session_id,
                ChannelSession.status == "active",
            )
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            # 补全缺失的用户信息（非破坏性更新）
            updated = False
            if external_user_id and not existing.external_user_id:
                existing.external_user_id = external_user_id
                updated = True
            if external_user_name and not existing.external_user_name:
                existing.external_user_name = external_user_name
                updated = True
            if updated:
                try:
                    await db.commit()
                except Exception as e:  # pragma: no cover
                    logger.warning("Update channel session failed: %s", e)
                    await db.rollback()
            return existing.internal_session_id

        # 2. 未命中，创建新映射
        internal_session_id = str(uuid.uuid4())
        new_record = ChannelSession(
            platform=platform,
            external_session_id=external_session_id,
            external_user_id=external_user_id,
            external_user_name=external_user_name,
            internal_session_id=internal_session_id,
            channel_type=channel_type,
            extra_metadata=metadata,
            status="active",
        )
        db.add(new_record)
        try:
            await db.commit()
        except Exception as e:
            logger.error(
                "Create channel session failed (platform=%s, ext=%s): %s",
                platform,
                external_session_id,
                e,
            )
            await db.rollback()
            # 并发场景：回滚后重查一次
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing is not None:
                return existing.internal_session_id
            raise
        logger.info(
            "Mapped new session: platform=%s ext=%s -> internal=%s",
            platform,
            external_session_id,
            internal_session_id,
        )
        return internal_session_id

    async def close_session(
        self,
        platform: str,
        external_session_id: str,
    ) -> bool:
        """关闭会话映射（status='closed'）。

        Args:
            platform: 平台标识。
            external_session_id: 平台侧会话 ID。

        Returns:
            bool: True 表示成功更新；False 表示未找到。
        """
        if self.db is not None:
            return await self._close_with_db(self.db, platform, external_session_id)
        async with AsyncSessionLocal() as db:
            return await self._close_with_db(db, platform, external_session_id)

    async def _close_with_db(
        self,
        db: AsyncSession,
        platform: str,
        external_session_id: str,
    ) -> bool:
        """在指定 session 中执行关闭操作。"""
        stmt = (
            update(ChannelSession)
            .where(
                ChannelSession.platform == platform,
                ChannelSession.external_session_id == external_session_id,
                ChannelSession.status == "active",
            )
            .values(status="closed")
        )
        try:
            result = await db.execute(stmt)
            await db.commit()
            return result.rowcount > 0
        except Exception as e:  # pragma: no cover
            logger.error("Close session failed: %s", e)
            await db.rollback()
            return False

    async def get_by_internal_id(
        self, internal_session_id: str
    ) -> Optional[ChannelSession]:
        """根据内部 session_id 反查外部平台信息。

        Args:
            internal_session_id: 内部会话 ID。

        Returns:
            Optional[ChannelSession]: 映射记录；无返回 None。
        """
        if self.db is not None:
            return await self._get_by_internal_with_db(self.db, internal_session_id)
        async with AsyncSessionLocal() as db:
            return await self._get_by_internal_with_db(db, internal_session_id)

    async def _get_by_internal_with_db(
        self, db: AsyncSession, internal_session_id: str
    ) -> Optional[ChannelSession]:
        stmt = select(ChannelSession).where(
            ChannelSession.internal_session_id == internal_session_id
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_recent(
        self,
        platform: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ChannelSession], int]:
        """分页查询渠道会话列表（供管理后台使用）。

        Args:
            platform: 平台标识筛选（可选）。
            status: 状态筛选（可选）。
            keyword: 关键词（匹配 external_user_name / external_session_id）。
            limit: 每页条数。
            offset: 偏移量。

        Returns:
            tuple: (records, total)。
        """
        from sqlalchemy import func, or_

        async with AsyncSessionLocal() as db:
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

            base = base.order_by(ChannelSession.id.desc()).limit(limit).offset(offset)

            result = await db.execute(base)
            records = list(result.scalars().all())
            count_result = await db.execute(count_base)
            total = count_result.scalar() or 0
            return records, total


# 全局单例
session_mapper = SessionMapper()
