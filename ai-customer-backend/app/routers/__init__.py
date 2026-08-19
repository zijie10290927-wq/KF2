"""路由层：统一导出全部 APIRouter。"""

from app.adapters.openai_compat import router as openai_compat_router
from app.adapters.webhook_router import router as webhook_router
from app.adapters.widget.widget_server import router as widget_router
from app.routers.admin_channel import router as admin_channel_router
from app.routers.admin_chat_logs import router as admin_chat_logs_router
from app.routers.admin_config import router as admin_config_router
from app.routers.admin_knowledge import router as admin_knowledge_router
from app.routers.admin_users import router as admin_users_router
from app.routers.auth import router as auth_router
from app.routers.chat import router as chat_router

__all__ = [
    "auth_router",
    "chat_router",
    "admin_knowledge_router",
    "admin_config_router",
    "admin_chat_logs_router",
    "admin_users_router",
    "admin_channel_router",
    "webhook_router",
    "openai_compat_router",
    "widget_router",
]
