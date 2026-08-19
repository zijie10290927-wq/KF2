"""渠道适配层 (Channel Adapter Layer)。

作为第三方客服平台（智齿/七鱼/Udesk/Chatwoot/Dify 等）与 Agent 核心之间的桥梁，
统一处理：
1. Webhook 接收与签名验证
2. 外部会话 ↔ 内部会话映射
3. SSE 事件 → 平台原生响应格式转换
4. OpenAI 兼容端点反向暴露
5. JS Widget SDK 嵌入服务端

对外暴露：
- BaseAdapter: 适配器基类
- SessionMapper: 会话映射器
- get_adapter(): 平台适配器工厂
"""

from app.adapters.base import BaseAdapter
from app.adapters.session_mapper import SessionMapper

__all__ = ["BaseAdapter", "SessionMapper"]
