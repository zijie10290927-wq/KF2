"""配置管理路由 /admin/config/*（需 admin 角色）。

- GET    /admin/config/model                       模型配置列表
- POST   /admin/config/model                       新增模型配置
- PUT    /admin/config/model/{model_id}            更新模型配置
- DELETE /admin/config/model/{model_id}            删除模型配置
- PATCH  /admin/config/model/{model_id}/toggle     启用/禁用模型
- PATCH  /admin/config/model/{model_id}/default    设为默认模型
- GET    /admin/config/fallback-message           读取兜底话术配置
- PUT    /admin/config/fallback-message           更新兜底话术配置
- GET    /admin/config/system/{key}                读取通用 KV 配置
- PUT    /admin/config/system/{key}                更新通用 KV 配置
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel

from app.exceptions import NotFoundError
from app.models import User
from app.schemas.admin import (
    FallbackConfig,
    FallbackMessageUpdate,
    ModelConfigCreate,
    ModelConfigOut,
    ModelConfigUpdate,
)
from app.schemas.common import ApiResponse
from app.services.config_service import ConfigService
from app.services.deps import get_admin_user, get_config_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/config", tags=["B端-配置管理"])


def _model_to_out(model) -> dict:
    """将 ModelConfig ORM 对象序列化为输出字典（不含 api_key）。

    Args:
        model: ModelConfig ORM 对象。

    Returns:
        dict: ModelConfigOut 兼容字典。
    """
    return ModelConfigOut(
        id=model.id,
        model_name=model.model_name,
        api_base=model.api_base,
        temperature=model.temperature,
        max_tokens=model.max_tokens,
        enabled=bool(model.enabled),
        is_default=bool(model.is_default),
        created_at=model.created_at,
        updated_at=model.updated_at,
    ).model_dump(mode="json")


# ------------------------------------------------------------------ #
# 模型配置 CRUD
# ------------------------------------------------------------------ #
@router.get("/model", response_model=ApiResponse, summary="模型配置列表")
async def list_models(
    enabled_only: bool = False,
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """获取所有模型配置（不含 API Key）。"""
    models = await config_service.list_models(enabled_only=enabled_only)
    return ApiResponse.success(
        data=[_model_to_out(m) for m in models]
    )


@router.post("/model", response_model=ApiResponse, summary="新增模型配置")
async def create_model(
    payload: ModelConfigCreate,
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """新增模型配置（API Key 经 Fernet 加密存储）。"""
    try:
        model = await config_service.create_model(
            model_name=payload.model_name,
            api_base=payload.api_base,
            api_key=payload.api_key,
            temperature=float(payload.temperature),
            max_tokens=payload.max_tokens,
            enabled=payload.enabled,
            is_default=payload.is_default,
        )
    except Exception as e:
        # 唯一键冲突等
        logger.error("Create model failed: %s", e)
        return ApiResponse.error(message=f"新增失败: {e}")
    return ApiResponse.success(
        data=_model_to_out(model), message="模型配置已新增"
    )


@router.put("/model/{model_id}", response_model=ApiResponse, summary="更新模型配置")
async def update_model(
    model_id: int = Path(..., ge=1),
    payload: ModelConfigUpdate = ...,
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """更新模型配置；api_key 为空则保留原密文。"""
    model = await config_service.update_model(
        model_id=model_id,
        model_name=payload.model_name,
        api_base=payload.api_base,
        api_key=payload.api_key or None,
        temperature=float(payload.temperature) if payload.temperature is not None else None,
        max_tokens=payload.max_tokens,
        enabled=payload.enabled,
        is_default=payload.is_default,
    )
    if model is None:
        raise NotFoundError("模型不存在")
    return ApiResponse.success(data=_model_to_out(model), message="模型配置已更新")


@router.delete("/model/{model_id}", response_model=ApiResponse, summary="删除模型配置")
async def delete_model(
    model_id: int = Path(..., ge=1),
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """删除模型配置。"""
    deleted = await config_service.delete_model(model_id)
    if not deleted:
        raise NotFoundError("模型不存在")
    return ApiResponse.success(message="模型配置已删除")


class TogglePayload(BaseModel):
    """启用/禁用请求体。"""

    enabled: bool


@router.patch("/model/{model_id}/toggle", response_model=ApiResponse, summary="启用/禁用模型")
async def toggle_model(
    model_id: int = Path(..., ge=1),
    payload: TogglePayload = ...,
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """启用或禁用模型。"""
    model = await config_service.toggle_model(model_id, payload.enabled)
    if model is None:
        raise NotFoundError("模型不存在")
    return ApiResponse.success(data=_model_to_out(model), message="状态已更新")


@router.patch("/model/{model_id}/default", response_model=ApiResponse, summary="设为默认模型")
async def set_default_model(
    model_id: int = Path(..., ge=1),
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """将指定模型设为默认（自动取消其他默认）。"""
    model = await config_service.set_default_model(model_id)
    if model is None:
        raise NotFoundError("模型不存在")
    return ApiResponse.success(data=_model_to_out(model), message="已设为默认模型")


# ------------------------------------------------------------------ #
# 兜底话术
# ------------------------------------------------------------------ #
@router.get("/fallback-message", response_model=ApiResponse, summary="读取兜底话术配置")
async def get_fallback_message(
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """读取兜底话术、转人工/电话按钮、电话号码。"""
    config: FallbackConfig = await config_service.get_fallback_message()
    return ApiResponse.success(data=config.model_dump(mode="json"))


@router.put("/fallback-message", response_model=ApiResponse, summary="更新兜底话术配置")
async def update_fallback_message(
    payload: FallbackMessageUpdate,
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """更新兜底话术配置（仅写入非空字段）。"""
    if payload.message is not None:
        await config_service.set("fallback_message", payload.message)
    if payload.show_transfer_button is not None:
        await config_service.set(
            "show_transfer_button", "true" if payload.show_transfer_button else "false"
        )
    if payload.show_phone is not None:
        await config_service.set(
            "show_phone", "true" if payload.show_phone else "false"
        )
    if payload.phone_number is not None:
        await config_service.set("phone_number", payload.phone_number)

    config: FallbackConfig = await config_service.get_fallback_message()
    return ApiResponse.success(data=config.model_dump(mode="json"), message="兜底配置已更新")


# ------------------------------------------------------------------ #
# 通用 KV 配置
# ------------------------------------------------------------------ #
class KVUpdate(BaseModel):
    """通用 KV 更新请求体。"""

    value: str
    description: Optional[str] = None


@router.get("/system/{key}", response_model=ApiResponse, summary="读取 KV 配置")
async def get_system_config(
    key: str = Path(..., min_length=1, max_length=128),
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """按 key 读取 KV 配置（Redis 缓存 → DB → 默认值）。"""
    value = await config_service.get(key)
    return ApiResponse.success(data={"key": key, "value": value})


@router.put("/system/{key}", response_model=ApiResponse, summary="更新 KV 配置")
async def set_system_config(
    key: str = Path(..., min_length=1, max_length=128),
    payload: KVUpdate = ...,
    config_service: ConfigService = Depends(get_config_service),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """按 key 更新 KV 配置（DB upsert + 删 Redis 缓存）。"""
    await config_service.set(key, payload.value, description=payload.description)
    return ApiResponse.success(
        data={"key": key, "value": payload.value}, message="配置已更新"
    )
