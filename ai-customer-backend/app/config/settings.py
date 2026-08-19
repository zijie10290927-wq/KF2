"""全局配置加载：基于 Pydantic Settings 从 .env 文件与环境变量加载全部配置。"""

from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置。所有配置项均可通过环境变量覆盖。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===== 应用 =====
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    APP_PORT: int = 8000
    CORS_ALLOWED_ORIGINS: str = "*"

    # ===== MySQL =====
    DB_TYPE: str = "mysql"  # mysql | sqlite
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "ai_customer"

    # ===== Redis =====
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    # ===== Milvus =====
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION: str = "knowledge_embeddings"

    # ===== MinIO =====
    MINIO_HOST: str = "localhost"
    MINIO_PORT: int = 9000
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "knowledge"
    MINIO_SECURE: bool = False

    # ===== LLM 模型 (默认) =====
    LLM_API_BASE: str = "https://api.duc.ai/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL_NAME: str = "duc-v2"

    # ===== Embedding =====
    EMBEDDING_PROVIDER: str = "dashscope"
    EMBEDDING_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-v3"
    EMBEDDING_DIM: int = 1024

    # ===== JWT 认证 =====
    JWT_SECRET_KEY: str = "please-change-this-secret-key-to-random-string-at-least-32-chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24

    # ===== 加密 =====
    CRYPTO_SECRET_KEY: str = "please-change-this-32-byte-url-safe-base64-key"

    # ===== 限流 =====
    RATE_LIMIT_MAX: int = 600
    RATE_LIMIT_WINDOW: int = 60

    # ===== RAG 默认参数 =====
    RAG_TOP_K: int = 5
    RAG_SCORE_THRESHOLD: float = 0.60
    RAG_CHUNK_SIZE: int = 512
    RAG_CHUNK_OVERLAP: int = 64

    # ===== 记忆与意图阈值 =====
    SHORT_TERM_TTL: int = 86400
    MAX_SHORT_TERM: int = 20
    INTENT_CONFIDENCE_HIGH: float = 0.85
    INTENT_CONFIDENCE_LOW: float = 0.60

    # ===== 渠道适配层 (Section 11) =====
    # Webhook 接收
    WEBHOOK_ENABLED: bool = True
    WEBHOOK_HMAC_SECRET: str = "please-change-webhook-hmac-secret"

    # OpenAI 兼容端点
    OPENAI_COMPAT_ENABLED: bool = True
    OPENAI_COMPAT_API_KEY: str = "please-change-openai-compat-api-key"

    # JS Widget
    WIDGET_ENABLED: bool = True
    WIDGET_APP_KEYS: str = ""  # 逗号分隔的 app_key 列表

    # 智齿科技
    ZHIBO_API_BASE: str = "https://api.sobot.com"
    ZHIBO_API_TOKEN: str = ""
    ZHIBO_WEBHOOK_SECRET: str = ""
    ZHIBO_APP_KEY: str = ""

    # Chatwoot（可选）
    CHATWOOT_API_BASE: str = ""
    CHATWOOT_ACCESS_TOKEN: str = ""

    # ===== 认证排除路径 (JWT 中间件白名单) =====
    AUTH_EXCLUDE_PATHS: str = (
        "/api/v1/auth/login,"
        "/api/v1/auth/register,"
        "/health,"
        "/docs,"
        "/redoc,"
        "/openapi.json,"
        "/favicon.ico,"
        "/,"
        # 渠道适配层使用自身鉴权（HMAC / API Key / app_key），不走 JWT
        "/api/v1/webhook/**,"
        "/api/v1/openai/**,"
        "/api/v1/widget/**"
    )

    # ===== 访问根路径 (前端 baseURL 拼接用) =====
    API_PREFIX: str = "/api/v1"

    # ------------------------------------------------------------------ #
    # 派生属性
    # ------------------------------------------------------------------ #
    @property
    def async_database_url(self) -> str:
        """异步数据库连接 URL（支持 MySQL 和 SQLite）。"""
        if self.DB_TYPE == "sqlite":
            import os
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data", "ai_customer.db"
            )
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            return f"sqlite+aiosqlite:///{db_path}"
        return (
            f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"
        )

    @property
    def redis_url(self) -> str:
        """Redis 连接 URL。"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def cors_origins_list(self) -> List[str]:
        """CORS 允许来源列表。"""
        if self.CORS_ALLOWED_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def auth_exclude_paths_list(self) -> List[str]:
        """JWT 中间件排除路径列表。"""
        return [p.strip() for p in self.AUTH_EXCLUDE_PATHS.split(",") if p.strip()]

    @property
    def widget_app_keys_list(self) -> List[str]:
        """Widget 授权 app_key 列表（来自 .env 逗号分隔）。"""
        return [k.strip() for k in self.WIDGET_APP_KEYS.split(",") if k.strip()]

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def _validate_jwt_secret(cls, v: str) -> str:
        if len(v) < 16:
            raise ValueError("JWT_SECRET_KEY 长度至少 16 个字符")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """单例获取 Settings 实例。"""
    return Settings()


# 全局配置单例
settings = get_settings()
