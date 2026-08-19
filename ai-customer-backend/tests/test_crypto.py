"""加密工具测试：Fernet 加解密往返、密钥派生、异常处理。"""

import pytest

from app.utils.crypto import decrypt, decrypt_api_key, encrypt, encrypt_api_key


class TestEncryptDecrypt:
    def test_roundtrip(self):
        """加密后解密应还原明文。"""
        plaintext = "sk-real-api-key-abc123"
        assert decrypt(encrypt(plaintext)) == plaintext

    def test_custom_secret_key(self):
        """使用自定义密钥加解密应正常往返。"""
        plaintext = "secret-value"
        ciphertext = encrypt(plaintext, secret_key="my-custom-key")
        assert decrypt(ciphertext, secret_key="my-custom-key") == plaintext

    def test_ciphertext_differs_from_plaintext(self):
        """密文不得等于明文。"""
        assert encrypt("password123") != "password123"

    def test_unicode_roundtrip(self):
        """中文等多字节字符加解密应无损。"""
        plaintext = "密钥测试-中文-🔐"
        assert decrypt(encrypt(plaintext)) == plaintext

    def test_wrong_key_raises(self):
        """密钥不匹配时解密应抛 ValueError。"""
        ciphertext = encrypt("data", secret_key="key-a")
        with pytest.raises(ValueError):
            decrypt(ciphertext, secret_key="key-b")

    def test_invalid_ciphertext_raises(self):
        """非法密文解密应抛 ValueError（而非底层 InvalidToken 泄露）。"""
        with pytest.raises(ValueError):
            decrypt("not-a-valid-fernet-token")


class TestApiKeyHelpers:
    def test_api_key_roundtrip(self):
        """API Key 便捷封装应正常往返。"""
        key = "sk-proj-xxxxxxxxxxxxxxxx"
        assert decrypt_api_key(encrypt_api_key(key)) == key
