"""B6 回归测试：配置编辑空密钥字段不得清空已有密钥。

契约（前后端共同保证「留空则不修改」）：
- ModelConfig.update_model(api_key="")  → 保留原密文
- ChannelAdminService.save_config(api_token="" / webhook_secret="") → 保留原密文
- 掩码值（*** 开头）回传 → 同样不覆盖真实密钥
"""

from app.schemas.webhook import ChannelConfigDTO
from app.services.channel_admin_service import ChannelAdminService
from app.services.config_service import ConfigService
from app.utils.crypto import decrypt_api_key, encrypt_api_key


class TestModelConfigEmptyKeyKept:
    async def test_update_with_empty_api_key_keeps_existing(self, db_session):
        svc = ConfigService(db_session)
        model = await svc.create_model("test-model", "https://api.example.com", "sk-origin")

        # 编辑表单提交空 api_key（「留空则不修改」）
        updated = await svc.update_model(model.id, api_key="")
        assert updated is not None
        assert decrypt_api_key(updated.api_key_encrypted) == "sk-origin"

    async def test_update_with_none_api_key_keeps_existing(self, db_session):
        svc = ConfigService(db_session)
        model = await svc.create_model("test-model", "https://api.example.com", "sk-origin")

        updated = await svc.update_model(model.id, model_name="renamed", api_key=None)
        assert updated is not None
        assert updated.model_name == "renamed"
        assert decrypt_api_key(updated.api_key_encrypted) == "sk-origin"

    async def test_update_with_real_api_key_replaces(self, db_session):
        svc = ConfigService(db_session)
        model = await svc.create_model("test-model", "https://api.example.com", "sk-origin")

        updated = await svc.update_model(model.id, api_key="sk-new")
        assert decrypt_api_key(updated.api_key_encrypted) == "sk-new"


class TestChannelConfigEmptySecretKept:
    async def test_save_with_empty_secrets_keeps_existing(self, db_session):
        svc = ChannelAdminService(db_session)

        # 首次保存真实密钥
        await svc.save_config(
            ChannelConfigDTO(
                platform="zhibo",
                display_name="智齿",
                enabled=True,
                api_token="tok-origin",
                webhook_secret="sec-origin",
            )
        )

        # 编辑保存：密钥留空（前端 B6 修复后不再提交空字段，此处验证后端双保险）
        await svc.save_config(
            ChannelConfigDTO(
                platform="zhibo",
                display_name="智齿改名",
                enabled=True,
                api_token="",
                webhook_secret="",
            )
        )

        # 通过底层 ConfigService 读取真实密文并解密验证
        config_service = ConfigService(db_session)
        token_enc = await config_service.get("channel:zhibo:api_token")
        secret_enc = await config_service.get("channel:zhibo:webhook_secret")
        assert token_enc is not None and decrypt_api_key(token_enc) == "tok-origin"
        assert secret_enc is not None and decrypt_api_key(secret_enc) == "sec-origin"

    async def test_save_with_masked_secrets_keeps_existing(self, db_session):
        """管理端回显的掩码值（***）被原样提交时，不得覆盖真实密钥。"""
        svc = ChannelAdminService(db_session)
        await svc.save_config(
            ChannelConfigDTO(
                platform="zhibo",
                display_name="智齿",
                enabled=True,
                api_token="tok-origin",
                webhook_secret="sec-origin",
            )
        )

        # 掩码值原样回传
        await svc.save_config(
            ChannelConfigDTO(
                platform="zhibo",
                display_name="智齿",
                enabled=True,
                api_token="***abc",
                webhook_secret="***def",
            )
        )

        config_service = ConfigService(db_session)
        token_enc = await config_service.get("channel:zhibo:api_token")
        secret_enc = await config_service.get("channel:zhibo:webhook_secret")
        assert decrypt_api_key(token_enc) == "tok-origin"
        assert decrypt_api_key(secret_enc) == "sec-origin"

    async def test_save_with_real_secrets_replaces(self, db_session):
        svc = ChannelAdminService(db_session)
        await svc.save_config(
            ChannelConfigDTO(
                platform="zhibo",
                display_name="智齿",
                enabled=True,
                api_token="tok-origin",
            )
        )
        await svc.save_config(
            ChannelConfigDTO(
                platform="zhibo",
                display_name="智齿",
                enabled=True,
                api_token="tok-new",
            )
        )
        config_service = ConfigService(db_session)
        token_enc = await config_service.get("channel:zhibo:api_token")
        assert decrypt_api_key(token_enc) == "tok-new"


class TestCryptoRoundTrip:
    """加密工具往返一致性（支撑上述断言的可信度）。"""

    def test_encrypt_decrypt_round_trip(self):
        cipher = encrypt_api_key("sk-roundtrip")
        assert cipher != "sk-roundtrip"
        assert decrypt_api_key(cipher) == "sk-roundtrip"
