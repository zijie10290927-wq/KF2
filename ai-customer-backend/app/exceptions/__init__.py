"""自定义异常层。"""


class AppException(Exception):
    """应用基础异常。"""

    code: int = -1
    message: str = "应用内部错误"

    def __init__(self, message: str | None = None, code: int | None = None) -> None:
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code
        super().__init__(self.message)


class AuthError(AppException):
    """认证失败。"""

    code = 401
    message = "认证失败"


class PermissionDeniedError(AppException):
    """权限不足。"""

    code = 403
    message = "无权访问"


class RateLimitExceededError(AppException):
    """限流触发。"""

    code = 429
    message = "请求过于频繁，请稍后重试"


class NotFoundError(AppException):
    """资源不存在。"""

    code = 404
    message = "资源不存在"


class ConfigError(AppException):
    """配置异常。"""

    code = 5001
    message = "配置缺失或无效"


# ===== 渠道适配层异常 (P2 预留) =====
class AdapterError(AppException):
    """适配器基础异常。"""

    code = 5002
    message = "渠道适配器错误"


class AdapterAuthError(AdapterError):
    """适配器签名/鉴权失败。"""

    code = 5003
    message = "渠道适配器鉴权失败"


class AdapterSendError(AdapterError):
    """适配器消息发送失败。"""

    code = 5004
    message = "渠道适配器消息发送失败"
