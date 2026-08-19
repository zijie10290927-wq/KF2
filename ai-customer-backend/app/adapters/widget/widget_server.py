"""Widget 服务端 — /api/v1/widget。

职责：
1. GET  /widget/embed.js       返回 Widget JS SDK（1h 浏览器缓存）
2. GET  /widget/chat           返回 iframe 聊天页面（需 app_key）
3. POST /widget/session        创建 Widget 匿名会话（widget_xxxx 格式）

鉴权：X-Widget-App-Key 头或 app_key query 参数，比对 settings.WIDGET_APP_KEYS
CORS：独立 allow_origins=["*"] + expose_headers=["X-Session-Id"]
"""

import logging
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Header, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from app.config.settings import settings
from app.schemas.common import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/widget", tags=["渠道适配-Widget"])

# Widget 会话缓存（session_id -> 创建时间，TTL 86400）
_widget_sessions: dict[str, float] = {}
_WIDGET_SESSION_TTL = 86400  # 24h


def _verify_app_key(app_key: Optional[str]) -> bool:
    """校验 app_key。

    Args:
        app_key: 待校验的 key。

    Returns:
        bool: 是否合法。
    """
    if not settings.WIDGET_ENABLED:
        return False
    keys = settings.widget_app_keys_list
    if not keys:
        logger.warning("WIDGET_APP_KEYS not configured, allow all (dev only)")
        return True
    if not app_key:
        return False
    return app_key in keys


def _extract_app_key(
    request: Request, x_widget_app_key: Optional[str], app_key_query: Optional[str]
) -> Optional[str]:
    """从多个来源提取 app_key。"""
    if x_widget_app_key:
        return x_widget_app_key.strip()
    if app_key_query:
        return app_key_query.strip()
    return None


@router.get("/embed.js", response_class=PlainTextResponse, summary="返回 Widget JS SDK")
async def widget_embed_js() -> PlainTextResponse:
    """返回 chat-widget.js 内容（带 1 小时浏览器缓存）。

    实际生产中此文件应预先生成并缓存，这里直接读取磁盘文件。
    """
    import os
    from pathlib import Path

    sdk_path = (
        Path(__file__).parent / "static" / "chat-widget.js"
    )
    try:
        if not sdk_path.exists():
            return PlainTextResponse(
                content="// chat-widget.js not found", media_type="application/javascript"
            )
        content = sdk_path.read_text(encoding="utf-8")
        return PlainTextResponse(
            content=content,
            media_type="application/javascript",
            headers={
                "Cache-Control": "public, max-age=3600",
                "Access-Control-Allow-Origin": "*",
            },
        )
    except Exception as e:
        logger.error("Read widget sdk failed: %s", e)
        return PlainTextResponse(
            content=f"// load error: {e}", media_type="application/javascript"
        )


@router.get("/chat", response_class=HTMLResponse, summary="iframe 聊天页面")
async def widget_chat_page(
    request: Request,
    app_key: Optional[str] = Query(default=None, description="Widget app key"),
) -> HTMLResponse:
    """返回 iframe 嵌入用的聊天页面。

    需要通过 app_key query 参数验证。
    """
    if not _verify_app_key(app_key):
        return HTMLResponse(
            content="<html><body><h2>Invalid app_key</h2></body></html>",
            status_code=403,
        )

    # 简化版：返回一个最小可用的聊天 HTML（实际可挂载完整 Vue 应用）
    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI 智能客服</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f7fa; height: 100vh; display: flex; flex-direction: column; }
