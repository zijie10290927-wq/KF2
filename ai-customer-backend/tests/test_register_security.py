"""注册接口提权防护测试（回归：Blocker B1 修复）。"""

import pytest

from app.exceptions import AuthError
from app.models import User
from app.schemas.auth import RegisterRequest
from app.services.auth_service import AuthService


class TestRegisterNoPrivilegeEscalation:
    async def test_register_with_admin_role_is_forced_to_user(self, db_session):
        """尝试以 role=admin 注册，服务端必须强制降为 user。"""
        svc = AuthService(db_session)
        user = await svc.register("hacker", "hack123456", role="admin")
        assert user.role == "user"

    async def test_register_normal_user(self, db_session):
        svc = AuthService(db_session)
        user = await svc.register("normaluser", "safe123456")
        assert user.role == "user"

    async def test_duplicate_username_rejected(self, db_session, test_user):
        svc = AuthService(db_session)
        with pytest.raises(AuthError):
            await svc.register(test_user.username, "another-pass-123")


class TestRegisterSchema:
    def test_schema_rejects_admin_role(self):
        """Schema 层拒绝 role=admin（第一层防线）。"""
        with pytest.raises(ValueError):
            RegisterRequest(username="someone", password="123456", role="admin")

    def test_schema_accepts_user_role(self):
        req = RegisterRequest(username="someone", password="123456")
        assert req.role == "user"

    def test_schema_rejects_other_roles(self):
        with pytest.raises(ValueError):
            RegisterRequest(username="someone", password="123456", role="superadmin")
