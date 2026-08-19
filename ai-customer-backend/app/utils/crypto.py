"""对称加密工具：API Key 加解密 (Fernet AES-128-CBC)。

密钥来源：settings.CRYPTO_SECRET_KEY（32 字节 url-safe base64）。
"""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.config.settings import settings

logger = logging.getLogger(__name__)


def _derive_key(secret: str) -> bytes:
    """将任意长度的密钥派生为 Fernet 要求的 32 字节 url-safe base64。"""
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt(plaintext: str, secret_key: str | None = None) -> str:
    """Fernet AES 加密，返回 base64 字符串。"""
    secret = secret_key or settings.CRYPTO_SECRET_KEY
    fernet = Fernet(_derive_key(secret))
    token = fernet.encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt(ciphertext: str, secret_key: str | None = None) -> str:
    """Fernet AES 解密，返回明文。失败抛 ValueError。"""
    secret = secret_key or settings.CRYPTO_SECRET_KEY
    fernet = Fernet(_derive_key(secret))
    try:
        token = fernet.decrypt(ciphertext.encode("utf-8"))
        return token.decode("utf-8")
    except InvalidToken as e:
        logger.error("Decrypt failed: InvalidToken")
        raise ValueError("解密失败：密文无效或密钥不匹配") from e


def encrypt_api_key(api_key: str) -> str:
    """便捷封装：加密 API Key。"""
    return encrypt(api_key)


def decrypt_api_key(encrypted: str) -> str:
    """便捷封装：解密 API Key。"""
    return decrypt(encrypted)
