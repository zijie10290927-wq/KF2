"""Redis 异步连接池。

用于：对话短期记忆 (TTL 24h) / Token 白名单 / 滑动窗口限流 / 配置缓存。
当 Redis 服务器不可用时，自动降级到 fakeredis（内存模式）。
"""

import logging

from redis.asyncio import Redis, from_url

from app.config.settings import settings

logger = logging.getLogger(__name__)

# fakeredis 降级客户端（惰性初始化）
_fakeredis_client = None


def _get_fakeredis_client() -> Redis:
    """获取 fakeredis 客户端（惰性初始化）。"""
    global _fakeredis_client
    if _fakeredis_client is None:
        import fakeredis.aioredis as fakeredis_aio
        _fakeredis_client = fakeredis_aio.FakeRedis(decode_responses=True)
        logger.info("Redis degraded to fakeredis (in-memory mode)")
    return _fakeredis_client


class _RedisProxy:
    """透明代理：当真实 Redis 不可用时，自动委托给 fakeredis。

    解决 Python 模块导入引用问题：``from app.config.redis import redis_client``
    捕获的是代理对象引用，切换降级时所有引用自动生效。
    """

    def __init__(self, real_client: Redis) -> None:
        self._real = real_client
        self._degraded = False

    def _client(self) -> Redis:
        if self._degraded:
            return _get_fakeredis_client()
        return self._real

    def __getattr__(self, name):  # noqa: D401
        return getattr(self._client(), name)


# 异步 Redis 客户端单例（decode_responses=True 自动解码为 str）
# 使用代理包装，使所有 ``from app.config.redis import redis_client`` 的引用
# 在 ping_redis() 切换降级时自动生效。
redis_client: _RedisProxy = _RedisProxy(
    from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=50,
        health_check_interval=30,
        retry_on_timeout=True,
    )
)


async def ping_redis() -> bool:
    """检查 Redis 连通性。失败时自动切换到 fakeredis 降级模式。"""
    try:
        return bool(await redis_client._real.ping())
    except Exception as e:  # pragma: no cover
        logger.error("Redis ping failed: %s", e)
        # 降级到 fakeredis
        redis_client._degraded = True
        try:
            return bool(await _get_fakeredis_client().ping())
        except Exception:
            return False
