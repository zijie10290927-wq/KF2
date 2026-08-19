"""ConfigService — 配置管理服务。

统一管理 system_configs (KV) 和 model_configs，带 10 分钟 Redis 缓存。
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.redis import redis_client
from app.config.settings import settings
from app.models import ModelConfig, SystemConfig
from app.models.system_config import DEFAULT_SYSTEM_CONFIGS
from app.schemas.admin import FallbackConfig
from app.utils.crypto import decrypt_api_key, encrypt_api_key

logger = logging.getLogger(__name__)

# Redis 缓存键前缀与 TTL
_CONFIG_CACHE_PREFIX = "config:cache:"
_CONFIG_CACHE_TTL = 600  # 10 分钟
_MODELS_CACHE_KEY = "models:cache:all"
_MODELS_CACHE_TTL = 3600  # 1 小时


class ConfigService:
    """配置管理服务：KV 配置 + 模型配置，带 Redis 缓存。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # system_configs (KV)
    # ------------------------------------------------------------------ #
    async def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """读取 KV 配置：Redis 缓存 → DB → 默认值。"""
        cache_key = f"{_CONFIG_CACHE_PREFIX}{key}"
        # 1. Redis 缓存
        try:
            cached = await redis_client.get(cache_key)
            if cached is not None:
                return cached
        except Exception as e:  # pragma: no cover
            logger.warning("Redis get %s failed: %s", cache_key, e)

        # 2. DB 查询
        try:
            stmt = select(SystemConfig).where(SystemConfig.config_key == key)
            result = await self.db.execute(stmt)
            row = result.scalar_one_or_none()
            if row is not None:
                value = row.config_value
                await self._set_cache(cache_key, value)
                return value
        except Exception as e:  # pragma: no cover
            logger.error("DB get config %s failed: %s", key, e)

        # 3. 默认值
        return DEFAULT_SYSTEM_CONFIGS.get(key, default)

    async def get_int(self, key: str, default: int) -> int:
        v = await self.get(key)
        if v is None:
            return default
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    async def get_float(self, key: str, default: float) -> float:
        v = await self.get(key)
        if v is None:
            return default
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    async def get_bool(self, key: str, default: bool) -> bool:
        v = await self.get(key)
        if v is None:
            return default
        return v.strip().lower() in ("1", "true", "yes", "on")

    async def set(self, key: str, value: str, description: Optional[str] = None) -> None:
        """DB upsert + 删 Redis 缓存。"""
        stmt = select(SystemConfig).where(SystemConfig.config_key == key)
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            row = SystemConfig(
                config_key=key,
                config_value=value,
                description=description,
            )
            self.db.add(row)
        else:
            row.config_value = value
            if description is not None:
                row.description = description
        await self.db.commit()
        await self._invalidate_cache(key)

    async def get_fallback_message(self) -> FallbackConfig:
        """组装兜底配置。"""
        message = await self.get("fallback_message", DEFAULT_SYSTEM_CONFIGS["fallback_message"])
        show_transfer = await self.get_bool("show_transfer_button", True)
        show_phone = await self.get_bool("show_phone", True)
        phone = await self.get("phone_number", DEFAULT_SYSTEM_CONFIGS["phone_number"])
        return FallbackConfig(
            fallback_message=message or DEFAULT_SYSTEM_CONFIGS["fallback_message"],
            show_transfer_button=show_transfer,
            show_phone=show_phone,
            phone_number=phone or "",
        )

    # ------------------------------------------------------------------ #
    # model_configs
    # ------------------------------------------------------------------ #
    async def get_default_model(self) -> Optional[ModelConfig]:
        """返回 is_default=1 and enabled=1 的模型配置。"""
        stmt = select(ModelConfig).where(
            ModelConfig.is_default.is_(True),
            ModelConfig.enabled.is_(True),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_model_by_name(self, model_name: str) -> Optional[ModelConfig]:
        stmt = select(ModelConfig).where(ModelConfig.model_name == model_name)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_model_by_id(self, model_id: int) -> Optional[ModelConfig]:
        stmt = select(ModelConfig).where(ModelConfig.id == model_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_models(self, enabled_only: bool = False) -> list[ModelConfig]:
        """模型列表（带缓存）。"""
        try:
            cached = await redis_client.get(_MODELS_CACHE_KEY)
            if cached is not None:
                import json

                data = json.loads(cached)
                if enabled_only:
                    data = [m for m in data if m.get("enabled")]
                # 注意：缓存的是序列化 dict，此处直接返回 ORM 对象需要从 DB
                # 但为简化，缓存命中时仍走 DB（缓存主要用于减少 enabled 查询频率）
        except Exception:  # pragma: no cover
            pass

        stmt = select(ModelConfig).order_by(ModelConfig.id.desc())
        if enabled_only:
            stmt = stmt.where(ModelConfig.enabled.is_(True))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_decrypted_api_key(self, model: ModelConfig) -> str:
        """解密模型 API Key。"""
        try:
            return decrypt_api_key(model.api_key_encrypted)
        except ValueError:
            logger.error("Decrypt api_key failed for model %s", model.model_name)
            return ""

    async def create_model(
        self,
        model_name: str,
        api_base: str,
        api_key: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        enabled: bool = True,
        is_default: bool = False,
    ) -> ModelConfig:
        """创建模型配置（API Key 加密存储）。"""
        encrypted = encrypt_api_key(api_key)
        model = ModelConfig(
            model_name=model_name,
            api_base=api_base,
            api_key_encrypted=encrypted,
            temperature=temperature,
            max_tokens=max_tokens,
            enabled=enabled,
            is_default=is_default,
        )
        self.db.add(model)
        # 若设为默认，取消其他默认
        if is_default:
            await self._clear_other_defaults(model)
        await self.db.commit()
        await self.db.refresh(model)
        await self._invalidate_models_cache()
        return model

    async def _clear_other_defaults(self, exclude: ModelConfig) -> None:
        stmt = select(ModelConfig).where(
            ModelConfig.is_default.is_(True),
            ModelConfig.id != exclude.id if exclude.id else True,
        )
        result = await self.db.execute(stmt)
        for m in result.scalars().all():
            m.is_default = False

    async def update_model(
        self,
        model_id: int,
        model_name: Optional[str] = None,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        enabled: Optional[bool] = None,
        is_default: Optional[bool] = None,
    ) -> Optional[ModelConfig]:
        """更新模型配置；api_key 为空则保留原密文。

        Args:
            model_id: 模型 ID。
            model_name: 模型名称（可选）。
            api_base: API 基址（可选）。
            api_key: 明文 API Key（可选；None 表示不修改）。
            temperature: 温度（可选）。
            max_tokens: 最大 token（可选）。
            enabled: 是否启用（可选）。
            is_default: 是否设为默认（可选）。

        Returns:
            Optional[ModelConfig]: 更新后的模型对象；不存在返回 None。
        """
        model = await self.get_model_by_id(model_id)
        if model is None:
            return None

        if model_name is not None:
            model.model_name = model_name
        if api_base is not None:
            model.api_base = api_base
        if api_key:
            model.api_key_encrypted = encrypt_api_key(api_key)
        if temperature is not None:
            model.temperature = temperature
        if max_tokens is not None:
            model.max_tokens = max_tokens
        if enabled is not None:
            model.enabled = enabled
        if is_default is True:
            await self._clear_other_defaults(model)
            model.is_default = True
        elif is_default is False:
            model.is_default = False

        await self.db.commit()
        await self.db.refresh(model)
        await self._invalidate_models_cache()
        return model

    async def delete_model(self, model_id: int) -> bool:
        """删除模型配置。

        Args:
            model_id: 模型 ID。

        Returns:
            bool: 是否删除成功。
        """
        model = await self.get_model_by_id(model_id)
        if model is None:
            return False
        await self.db.delete(model)
        await self.db.commit()
        await self._invalidate_models_cache()
        return True

    async def toggle_model(self, model_id: int, enabled: bool) -> Optional[ModelConfig]:
        """启用/禁用模型。

        Args:
            model_id: 模型 ID。
            enabled: True 启用，False 禁用。

        Returns:
            Optional[ModelConfig]: 更新后的模型；不存在返回 None。
        """
        model = await self.get_model_by_id(model_id)
        if model is None:
            return None
        model.enabled = enabled
        await self.db.commit()
        await self.db.refresh(model)
        await self._invalidate_models_cache()
        return model

    async def set_default_model(self, model_id: int) -> Optional[ModelConfig]:
        """将指定模型设为默认（取消其他默认）。

        Args:
            model_id: 模型 ID。

        Returns:
            Optional[ModelConfig]: 更新后的模型；不存在返回 None。
        """
        model = await self.get_model_by_id(model_id)
        if model is None:
            return None
        await self._clear_other_defaults(model)
        model.is_default = True
        model.enabled = True  # 默认模型必须启用
        await self.db.commit()
        await self.db.refresh(model)
        await self._invalidate_models_cache()
        return model

    # ------------------------------------------------------------------ #
    # 缓存辅助
    # ------------------------------------------------------------------ #
    async def _set_cache(self, key: str, value: str) -> None:
        try:
            await redis_client.set(key, value, ex=_CONFIG_CACHE_TTL)
        except Exception as e:  # pragma: no cover
            logger.warning("Redis set %s failed: %s", key, e)

    async def _invalidate_cache(self, key: str) -> None:
        try:
            await redis_client.delete(f"{_CONFIG_CACHE_PREFIX}{key}")
        except Exception:  # pragma: no cover
            pass

    async def _invalidate_models_cache(self) -> None:
        try:
            await redis_client.delete(_MODELS_CACHE_KEY)
        except Exception:  # pragma: no cover
            pass

    # ------------------------------------------------------------------ #
    # 默认模型兜底（DB 无配置时返回环境变量默认值）
    # ------------------------------------------------------------------ #
    async def get_default_or_env_model(self) -> Optional[ModelConfig]:
        """优先 DB 默认模型，无则返回 None（由 LLMService 用 env 兜底）。"""
        return await self.get_default_model()
