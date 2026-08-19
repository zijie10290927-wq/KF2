"""直接插入 admin/demo 用户（绕过 AuthService 因为它的 fallback 误导 exists 判断）。"""
import asyncio
import os
import sys
import bcrypt

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ai-customer-backend"))
os.chdir(BACKEND_DIR)
sys.path.insert(0, BACKEND_DIR)

from dotenv import load_dotenv
load_dotenv()

from app.config.database import AsyncSessionLocal
from sqlalchemy import text


def _h(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def main():
    admin_hash = _h("admin123")
    demo_hash = _h("demo123")
    now_sql = "NOW()"

    async with AsyncSessionLocal() as db:
        # 先清空再插入，保证幂等
        await db.execute(text("DELETE FROM users WHERE username IN ('admin', 'demo')"))

        await db.execute(
            text(f"""
            INSERT INTO users (username, password_hash, role, status, created_at, updated_at)
            VALUES ('admin', :h1, 'admin', 1, {now_sql}, {now_sql}),
                   ('demo',  :h2, 'user',  1, {now_sql}, {now_sql})
            """),
            {"h1": admin_hash, "h2": demo_hash},
        )
        await db.commit()
        print("✅ 已写入 admin/admin123 与 demo/demo123 到 users 表")

        r = await db.execute(text("SELECT id, username, role, LEFT(password_hash, 20) FROM users"))
        for row in r.fetchall():
            print(" -", row)


if __name__ == "__main__":
    asyncio.run(main())
