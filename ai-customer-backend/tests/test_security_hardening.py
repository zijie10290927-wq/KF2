"""B2 / B3 安全加固回归测试。

覆盖：
- B2 生产环境内置 admin 后门封禁（登录降级/启动初始化/弱口令拦截）
- B3 生产环境默认密钥 fail-fast
- B1 修复的回归确认（初始化建号不再被 register 的角色强制降级）
"""

import pytest

from app.config.settings import Settings, validate_production_security
from app.exceptions import AuthError
from app.services.auth_service import AuthService, init_default_accounts


# ---------------------------------------------------------------------- #
# B3: 默认密钥 fail-fast
# ---------------------------------------------------------------------- #
class TestProductionSecretValidation:
    def _prod_settings(self, **overrides) -> Settings:
        """构造生产环境 Settings（隔离 .env 与环境变量）。"""
        base = {
            "APP_ENV": "production",
            "JWT_SECRET_KEY": "x" * 48,  # 合法长度，非占位符
            "CRYPTO_SECRET_KEY": "real-key-not-placeholder",
            "WEBHOOK_HMAC_SECRET": "real-hmac-secret",
            "OPENAI_COMPAT_API_KEY": "sk-real-key",
            "MINIO_ACCESS_KEY": "real-access-key",
            "MINIO_SECRET_KEY": "real-secret-key",
        }
        base.update(overrides)
        return Settings(_env_file=None, **base)

    def test_production_with_all_real_secrets_passes(self):
        s = self._prod_settings()
        assert s.insecure_default_secrets == []
        validate_production_security(s)  # 不抛异常

    def test_production_with_placeholder_jwt_raises(self):
        s = self._prod_settings(
            JWT_SECRET_KEY="please-change-this-secret-key-to-random-string-at-least-32-chars"
        )
        names = [n for n, _ in s.insecure_default_secrets]
        assert names == ["JWT_SECRET_KEY"]
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            validate_production_security(s)

    def test_production_with_default_minio_credentials_raises(self):
        s = self._prod_settings(MINIO_ACCESS_KEY="minioadmin", MINIO_SECRET_KEY="minioadmin")
        names = {n for n, _ in s.insecure_default_secrets}
        assert names == {"MINIO_ACCESS_KEY", "MINIO_SECRET_KEY"}
        with pytest.raises(RuntimeError):
            validate_production_security(s)

    def test_non_production_env_passes_even_with_placeholders(self):
        """开发/测试环境允许占位密钥（不阻断本地开发）。"""
        s = Settings(
            _env_file=None,
            APP_ENV="development",
            JWT_SECRET_KEY="please-change-this-secret-key-to-random-string-at-least-32-chars",
        )
        assert s.insecure_default_secrets != []
        validate_production_security(s)  # 非 production 放行


# ---------------------------------------------------------------------- #
# B2: 内置账号后门封禁
# ---------------------------------------------------------------------- #
class _BrokenDB:
    """模拟 DB 不可达：任何 execute 都抛异常。"""

    async def execute(self, *_args, **_kwargs):
        raise RuntimeError("db unreachable")


class TestBuiltinUserFallbackGating:
    async def test_production_builtin_admin_login_rejected_when_db_down(self, monkeypatch):
        """生产环境 DB 不可达时，内置 admin/admin123 必须登录失败（fail-closed）。"""
        from app.config.settings import settings

        monkeypatch.setattr(settings, "APP_ENV", "production")
        svc = AuthService(_BrokenDB())  # type: ignore[arg-type]
        with pytest.raises(AuthError):
            await svc.login("admin", "admin123")

    async def test_dev_builtin_admin_login_still_works_when_db_down(self, monkeypatch):
        """非生产环境保留开发降级便利（回归确认）。"""
        from app.config.settings import settings

        monkeypatch.setattr(settings, "APP_ENV", "development")
        svc = AuthService(_BrokenDB())  # type: ignore[arg-type]
        token = await svc.login("admin", "admin123")
        assert token.user_info.role == "admin"

    async def test_production_get_user_returns_none_when_db_down(self, monkeypatch):
        from app.config.settings import settings

        monkeypatch.setattr(settings, "APP_ENV", "production")
        svc = AuthService(_BrokenDB())  # type: ignore[arg-type]
        assert await svc.get_user_by_username("admin") is None
        assert await svc.get_user_by_id(1) is None


# ---------------------------------------------------------------------- #
# B2: 启动初始化策略
# ---------------------------------------------------------------------- #
class TestInitDefaultAccounts:
    async def test_dev_creates_admin_and_demo(self, db_session, monkeypatch):
        from app.config.settings import settings

        monkeypatch.setattr(settings, "APP_ENV", "development")
        await init_default_accounts(db_session)

        admin = await AuthService(db_session).get_user_by_username("admin")
        demo = await AuthService(db_session).get_user_by_username("demo")
        assert admin is not None and admin.role == "admin"
        assert AuthService.verify_password("admin123", admin.password_hash)
        assert demo is not None and demo.role == "user"

    async def test_prod_without_init_password_creates_nothing(self, db_session, monkeypatch):
        from app.config.settings import settings

        monkeypatch.setattr(settings, "APP_ENV", "production")
        monkeypatch.setattr(settings, "INIT_ADMIN_PASSWORD", "")
        await init_default_accounts(db_session)

        assert await AuthService(db_session).get_user_by_username("admin") is None
        assert await AuthService(db_session).get_user_by_username("demo") is None

    async def test_prod_with_init_password_creates_admin_only(self, db_session, monkeypatch):
        from app.config.settings import settings

        monkeypatch.setattr(settings, "APP_ENV", "production")
        monkeypatch.setattr(settings, "INIT_ADMIN_PASSWORD", "S3cure!Random#Pass")
        await init_default_accounts(db_session)

        admin = await AuthService(db_session).get_user_by_username("admin")
        assert admin is not None
        assert admin.role == "admin"
        assert AuthService.verify_password("S3cure!Random#Pass", admin.password_hash)
        # 生产环境绝不创建 demo 账号
        assert await AuthService(db_session).get_user_by_username("demo") is None

    async def test_prod_blocks_startup_when_admin_keeps_weak_password(
        self, db_session, monkeypatch
    ):
        """生产环境已有 admin 且密码仍是 admin123 → 启动失败（fail-closed）。"""
        from app.config.settings import settings

        await AuthService(db_session).create_user("admin", "admin123", role="admin")
        monkeypatch.setattr(settings, "APP_ENV", "production")
        monkeypatch.setattr(settings, "INIT_ADMIN_PASSWORD", "")
        with pytest.raises(RuntimeError, match="admin123"):
            await init_default_accounts(db_session)

    async def test_prod_allows_startup_when_admin_password_changed(
        self, db_session, monkeypatch
    ):
        await AuthService(db_session).create_user("admin", "Strong#Pass!2026", role="admin")
        from app.config.settings import settings

        monkeypatch.setattr(settings, "APP_ENV", "production")
        await init_default_accounts(db_session)  # 不抛异常

    async def test_init_is_idempotent_in_dev(self, db_session, monkeypatch):
        from app.config.settings import settings

        monkeypatch.setattr(settings, "APP_ENV", "development")
        await init_default_accounts(db_session)
        await init_default_accounts(db_session)  # 二次执行不报"用户名已存在"
