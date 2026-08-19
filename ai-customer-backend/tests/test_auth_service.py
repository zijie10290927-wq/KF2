"""认证服务测试：密码哈希、JWT 签发/校验、异常消息不泄露内部信息。"""

import pytest

from app.exceptions import AuthError
from app.services.auth_service import AuthService


class TestPasswordHash:
    def test_hash_and_verify(self):
        """哈希后应能正确验证原密码。"""
        raw = "MySecure@Pass123"
        hashed = AuthService.hash_password(raw)
        assert hashed != raw
        assert hashed.startswith("$2")  # bcrypt 前缀
        assert AuthService.verify_password(raw, hashed) is True

    def test_verify_wrong_password(self):
        """错误密码验证应失败。"""
        hashed = AuthService.hash_password("correct-password")
        assert AuthService.verify_password("wrong-password", hashed) is False

    def test_hash_is_salted(self):
        """同一密码两次哈希结果应不同（盐随机）。"""
        assert AuthService.hash_password("same") != AuthService.hash_password("same")


class TestJWTToken:
    def test_encode_decode_roundtrip(self):
        """签发的 Token 应能解码并还原 payload。"""
        payload = {"user_id": 42, "username": "alice", "role": "admin"}
        token = AuthService.create_access_token(payload)
        decoded = AuthService.decode_token(token)
        assert decoded["user_id"] == 42
        assert decoded["username"] == "alice"
        assert decoded["role"] == "admin"

    def test_decode_invalid_token_raises_auth_error(self):
        """非法 Token 应抛 AuthError。"""
        with pytest.raises(AuthError):
            AuthService.decode_token("this-is-not-a-jwt")

    def test_auth_error_message_no_internal_leak(self):
        """回归测试：AuthError 消息不得包含底层异常细节（审查标准 3.1）。"""
        try:
            AuthService.decode_token("malformed.token.here")
            pytest.fail("should have raised AuthError")
        except AuthError as e:
            # 修复前消息为 "Token 无效或已过期: Not enough segments"（泄露内部实现）
            assert "Not enough segments" not in str(e)
            assert "Signature" not in str(e)

    def test_decode_tampered_token_raises(self):
        """篡改 payload 的 Token 应验签失败。"""
        token = AuthService.create_access_token({"user_id": 1, "role": "user"})
        header, payload, sig = token.split(".")
        # 篡改 payload 段（baseurl 替换字符制造差异）
        tampered = f"{header}.{payload[:-2]}aa.{sig}"
        with pytest.raises(AuthError):
            AuthService.decode_token(tampered)
