"""平台适配器注册工厂。

职责：
1. 维护 platform_name → AdapterClass 的注册表
2. 提供 get_adapter() 单例工厂方法
3. 提供 list_adapters() 列出已注册适配器

扩展新平台的步骤：
1. 在 platforms/ 下新建 <platform>_adapter.py 继承 BaseAdapter
2. 实现三个抽象方法：verify_signature / parse_incoming / send_reply
3. 在本文件的 _ADAPTER_REGISTRY 注册 {platform_name: AdapterClass}
"""

import logging
from typing import Optional

from app.adapters.base import BaseAdapter
from app.adapters.platforms.generic_adapter import GenericAdapter
from app.adapters.platforms.zhibo_adapter import ZhiboAdapter

logger = logging.getLogger(__name__)

# 平台注册表：platform_name -> AdapterClass
_ADAPTER_REGISTRY: dict[str, type[BaseAdapter]] = {
    "zhibo": ZhiboAdapter,
    "generic": GenericAdapter,
    # 后续新增：qiyu/udesk/chatwoot/zendesk
}

# 单例缓存：platform_name -> AdapterInstance
_ADAPTER_INSTANCES: dict[str, BaseAdapter] = {}


def get_adapter(platform: str) -> Optional[BaseAdapter]:
    """根据平台名获取适配器实例（单例）。

    Args:
        platform: 平台标识（zhibo/generic 等）。

    Returns:
        Optional[BaseAdapter]: 适配器实例；未注册则返回 generic 兜底适配器。
    """
    platform = (platform or "").strip().lower()

    # 已缓存则直接返回
    if platform in _ADAPTER_INSTANCES:
        return _ADAPTER_INSTANCES[platform]

    # 查注册表
    cls = _ADAPTER_REGISTRY.get(platform)
    if cls is None:
        # 未注册 → 兜底 GenericAdapter
        logger.warning(
            "Platform %r not registered, fallback to GenericAdapter", platform
        )
        cls = GenericAdapter
        platform = "generic"

    instance = cls()
    _ADAPTER_INSTANCES[platform] = instance
    return instance


def list_adapters() -> list[dict]:
    """列出所有已注册的适配器。

    Returns:
        list[dict]: 每项含 platform/display_name/registered 字段。
    """
    result = []
    for name, cls in _ADAPTER_REGISTRY.items():
        result.append(
            {
                "platform": name,
                "display_name": cls.display_name,
                "registered": True,
            }
        )
    return result


def is_registered(platform: str) -> bool:
    """判断平台是否已注册。

    Args:
        platform: 平台标识。

    Returns:
        bool: 是否注册。
    """
    return (platform or "").strip().lower() in _ADAPTER_REGISTRY
