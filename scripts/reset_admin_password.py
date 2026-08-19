"""临时脚本：重置 admin/demo 密码为 admin123/demo123。"""
import asyncio
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ai-customer-backend"))
os.chdir(BACKEND_DIR)
sys.path.insert(0, BACKEND_DIR)

from dotenv import load_dotenv
load_dotenv()

from app.config.database import AsyncSessionLocal
import bcrypt
from sqlalchemy import text


def _bcrypt_hash(pw: str) -> str:
    """直接使用 bcrypt 生成哈希（兼容 passlib bcrypt 格式：$2b$ 前缀）。"""
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def main():
    new_admin_hash = _bcrypt_hash("admin123")
    new_demo_hash = _bcrypt_hash("demo123")

    async with AsyncSessionLocal() as db:
        r = await db.execute(text("SELECT id, username, role FROM users"))
        rows = r.fetchall()
        print("[现状] users 表内容:", rows)

        await db.execute(
            text("UPDATE users SET password_hash = :h WHERE username = 'admin'"),
            {"h": new_admin_hash},
        )
        await db.execute(
            text("UPDATE users SET password_hash = :h WHERE username = 'demo'"),
            {"h": new_demo_hash},
        )
        await db.commit()
        print("✅ 已重置 admin -> admin123, demo -> demo123")

        r2 = await db.execute(text("SELECT username, LEFT(password_hash, 30) FROM users"))
        print("[验证] 更新后用户密码哈希:", r2.fetchall())


if __name__ == "__main__":
    asyncio.run(main())
