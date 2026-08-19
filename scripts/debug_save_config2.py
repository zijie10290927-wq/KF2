# -*- coding: utf-8 -*-
"""在后端工作目录下运行，捕获 save_config 的详细异常。"""
import asyncio
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "ai-customer-backend"
os.chdir(BACKEND_DIR)  # 确保 .env 被正确加载

import sys
sys.path.insert(0, str(BACKEND_DIR))


async def main():
    """主调试函数。"""
    from app.config.database import AsyncSessionLocal
    from app.schemas.webhook import ChannelConfigDTO
    from app.services.channel_admin_service import ChannelAdminService
    from app.config.settings import settings
    print(f"运行目录={os.getcwd()}")
    print(f"MYSQL_PASSWORD 已设置={bool(settings.MYSQL_PASSWORD)} 长度={len(settings.MYSQL_PASSWORD)}")
    print(f"DB URL 预览: {settings.async_database_url.split('@')[0]}@...")

    # 1. 调用 list_configs 预热
    async with AsyncSessionLocal() as db:
        svc = ChannelAdminService(db)
        cfgs = await svc.list_configs()
        print(f"\n[list_configs] 条数={len(cfgs)}:")
        for c in cfgs:
            print(f"  - platform={c.platform} name={c.display_name} enabled={c.enabled}")

    # 2. 调用 save_config - 用一个新的 platform id 避免冲突（已存在 generic/zhibo，用 test_script）
    async with AsyncSessionLocal() as db:
        svc = ChannelAdminService(db)
        cfg = ChannelConfigDTO(
            platform="test_script",
            display_name="调试脚本专用渠道",
            enabled=False,
            api_token="apit_123",
            webhook_secret="whsec_456",
            app_key="appk_789",
            api_base="https://example.com",
            remark="调试脚本创建，测试完成后删除",
        )
        try:
            saved = await svc.save_config(cfg)
            print("\n✅ save_config 成功保存:")
            print(f"   platform={saved.platform}")
            print(f"   display_name={saved.display_name}")
            print(f"   enabled={saved.enabled}")
            print(f"   api_token(掩码)={saved.api_token!r}")
            print(f"   webhook_secret(掩码)={saved.webhook_secret!r}")
            print(f"   app_key={saved.app_key!r}")
            print(f"   api_base={saved.api_base!r}")
            print(f"   remark={saved.remark!r}")
        except Exception as e:
            print("\n❌ save_config 失败:")
            print(f"   异常类型: {type(e).__module__}.{type(e).__name__}")
            print(f"   异常内容: {e}")
            import traceback
            print("\n=== 完整 Traceback ===")
            traceback.print_exc()
            return 1

    # 3. 验证落库 - 再读一次
    async with AsyncSessionLocal() as db:
        svc = ChannelAdminService(db)
        cfgs2 = await svc.list_configs()
        found = [c for c in cfgs2 if c.platform == "test_script"]
        if found:
            c = found[0]
            print(f"\n✅ 落库确认: test_script 存在")
            print(f"   enabled={c.enabled}  remark={c.remark!r}  app_key={c.app_key!r}")
        else:
            print(f"\n❌ 落库失败: test_script 不在配置列表中")
            return 1
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
