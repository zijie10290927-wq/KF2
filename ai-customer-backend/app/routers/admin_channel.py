"""管理后台渠道管理 API — /api/v1/admin/channels。

核心接口：
- GET    /overview                       渠道总览统计
- GET    /configs                        渠道配置列表
- POST   /configs                        保存/更新渠道配置
- PUT    /{platform}/status              启用/停用渠道
- POST   /{platform}/test                测试渠道连接
- GET    /conversations                  会话记录列表（含筛选 + 分页）
- GET    /conversations/{session_id}/messages   会话消息详情
- GET    /webhook-logs                   Webhook 请求日志
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.models import User
from app.schemas.common import ApiResponse
from app.schemas.webhook import ChannelConfigDTO
from app.services.channel_admin_service import ChannelAdminService
from app.services.deps import get_admin_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/channels", tags=["管理后台-渠道管理"])


def _get_service(db: AsyncSession = Depends(get_db)) -> ChannelAdminService:
    """依赖注入 ChannelAdminService。"""
    return ChannelAdminService(db)


@router.get("/overview", response_model=ApiResponse, summary="渠道总览统计")
async def channel_overview(
    service: ChannelAdminService = Depends(_get_service),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """获取渠道总览统计（今日消息数/活跃渠道/平均响应时间/转人工率）。"""
    overview = await service.get_overview()
    return ApiResponse.success(data=overview.model_dump())


@router.get("/configs", response_model=ApiResponse, summary="获取渠道配置列表")
async def list_channel_configs(
    service: ChannelAdminService = Depends(_get_service),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """获取所有渠道配置（敏感字段已掩码）。"""
    configs = await service.list_configs()
    return ApiResponse.success(
        data=[c.model_dump() for c in configs]
    )


@router.post("/configs", response_model=ApiResponse, summary="保存/更新渠道配置")
async def save_channel_config(
    config: ChannelConfigDTO,
    service: ChannelAdminService = Depends(_get_service),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """保存或更新渠道配置（API Token/Webhook Secret 会加密存储）。"""
    saved = await service.save_config(config)
    return ApiResponse.success(data=saved.model_dump(), message="配置已保存")


@router.put("/{platform}/status", response_model=ApiResponse, summary="启用/停用渠道")
async def toggle_channel_status(
    platform: str = Path(..., description="平台标识"),
    enabled: bool = Query(..., description="True 启用，False 禁用"),
    service: ChannelAdminService = Depends(_get_service),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """启用或停用指定渠道。"""
    ok = await service.toggle_status(platform, enabled)
    return ApiResponse.success(
        data={"platform": platform, "enabled": enabled, "updated": ok},
        message=f"渠道 {platform} 已{'启用' if enabled else '停用'}",
    )


@router.post("/{platform}/test", response_model=ApiResponse, summary="测试渠道连接")
async def test_channel_connection(
    platform: str = Path(..., description="平台标识"),
    service: ChannelAdminService = Depends(_get_service),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """测试渠道连接是否正常。"""
    result = await service.test_connection(platform)
    if result.get("success"):
        return ApiResponse.success(data=result, message=result.get("message", "测试通过"))
    return ApiResponse.error(
        message=result.get("message", "测试失败"), code=-1, data=result
    )


@router.get("/conversations", response_model=ApiResponse, summary="会话记录列表")
async def list_conversations(
    platform: Optional[str] = Query(default=None, description="平台筛选"),
    status: Optional[str] = Query(default=None, description="状态筛选"),
    keyword: Optional[str] = Query(default=None, description="关键词"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    service: ChannelAdminService = Depends(_get_service),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """查询渠道会话记录列表（支持筛选 + 分页）。"""
    records, total = await service.list_conversations(
        platform=platform, status=status, keyword=keyword,
        page=page, page_size=page_size,
    )
    items = []
    for r in records:
        items.append(
            {
                "id": r.id,
                "platform": r.platform,
                "external_session_id": r.external_session_id,
                "external_user_id": r.external_user_id,
                "external_user_name": r.external_user_name,
                "internal_session_id": r.internal_session_id,
                "channel_type": r.channel_type,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
        )
    return ApiResponse.success(
        data={"items": items, "total": total, "page": page, "page_size": page_size}
    )


@router.get(
    "/conversations/{session_id}/messages",
    response_model=ApiResponse,
    summary="会话消息详情",
)
async def get_conversation_messages(
    session_id: str,
    service: ChannelAdminService = Depends(_get_service),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """查询指定会话的消息详情（按时间正序）。"""
    messages = await service.get_conversation_messages(session_id)
    items = []
    for m in messages:
        items.append(
            {
                "id": m.id,
                "message_id": m.message_id,
                "session_id": m.session_id,
                "role": m.role,
                "content": m.content,
                "intent": m.intent,
                "sources": m.sources,
                "model_used": m.model_used,
                "tokens_used": m.tokens_used,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
        )
    return ApiResponse.success(data=items)


@router.get("/webhook-logs", response_model=ApiResponse, summary="Webhook 请求日志")
async def list_webhook_logs(
    platform: Optional[str] = Query(default=None, description="平台筛选"),
    status: Optional[str] = Query(default=None, description="状态筛选"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    service: ChannelAdminService = Depends(_get_service),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """查询 Webhook 请求日志（支持筛选 + 分页）。"""
    logs, total = await service.list_webhook_logs(
        platform=platform, status=status, page=page, page_size=page_size
    )
    return ApiResponse.success(
        data={"items": logs, "total": total, "page": page, "page_size": page_size}
    )
