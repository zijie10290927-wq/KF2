# AI 智能客服系统 (ZNKF)

基于 FastAPI + Vue3 的全栈 AI 智能客服解决方案，为 AI 出图产品用户提供智能问答服务。支持多渠道接入、知识库 RAG 检索、多模型调用、兜底引导等核心能力。

## 核心特性

- **智能问答引擎**：意图识别 + RAG 检索增强生成，支持多模型动态切换
- **知识库管理**：文档上传、分块、向量化、检索（Milvus 向量库）
- **多渠道适配**：智齿科技、京东开放平台、通用 Webhook、OpenAI 兼容端点、JS Widget
- **降级容灾**：MySQL/Redis/Milvus/MinIO 不可用时自动降级到本地实现（SQLite/fakeredis/milvus-lite/本地文件系统）
- **安全加固**：JWT 认证、CSRF 防护、SSRF 防护、速率限制、密钥加密、审计日志
- **生产就绪**：Docker Compose 编排、Alembic 迁移锁定、健康检查、非 root 容器

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.13 + FastAPI + SQLAlchemy 2.0 + Alembic |
| 前端 | Vue 3.4 + TypeScript 5 + Vite 5 + Element Plus + Pinia |
| 数据库 | MySQL 8.0 (降级 SQLite) |
| 缓存 | Redis 7 (降级 fakeredis) |
| 向量库 | Milvus 2.4 (降级 milvus-lite) |
| 对象存储 | MinIO (降级本地文件系统) |
| 部署 | Docker Compose + Gunicorn + Uvicorn |

## 项目结构

```
KF2/
├── ai-customer-backend/          # 后端服务
│   ├── app/
│   │   ├── adapters/             # 渠道适配层（智齿/京东/通用/OpenAI/Widget）
│   │   ├── config/               # 配置（database/redis/milvus/minio/settings）
│   │   ├── middleware/           # 中间件（auth/logging/rate_limiter）
│   │   ├── models/               # ORM 模型
│   │   ├── routers/              # API 路由（auth/chat/admin_*）
│   │   ├── schemas/              # Pydantic 数据模型
│   │   ├── security/             # 安全工具（url_guard）
│   │   ├── services/             # 业务服务（auth/chat/rag/llm/intent/knowledge...）
│   │   ├── utils/                # 工具（crypto/sse/document_parser）
│   │   └── main.py               # 应用入口
│   ├── alembic/                  # 数据库迁移
│   ├── tests/                    # 测试套件
│   ├── requirements.txt
│   └── .env.example              # 环境变量模板
├── ai-customer-frontend/         # 前端应用
│   ├── src/
│   │   ├── api/                  # API 调用封装
│   │   ├── components/           # Vue 组件
│   │   ├── views/                # 页面（chat/admin）
│   │   ├── stores/               # Pinia 状态管理
│   │   └── utils/                # 工具（sse/markdown/format）
│   └── package.json
├── scripts/                      # 运维/测试脚本
├── docker-compose.yml            # 基础设施编排（etcd/minio/milvus）
├── docker-compose.app.yml        # 应用层编排（backend/nginx/redis）
└── README.md
```

## 快速开始

### 方式一：Docker Compose 一键启动（推荐）

```bash
# 1. 准备环境变量
cp ai-customer-backend/.env.example ai-customer-backend/.env
# 编辑 .env，填入你的密钥（JWT_SECRET_KEY、CRYPTO_SECRET_KEY、LLM_API_KEY 等）

# 2. 启动基础设施（etcd/minio/milvus）
docker compose -f docker-compose.yml up -d

# 3. 构建后端镜像
cd ai-customer-backend && docker build -t ai-customer-backend:prod . && cd ..

# 4. 构建前端
cd ai-customer-frontend && npm install && npm run build && cd ..

# 5. 准备生产环境变量
cp ai-customer-backend/.env.example ai-customer-backend/.env.production
# 编辑 .env.production，设置 APP_ENV=production 和安全随机密钥

# 6. 启动应用层（backend/nginx/redis）
docker compose --env-file ./ai-customer-backend/.env.production \
  -f docker-compose.yml -f docker-compose.app.yml up -d

# 7. 访问
# 前端：http://localhost
# 后端 API：http://localhost:8000
# API 文档：http://localhost:8000/docs
```

### 方式二：本地开发模式

```bash
# 后端
cd ai-customer-backend
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 配置数据库等
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 前端（另开终端）
cd ai-customer-frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

## 环境配置

复制 `.env.example` 为 `.env` 并填写以下关键配置：

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `APP_ENV` | 环境标识 | `development` / `production` |
| `MYSQL_*` | MySQL 连接 | `localhost:3306` |
| `REDIS_*` | Redis 连接 | `localhost:6379` |
| `MILVUS_*` | Milvus 连接 | `localhost:19530` |
| `MINIO_*` | MinIO 连接 | `localhost:9000` |
| `LLM_API_KEY` | LLM 服务密钥 | DeepSeek / OpenAI 兼容 |
| `EMBEDDING_API_KEY` | Embedding 服务密钥 | SiliconFlow / DashScope |
| `JWT_SECRET_KEY` | JWT 签名密钥（≥32 字符随机串） | 生产必须修改 |
| `CRYPTO_SECRET_KEY` | API Key 加密密钥（32 字节 URL Safe Base64） | 生产必须修改 |
| `CORS_ALLOWED_ORIGINS` | CORS 允许域名 | 生产禁止用 `*` |

> **安全提示**：生产环境必须设置 `APP_ENV=production`，并将所有 `please-change-*` 占位符替换为安全随机值。生产环境若检测到 admin 账号仍使用默认弱口令 `admin123`，应用将拒绝启动（fail-closed）。

## 默认账号（仅开发环境）

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | `admin` | `admin123` |
| 演示用户 | `demo` | `demo123` |

> 生产环境不创建默认账号。如需初始化管理员，设置环境变量 `INIT_ADMIN_PASSWORD=<强口令>`。

## 测试

```bash
cd ai-customer-backend
pytest tests/ -v
```

测试覆盖：认证服务、聊天服务、LLM 服务、意图识别、SSE、加密、安全加固、SSRF 防护等。

## 降级机制

当外部服务不可用时，系统自动降级以保证核心功能可用：

| 服务 | 降级方案 |
|------|---------|
| MySQL | SQLite（本地文件） |
| Redis | fakeredis（内存） |
| Milvus | milvus-lite（本地文件） |
| MinIO | 本地文件系统 `data/minio_local/<bucket>/` |

## 文档

- [说明文档](说明文档.md) - 项目全生命周期管理文档
- [框架设计文档](框架设计文档.md) - 架构设计说明
- [CODE_WIKI 完整文档](CODE_WIKI_完整文档2.0.md) - 代码实现参考
- [京东接入配置与申请清单](京东接入配置与申请清单.md) - 京东渠道接入指南

## 许可证

私有项目，未开源。
