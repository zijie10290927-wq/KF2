# -*- coding: utf-8 -*-
"""调试 save_config 失败原因，模拟调用链路。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ai-customer-backend"))

from app.schemas.webhook import ChannelConfigDTO


async def main():
    """模拟 save_config 调用链，捕获详细异常。"""
    from app.config.database import AsyncSessionLocal
    from app.services.channel_admin_service import ChannelAdminService
    from app.utils.crypto import encrypt_api_key

    # 1. 先测试加密
    try:
        enc = encrypt_api_key("test_secret_123")
        print("✅ encrypt_api_key('test_secret_123') =", enc[:40], "...")
    except Exception as e:
        print("❌ encrypt_api_key 失败:", type(e).__name__, e)
        import traceback; traceback.print_exc()
        return 1

    # 2. 调用 save_config
    async with AsyncSessionLocal() as db:
        svc = ChannelAdminService(db)
        cfg = ChannelConfigDTO(
            platform="generic",
            display_name="测试渠道-debug脚本",
            enabled=True,
            webhook_secret="test_secret_123",
            app_key="test_app_key_001",
            api_token="test_token_xxx",
            remark="debug脚本创建",
        )
        try:
            saved = await svc.save_config(cfg)
            print("✅ save_config 成功:")
            print(f"   platform={saved.platform}")
            print(f"   display_name={saved.display_name}")
            print(f"   enabled={saved.enabled}")
            print(f"   api_token(掩码)={saved.api_token!r}")
            print(f"   webhook_secret(掩码)={saved.webhook_secret!r}")
        except Exception as e:
            print("❌ save_config 失败:", type(e).__name__, e)
            import traceback; traceback.print_exc()
            return 1
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
