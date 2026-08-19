# -*- coding: utf-8 -*-
"""插入渠道会话 + 消息测试数据（开发环境验证用）。

本脚本创建 2 条 ChannelSession 映射（智齿科技/通用接入），
以及 2 条 ChatMessage 时间线消息，用于验证管理后台「会话记录」Tab 的
列表展示、筛选、详情抽屉功能。
运行方式：
  .venv\Scripts\python.exe ..\scripts\seed_conversation_testdata.py
"""
import asyncio
import os
import sys
import uuid

os.chdir(os.path.dirname(__file__))  # scripts/
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ai-customer-backend"))
os.chdir(BACKEND_DIR)
sys.path.insert(0, BACKEND_DIR)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

from sqlalchemy import select, and_  # noqa: E402
from app.config.database import AsyncSessionLocal  # noqa: E402
from app.models import ChannelSession, ChatMessage, ChatSession  # noqa: E402


async def main() -> None:
    """主入口：查 ChatSession → 建 ChannelSession ×2 → 建 ChatMessage ×2。"""
    async with AsyncSessionLocal() as db:
        # 1. pick/create internal chat_session
        r = await db.execute(select(ChatSession).limit(1))
        cs = r.scalars().first()
        if cs:
            internal_id = cs.session_id
            print(f"[info] 复用已有 chat_session: {internal_id}")
        else:
            internal_id = str(uuid.uuid4())
            db.add(ChatSession(
                session_id=internal_id,
                user_id=3,
                title="渠道会话测试 - 演示对话",
                status="active",
            ))
            await db.commit()
            print(f"[info] 新建 chat_session: {internal_id}")

        # 2. 渠道会话映射（2 条）
        specs = [
            dict(platform="zhibo",
                 external_session_id="EX-ZB-DEMO-001",
                 external_user_id="zhibo_user_001",
                 external_user_name="王小智",
                 channel_type="api", status="active"),
            dict(platform="generic",
                 external_session_id="EX-GE-DEMO-999",
                 external_user_id="ext_user_88",
                 external_user_name="李通用",
                 channel_type="webhook", status="active"),
        ]
        for s in specs:
            rr = await db.execute(
                select(ChannelSession).where(and_(
                    ChannelSession.platform == s["platform"],
                    ChannelSession.external_session_id == s["external_session_id"],
                ))
            )
            if rr.scalars().first():
                print(f"[skip] 已存在 {s['platform']}/{s['external_session_id']}")
                continue
            db.add(ChannelSession(internal_session_id=internal_id, **s))
            print(f"[insert] ChannelSession {s['platform']}/{s['external_session_id']}")
        await db.commit()

        # 3. 消息时间线（2 条：用户 + 助手）；message_id 不能为空，必须显式给 UUID
        rr3 = await db.execute(select(ChatMessage).where(
            ChatMessage.session_id == internal_id
        ).limit(1))
        if rr3.scalars().first():
            print("[skip] messages already exist for session")
        else:
            db.add_all([
                ChatMessage(
                    message_id=str(uuid.uuid4()),
                    session_id=internal_id,
                    role="user",
                    content="你好，请问如何使用AI作图？有什么入门建议吗？",
                    intent="faq_howto",
                    sources=[],
                    model_used="demo-insert",
                    tokens_used=8,
                ),
                ChatMessage(
                    message_id=str(uuid.uuid4()),
                    session_id=internal_id,
                    role="assistant",
                    content="您好！欢迎使用AI出图助手😊 您可以用自然语言描述想要的画面，例如「夕阳下的橘猫，油画风格」，然后点击发送即可生成图片。想了解更多？输入「帮助」查看使用指南。",
                    intent="faq_howto_answer",
                    sources=[],
                    model_used="qwen2.5-7b-instruct",
                    tokens_used=56,
                ),
            ])
            await db.commit()
            print("[insert] 2 ChatMessage rows (timeline)")

    print("[done] seed_conversation_testdata finished OK")


if __name__ == "__main__":
    asyncio.run(main())
