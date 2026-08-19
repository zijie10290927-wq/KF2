"""MemoryService — 对话记忆管理。

Redis 短期记忆（滑动窗口）+ MySQL 长期持久化 双写。
"""

import json
import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.redis import redis_client
from app.config.settings import settings
from app.models import ChatMessage

logger = logging.getLogger(__name__)

_HISTORY_KEY_PREFIX = "session:history:"

# 默认常量（与 settings 一致）
SHORT_TERM_TTL = settings.SHORT_TERM_TTL  # 86400 (24h)
MAX_SHORT_TERM = settings.MAX_SHORT_TERM  # 20


class MemoryService:
    """对话记忆：Redis 短期 + MySQL 长期 双写。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _key(session_id: str) -> str:
        return f"{_HISTORY_KEY_PREFIX}{session_id}"

    # ------------------------------------------------------------------ #
    # 读取历史
    # ------------------------------------------------------------------ #
    async def get_history(self, session_id: str) -> list[dict[str, Any]]:
        """获取最近 MAX_SHORT_TERM 条历史消息。

        返回格式：[{role, content, ...}]
        """
        try:
            raw_list = await redis_client.lrange(self._key(session_id), -MAX_SHORT_TERM, -1)
        except Exception as e:  # pragma: no cover
            logger.error("Redis get_history failed: %s", e)
            return []

        history: list[dict[str, Any]] = []
        for raw in raw_list:
            try:
                history.append(json.loads(raw))
            except (json.JSONDecodeError, TypeError):
                continue
        return history

    # ------------------------------------------------------------------ #
    # 写入消息（双写）
    # ------------------------------------------------------------------ #
    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        message_id: Optional[str] = None,
        intent: Optional[str] = None,
        sources: Optional[list[dict]] = None,
        model_used: Optional[str] = None,
        tokens_used: Optional[int] = None,
    ) -> None:
        """双写：① Redis rpush+ltrim+expire（滑动窗口）；② MySQL 异步插入 ChatMessage。

        注意：在 ChatService 的 finally 块中调用时，需使用独立 AsyncSession 或
        正确 await，避免主会话提前关闭导致写入失败。
        """
        import uuid

        msg_id = message_id or str(uuid.uuid4())
        record = {
            "message_id": msg_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "intent": intent,
            "sources": sources,
            "model_used": model_used,
        }

        # 1. Redis 滑动窗口
        try:
            key = self._key(session_id)
            await redis_client.rpush(key, json.dumps(record, ensure_ascii=False))
            await redis_client.ltrim(key, -MAX_SHORT_TERM, -1)
            await redis_client.expire(key, SHORT_TERM_TTL)
        except Exception as e:  # pragma: no cover
            logger.error("Redis save_message failed: %s", e)

        # 2. MySQL 持久化
        try:
            msg = ChatMessage(
                message_id=msg_id,
                session_id=session_id,
                role=role,
                content=content,
                intent=intent,
                sources=sources,
                model_used=model_used,
                tokens_used=tokens_used,
            )
            self.db.add(msg)
            await self.db.commit()
        except Exception as e:  # pragma: no cover
            logger.error("MySQL save_message failed: %s", e)
            await self.db.rollback()

    # ------------------------------------------------------------------ #
    # 清空历史
    # ------------------------------------------------------------------ #
    async def clear_history(self, session_id: str) -> None:
        """清空 Redis + 软删除 DB 记录（这里直接物理删除消息）。"""
        try:
            await redis_client.delete(self._key(session_id))
        except Exception as e:  # pragma: no cover
            logger.error("Redis clear_history failed: %s", e)

        try:
            from sqlalchemy import delete

            stmt = delete(ChatMessage).where(ChatMessage.session_id == session_id)
            await self.db.execute(stmt)
            await self.db.commit()
        except Exception as e:  # pragma: no cover
            logger.error("MySQL clear_history failed: %s", e)
            await self.db.rollback()