.header { background: #409EFF; color: #fff; padding: 16px; font-size: 16px; font-weight: 500; }
.messages { flex: 1; overflow-y: auto; padding: 16px; }
.msg { margin-bottom: 12px; max-width: 80%; padding: 10px 14px; border-radius: 12px; word-wrap: break-word; white-space: pre-wrap; }
.msg.user { background: #409EFF; color: #fff; margin-left: auto; }
.msg.bot { background: #fff; color: #303133; border: 1px solid #e4e7ed; }
.input-area { display: flex; padding: 12px; border-top: 1px solid #e4e7ed; background: #fff; }
.input-area input { flex: 1; padding: 10px 14px; border: 1px solid #dcdfe6; border-radius: 8px; outline: none; }
.input-area button { margin-left: 8px; padding: 0 20px; background: #409EFF; color: #fff; border: none; border-radius: 8px; cursor: pointer; }
.input-area button:hover { background: #66b1ff; }
</style>
</head>
<body>
<div class="header">AI 智能客服</div>
<div class="messages" id="msgBox">
  <div class="msg bot">您好！我是AI智能客服，请问有什么可以帮您？</div>
</div>
<div class="input-area">
  <input id="msgInput" type="text" placeholder="请输入您的问题..." autocomplete="off"/>
  <button id="sendBtn" onclick="sendMessage()">发送</button>
</div>
<script>
let sessionId = null;
async function createSession() {
  try {
    const res = await fetch('/api/v1/widget/session', { method: 'POST' });
    const data = await res.json();
    if (data.code === 0 && data.data) sessionId = data.data.session_id;
  } catch(e) { console.error('create session failed', e); }
}
async function sendMessage() {
  const input = document.getElementById('msgInput');
  const msg = input.value.trim();
  if (!msg) return;
  if (!sessionId) await createSession();
  addMessage(msg, 'user');
  input.value = '';
  const base = (import.meta && import.meta.env && import.meta.env.VITE_API_BASE_URL) || '';
  try {
    const resp = await fetch(base + '/api/v1/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, message: msg, history: [] })
    });
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let botEl = addMessage('', 'bot');
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\\n');
      buffer = lines.pop();
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const d = JSON.parse(line.slice(6));
            if (d.content) botEl.textContent += d.content;
          } catch(e) {}
        }
      }
    }
  } catch(e) {
    addMessage('请求失败: ' + e.message, 'bot');
  }
}
function addMessage(text, cls) {
  const box = document.getElementById('msgBox');
  const el = document.createElement('div');
  el.className = 'msg ' + cls;
  el.textContent = text;
  box.appendChild(el);
  box.scrollTop = box.scrollHeight;
  return el;
}
document.getElementById('msgInput').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') sendMessage();
});
</script>
</body>
</html>"""
    return HTMLResponse(content=html, headers={"X-Frame-Options": "SAMEORIGIN"})


@router.post("/session", response_model=ApiResponse, summary="创建 Widget 匿名会话")
async def create_widget_session(
    request: Request,
    x_widget_app_key: Optional[str] = Header(default=None, alias="X-Widget-App-Key"),
    app_key: Optional[str] = Query(default=None, description="Widget app key"),
) -> ApiResponse:
    """创建 Widget 匿名会话，返回 widget_xxxx 格式 session_id。

    Returns:
        ApiResponse: data.session_id 为新生成的 widget 会话 ID。
    """
    app_key_val = _extract_app_key(request, x_widget_app_key, app_key)
    if not _verify_app_key(app_key_val):
        return JSONResponse(
            status_code=401,
            content={
                "code": 401,
                "message": "Invalid or missing app_key",
                "data": None,
            },
            headers={"X-Session-Id": ""},
        )

    # 生成 widget_xxxx 格式 session_id
    session_id = f"widget_{uuid.uuid4().hex[:20]}"

    # 缓存（带 TTL 清理）
    now = time.time()
    # 顺便清理过期项
    if len(_widget_sessions) > 1000:
        expired = [k for k, t in _widget_sessions.items() if now - t > _WIDGET_SESSION_TTL]
        for k in expired:
            _widget_sessions.pop(k, None)
    _widget_sessions[session_id] = now

    return JSONResponse(
        status_code=200,
        content={
            "code": 0,
            "message": "success",
            "data": {"session_id": session_id, "ttl": _WIDGET_SESSION_TTL},
        },
        headers={"X-Session-Id": session_id},
    )


@router.get("/health", response_model=ApiResponse, summary="Widget 健康检查")
async def widget_health() -> ApiResponse:
    """Widget 服务健康检查。"""
    return ApiResponse.success(
        data={
            "enabled": settings.WIDGET_ENABLED,
            "app_keys_configured": len(settings.widget_app_keys_list),
            "active_sessions": len(_widget_sessions),
        }
    )
