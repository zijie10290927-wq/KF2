"""initial schema: 8 core tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-17 00:00:00

创建 8 张核心表：
users / chat_sessions / chat_messages / knowledge_docs / knowledge_chunks
model_configs / system_configs / channel_sessions
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("role", sa.Enum("user", "admin", name="user_role"), nullable=False, server_default="user"),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("idx_username", "users", ["username"])

    # 2. chat_sessions
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False, server_default="新对话"),
        sa.Column("status", sa.Enum("active", "closed", "transferred", name="session_status"), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", name="uq_chat_sessions_session_id"),
    )
    op.create_index("idx_user_id", "chat_sessions", ["user_id"])
    op.create_index("idx_session_id", "chat_sessions", ["session_id"])

    # 3. chat_messages
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.Enum("user", "assistant", "system", name="message_role"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(length=32), nullable=True),
        sa.Column("sources", sa.JSON(), nullable=True),
        sa.Column("model_used", sa.String(length=64), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", name="uq_chat_messages_message_id"),
    )
    op.create_index("idx_chat_messages_session_id", "chat_messages", ["session_id"])
    op.create_index("idx_chat_messages_created_at", "chat_messages", ["created_at"])

    # 4. knowledge_docs
    op.create_table(
        "knowledge_docs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("doc_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=256), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("file_type", sa.String(length=16), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("chunk_size", sa.Integer(), nullable=False, server_default="512"),
        sa.Column("overlap", sa.Integer(), nullable=False, server_default="64"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Enum("uploading", "processing", "indexed", "failed", name="doc_status"), nullable=False, server_default="uploading"),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_id", name="uq_knowledge_docs_doc_id"),
    )
    op.create_index("idx_knowledge_docs_status", "knowledge_docs", ["status"])

    # 5. knowledge_chunks
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("chunk_id", sa.String(length=36), nullable=False),
        sa.Column("doc_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("extra_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["doc_id"], ["knowledge_docs.doc_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chunk_id", name="uq_knowledge_chunks_chunk_id"),
    )
    op.create_index("idx_knowledge_chunks_doc_id", "knowledge_chunks", ["doc_id"])

    # 6. model_configs
    op.create_table(
        "model_configs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("api_base", sa.String(length=256), nullable=False),
        sa.Column("api_key_encrypted", sa.String(length=512), nullable=False),
        sa.Column("temperature", sa.Numeric(precision=3, scale=2), nullable=False, server_default="0.70"),
        sa.Column("max_tokens", sa.Integer(), nullable=False, server_default="2048"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_name", name="uk_model_name"),
    )

    # 7. system_configs
    op.create_table(
        "system_configs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("config_key", sa.String(length=128), nullable=False),
        sa.Column("config_value", sa.Text(), nullable=False),
        sa.Column("description", sa.String(length=256), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("config_key", name="uk_config_key"),
    )

    # 8. channel_sessions
    op.create_table(
        "channel_sessions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("external_session_id", sa.String(length=128), nullable=False),
        sa.Column("external_user_id", sa.String(length=128), nullable=True),
        sa.Column("external_user_name", sa.String(length=128), nullable=True),
        sa.Column("internal_session_id", sa.String(length=36), nullable=False),
        sa.Column("channel_type", sa.String(length=32), nullable=True),
        sa.Column("extra_metadata", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform", "external_session_id", name="uk_platform_session"),
    )
    op.create_index("idx_channel_sessions_platform", "channel_sessions", ["platform"])
    op.create_index("idx_channel_sessions_internal_session_id", "channel_sessions", ["internal_session_id"])

    # 预置默认系统配置
    op.execute(
        """
        INSERT INTO system_configs (config_key, config_value, description) VALUES
        ('fallback_message', '抱歉，我暂时无法回答该问题。您可以选择转接人工客服或拨打 400-xxx-xxxx 咨询。', '兜底引导话术'),
        ('show_transfer_button', 'true', '是否显示转人工按钮'),
        ('show_phone', 'true', '是否显示电话提示'),
        ('phone_number', '400-xxx-xxxx', '客服电话'),
        ('rag_top_k', '5', '知识库检索返回条数'),
        ('rag_score_threshold', '0.60', '向量检索最低相似度阈值'),
        ('rag_chunk_size', '512', '分块大小'),
        ('rag_chunk_overlap', '64', '分块重叠字符数'),
        ('rag_hybrid_search', 'true', '是否启用混合检索'),
        ('rag_query_rewrite', 'true', '是否启用 Query 改写'),
        ('intent_confidence_high', '0.85', '意图识别高置信度阈值'),
        ('intent_confidence_low', '0.60', '意图识别低置信度阈值')
        """
    )


def downgrade() -> None:
    op.drop_table("channel_sessions")
    op.drop_table("system_configs")
    op.drop_table("model_configs")
    op.drop_index("idx_knowledge_chunks_doc_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index("idx_knowledge_docs_status", table_name="knowledge_docs")
    op.drop_table("knowledge_docs")
    op.drop_index("idx_chat_messages_created_at", table_name="chat_messages")
    op.drop_index("idx_chat_messages_session_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("idx_session_id", table_name="chat_sessions")
    op.drop_index("idx_user_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")
    op.drop_index("idx_username", table_name="users")
    op.drop_table("users")
