# AI 出图产品智能客服 Agent · Code Wiki

> 本文档是对 **AI 出图产品智能客服 Agent** 项目的结构化代码知识库，覆盖项目整体架构、模块职责、关键类与函数、依赖关系、运行方式等核心内容。
> 本文档由「核心架构文档」+「渠道嵌入方案」+「适配器完整实现」三部分合并而成，构成项目唯一权威 Code Wiki。
> 项目根路径：`c:\Users\admin\Desktop\ZNKF\a1`
> 技术栈：Python 3.13.15 (amd64) / FastAPI / SQLAlchemy 2.0 / Vue 3.4 / TypeScript 5 / MySQL 8 / Milvus 2.4 / Redis 7 / MinIO

---

## 目录

1. [项目概览](#1-项目概览)
2. [整体架构](#2-整体架构)
3. [目录结构](#3-目录结构)
4. [后端模块详解](#4-后端模块详解)
   - 4.1 [配置层 config](#41-配置层-config)
   - 4.2 [数据模型层 models](#42-数据模型层-models)
   - 4.3 [请求/响应模型 schemas](#43-请求响应模型-schemas)
   - 4.4 [路由层 routers](#44-路由层-routers)
   - 4.5 [业务服务层 services](#45-业务服务层-services)
   - 4.6 [中间件 middleware](#46-中间件-middleware)
   - 4.7 [工具层 utils](#47-工具层-utils)
5. [前端模块详解](#5-前端模块详解)
   - 5.1 [入口与构建配置](#51-入口与构建配置)
   - 5.2 [路由 router](#52-路由-router)
   - 5.3 [状态管理 stores](#53-状态管理-stores)
   - 5.4 [API 请求层](#54-api-请求层)
   - 5.5 [公共组件 components](#55-公共组件-components)
   - 5.6 [视图 views](#56-视图-views)
6. [数据库设计](#6-数据库设计)
   - 6.1 [核心表结构](#61-核心表结构)
   - 6.2 [向量数据库 Milvus](#62-向量数据库-milvus)
   - 6.3 [Redis 缓存设计](#63-redis-缓存设计)
7. [依赖关系](#7-依赖关系)
8. [项目运行方式](#8-项目运行方式)
9. [关键流程与时序](#9-关键流程与时序)
10. [意图识别与 RAG 调优](#10-意图识别与-rag-调优)
11. [渠道适配层 adapters](#11-渠道适配层-adapters)
    - 11.1 [适配层定位与嵌入策略](#111-适配层定位与嵌入策略)
    - 11.2 [适配层目录结构](#112-适配层目录结构)
    - 11.3 [适配器基类 BaseAdapter](#113-适配器基类-baseadapter)
    - 11.4 [智齿科技适配器 ZhiboAdapter](#114-智齿科技适配器-zhiboadapter)
    - 11.5 [通用适配器 GenericAdapter](#115-通用适配器-genericadapter)
    - 11.6 [适配器注册工厂](#116-适配器注册工厂)
    - 11.7 [Webhook 统一路由](#117-webhook-统一路由)
    - 11.8 [会话映射器 SessionMapper](#118-会话映射器-sessionmapper)
    - 11.9 [渠道会话表 ChannelSession](#119-渠道会话表-channelsession)
    - 11.10 [OpenAI 兼容端点](#1110-openai-兼容端点)
    - 11.11 [JS Widget SDK 与服务端](#1111-js-widget-sdk-与服务端)
    - 11.12 [管理后台渠道管理](#1112-管理后台渠道管理)
    - 11.13 [ChatService 同步方法扩展](#1113-chatservice-同步方法扩展)
    - 11.14 [渠道适配层数据流时序](#1114-渠道适配层数据流时序)

---

## 1. 项目概览

**AI 出图产品智能客服 Agent** 是一套基于 **FastAPI + Vue3** 的全栈 AI 智能客服解决方案，为 AI 出图产品用户提供智能问答服务。

### 核心能力

| 能力 | 说明 |
|------|------|
| **意图识别** | 基于 LLM + 规则引擎的双层判断，区分产品相关问题 (`product_qa`) 与无关问题 (`off_topic`) |
| **RAG 知识库检索** | 上传 PDF/Word/TXT/MD 文档，自动分块向量化至 Milvus，语义检索增强回答质量 |
| **多模型动态切换** | 支持 DUC、DeepSeek 等兼容 OpenAI 协议的模型，后台热切换 |
| **流式对话 (SSE)** | Server-Sent Events 实时流式输出，支持 Markdown 渲染 / 引用来源标签 |
| **无关问题兜底** | 非产品相关问题输出引导话术，提供转人工客服入口与客服电话 |
| **对话记忆** | Redis 短期记忆（TTL 24h，最近 20 条）+ MySQL 长期持久化 |
| **管理后台** | 知识库管理、模型配置、话术配置、对话记录查询、用户管理 |
| **渠道适配层** | 通过 Webhook / OpenAI 兼容端点 / JS Widget 三层混合方案对接智齿、七鱼、Udesk、Chatwoot 等第三方客服平台，无需改动 Agent 核心 |

### 用户角色

| 角色 | 说明 |
|------|------|
| **C 端用户** | AI 出图产品使用者，通过对话窗口提问 |
| **运营/管理员** | 管理知识库内容、配置应答规则、查看对话记录 |

### 功能优先级

| 优先级 | 功能模块 | 说明 |
|--------|----------|------|
| **P0（必须）** | 智能问答引擎、知识库检索、多模型调用、兜底引导、前后端骨架 | 核心闭环能力 |
| **P1（重要）** | 知识库管理后台、模型动态切换、记忆管理(Redis)、Docker 部署 | 运营支撑能力 |
| **P2（可选）** | 用户认证权限、仪表盘、数据统计分析、用户反馈 | 后续迭代 |

---

## 2. 整体架构

### 2.1 系统全景架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 (Nginx / Vite)                      │
│    Vue3 + TypeScript + Element Plus + Pinia + TailwindCSS    │
│  ┌──────────────┐ ┌──────────────┐ ┌─────────────────────┐  │
│  │ C端智能对话页 │ │  登录/权限   │ │  B端管理后台         │  │
│  └──────────────┘ └──────────────┘ └─────────────────────┘  │
└──────────────────────┬───────────────────────────────────────┘
                       │ HTTP / SSE (Bearer JWT)
┌──────────────────────▼───────────────────────────────────────┐
│                后端服务 (FastAPI / Python 3.13.15)              │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  API 层 Routers    chat / auth / admin_*                 │  │
│  ├─────────────────────────────────────────────────────────┤  │
│  │  中间件层    JWT认证 │ CORS │ 限流 │ 请求日志 │ 异常处理  │  │
│  ├─────────────────────────────────────────────────────────┤  │
│  │  服务层 Services                                         │  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────────────┐  │  │
│  │  │ IntentSvc  │ │  RAGSvc    │ │    LLMSvc          │  │  │
│  │  │ 意图识别    │ │ 知识库检索  │ │ 模型调用(流/非流)   │  │  │
│  │  └────────────┘ └────────────┘ └────────────────────┘  │  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────────────┐  │  │
│  │  │ ChatSvc    │ │KnowledgeSvc│ │   ConfigSvc        │  │  │
│  │  │ 对话编排    │ │文档解析索引│ │   配置管理          │  │  │
│  │  └────────────┘ └────────────┘ └────────────────────┘  │  │
│  │  ┌────────────┐ ┌────────────┐                          │  │
│  │  │ AuthSvc    │ │ MemorySvc  │                          │  │
│  │  │ 认证鉴权    │ │ 记忆管理    │                          │  │
│  │  └────────────┘ └────────────┘                          │  │
│  └─────────────────────────────────────────────────────────┘  │
└──────────────┬───────────────────────────────────────────────┘
               │
    ┌──────────┼──────────────────────────┬─────────┐
    ▼          ▼           ▼              ▼         ▼
┌────────┐ ┌───────┐  ┌────────┐   ┌──────────┐ ┌───────┐
│ MySQL  │ │ Redis │  │ Milvus │   │  MinIO   │ │DUC API│
│ 持久化  │ │ 对话  │  │ 向量   │   │ 文件存储 │ │ 大模型│
│ 业务数据│ │ 记忆  │  │ 检索   │   │ 原始文档 │ │       │
└────────┘ └───────┘  └────────┘   └──────────┘ └───────┘
```

### 2.2 后端分层模型

```
API 层 (Routers, 7+ 个路由文件, 含 admin_channel)
    ↓  {code:0, message, data} 统一响应 + SSE Flux
渠道适配层 (Adapters, 7 子模块, 🆕 对接第三方客服平台)
    ↓  Webhook 接收 / OpenAI 兼容 / JS Widget
中间件层 (Middleware, 5 类)
    ↓  鉴权 / 限流 / 日志 / 跨域 / 异常
Service 层 (9 个 Service, 含 ChannelAdminService)
    ↓  业务编排 (意图→检索→LLM→兜底→记忆)
配置层 (Config, 6 个连接配置)   ←→  数据层 (Models, 8 个 ORM, 含 ChannelSession)
    ↓                                    ↓
工具层 Utils                       Pydantic Schemas (DTO)
```

> 渠道适配层（Adapters）位于 API 层与核心 Service 之间，作为外部第三方客服平台（智齿/七鱼/Udesk/Chatwoot 等）与内部 Agent 核心之间的桥梁，**不改动现有 ChatService 核心编排逻辑**，仅通过新增的 `handle_message_sync` 同步方法调用。详见 [第 11 章](#11-渠道适配层-adapters)。

### 2.3 技术栈选型

| 层级 | 技术选型 | 说明/约束 |
|------|----------|-----------|
| **后端语言** | **Python 3.13.15 (amd64)** | **客户强制要求** |
| **Web 框架** | **FastAPI** | 异步高性能，原生支持 SSE，自动生成 OpenAPI 文档 |
| **ORM** | **SQLAlchemy 2.0** | 异步模式，支持 MySQL/PostgreSQL |
| **数据库迁移** | **Alembic** | 配合 SQLAlchemy 做版本化迁移 |
| **关系型数据库** | **MySQL 8.0** | 存储业务数据（用户/会话/消息/配置） |
| **向量数据库** | **Milvus 2.4** / ChromaDB（轻量替代） | 知识库文档向量化存储与语义检索 |
| **缓存** | **Redis 7.x** | 短期对话记忆、Token 缓存、限流 |
| **对象存储** | **MinIO** | 知识库原始文档存储 |
| **Embedding 模型** | text-embedding-v3（通义）或 **BGE-M3** | 文档向量化，建议维度 1024 |
| **LLM 调用** | **OpenAI SDK (AsyncOpenAI)** / httpx | 调用 DUC 等兼容 OpenAI 协议的模型 |
| **文档解析** | **PyMuPDF** (PDF) + **python-docx** (Word) + markdown | 知识库文档解析 |
| **文本分块** | **langchain-text-splitters** | RecursiveCharacterTextSplitter |
| **认证** | **python-jose** (JWT) + **passlib** (密码哈希) | 用户认证与鉴权 |
| **前端框架** | **Vue 3.4 + TypeScript 5.x** | 组合式 API（Composition API） |
| **前端构建** | **Vite 5.x** | 极速热更新 |
| **UI 库** | **Element Plus 2.x** | 管理后台组件丰富 |
| **状态管理** | **Pinia** | 轻量、TS 友好 |
| **CSS 方案** | **Tailwind CSS + SCSS** | 快速布局 + 自定义样式 |
| **Markdown 渲染** | **markdown-it + highlight.js** | 渲染 AI 回答 |
| **任务队列（可选）** | **Celery + Redis** | 文档异步处理 |
| **部署** | **Docker + Docker Compose** | 容器化一键部署 |

---

## 3. 目录结构

```
ai-customer-agent/
├── ai-customer-backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                         # FastAPI 应用入口
│   │   ├── config/                         # 配置层
│   │   │   ├── __init__.py
│   │   │   ├── settings.py                 # Pydantic Settings（环境变量加载）
│   │   │   ├── database.py                 # SQLAlchemy async engine + Session
│   │   │   ├── redis.py                    # Redis 异步连接池
│   │   │   ├── milvus.py                   # Milvus Client 连接
│   │   │   └── minio.py                    # MinIO Client 连接
│   │   ├── models/                         # SQLAlchemy ORM 实体层
│   │   │   ├── __init__.py
│   │   │   ├── user.py                     # User (用户表)
│   │   │   ├── session.py                  # ChatSession (会话表)
│   │   │   ├── message.py                  # ChatMessage (消息表)
│   │   │   ├── knowledge_doc.py            # KnowledgeDoc (知识库文档元数据)
│   │   │   ├── knowledge_chunk.py          # KnowledgeChunk (知识分块)
│   │   │   ├── model_config.py             # ModelConfig (模型配置)
│   │   │   ├── system_config.py            # SystemConfig (系统配置 KV)
│   │   │   └── channel_session.py         # ChannelSession (🆕 渠道会话映射)
│   │   ├── schemas/                        # Pydantic 请求/响应 DTO
│   │   │   ├── __init__.py
│   │   │   ├── chat.py                     # ChatRequest / SSEEvent / MessageItem
│   │   │   ├── knowledge.py                # DocUpload / DocListItem
│   │   │   ├── admin.py                    # ModelConfigUpdate / FallbackUpdate
│   │   │   ├── auth.py                     # LoginRequest / TokenResponse / UserInfo
│   │   │   └── webhook.py                  # 🆕 Webhook 请求/响应 DTO
│   │   ├── routers/                        # API 路由层
│   │   │   ├── __init__.py
│   │   │   ├── chat.py                     # C端对话接口 (/chat/*)
│   │   │   ├── auth.py                     # 认证接口 (/auth/*)
│   │   │   ├── admin_knowledge.py          # 知识库管理 (/admin/knowledge/*)
│   │   │   ├── admin_config.py             # 配置管理 (/admin/config/*)
│   │   │   ├── admin_chat_logs.py          # 对话记录 (/admin/chat/*)
│   │   │   ├── admin_users.py              # 用户管理 (/admin/users/*)
│   │   │   └── admin_channel.py            # 🆕 渠道管理 (/admin/channels/*)
│   │   ├── adapters/                       # 🆕 渠道适配层 (对接第三方客服平台)
│   │   │   ├── __init__.py
│   │   │   ├── base.py                     # 适配器基类 BaseAdapter
│   │   │   ├── webhook_router.py           # Webhook 统一路由入口
│   │   │   ├── session_mapper.py           # 外部会话 ↔ 内部会话映射
│   │   │   ├── response_adapter.py         # SSE 事件 → 平台响应格式转换
│   │   │   ├── openai_compat.py            # OpenAI 兼容端点
│   │   │   ├── platforms/                  # 各平台专用适配器
│   │   │   │   ├── __init__.py             # 适配器注册工厂
│   │   │   │   ├── zhibo_adapter.py        # 智齿科技适配器
│   │   │   │   ├── qiyu_adapter.py         # 网易七鱼适配器 (预留)
│   │   │   │   ├── udesk_adapter.py        # Udesk 适配器 (预留)
│   │   │   │   ├── zendesk_adapter.py      # Zendesk 适配器 (预留)
│   │   │   │   ├── chatwoot_adapter.py     # Chatwoot 适配器 (预留)
│   │   │   │   └── generic_adapter.py      # 通用适配器 (兜底)
│   │   │   └── widget/                     # 🆕 JS Widget SDK
│   │   │       ├── widget_server.py       # Widget 服务端 (CORS + 匿名认证)
│   │   │       └── static/
│   │   │           └── chat-widget.js      # 嵌入式 JS SDK (<script> 引入)
│   │   ├── services/                       # 业务逻辑层 (核心)
│   │   │   ├── __init__.py
│   │   │   ├── intent_service.py           # IntentService 意图识别
│   │   │   ├── rag_service.py              # RAGService RAG检索
│   │   │   ├── llm_service.py              # LLMService 模型调用封装
│   │   │   ├── chat_service.py             # ChatService 对话编排(核心调度)
│   │   │   ├── memory_service.py           # MemoryService 记忆管理(Redis+MySQL)
│   │   │   ├── knowledge_service.py        # KnowledgeService 文档处理流水线
│   │   │   ├── config_service.py           # ConfigService 配置管理
│   │   │   ├── auth_service.py             # AuthService 认证鉴权逻辑
│   │   │   └── channel_admin_service.py   # 🆕 ChannelAdminService 渠道管理服务
│   │   ├── middleware/                     # 中间件
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                     # JWT 认证中间件
│   │   │   ├── rate_limiter.py             # 滑动窗口限流中间件
│   │   │   └── logging.py                  # 请求日志中间件
│   │   ├── utils/                          # 工具函数
│   │   │   ├── __init__.py
│   │   │   ├── document_parser.py          # PDF/Word/TXT/MD 多格式解析器
│   │   │   ├── crypto.py                   # API Key 加解密 (AES/Fernet)
│   │   │   └── sse.py                      # SSE 响应构建工具
│   │   └── exceptions/                     # 自定义异常
│   │       └── __init__.py                 # 含 AdapterAuthError / AdapterSendError
│   ├── alembic/                            # 数据库迁移
│   │   ├── versions/                       # 迁移脚本目录
│   │   └── env.py                          # Alembic 环境配置
│   ├── alembic.ini
│   ├── tests/                              # 单元测试
│   │   ├── test_intent.py                  # 意图识别单元测试
│   │   ├── test_rag.py                     # RAG 检索单元测试
│   │   └── test_chat.py                    # 对话编排单元测试
│   ├── docker/
│   │   └── Dockerfile                      # 后端多阶段构建
│   ├── docker-compose.yml                  # 全栈编排 (6 服务)
│   ├── requirements.txt                    # Python 依赖清单
│   ├── .env.example                        # 环境变量模板
│   ├── Makefile                            # 常用命令快捷入口
│   └── README.md
│
├── ai-customer-frontend/                   # Vue3 前端
│   ├── public/
│   │   └── favicon.ico
│   ├── src/
│   │   ├── main.ts                         # 应用入口
│   │   ├── App.vue                         # 根组件
│   │   ├── router/
│   │   │   └── index.ts                    # 路由配置 + 权限守卫
│   │   ├── stores/                         # Pinia 状态管理
│   │   │   ├── chat.ts                     # 对话状态 (消息/流式/会话)
│   │   │   ├── auth.ts                     # 认证状态 (token/userInfo) 
│   │   │   └── admin.ts                    # 管理后台状态 (文档/模型/记录)
│   │   ├── api/                            # 请求层 (Axios 封装)
│   │   │   ├── request.ts                  # axios 实例 + 拦截器
│   │   │   ├── chat.ts                     # 对话 API
│   │   │   ├── knowledge.ts                # 知识库 API
│   │   │   ├── model.ts                    # 模型配置 API
│   │   │   ├── auth.ts                     # 认证 API
│   │   │   └── channel.js                  # 🆕 渠道管理 API
│   │   ├── views/                          # 页面视图
│   │   │   ├── chat/
│   │   │   │   └── ChatView.vue            # C端智能对话主页面
│   │   │   ├── admin/
│   │   │   │   ├── Dashboard.vue           # 仪表盘
│   │   │   │   ├── KnowledgeManage.vue     # 知识库管理
│   │   │   │   ├── ModelConfig.vue         # 模型配置
│   │   │   │   ├── FallbackConfig.vue      # 话术配置
│   │   │   │   ├── ChatLogs.vue            # 对话记录
│   │   │   │   ├── UserManage.vue          # 用户管理
│   │   │   │   └── ChannelManagement.vue   # 🆕 渠道管理
│   │   │   └── Login.vue                   # 登录页
│   │   ├── components/                     # 组件
│   │   │   ├── chat/                       # C端对话组件
│   │   │   │   ├── MessageList.vue         # 消息列表(虚拟滚动)
│   │   │   │   ├── UserMessage.vue         # 用户消息气泡
│   │   │   │   ├── AssistantMessage.vue    # AI回答气泡
│   │   │   │   ├── FallbackCard.vue        # 兜底引导卡片
│   │   │   │   ├── ChatInput.vue           # 输入区域
│   │   │   │   ├── SessionSidebar.vue      # 会话侧栏
│   │   │   │   └── TypingIndicator.vue     # 打字中动画
│   │   │   ├── admin/                      # B端管理组件
│   │   │   │   ├── UploadZone.vue          # 拖拽上传区域
│   │   │   │   ├── DocTable.vue            # 文档列表表格
│   │   │   │   └── StatCard.vue            # 统计卡片
│   │   │   └── common/                     # 通用组件
│   │   │       ├── MarkdownRenderer.vue    # Markdown 渲染
│   │   │       └── LoadingSpinner.vue      # 加载指示器
│   │   ├── utils/                          # 工具
│   │   │   ├── sse.ts                      # SSE 流式接收 (fetch+ReadableStream)
│   │   │   ├── markdown.ts                 # Markdown 渲染配置
│   │   │   └── format.ts                   # 日期/数字格式化
│   │   ├── styles/
│   │   │   ├── global.scss                 # 全局样式
│   │   │   └── chat.scss                   # 对话页专用样式
│   │   └── types/
│   │       └── index.ts                    # 全局 TypeScript 类型定义
│   ├── .env.development                    # 开发环境变量
│   ├── .env.production                     # 生产环境变量
│   ├── vite.config.ts                      # Vite 配置
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   ├── package.json
│   ├── nginx.conf                          # 生产 Nginx 配置
│   └── index.html
│
└── docs/                                   # 项目文档 (本目录现有 PRD 等)
```

---

## 4. 后端模块详解

### 4.1 配置层 config

#### 4.1.1 settings.py — 全局配置加载

**职责**：基于 Pydantic `BaseSettings` 从 `.env` 文件与环境变量加载全部配置。

| 配置分组 | 关键字段 | 默认值 | 说明 |
|---------|---------|--------|------|
| **应用** | `APP_ENV`、`LOG_LEVEL`、`APP_PORT` | dev / INFO / 8000 | 运行环境与日志级别 |
| **MySQL** | `MYSQL_HOST`、`PORT`、`USER`、`PASSWORD`、`DB` | localhost / 3306 / root | 关系库连接 |
| **Redis** | `REDIS_HOST`、`PORT`、`DB` | localhost / 6379 / 0 | 缓存连接 |
| **Milvus** | `MILVUS_HOST`、`PORT`、`COLLECTION` | localhost / 19530 | 向量库连接 |
| **MinIO** | `MINIO_HOST`、`PORT`、`ACCESS_KEY`、`SECRET_KEY`、`BUCKET` | localhost / 9000 | 对象存储 |
| **JWT** | `JWT_SECRET_KEY`、`JWT_EXPIRE_HOURS`、`JWT_ALGORITHM` | HS256 / 24h | 认证令牌 |
| **加密** | `CRYPTO_SECRET_KEY` | — | API Key 对称加密密钥 |
| **限流** | `RATE_LIMIT_MAX`、`RATE_LIMIT_WINDOW` | 30 / 60s | 每用户每分钟请求数 |

#### 4.1.2 database.py — SQLAlchemy 异步引擎

**关键组件**：

| 组件 | 作用 |
|------|------|
| `ASYNC_DATABASE_URL` | `mysql+aiomysql://user:pwd@host:port/db?charset=utf8mb4` |
| `AsyncEngine` | `create_async_engine(pool_size=20, max_overflow=40)` 连接池 |
| `AsyncSessionLocal` | `sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)` |
| `Base` | `declarative_base()` 所有 ORM 模型继承基类 |
| `get_db()` | FastAPI 依赖注入，yield 会话、finally close |

#### 4.1.3 redis.py — Redis 异步连接池

```python
# 核心对象
redis_client: Redis = redis.asyncio.from_url(
    f"redis://{host}:{port}/{db}",
    encoding="utf-8",
    decode_responses=True,
    max_connections=50,
)
```

#### 4.1.4 milvus.py — Milvus Client

| 方法 | 作用 |
|------|------|
| `connect()` | 建立 Milvus gRPC 连接，超时 5s |
| `ensure_collection()` | 检查 `knowledge_embeddings` 是否存在，不存在则按 schema 创建 + 建索引 |
| `get_client()` | 返回 `MilvusClient` 单例 |

#### 4.1.5 minio.py — MinIO Client

| 方法 | 作用 |
|------|------|
| `ensure_bucket(bucket)` | 不存在则创建 bucket，设置 `policy=public-read` |
| `upload_file(bucket, obj_name, file_path)` | 上传文件 |
| `get_presigned_url(bucket, obj_name)` | 生成 7 天预签名下载 URL |

---

### 4.2 数据模型层 models

> 全部模型继承 `Base`，使用 SQLAlchemy 2.0 声明式语法。时间字段用 `server_default=func.now()` / `onupdate=func.now()`。

#### 4.2.1 User — users 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK, AUTO_INCREMENT | 主键 |
| `username` | VARCHAR(64) | NOT NULL, UNIQUE, INDEX | 用户名 |
| `password_hash` | VARCHAR(256) | NOT NULL | BCrypt 哈希密码 |
| `role` | ENUM('user','admin') | DEFAULT 'user' | 角色 |
| `status` | TINYINT | DEFAULT 1 | 1:正常 0:禁用 |
| `created_at` / `updated_at` | DATETIME | — | 时间戳 |

#### 4.2.2 ChatSession — chat_sessions 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK | 主键 |
| `session_id` | VARCHAR(36) | NOT NULL, UNIQUE, INDEX | UUID |
| `user_id` | BIGINT | NOT NULL, FK→users.id, INDEX | 所属用户 |
| `title` | VARCHAR(256) | DEFAULT '新对话' | 会话标题 |
| `status` | ENUM('active','closed','transferred') | DEFAULT 'active' | 会话状态 |
| `created_at` / `updated_at` | DATETIME | — | 时间戳 |

#### 4.2.3 ChatMessage — chat_messages 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK | 主键 |
| `message_id` | VARCHAR(36) | NOT NULL, UNIQUE | UUID |
| `session_id` | VARCHAR(36) | NOT NULL, FK→sessions.session_id, INDEX | 会话ID |
| `role` | ENUM('user','assistant','system') | NOT NULL | 消息角色 |
| `content` | TEXT | NOT NULL | 消息内容 |
| `intent` | VARCHAR(32) | NULL | product_qa / off_topic / ambiguous |
| `sources` | JSON | NULL | 引用来源 `[{title, score, snippet}]` |
| `model_used` | VARCHAR(64) | NULL | 使用的模型名 |
| `tokens_used` | INT | NULL | 消耗 token 数 |
| `created_at` | DATETIME | INDEX | 创建时间 |

#### 4.2.4 KnowledgeDoc — knowledge_docs 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK | 主键 |
| `doc_id` | VARCHAR(36) | NOT NULL, UNIQUE | UUID |
| `filename` | VARCHAR(256) | NOT NULL | 原始文件名 |
| `file_path` | VARCHAR(512) | NOT NULL | MinIO 路径 |
| `file_type` | VARCHAR(16) | NOT NULL | pdf/docx/txt/md |
| `file_size` | BIGINT | NULL | 字节数 |
| `category` | VARCHAR(64) | NULL | 知识分类标签 |
| `chunk_size` | INT | DEFAULT 512 | 分块大小 |
| `overlap` | INT | DEFAULT 64 | 分块重叠 |
| `chunk_count` | INT | DEFAULT 0 | 分块总数 |
| `status` | ENUM('uploading','processing','indexed','failed') | DEFAULT 'uploading', INDEX | 处理状态 |
| `error_msg` | TEXT | NULL | 失败原因 |
| `created_at` / `updated_at` | DATETIME | — | 时间戳 |

#### 4.2.5 KnowledgeChunk — knowledge_chunks 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK | 主键 |
| `chunk_id` | VARCHAR(36) | NOT NULL, UNIQUE | 对应 Milvus 中的主键 ID |
| `doc_id` | VARCHAR(36) | NOT NULL, FK→docs.doc_id, INDEX | 所属文档 |
| `chunk_index` | INT | NOT NULL | 在文档中的序号 |
| `content` | TEXT | NOT NULL | 分块文本内容 |
| `token_count` | INT | NULL | token 数量 |
| `metadata` | JSON | NULL | `{page, section, category, ...}` |
| `created_at` | DATETIME | — | 创建时间 |

#### 4.2.6 ModelConfig — model_configs 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK | 主键 |
| `model_name` | VARCHAR(64) | NOT NULL, UNIQUE | 模型名称（如 duc-v2） |
| `api_base` | VARCHAR(256) | NOT NULL | API Base URL |
| `api_key_encrypted` | VARCHAR(512) | NOT NULL | AES 加密后的 API Key |
| `temperature` | DECIMAL(3,2) | DEFAULT 0.70 | 温度参数 (0~1) |
| `max_tokens` | INT | DEFAULT 2048 | 最大生成 Token 数 |
| `enabled` | TINYINT | DEFAULT 1 | 是否启用 |
| `is_default` | TINYINT | DEFAULT 0 | 是否为默认模型 |
| `created_at` / `updated_at` | DATETIME | — | 时间戳 |

#### 4.2.7 SystemConfig — system_configs 表 (KV 存储)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK | 主键 |
| `config_key` | VARCHAR(128) | NOT NULL, UNIQUE | 配置键 |
| `config_value` | TEXT | NOT NULL | 配置值 |
| `description` | VARCHAR(256) | NULL | 配置说明 |
| `updated_at` | DATETIME | ON UPDATE CURRENT_TIMESTAMP | 更新时间 |

**预置核心配置项**：

| config_key | 默认值 | 说明 |
|-----------|--------|------|
| `fallback_message` | 抱歉，我暂时无法回答该问题。您可以选择转接人工客服或拨打 400-xxx-xxxx 咨询。 | 兜底引导话术 |
| `show_transfer_button` | `true` | 是否显示转人工按钮 |
| `show_phone` | `true` | 是否显示电话提示 |
| `phone_number` | `400-xxx-xxxx` | 客服电话 |
| `rag_top_k` | `5` | 知识库检索返回条数 |
| `rag_score_threshold` | `0.60` | 向量检索最低相似度阈值 |
| `rag_chunk_size` | `512` | 分块大小 |
| `rag_chunk_overlap` | `64` | 分块重叠字符数 |
| `rag_hybrid_search` | `true` | 是否启用混合检索 |
| `rag_query_rewrite` | `true` | 是否启用 Query 改写 |
| `intent_confidence_high` | `0.85` | 意图识别高置信度阈值 |
| `intent_confidence_low` | `0.60` | 意图识别低置信度阈值 |

#### 4.2.8 ChannelSession — channel_sessions 表 (🆕 渠道会话映射)

> 详见 [11.9 渠道会话表 ChannelSession](#119-渠道会话表-channelsession)。该表存储外部第三方客服平台会话与内部 `chat_sessions.session_id` 的双向映射，是渠道适配层运行的核心数据结构。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK, AUTO_INCREMENT | 主键 |
| `platform` | VARCHAR(32) | NOT NULL, INDEX | 平台名 (zhibo/qiyu/udesk/zendesk/chatwoot/generic) |
| `external_session_id` | VARCHAR(128) | NOT NULL | 平台侧会话 ID |
| `external_user_id` | VARCHAR(128) | NULL | 平台侧用户 ID |
| `external_user_name` | VARCHAR(128) | NULL | 平台侧用户名 |
| `internal_session_id` | VARCHAR(36) | NOT NULL, INDEX | 对应 chat_sessions.session_id |
| `channel_type` | VARCHAR(32) | NULL | 渠道类型 (web/app/wechat/douyin/xiaohongshu) |
| `metadata` | JSON | NULL | 平台透传的额外信息 |
| `status` | VARCHAR(16) | DEFAULT 'active' | active/closed/transferred |
| `created_at` / `updated_at` | DATETIME | — | 时间戳 |

**联合唯一索引**: `uk_platform_session` (platform, external_session_id) — 同一平台同一外部会话只映射一次。

---

### 4.3 请求/响应模型 schemas

#### 4.3.1 chat.py — 对话相关 DTO

| 模型 | 用途 | 关键字段 |
|------|------|---------|
| `StreamChatRequest` | 流式对话请求 | `session_id: str`, `message: str`, `history: list[ChatMessageItem]` |
| `ChatMessageItem` | 消息单元 | `role: Literal['user','assistant','system']`, `content: str` |
| `SSEEvent` | SSE 事件（序列化 JSON 输出） | `type: Literal['answer','source','fallback','done','error']`, `content: str` (可选), `sources: list[SourceItem]` (可选), `data: dict` (可选) |
| `SourceItem` | 引用来源 | `title: str`, `score: float`, `snippet: str` |
| `ChatSessionDTO` | 会话信息 | `session_id: str`, `title: str`, `created_at: datetime` |
| `ChatMessageDTO` | 消息详情 | `message_id: str`, `role: str`, `content: str`, `sources: list`, `created_at: datetime` |
| `TransferHumanRequest` | 转人工请求 | `session_id: str`, `reason: str` |
| `TransferHumanResponse` | 转人工响应 | `transfer_status: str`, `human_service_url: str`, `phone: str`, `message: str` |

#### 4.3.2 knowledge.py — 知识库 DTO

| 模型 | 用途 | 关键字段 |
|------|------|---------|
| `DocUploadResponse` | 上传响应 | `doc_id: str`, `filename: str`, `chunk_count: int`, `status: str` |
| `DocListItem` | 文档列表项 | `doc_id`, `filename`, `file_type`, `chunk_count`, `status`, `created_at` |
| `DocFilterParams` | 筛选参数 | `page: int=1`, `page_size: int=10`, `status: str=None` |

#### 4.3.3 admin.py — 管理后台 DTO

| 模型 | 用途 | 关键字段 |
|------|------|---------|
| `ModelConfigUpdate` | 模型配置新增/更新 | `model_name`, `api_base`, `api_key`, `temperature`, `max_tokens`, `enabled`, `is_default` |
| `FallbackMessageUpdate` | 兜底话术更新 | `message`, `show_transfer_button`, `show_phone`, `phone_number` |
| `ChatLogFilter` | 对话记录筛选 | `session_id`, `start_date`, `end_date`, `intent`, `page`, `page_size` |
| `ChatLogItem` | 对话记录条目 | 会话ID、用户、问题摘要、意图、时间、状态 |

#### 4.3.4 auth.py — 认证 DTO

| 模型 | 用途 | 关键字段 |
|------|------|---------|
| `LoginRequest` | 登录请求 | `username: str (NotBlank)`, `password: str (NotBlank)` |
| `TokenResponse` | 登录响应 | `access_token: str`, `token_type: str="bearer"`, `expires_in: int`, `user_info: UserInfo` |
| `UserInfo` | 用户信息 | `user_id`, `username`, `role`, `status` |

---

### 4.4 路由层 routers

> 全部路由前缀：`/api/v1`。统一返回 `{"code": 0, "message": "success", "data": {...}}`；SSE 流式接口使用 `StreamingResponse`，`media_type="text/event-stream"`。
> 🆕 渠道适配层路由（`/api/v1/webhook/*`、`/api/v1/openai/*`、`/api/v1/widget/*`、`/api/v1/admin/channels/*`）详见 [第 11 章](#11-渠道适配层-adapters)。

#### 4.4.1 chat.py — C 端对话接口

| HTTP | 路径 | 函数签名 | 功能 |
|------|------|---------|------|
| **POST** | `/chat/stream` | `async def stream_chat(req: StreamChatRequest, db: Session = Depends, user = Depends(get_current_user))` | **核心**：发送消息，SSE 流式返回回答 |
| **GET** | `/chat/sessions/{session_id}/messages` | `async def get_messages(session_id, page=1, page_size=20, ...)` | 分页获取会话消息历史 |
| **POST** | `/chat/sessions` | `async def create_session(user=...)` | 创建新会话，返回 `{session_id, title, created_at}` |
| **POST** | `/chat/transfer-human` | `async def transfer_human(req: TransferHumanRequest)` | 申请转人工客服 |

#### 4.4.2 auth.py — 认证接口

| HTTP | 路径 | 功能 |
|------|------|------|
| POST | `/auth/login` | 登录验证 → 返回 JWT Token + 用户信息 |
| POST | `/auth/logout` | 登出（黑名单 Token 写入 Redis） |
| GET | `/auth/me` | 获取当前登录用户信息 |

#### 4.4.3 admin_knowledge.py — 知识库管理 (需 admin 角色)

| HTTP | 路径 | 功能 |
|------|------|------|
| POST | `/admin/knowledge/upload` | multipart/form-data 上传文档 → 异步处理 → 返回 doc_id + 状态 |
| GET | `/admin/knowledge/docs` | 分页获取文档列表（支持状态筛选） |
| DELETE | `/admin/knowledge/docs/{doc_id}` | 删除文档（MySQL + Milvus + MinIO 联动清理） |
| POST | `/admin/knowledge/docs/{doc_id}/reindex` | 重新向量化索引 |

#### 4.4.4 admin_config.py — 配置管理 (需 admin)

| HTTP | 路径 | 功能 |
|------|------|------|
| GET/PUT | `/admin/config/model` | 列表 / 新增 / 更新模型配置 |
| DELETE | `/admin/config/model/{id}` | 删除模型配置 |
| PATCH | `/admin/config/model/{id}/toggle` | 启用/禁用模型 |
| GET/PUT | `/admin/config/fallback-message` | 读取 / 更新兜底话术配置 |
| GET/PUT | `/admin/config/system/{key}` | 通用 KV 配置读写 |

#### 4.4.5 admin_chat_logs.py — 对话记录 (需 admin)

| HTTP | 路径 | 功能 |
|------|------|------|
| GET | `/admin/chat/logs` | 按会话/日期/意图分页查询对话记录摘要 |
| GET | `/admin/chat/logs/{session_id}` | 获取指定会话的完整对话详情 |

#### 4.4.6 admin_users.py — 用户管理 (需 admin)

| HTTP | 路径 | 功能 |
|------|------|------|
| GET | `/admin/users` | 用户列表分页 |
| POST | `/admin/users` | 创建用户（含密码哈希） |
| PUT | `/admin/users/{id}` | 更新用户信息 |
| PATCH | `/admin/users/{id}/toggle` | 启用/禁用用户 |
| PATCH | `/admin/users/{id}/reset-password` | 重置密码 |

---

### 4.5 业务服务层 services

#### 4.5.1 IntentService — 意图识别服务

**文件**: `services/intent_service.py`

**职责**: 判断用户输入属于 `product_qa`（产品相关）还是 `off_topic`（无关问题），支持 `ambiguous`（模糊）三分类。

**核心字段**:

| 常量 | 值 | 说明 |
|------|----|------|
| `CONFIDENCE_HIGH` | 0.85 | 高于此值直接采信分类结果 |
| `CONFIDENCE_LOW` | 0.60 | 低于此值判定为 ambiguous |
| `INTENT_PROMPT_V2` | — | Few-shot 增强版分类 Prompt（含 10 条示例 + 多轮上下文） |
| `QUICK_OFF_TOPIC_PATTERNS` | list[regex] | 纯问候、极短无意义、无关关键词正则（第一层快速过滤） |
| `QUICK_PRODUCT_PATTERNS` | list[regex] | 生成/出图/提示词/报错/付费等关键词正则（第一层快速过滤） |

**核心方法**:

| 方法 | 作用 |
|------|------|
| `async classify(message: str, history: list) -> IntentResult` | **主入口**：第一层规则过滤 → 第二层 LLM 精细判断 → 置信度策略 → 返回 `IntentResult(intent, confidence)` |
| `_match_rules(message: str) -> IntentResult \| None` | 第一层：关键词/正则快速匹配，0ms 无 API 调用，匹配则直接返回高置信度结果 |
| `async _call_llm_classify(message: str, history: list) -> IntentResult` | 第二层：调用 LLM，temperature=0.05，JSON 模式输出，正则提取 intent + confidence |
| `_apply_confidence_strategy(result: IntentResult) -> IntentResult` | 置信度兜底：≥0.85 直取，0.60~0.85 间若 off_topic 则保守改为 product_qa（宁可多答不漏答），<0.60 返回 ambiguous |
| `_parse_json_safe(text: str) -> dict` | 从模型输出中容错提取 JSON（支持首尾噪声） |

**返回结构**:

```python
@dataclass
class IntentResult:
    intent: Literal["product_qa", "off_topic", "ambiguous"]
    confidence: float
```

#### 4.5.2 RAGService — RAG 知识库检索服务

**文件**: `services/rag_service.py`

**职责**: 知识库语义检索 + 上下文拼接 + 可选混合检索 / Query 改写 / Re-ranking。

**依赖**: Milvus Client、Embedding 模型、ConfigService

**核心方法**:

| 方法 | 作用 |
|------|------|
| `async retrieve(query: str, top_k: int=None) -> list[RetrievalResult]` | **主检索入口**：Query 改写（可选）→ 向量化 → 混合检索（向量+关键词）→ RRF 融合 → 低分过滤 → Re-rank（可选） |
| `async build_context(results: list[RetrievalResult]) -> str` | 将检索结果拼接为 LLM 可读的上下文字符串，格式 `[来源1] xxx\n\n[来源2] xxx` |
| `async _vector_search(query_embedding: list[float], top_k: int) -> list` | Milvus 向量检索，`metric_type=COSINE`，取 top_k*2 预留 |
| `async _keyword_search(query: str, top_k: int) -> list` | MySQL `LIKE` 模糊匹配或 Elasticsearch 关键词检索 |
| `_rrf_fusion(*result_lists, k=60)` | RRF（Reciprocal Rank Fusion）公式 `score = Σ 1/(k + rank)` 融合排序 |
| `async _rewrite_query(query: str) -> list[str]` | LLM Query 改写，返回 1~3 个改写版本（口语化→标准术语） |
| `async _rerank(query: str, candidates: list[str], top_k: int)` | BGE-Reranker-v2-m3 Cross-Encoder 重排序 |

#### 4.5.3 LLMService — 大模型调用服务

**文件**: `services/llm_service.py`

**职责**: 多模型统一调用封装，支持流式/非流式、动态模型切换、API Key 解密。

**核心方法**:

| 方法 | 作用 |
|------|------|
| `async get_client(model_name: str=None) -> AsyncOpenAI` | 从 DB 读取默认或指定模型配置，解密 API Key，构建 OpenAI 兼容的 AsyncOpenAI 客户端 |
| `async generate(messages: list[dict], system_prompt: str=None, stream: bool=False, model_name: str=None)` | 通用生成接口。非流式返回 str；流式返回 `AsyncGenerator[str, None]` |
| `async _stream_generate(client, model_config, messages)` | 流式生成器：遍历 chunk → 跳过 None → `yield delta.content` |
| `async count_tokens(text: str) -> int` | 调用 tokenizer 或估算 API 返回 usage |
| `async list_enabled_models() -> list[dict]` | 从 DB 读所有启用模型缓存 |

#### 4.5.4 ChatService — 对话编排服务 (核心调度)

**文件**: `services/chat_service.py`

**职责**: 串联 **意图识别 → RAG 检索 → LLM 生成 → 兜底引导 → 记忆存储** 的完整编排。

**依赖**: IntentService / RAGService / LLMService / MemoryService / ConfigService

**核心系统提示词**:

```python
SYSTEM_PROMPT = """你是一个AI出图产品的智能客服助手。请根据以下知识库内容回答用户问题。
如果知识库内容不足以回答，请基于你的知识给出合理回答，但要注明"仅供参考"。
回答要简洁、专业、友好，使用 Markdown 格式。

【知识库内容】
{context}
【结束】
"""

AMBIGUOUS_PROMPT = """您好！我不太确定您的问题。您是想咨询AI出图产品的相关问题吗？
您可以尝试这样提问：
• "如何生成一张水墨风格的山水画？"
• "图片分辨率最高支持多少？"
• "提示词怎么写效果更好？"
如果以上都不是您想问的，您可以转人工客服或拨打 {phone}。"""
```

**核心方法**:

| 方法 | 作用 |
|------|------|
| `async handle_message_stream(session_id: str, message: str, history: list) -> AsyncGenerator[SSEEvent]` | **完整流式处理流程**，见下方流程图 |

**处理流程**:

```
handle_message_stream 执行步骤：
┌─ Step 1: 调 intent_service.classify(message, history) 识别意图
├─ Step 2: 判断意图分支
│   ├─ off_topic → SSE: answer(兜底话术) + fallback({show_transfer, show_phone, phone}) + done → return
│   └─ ambiguous → SSE: answer(澄清话术) + done → return
│   └─ product_qa → 继续
├─ Step 3: rag_service.retrieve(message) 获取检索结果 + rag_service.build_context 拼接上下文
├─ Step 4: memory_service.get_history(session_id) 加载 Redis 短期历史（最近20条）
├─ Step 5: 组装 SYSTEM_PROMPT + 历史消息 + 当前用户消息
├─ Step 6: SSE 先下发 source 事件（引用来源列表）
├─ Step 7: llm_service.generate(..., stream=True) 逐 token 下发 answer 事件，累积 full_answer
├─ Step 8: SSE 下发 done 事件
└─ Step 9: finally: memory_service.save_message(用户消息+AI回答) → Redis+MySQL双写
```

#### 4.5.5 MemoryService — 对话记忆管理

**文件**: `services/memory_service.py`

**职责**: **Redis 短期记忆（滑动窗口）+ MySQL 长期持久化** 双写。

**常量**:

| 常量 | 值 | 说明 |
|------|----|------|
| `SHORT_TERM_TTL` | 86400 (24h) | Redis 中对话历史的过期时间 |
| `MAX_SHORT_TERM` | 20 | 每个会话保留最近 N 条消息在 Redis |

**核心方法**:

| 方法 | 作用 |
|------|------|
| `async get_history(session_id: str) -> list[dict]` | `redis.lrange(key, -MAX_SHORT_TERM, -1)` → JSON parse 返回最近消息列表 |
| `async save_message(session_id, role, content, **extra)` | **双写**：① `redis.rpush` + `ltrim` + `expire`（滑动窗口）；② DB 异步插入 `ChatMessage` |
| `async clear_history(session_id)` | 清空 Redis + 软删除 DB 记录 |

#### 4.5.6 KnowledgeService — 知识库文档处理

**文件**: `services/knowledge_service.py`

**职责**: 文档 **上传 → 解析 → 清洗 → 分块 → 向量化 → 入库 (Milvus+MySQL+MinIO)** 完整流水线。

**核心方法**:

| 方法 | 作用 |
|------|------|
| `async process_document(doc_id: str, file: UploadFile, category: str, chunk_size: int, overlap: int)` | **处理流水线**：7 步异步执行，期间更新 doc status |
| `Step 1 _save_to_minio(file)` | 保存原始文件到 MinIO，path=`knowledge/yyyy/MM/dd/{uuid}.{ext}` |
| `Step 2 _parse_document(file, filename) -> str` | 根据扩展名路由：PyMuPDF→`_parse_pdf`、python-docx→`_parse_docx`、直接读取→txt/md |
| `Step 3 _clean_text(raw_text) -> str` | 去除多余空行/页眉页脚/控制字符/多余空格 |
| `Step 4 _split_by_headers(cleaned)` | 识别 Markdown/Word 标题，按标题预切分 sections |
| `Step 5 RecursiveCharacterTextSplitter` | 每个 section 内分块（按 \n\n→\n→句号→空格→字符 逐级切分） |
| `Step 6 embedder.batch_embed(texts)` | 批量向量化 |
| `Step 7 milvus.insert + db.add chunks + doc.status=indexed` | 写入 Milvus + MySQL，更新 chunk_count |
| `async delete_document(doc_id)` | 联动清理：MinIO 文件 + Milvus chunk + MySQL chunk + MySQL doc |
| `async reindex(doc_id)` | 先 delete 再 process_document |

#### 4.5.7 ConfigService — 配置管理

**文件**: `services/config_service.py`

**职责**: 统一管理 system_configs（KV）和 model_configs，带 10 分钟 Redis 缓存。

**核心方法**:

| 方法 | 作用 |
|------|------|
| `async get(key: str, default=None) -> str` | 先查 Redis 缓存 `config:cache:{key}` → 未命中查 DB → 写缓存 10min → 返回 |
| `async set(key: str, value: str, description=None)` | DB upsert + 删 Redis 缓存 |
| `async get_fallback_message() -> FallbackConfig` | 组装 fallback_message / show_transfer_button / show_phone / phone_number |
| `async get_default_model() -> ModelConfig` | 返回 `is_default=1 and enabled=1` 的模型配置 |
| `async list_models(enabled_only=False)` | 模型列表（带缓存） |

#### 4.5.8 AuthService — 认证鉴权

**文件**: `services/auth_service.py`

**职责**: JWT 签发/验证、密码哈希、权限检查。

| 方法 | 作用 |
|------|------|
| `async login(username, password) -> TokenResponse` | 查用户 → BCrypt 校验 → 签发 JWT（含 user_id/username/role）→ 写入 Redis token 白名单 |
| `async verify_token(token: str) -> dict` | 解码 JWT → 检查 Redis 白名单 → 返回 payload |
| `async hash_password(raw_password) -> str` | passlib bcrypt 哈希 |
| `async blacklist_token(token: str)` | logout 时把 token 加入 Redis 黑名单（TTL = JWT 剩余过期时间） |

---

### 4.6 中间件 middleware

#### 4.6.1 JWT 认证中间件 AuthMiddleware

- **exclude_paths**: `/api/v1/auth/login`, `/docs`, `/openapi.json`, `/api/v1/chat/**` (C 端聊天是否需登录按需求调整)
- 从 `Authorization: Bearer xxx` 提取 token → `AuthService.verify_token` → 成功：`request.state.user = payload`；失败：401 `{"code": 401, "message":"请先登录"}`

#### 4.6.2 限流中间件 RateLimitMiddleware

- **策略**: 滑动窗口，默认 30 次/分钟/用户
- **实现**: Redis 有序集合 `rate_limit:{user_id}`，member=timestamp，score=timestamp，每次请求 zremrangebyscore 清理过期 + zadd + zcard 比较，超限返回 429 `{"code": 429, "message":"请求过于频繁，请稍后重试"}`

#### 4.6.3 请求日志中间件 RequestLogMiddleware

- 记录每个请求的 `method`、`path`、`query`、`user_id`、`耗时 ms`、`HTTP 状态码`
- INFO 级别日志，可配置慢请求阈值（>500ms 打 WARN）

#### 4.6.4 CORS 中间件 (FastAPI 内置)

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### 4.6.5 全局异常处理

```python
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    log.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "服务内部错误，请稍后重试", "data": None}
    )
# 另外单独处理 RequestValidationError (400) / HTTPException
```

---

### 4.7 工具层 utils

#### 4.7.1 document_parser.py — 多格式文档解析

| 函数 | 作用 |
|------|------|
| `parse_pdf(file_obj) -> str` | PyMuPDF (fitz) 逐页 `get_text()`，拼接，去除页码噪声 |
| `parse_docx(file_obj) -> str` | python-docx 遍历 paragraphs，join with \n |
| `parse_txt(file_obj) -> str` | 直接 read，utf-8 decode，兜底 GBK |
| `parse_md(file_obj) -> str` | 直接读取 markdown 原文 |
| `parse_auto(file, filename) -> str` | 按扩展名自动路由 |

#### 4.7.2 crypto.py — 对称加密

| 函数 | 作用 |
|------|------|
| `encrypt(plaintext: str, secret_key: str) -> str` | Fernet AES-128-CBC 加密，base64 输出 |
| `decrypt(ciphertext: str, secret_key: str) -> str` | 解密，用于 API Key 读取时还原 |

> 密钥来源：settings.CRYPTO_SECRET_KEY（32 字节 url-safe base64）

#### 4.7.3 sse.py — SSE 响应工具

| 函数 | 作用 |
|------|------|
| `sse_pack(event: SSEEvent) -> bytes` | 将事件序列化为 SSE 协议帧：`event: {type}\ndata: {json}\n\n` |
| `sse_stream(async_iter)` | 包装异步生成器，逐 pack 流式输出 |

---

## 5. 前端模块详解

> 根目录：`ai-customer-frontend`
> 技术栈：Vue 3.4 + TypeScript 5 + Vite 5 + Pinia 2 + Vue Router 4 + Element Plus 2.7 + Tailwind CSS + Sass

### 5.1 入口与构建配置

#### 5.1.1 main.ts — 应用入口

```
createApp(App)
  → 全量注册 @element-plus/icons-vue 图标
  → app.use(createPinia())
  → app.use(router)
  → app.use(ElementPlus, { locale: zhCn })   // 中文语言包
  → 引入 @/styles/global.scss
  → app.mount('#app')
```

#### 5.1.2 vite.config.ts

| 配置项 | 值 |
|--------|-----|
| **插件** | `vue()`、`AutoImport` (vue/vue-router/pinia API + ElementPlusResolver)、`Components` (自动按需注册 + ElementPlusResolver) |
| **resolve.alias** | `@` → `src` |
| **环境变量** | 读取 `VITE_API_BASE_URL` |
| **开发服务器** | port: 5173, host: 0.0.0.0 |
| **开发代理** | `/api` → `http://localhost:8000`，`proxyReq` 强制注入 `Accept: text/event-stream` 支持 SSE |
| **CSS** | scss 全局注入 `@use "@/styles/variables.scss" as *;` |

#### 5.1.3 环境变量

- `.env.development`: `VITE_API_BASE_URL=http://localhost:8000`
- `.env.production`: `VITE_API_BASE_URL=`（空，走 Nginx 同域反向代理）

---

### 5.2 路由 router

**History 模式**，全部懒加载，路由守卫做登录+权限校验：

| path | name | 组件 | meta |
|------|------|------|------|
| `/` | — | — | redirect `/chat` |
| `/chat` | `Chat` | `chat/ChatView.vue` | `{ title:'AI智能客服', requiresAuth:true }` |
| `/login` | `Login` | `Login.vue` | `{ title:'登录', requiresAuth:false }` |
| `/admin` | — | `AdminLayout.vue` | `{ requiresAuth:true, requiresAdmin:true }`，redirect `/admin/dashboard` |
| `/admin/dashboard` | `Dashboard` | `admin/Dashboard.vue` | requiresAdmin |
| `/admin/knowledge` | `KnowledgeManage` | `admin/KnowledgeManage.vue` | requiresAdmin |
| `/admin/model` | `ModelConfig` | `admin/ModelConfig.vue` | requiresAdmin |
| `/admin/fallback` | `FallbackConfig` | `admin/FallbackConfig.vue` | requiresAdmin |
| `/admin/chat-logs` | `ChatLogs` | `admin/ChatLogs.vue` | requiresAdmin |
| `/admin/users` | `UserManage` | `admin/UserManage.vue` | requiresAdmin |
| `/:pathMatch(.*)*` | — | — | redirect `/chat` |

**路由守卫 `router.beforeEach`**:
1. 设置 `document.title`
2. `!to.meta.requiresAuth` 直接放行
3. 未登录 → 重定向 `/login?redirect=fullPath`
4. `requiresAdmin && auth.userInfo.role !== 'admin'` → `ElMessage.warning('无权访问')` + 重定向 `/chat`
5. 放行

---

### 5.3 状态管理 stores

> 全部 Setup Store 写法。

#### 5.3.1 stores/chat.ts — 对话状态

**State**:
- `currentSessionId: string`
- `sessions: ChatSession[]`
- `messages: ChatMessage[]`
- `isStreaming: boolean` — 流式接收中
- `pendingMessage: string`
- `abortController: AbortController | null`
- `fallbackConfig: FallbackConfig | null`

**Actions**:

| 方法 | 作用 |
|------|------|
| `sendMessage(content: string)` | 调 streamChat()，内部：设置 isStreaming → addMessage(user) → fetch SSE → onToken 更新最后 AI 消息 content → onSource 写入 sources → onDone 取消流式 + 持久化 |
| `loadHistory(sessionId: string)` | 拉取消息历史，重置 messages |
| `createSession()` | POST `/chat/sessions` → 插入 sessions 首项 + 切换 |
| `switchSession(sessionId: string)` | 设置 currentSessionId + loadHistory |
| `stopStreaming()` | `abortController.abort()`，isStreaming=false |
| `transferToHuman(reason: string)` | POST `/chat/transfer-human`，获取人工 URL 和电话 |

#### 5.3.2 stores/auth.ts — 认证状态

**State**: `token: string`（localStorage 读写）、`userInfo: UserInfo | null`

**Getters**: `isLoggedIn = computed(() => !!token.value)`、`isAdmin`

**Actions**: `login(username, password)` → `setToken` + `setUserInfo`；`logout()` → 调 API + 清 localStorage + 跳登录页

#### 5.3.3 stores/admin.ts — 管理后台

**State**: `knowledgeDocs`、`modelConfigs`、`fallbackMessage`、`chatLogs`

**Actions**: `uploadDocument(file)`, `updateModelConfig()`, `updateFallback()`, `fetchChatLogs(filters)`

---

### 5.4 API 请求层

> 全部基于 `@/api/request` axios 实例，`baseURL = VITE_API_BASE_URL + '/api/v1'`，`timeout = 30000`。

#### 5.4.1 request.ts — axios 封装

- **请求拦截器**: authStore.token → `config.headers['Authorization'] = 'Bearer ' + token`
- **响应拦截器成功**: `data.code !== 0` → `ElMessage.error(data.message)` + reject；否则 resolve(data)
- **响应拦截器失败**: HTTP 401 → 清 token 跳 `/login`；HTTP 429 → "请求过于频繁"；其他 → 默认提示

#### 5.4.2 utils/sse.ts — SSE 流式接收 (核心)

**实现思路**：基于原生 `fetch + ReadableStream`（不用 EventSource，需支持 POST + 自定义 header + AbortController）。

**流程**:
1. 拼接 URL，读 localStorage token → 注入 Authorization
2. `fetch(url, { method, headers:{ 'Accept':'text/event-stream', ... }, body, signal })`
3. HTTP 错误处理：401→清token跳登录，403→"没有权限"，500→"服务器内部错误"
4. `response.body.getReader()` + `TextDecoder` 逐块解码，按 `\n` 切行
5. 匹配 `data:` 前缀行 → JSON.parse → 按 `type` 分发 callback：
   - `answer` → `onToken(data.content)`
   - `source` → `onSource(data.sources)`
   - `fallback` → `onFallback(data.data)`
   - `done` → `onDone(data.message_id)`
   - `error` → `onError(data.message)`
6. `AbortError` → `onDone`（用户取消）；其他 → `onError`

> 无自动重连机制，由视图层展示错误。

---

### 5.5 公共组件 components

#### 5.5.1 C 端对话组件树

```
ChatView.vue (页面)
├── SessionSidebar.vue          # 会话列表侧栏 (w:260px)
│   ├── SessionItem.vue         # 单个会话条目 (h:52px)
│   └── NewSessionButton.vue    # 新建对话按钮
├── ChatMain.vue                # 对话主区域 (flex:1)
│   ├── MessageList.vue         # 消息列表 (虚拟滚动)
│   │   ├── UserMessage.vue     # 用户气泡：右对齐，蓝底#409EFF，白字，圆角12px
│   │   ├── AssistantMessage.vue# AI气泡：左对齐，白底卡片+1px边框，圆角12px，含阴影
│   │   │   ├── MarkdownRenderer.vue  # markdown-it + highlight.js
│   │   │   ├── SourceTags.vue        # 引用来源标签 (bg:#ECF5FF color:#409EFF)
│   │   │   └── TypingIndicator.vue   # 三点跳动动画
│   │   ├── FallbackCard.vue    # 兜底引导卡片 (橙色边框#E6A23C)
│   │   │   ├── TransferButton.vue
│   │   │   └── PhoneLink.vue
│   │   └── SystemMessage.vue
│   ├── ChatInput.vue           # 输入区域 (h:80px)
│   │   ├── TextArea.vue        # AutoResize Textarea
│   │   └── SendButton.vue      # 40x40 蓝色按钮
│   └── ScrollManager.vue       # 自动滚动到最新消息，用户上滑时暂停
└── TransferModal.vue           # 转人工确认弹窗
```

#### 5.5.2 B 端管理组件树

```
AdminLayout.vue
├── AdminSidebar.vue            # 200px 侧边导航（仪表盘/知识库/模型/话术/记录/用户）
├── AdminHeader.vue             # 56px 顶部栏
├── Dashboard.vue               # 仪表盘页面
│   └── StatCard.vue × 4        # 今日对话数/转人工率/知识命中率/活跃用户
├── KnowledgeManage.vue         # 知识库管理
│   ├── UploadZone.vue          # 拖拽上传区域 (虚线边框, hover变色)
│   ├── DocTable.vue            # 文档列表表格 (状态标签 4 色)
│   └── DocStatusTag.vue        # 状态标签组件
├── ModelConfig.vue             # 模型配置
│   ├── ModelForm.vue           # 新增/编辑表单 (temperature滑块)
│   └── ModelCard.vue           # 模型卡片
├── FallbackConfig.vue          # 话术配置
│   └── FallbackForm.vue        # 编辑表单 + 预览卡片
├── ChatLogs.vue                # 对话记录
│   ├── LogFilter.vue           # 筛选条件 (日期/用户/意图/状态)
│   ├── LogTable.vue            # 记录表格
│   └── LogDetail.vue           # 右侧 480px Drawer 对话详情
└── UserManage.vue              # 用户管理
```

---

### 5.6 视图 views

| 页面文件 | 主要内容 |
|---------|---------|
| `chat/ChatView.vue` | C端核心页：三栏布局，侧栏会话列表 + 主对话区 + 底部输入区 |
| `Login.vue` | 居中卡片：用户名 + 密码 + 登录按钮，登录成功后跳 redirect 或 /chat |
| `admin/Dashboard.vue` | 4 张统计卡片 + 折线图(近7日趋势) + 饼图(意图分布) + 最近对话表格 |
| `admin/KnowledgeManage.vue` | 拖拽上传区 + 文档列表表格(含分页) + 删除/重新索引操作 |
| `admin/ModelConfig.vue` | 模型卡片列表 + 新增/编辑表单(含 temperature 滑块, 0~1 步长0.05) |
| `admin/FallbackConfig.vue` | 多行文本域编辑话术 + 显示选项开关 + 电话输入框 + 实时预览卡片 |
| `admin/ChatLogs.vue` | 筛选条件栏 + 数据表格 + 右侧 Drawer 展示完整对话详情 |
| `admin/UserManage.vue` | 用户表格 + 新增/编辑用户弹窗 + 重置密码 + 启用禁用 |

---

## 6. 数据库设计

### 6.1 核心表结构

详见 **4.2 数据模型层**，共 8 张核心表（含 🆕 渠道适配层新增的 `channel_sessions`）：

| 表名 | 用途 | 核心索引 |
|------|------|---------|
| `users` | 用户账号 | `idx_username` (username UNIQUE) |
| `chat_sessions` | 对话会话 | `idx_user_id`、`idx_session_id` (session_id UNIQUE) |
| `chat_messages` | 对话消息 | `idx_session_id`、`idx_created_at` |
| `knowledge_docs` | 知识库文档元数据 | `idx_status` |
| `knowledge_chunks` | 知识分块 | `idx_doc_id` |
| `model_configs` | 多模型配置 | `uk_model_name` (model_name UNIQUE) |
| `system_configs` | KV 系统配置 | `uk_config_key` (config_key UNIQUE) |
| `channel_sessions` 🆕 | 外部平台 ↔ 内部会话映射 | `idx_platform`、`idx_internal_session_id`、`uk_platform_session` (platform+external_session_id) |

**ER 关系**:

```
users ──1:N──> chat_sessions ──1:N──> chat_messages
                                          │
                                     N:1 (可选, sources JSON)
                                          ▼
                                   knowledge_chunks

knowledge_docs ──1:N──> knowledge_chunks
                              │
                         1:1 (向量映射)
                              ▼
                    Milvus: knowledge_embeddings

model_configs (独立，被 LLMService 读取)
system_configs (独立 KV，被 ConfigService 读取)

🆕 channel_sessions ──N:1──> chat_sessions  (internal_session_id → session_id)
        │
   外部平台会话映射 (platform + external_session_id 唯一)
        │
   被 SessionMapper 读写，被 ChannelAdminService 统计
```

### 6.2 向量数据库 Milvus

**Collection**: `knowledge_embeddings`

| 字段名 | 类型 | 参数 | 说明 |
|--------|------|------|------|
| `chunk_id` | VARCHAR | max_length=36, **PK** | 对应 MySQL knowledge_chunks.chunk_id |
| `doc_id` | VARCHAR | max_length=36 | 所属文档 |
| `content` | VARCHAR | max_length=8192 | 分块原文（冗余存储，方便直接返回） |
| `embedding` | FLOAT_VECTOR | dim=1024 | 向量，BGE-M3 或 text-embedding-v3 |
| `category` | VARCHAR | max_length=64 | 知识分类标签 |

**索引**:

| 索引项 | 值 |
|--------|-----|
| index_field | `embedding` |
| index_type | `IVF_FLAT`（生产建议 `HNSW`） |
| metric_type | `COSINE` |
| params | `{nlist: 128}` |

### 6.3 Redis 缓存设计

| Key 模式 | 类型 | TTL | 说明 |
|----------|------|-----|------|
| `session:{session_id}:history` | List | 86400 (24h) | 最近 20 条对话历史，JSON 字符串，滑动窗口 ltrim |
| `token:{jwt_token}` | String | 与 JWT exp 一致 | Token 白名单/黑名单判断 |
| `rate_limit:{user_id}` | ZSet | 60s | 滑动窗口限流 (member + score = timestamp_ms) |
| `doc_process:{doc_id}` | String | 1800 (30min) | 文档处理状态锁，防止重复处理 |
| `config:cache:{config_key}` | String | 600 (10min) | system_configs 缓存，减少 DB 查询 |
| `models:cache:all` | String | 3600 (1h) | 全部启用模型配置的 JSON 缓存 |
| `chat_abort:{message_id}` | String | 300 (5min) | 流式中断标记 |
| `webhook_dedup:{message_id}` 🆕 | String | 300 (5min) | Webhook 消息防重复处理标记（内存缓存兜底，重启后失效） |

---

## 7. 依赖关系

### 7.1 Python 后端依赖 (requirements.txt)

| 依赖包 | 版本建议 | 用途 |
|--------|---------|------|
| `fastapi` | ≥0.110 | Web 框架 |
| `uvicorn[standard]` | ≥0.29 | ASGI 服务器 |
| `sqlalchemy[asyncio]` | ≥2.0 | ORM + 异步 DB |
| `aiomysql` | ≥0.2 | MySQL 异步驱动 |
| `alembic` | ≥1.13 | 数据库迁移 |
| `redis[hiredis]` | ≥5.0 | Redis 异步客户端 |
| `pymilvus` | ≥2.4 | Milvus 向量库 SDK |
| `minio` | ≥7.2 | MinIO 对象存储 SDK |
| `openai` | ≥1.30 | AsyncOpenAI 兼容协议客户端 |
| `httpx` | ≥0.27 | 通用 HTTP client (备用) |
| `python-jose[cryptography]` | ≥3.3 | JWT 签发/验证 |
| `passlib[bcrypt]` | ≥1.7 | 密码 BCrypt 哈希 |
| `cryptography` | ≥42.0 | Fernet API Key 加解密 |
| `langchain-text-splitters` | ≥0.2 | RecursiveCharacterTextSplitter |
| `pymupdf` | ≥1.24 | PDF 解析 (PyMuPDF) |
| `python-docx` | ≥1.1 | Word 文档解析 |
| `markdown` | ≥3.6 | Markdown 解析 |
| `pydantic` | ≥2.6 | 数据验证 + Settings |
| `pydantic-settings` | ≥2.2 | 环境变量加载 |
| `python-multipart` | ≥0.0.9 | FastAPI 文件上传支持 |
| `orjson` | ≥3.10 | 高性能 JSON 序列化 |
| `python-dotenv` | ≥1.0 | .env 文件加载 |

### 7.2 前端依赖 (package.json)

| 包名 | 版本 | 用途 |
|------|------|------|
| `vue` | ^3.4.0 | 核心框架 |
| `typescript` | ^5.4.0 | 类型系统 |
| `vite` | ^5.2.0 | 构建工具 |
| `vue-router` | ^4.3.0 | 路由 |
| `pinia` | ^2.1.0 | 状态管理 |
| `element-plus` | ^2.7.0 | UI 组件库 |
| `@element-plus/icons-vue` | ^2.3.0 | 图标库 |
| `axios` | ^1.6.0 | HTTP 请求 |
| `markdown-it` | ^14.1.0 | Markdown 渲染 |
| `markdown-it-highlightjs` | ^4.1.0 | 代码高亮 |
| `highlight.js` | ^11.9.0 | 代码语法高亮 |
| `tailwindcss` | ^3.4.0 | 原子化 CSS |
| `sass` | ^1.77.0 | SCSS 预处理 |
| `unplugin-auto-import` | ^0.17.0 | API 自动导入 |
| `unplugin-vue-components` | ^0.27.0 | 组件自动导入 |
| `@vueuse/core` | ^10.9.0 | Vue 组合式工具集（虚拟滚动、防抖等） |

### 7.3 模块间调用依赖关系图

```
chat_router ──▶ ChatService ──┬──▶ IntentService ──▶ LLMService
                              │                        ▲
                              ├──▶ RAGService ────────┤
                              │      │                 │
                              │      ▼                 │
                              │   Milvus + Embedding   │
                              │                        │
                              ├──▶ LLMService ────────┴──▶ DUC/DeepSeek API
                              │         ▲
                              │         └──▶ ConfigService ──▶ system_configs
                              │                              └──▶ model_configs
                              ├──▶ MemoryService ──▶ Redis (短期)
                              │                   └──▶ MySQL chat_messages (长期)
                              └──▶ ConfigService (fallback message)

admin_knowledge_router ──▶ KnowledgeService ──▶ MinIO (原始文档)
                                                 ├─▶ DocumentParser + TextSplitter
                                                 ├─▶ Embedding + Milvus (向量)
                                                 └─▶ MySQL (docs + chunks 元数据)

🆕 渠道适配层依赖关系:
webhook_router ──┬──▶ get_adapter(platform) ──▶ BaseAdapter 子类 (Zhibo/Generic/...)
                  │                              ├─▶ verify_signature (HMAC-SHA256)
                  │                              ├─▶ parse_incoming (JSON 解析)
                  │                              └─▶ send_reply (httpx.AsyncClient → 平台 API)
                  ├──▶ SessionMapper ──▶ ChannelSession (MySQL channel_sessions)
                  └──▶ ChatService.handle_message_sync (🆕 非流式入口)
                                  ├─▶ (复用现有 IntentService/RAGService/LLMService/...)
                                  └─▶ MemoryService.save_message

openai_compat_router ──▶ ChatService.handle_message_stream / handle_message_sync

widget_server ──▶ (独立 CORS) ──▶ chat-widget.js (静态文件 / iframe 页面)

admin_channel_router ──▶ ChannelAdminService ──▶ ChannelSession (CRUD + 统计)
```

### 7.4 Python 后端新增依赖（渠道适配层）

| 依赖包 | 版本建议 | 用途 |
|--------|---------|------|
| `httpx` | ≥0.27 | 适配器调用第三方平台 Open API（异步 HTTP 客户端） |

> `httpx` 在原依赖清单中已列为「备用」，渠道适配层的 `send_reply` / `transfer_to_human` 等方法将其作为主力 HTTP 客户端。其余依赖（`fastapi` / `sqlalchemy` / `pydantic` 等）均复用现有版本，无需新增。

---

## 8. 项目运行方式

### 8.1 后端本地开发环境

#### 前置依赖

| 工具 | 版本要求 |
|------|---------|
| Python | 3.13.15 (amd64) |
| MySQL | 8.0+ |
| Redis | 7.x |
| Milvus | 2.4.x |
| MinIO | latest |

#### 步骤

```bash
# 1. 进入后端目录
cd ai-customer-backend

# 2. 创建虚拟环境并激活
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

# 3. 安装依赖
pip install -r requirements.txt

# 4. 复制环境变量模板
copy .env.example .env
# 根据实际情况编辑 .env（MySQL/Redis/Milvus/MinIO/JWT/LLM 配置）

# 5. 初始化数据库
alembic upgrade head

# 6. 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 7. 访问接口文档
# Swagger UI: http://localhost:8000/docs
# ReDoc:      http://localhost:8000/redoc
```

### 8.2 前端本地开发环境

```bash
# 1. 进入前端目录
cd ai-customer-frontend

# 2. 安装依赖
npm install
# 或 pnpm install / yarn

# 3. 启动开发服务器
npm run dev

# 4. 浏览器访问
# http://localhost:5173
```

### 8.3 Docker Compose 一键部署（推荐）

**服务编排 (docker-compose.yml)**：

| 服务名 | 镜像 | 端口 | 说明 |
|--------|------|------|------|
| `backend` | 本地构建 (Dockerfile，基础镜像 `python:3.13.15` amd64) | 8000:8000 | FastAPI 后端 |
| `frontend` | nginx:alpine | 80:80 | Vue 静态前端 (挂载 dist + nginx.conf) |
| `mysql` | mysql:8.0 | 3306:3306 | 卷: mysql_data |
| `redis` | redis:7-alpine | 6379:6379 | 卷: redis_data |
| `minio` | minio/minio:latest | 9000:9000, 9001:9001 | 对象存储，卷: minio_data |
| `etcd` | quay.io/coreos/etcd:v3.5.5 | — | Milvus 元数据依赖，卷: etcd_data |
| `milvus` | milvusdb/milvus:v2.4.5 | 19530:19530 | 向量库，依赖 etcd+minio，卷: milvus_data |

**一键启动命令**:

```bash
cd ai-customer-backend
docker-compose up -d

# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f backend

# 停止
docker-compose down
```

### 8.4 环境变量模板 (.env.example)

```bash
# ===== 数据库 =====
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_ROOT_PASSWORD=your_password_here
MYSQL_DATABASE=ai_customer

# ===== Redis =====
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# ===== Milvus =====
MILVUS_HOST=milvus
MILVUS_PORT=19530
MILVUS_COLLECTION=knowledge_embeddings

# ===== MinIO =====
MINIO_HOST=minio
MINIO_PORT=9000
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_BUCKET=knowledge

# ===== LLM 模型 (默认) =====
LLM_API_BASE=https://api.duc.ai/v1
LLM_API_KEY=sk-your-duc-api-key
LLM_MODEL_NAME=duc-v2

# ===== Embedding =====
EMBEDDING_PROVIDER=dashscope   # dashscope / local / openai
EMBEDDING_MODEL=text-embedding-v3
EMBEDDING_DIM=1024
DASHSCOPE_API_KEY=sk-your-dashscope-key

# ===== 认证 =====
JWT_SECRET_KEY=please-change-this-secret-key-to-random-string
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=24

# ===== 加密 =====
CRYPTO_SECRET_KEY=32-byte-url-safe-base64-key

# ===== 限流 =====
RATE_LIMIT_MAX=30
RATE_LIMIT_WINDOW=60

# ===== 应用 =====
APP_ENV=development
LOG_LEVEL=INFO
APP_PORT=8000
CORS_ALLOWED_ORIGINS=*

# ===== 渠道适配层 (🆕) =====
WEBHOOK_ENABLED=true
WEBHOOK_HMAC_SECRET=your-webhook-hmac-secret-key
OPENAI_COMPAT_ENABLED=true
OPENAI_COMPAT_API_KEY=sk-agent-your-api-key
WIDGET_ENABLED=true
WIDGET_APP_KEYS=app-key-1,app-key-2

# ===== 智齿科技 (🆕) =====
ZHIBO_API_BASE=https://api.sobot.com
ZHIBO_API_TOKEN=your-zhibo-token
ZHIBO_WEBHOOK_SECRET=your-zhibo-webhook-secret
ZHIBO_APP_KEY=your-zhibo-app-key

# ===== Chatwoot (🆕 可选) =====
CHATWOOT_API_BASE=https://your-chatwoot.com
CHATWOOT_ACCESS_TOKEN=your-chatwoot-token
```

### 8.5 Makefile 常用命令

```makefile
.PHONY: dev install migrate migrate-new seed test lint clean docker-up docker-down

dev:               # 启动本地开发服务
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

install:           # 安装依赖
	pip install -r requirements.txt

migrate:           # 执行数据库迁移
	alembic upgrade head

migrate-new:       # 生成迁移脚本
	alembic revision --autogenerate -m "$(msg)"

test:              # 运行单元测试
	pytest tests/ -v

lint:              # 代码检查
	ruff check app/

docker-up:         # Docker 启动
	docker-compose up -d --build

docker-down:       # Docker 停止
	docker-compose down
```

---

## 9. 关键流程与时序

> 本章覆盖**核心 Agent 流程**（C 端用户对话、知识库文档向量化、意图识别双层判断）。**渠道适配层的 Webhook / OpenAI 兼容数据流时序**详见 [11.14 渠道适配层数据流时序](#1114-渠道适配层数据流时序)。

### 9.1 用户提问完整流程（前后端联动）

```
用户浏览器           前端(Vue3)          后端(FastAPI)       IntentSvc       RAGSvc        LLM(DUC)       Milvus
    │                  │                    │                 │              │              │              │
    │──输入问题+Enter──▶│                    │                 │              │              │              │
    │                  │──POST /chat/stream │                 │              │              │              │
    │                  │  (session,msg,JWT) │                 │              │              │              │
    │                  │───────────────────▶│                 │              │              │              │
    │                  │                    │──classify(msg,h)│              │              │              │
    │                  │                    │◀──IntentResult──│              │              │              │
    │                  │                    │   product_qa    │              │              │              │
    │                  │                    │                 │              │              │              │
    │                  │                    │─────retrieve(query)──────────▶│              │              │
    │                  │                    │                 │              │──search───────────────────▶│
    │                  │                    │                 │              │◀──vectors+scores──────────│
    │                  │                    │◀────top-k chunks─────────────│              │              │
    │                  │                    │                 │              │              │              │
    │                  │                    │────stream generate(system+context+history+user_msg)───────▶│
    │                  │◀──SSE: source─────│                 │              │              │              │
    │◀─显示引用来源标签│                    │                 │              │              │              │
    │                  │◀──SSE: token──────│◀──────────────delta content──────────────────────────────│
    │◀─逐字显示打字效果│◀──SSE: token──────│◀──────────────delta content──────────────────────────────│
    │◀─逐字显示打字效果│◀──SSE: token──────│◀──────────────delta content──────────────────────────────│
    │                  │                    │                 │              │              │              │
    │                  │◀──SSE: done────────│   (message_id)  │              │              │              │
    │◀─发送完成+保存── │                    │                 │              │              │              │
    │                  │                    │────save_msg(Redis lpush + ltrim + expire)                 │
    │                  │                    │────save_msg(MySQL ChatMessage 异步插入)                   │
    │                  │                    │                 │              │              │              │
    │                  │                    │  [如果 off_topic 分支]                                      │
    │                  │◀──SSE: answer(话术)│                 │              │              │              │
    │◀─显示引导卡片─── │◀──SSE: fallback────│  {show_transfer:true, show_phone:true, phone:400-xxx}     │
    │  [转人工][电话] │◀──SSE: done────────│                 │              │              │              │
```

### 9.2 文档上传与向量化流程

```
管理员前端          admin_knowledge_router     KnowledgeService        MinIO       TextSplitter    Embedding    Milvus + MySQL
    │                      │                        │                  │             │              │           │
    │──拖拽文件上传───────▶│ POST /upload           │                  │             │              │           │
    │                      │ multipart/form-data    │                  │             │              │           │
    │                      │────────process_doc(doc_id, file)────────▶│             │              │           │
    │                      │                        │──save_to_minio──▶│             │              │           │
    │                      │                        │◀──── file_path ──│             │              │           │
    │                      │                        │                  │             │              │           │
    │                      │                        │──parse_document───┐             │              │           │
    │                      │                        │◀──cleaned_text ───┘             │              │           │
    │                      │                        │                              │              │           │
    │                      │                        │──split_by_headers ───────────▶│              │           │
    │                      │                        │◀──sections list──────────────│              │           │
    │                      │                        │──RecursiveCharacter split ───▶│              │           │
    │                      │                        │◀──list[chunk_text]───────────│              │           │
    │                      │                        │                                             │           │
    │                      │                        │──────batch_embed(chunks)──────────────────▶│           │
    │                      │                        │◀────list[embedding_vector]──────────────────│           │
    │                      │                        │                                                         │
    │                      │                        │────milvus.insert(embeddings + chunk_id + doc_id + content)│
    │                      │                        │────MySQL INSERT knowledge_chunks × N                 │
    │                      │                        │────MySQL UPDATE doc.status='indexed', chunk_count=N     │
    │                      │◀──{doc_id, chunk_count, status}─────────────────────────────────────────────────│
    │◀─显示成功+分块数─── │                                                         │           │
```

### 9.3 意图识别双层判断流程

```
用户输入 message + 对话历史 history
              │
              ▼
┌──────────────────────────────┐
│  第一层：规则引擎匹配 (0ms)    │
│                              │
│  QUICK_OFF_TOPIC_PATTERNS    │
│  正则 match → 命中？          │──YES──▶ IntentResult(off_topic, 0.99) ──┐
│                              │                                          │
│  QUICK_PRODUCT_PATTERNS      │                                          │
│  正则 search → 命中？         │──YES──▶ IntentResult(product_qa, 0.95)  │
│                              │                                          │
│          NO (都未命中)        │                                          │
└──────────────┬───────────────┘                                          │
               ▼                                                          │
┌──────────────────────────────┐                                          │
│  第二层：LLM 精细判断         │                                          │
│  Prompt V2 (Few-shot + 上下文)│                                          │
│  temperature=0.05            │                                          │
│  max_tokens=50               │                                          │
│  强制 JSON 输出               │                                          │
│  → parse JSON → intent + conf│                                          │
└──────────────┬───────────────┘                                          │
               ▼                                                          │
┌──────────────────────────────┐                                          │
│  置信度策略兜底               │                                          │
│                              │                                          │
│  conf ≥ 0.85 → 直接采信       │                                          │
│  0.60 ≤ conf < 0.85          │                                          │
│    → if off_topic: 改为 product_qa       │                                          │
│      (宁可多答，不可漏答)     │                                          │
│  conf < 0.60 → ambiguous     │                                          │
└──────────────┬───────────────┘                                          │
               ▼                                                          │
         IntentResult ────────────────────────────────────────────────────┘
```

---

## 10. 意图识别与 RAG 调优

### 10.1 意图识别 Prompt 版本演进

| 版本 | 特点 | 预期准确率 | 适用场景 |
|------|------|-----------|---------|
| **V1 (基础)** | 清晰分类标准 + JSON 格式约束 | ~88% | 早期 MVP |
| **V2 (Few-shot)** | +10 条代表性边界示例（9 正+1 负） | ~93% | 推荐默认版本 |
| **V3 (上下文)** | +最近对话历史注入 + 简短回复特殊处理说明 | ~96% | 多轮对话场景 |

### 10.2 意图识别评估指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 准确率 (Accuracy) | **≥ 95%** | 整体分类正确率 |
| product_qa 召回率 | **≥ 97%** | 相关问题不能被误判为无关（宁可多答不可漏答） |
| off_topic 精确率 | **≥ 93%** | 无关问题尽量正确拦截 |
| 平均响应时间 | **≤ 800ms** | 第一层规则命中 0ms；LLM 调用通常 300~600ms |

### 10.3 边界 Case 处理策略

| 边界场景 | 示例 | 处理策略 |
|----------|------|----------|
| 模糊问候语 | "你好"、"在吗" | confidence<0.7 → off_topic，但回复友好问候 + 引导提问 |
| 混合问题 | "今天天气不错，顺便问下怎么调分辨率" | 提取产品相关部分 → product_qa |
| 隐含产品问题 | "为什么我生成的图这么模糊" | 语义关联 → product_qa |
| 竞品对比 | "你们和Midjourney比怎么样" | 产品咨询范畴 → product_qa |
| 投诉/情绪 | "你们这破产品太垃圾了" | product_qa，触发安抚 + 转人工推荐 |
| 多轮上下文短回复 | 上一轮产品问答，本轮"好的谢谢" | 结合上下文 → product_qa |
| 低置信度 | 无意义输入 + 模型 conf<0.6 | ambiguous，回复澄清话术 + 示例问题 + 转人工入口 |

### 10.4 RAG 分块参数推荐

| 文档类型 | chunk_size | chunk_overlap | 说明 |
|----------|-----------|---------------|------|
| FAQ 问答对 | 256 | 32 | 每个 Q&A 较短，小块更精准 |
| 操作手册/指南 | 512 | 64 | 步骤需一定上下文（默认起点） |
| 产品介绍/说明 | 512 | 64 | 通用设置 |
| API 文档 | 768 | 96 | 接口描述较长，保留完整参数 |
| 更新日志 | 384 | 48 | 按版本条目切分 |
| 用户反馈/工单 | 256 | 32 | 通常较短 |

### 10.5 RAG 检索增强策略

| 策略 | 说明 | 优先级 |
|------|------|--------|
| **Query 改写** | 口语化问题 → 标准化检索词（1~3 个版本并行检索） | P0 默认启用 |
| **混合检索 + RRF** | Milvus 向量检索 + MySQL 关键词检索 → RRF(1/(k+rank)) 融合 | P0 默认启用 |
| **低分过滤** | rag_score_threshold=0.60，低于阈值的检索结果丢弃 | P0 |
| **重排序 Re-ranking** | BGE-Reranker-v2-m3 Cross-Encoder 对 top-20 → top-5 | P1（需额外 API） |
| **上下文截断** | rag_max_context_length=2048 token，避免超出 LLM 上下文窗口 | P1 |

### 10.6 RAG 评估指标

| 指标 | 计算方式 | 目标 |
|------|----------|------|
| Hit Rate@5 | Top5 结果中包含正确文档的比例 | ≥ 90% |
| MRR (Mean Reciprocal Rank) | 正确结果首次出现位置的倒数均值 | ≥ 0.80 |
| 平均检索延迟 | query → 返回结果耗时 | ≤ 200ms |
| 空检索率 | 未命中任何结果的比例 | ≤ 10% |

---

## 11. 渠道适配层 adapters

### 11.1 适配层定位与嵌入策略

**核心问题**：本项目 Agent 原生设计是**面向自有前端的闭环系统**——SSE 流式接口、JWT Bearer 认证、非 OpenAI 兼容响应格式、内部 session 体系。要嵌入第三方客服平台（智齿、七鱼、Udesk、Chatwoot、Dify 等），必须新增一层「渠道适配层（Channel Adapter）」作为桥梁。

#### 11.1.1 现有架构决定嵌入方式的关键特征

| 特征 | 当前设计 | 对嵌入的影响 |
|------|----------|-------------|
| 对话接口 | `POST /api/v1/chat/stream`（SSE 流式） | SSE 适合前端直连，**不适合服务端对服务端**（多数平台 Webhook 期望同步 JSON 或回调推送） |
| 认证方式 | JWT Bearer Token（面向前端用户） | 平台对接需要额外的 **API Key / HMAC 签名** 认证机制 |
| 响应格式 | `{"code": 0, "message": "success", "data": {...}}` | **非 OpenAI 兼容格式**，多数平台无法直接识别，需适配层 |
| 会话管理 | 内部 session_id + Redis + MySQL | 外部平台有自己的 session 体系，需做 **session 映射** |
| SSE 事件类型 | `answer` / `source` / `fallback` / `done` / `error` | 平台通常只接受纯文本或 Markdown，需**事件降级合并** |
| 意图分支 | product_qa → RAG+LLM / off_topic → 兜底话术 / ambiguous → 澄清 | 兜底话术中的「转人工」按钮在外部平台需转为**平台原生转人工指令** |

#### 11.1.2 四种嵌入方式与架构匹配度

| 嵌入方式 | 匹配度 | 原因 |
|----------|:------:|------|
| **Webhook 回调 + API 推送** | ⭐⭐⭐⭐⭐ | `ChatService.handle_message_stream` 本质是"接收消息→处理→返回结果"的服务，天然适配 Webhook 模式；SSE 流式可降级为异步推送 |
| **OpenAI 兼容接口适配** | ⭐⭐⭐⭐⭐ | `LLMService` 已使用 `AsyncOpenAI` 客户端，只需**反向暴露**一个 OpenAI 兼容的 `/v1/chat/completions` 端点 |
| **JS Widget / iframe 嵌入** | ⭐⭐⭐⭐ | 已有完整 Vue3 前端（ChatView.vue），可直接 iframe 嵌入或抽取为独立 Widget SDK |
| **Bot 协议接入** | ⭐⭐⭐ | 需额外开发 IM 协议适配（WebSocket 长连接），复杂度较高，优先级较低 |

#### 11.1.3 推荐嵌入策略：三层混合架构

```
Layer 1: Webhook + API Push     → 对接智齿/七鱼/Udesk/Zendesk 等专业客服平台
Layer 2: OpenAI 兼容端点        → 对接 Dify/FastGPT/Chatwoot 等开源平台 + 未来扩展
Layer 3: JS Widget / iframe     → 对接自有官网/产品页/电商店铺页面
```

#### 11.1.4 整体架构（在现有架构上新增）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        外部渠道（第三方客服平台）                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ 智齿科技  │ │ 网易七鱼  │ │ Udesk   │ │ Zendesk  │ │ Chatwoot/Dify   │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └───────┬──────────┘ │
│       │ Webhook    │ Webhook    │ Webhook    │ Webhook       │ OpenAI API   │
└───────┼────────────┼────────────┼────────────┼───────────────┼──────────────┘
┌───────▼────────────▼────────────▼────────────▼───────────────▼──────────────┐
│                    🆕 渠道适配层 (Channel Adapter Layer)                      │
│                    app/adapters/                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  Webhook Receiver   POST /api/v1/webhook/{platform}                     ││
│  │  • 验证签名 (HMAC-SHA256) • 解析平台消息 → 统一格式 • 返回 202 Accepted  ││
│  └──────────────────────────────┬──────────────────────────────────────────┘│
│  ┌──────────────────────────────▼──────────────────────────────────────────┐│
│  │  Session Mapper  外部 session_id ↔ 内部 session_id 映射                  ││
│  └──────────────────────────────┬──────────────────────────────────────────┘│
│  ┌──────────────────────────────▼──────────────────────────────────────────┐│
│  │  Response Adapter  SSE → 合并文本/逐段推送 • fallback → 平台转人工指令   ││
│  └──────────────────────────────┬──────────────────────────────────────────┘│
│  ┌──────────────────────────────▼──────────────────────────────────────────┐│
│  │  OpenAI-Compatible Endpoint  POST /api/v1/openai/chat/completions       ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    现有 Agent 核心（不改动）                                  │
│  ChatService.handle_message_stream / handle_message_sync (🆕)              │
│  ├── IntentService.classify()  ├── RAGService.retrieve()                   │
│  ├── LLMService.generate()     ├── MemoryService.save_message()            │
│  └── ConfigService.get()                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 11.2 适配层目录结构

```
app/
 ├── adapters/                          # 🆕 渠道适配层
 │   ├── __init__.py
 │   ├── base.py                        # 适配器基类 BaseAdapter
 │   ├── webhook_router.py              # Webhook 统一路由入口
 │   ├── session_mapper.py              # 外部会话 ↔ 内部会话映射
 │   ├── response_adapter.py            # SSE 事件 → 平台响应格式转换
 │   ├── openai_compat.py               # OpenAI 兼容端点
 │   ├── platforms/                     # 各平台专用适配器
 │   │   ├── __init__.py                # 适配器注册工厂 get_adapter()
 │   │   ├── zhibo_adapter.py          # 智齿科技适配器 (完整实现)
 │   │   ├── qiyu_adapter.py            # 网易七鱼适配器 (预留)
 │   │   ├── udesk_adapter.py           # Udesk 适配器 (预留)
 │   │   ├── zendesk_adapter.py         # Zendesk 适配器 (预留)
 │   │   ├── chatwoot_adapter.py        # Chatwoot 适配器 (预留)
 │   │   └── generic_adapter.py         # 通用适配器 (兜底，回调 URL 推送)
 │   └── widget/                        # 🆕 JS Widget SDK
 │       ├── widget_server.py           # Widget 服务端 (CORS + 匿名认证)
 │       └── static/
 │           └── chat-widget.js         # 嵌入式 JS SDK (<script> 引入)
 ├── models/channel_session.py          # 🆕 ChannelSession ORM
 ├── schemas/webhook.py                  # 🆕 Webhook 请求/响应 DTO
 ├── routers/admin_channel.py            # 🆕 管理后台渠道管理 API
 └── services/channel_admin_service.py # 🆕 ChannelAdminService
```

**新增文件清单**：

| 文件路径 | 说明 | 行数（约） |
|----------|------|:----------:|
| `app/adapters/__init__.py` | 适配层包初始化 | 5 |
| `app/adapters/base.py` | 适配器基类 | 60 |
| `app/adapters/webhook_router.py` | Webhook 统一路由 | 120 |
| `app/adapters/session_mapper.py` | 会话映射管理 | 80 |
| `app/adapters/response_adapter.py` | 响应格式转换 | 50 |
| `app/adapters/openai_compat.py` | OpenAI 兼容端点 | 100 |
| `app/adapters/platforms/__init__.py` | 适配器注册工厂 | 40 |
| `app/adapters/platforms/zhibo_adapter.py` | 智齿适配器 | 220 |
| `app/adapters/platforms/generic_adapter.py` | 通用适配器 | 80 |
| `app/adapters/widget/widget_server.py` | Widget 服务端 | 70 |
| `app/adapters/widget/static/chat-widget.js` | Widget JS SDK | 520 |
| `app/models/channel_session.py` | 渠道会话 ORM | 40 |
| `app/schemas/webhook.py` | Webhook DTO | 30 |
| `app/routers/admin_channel.py` | 管理后台 API | 70 |
| `app/services/channel_admin_service.py` | 管理服务 | 150 |
| `frontend/src/views/admin/ChannelManagement.vue` | 渠道管理页面 | 450 |
| `frontend/src/api/channel.js` | 前端 API 封装 | 40 |

---

### 11.3 适配器基类 BaseAdapter

**文件**: `app/adapters/base.py`

**职责**: 所有平台适配器的抽象基类，定义统一的消息收发契约。

```python
from abc import ABC, abstractmethod
from typing import Optional


class BaseAdapter(ABC):
    """渠道适配器基类，所有平台适配器继承此类"""

    platform_name: str = "generic"
    display_name: str = "通用接入"

    @abstractmethod
    def verify_signature(self, headers: dict, raw_body: bytes) -> bool:
        """验证平台 Webhook 签名（防伪造）"""
        ...

    @abstractmethod
    def parse_incoming(self, raw_body: bytes) -> dict:
        """
        解析平台消息为统一内部格式，返回:
        {
            "skip": bool,                       # 是否跳过非消息事件
            "external_session_id": str,
            "external_user_id": str | None,
            "external_user_name": str | None,
            "message": str,
            "message_id": str,
            "channel_type": str,
            "metadata": dict
        }
        """
        ...

    @abstractmethod
    async def send_reply(
        self,
        external_session_id: str,
        content: str,
        sources: Optional[list] = None,
        fallback: Optional[dict] = None,
    ):
        """将 Agent 回复推送回平台（content 为 Markdown 文本）"""
        ...

    def format_sources(self, sources: list) -> str:
        """将引用来源格式化为文本附加在回答末尾"""
        if not sources:
            return ""
        lines = ["\n\n---\n📎 参考来源："]
        for s in sources[:3]:
            lines.append(f"• {s['title']}（相关度 {s['score']:.0%}）")
        return "\n".join(lines)

    def format_fallback(self, fallback: dict) -> str:
        """将兜底配置转为文本提示"""
        parts = []
        if fallback.get("show_transfer"):
            parts.append("如需进一步帮助，请输入「转人工」")
        if fallback.get("show_phone"):
            parts.append(f"或拨打客服电话：{fallback.get('phone', '')}")
        return "\n".join(parts)
```

**关键设计**: 子类只需实现 `verify_signature` / `parse_incoming` / `send_reply` 三个方法，`format_sources` 与 `format_fallback` 由基类提供通用实现，子类可覆写以适配平台原生 UI。

---

### 11.4 智齿科技适配器 ZhiboAdapter

**文件**: `app/adapters/platforms/zhibo_adapter.py`

**职责**: 对接智齿科技客服平台，支持 Webhook 消息接收、Open API 消息推送、转人工指令、会话状态同步、消息已读回执、多轮上下文透传。

**类常量**:

| 常量 | 值 | 说明 |
|------|----|------|
| `platform_name` | `"zhibo"` | 平台标识 |
| `display_name` | `"智齿科技"` | 显示名 |
| `API_BASE` | `settings.ZHIBO_API_BASE or "https://api.sobot.com"` | API 基础路径 |
| `MSG_TYPE_MAP` | dict | 消息类型映射（text/image/file/audio/video/rich） |

**核心方法**:

| 方法 | 作用 |
|------|------|
| `verify_signature(headers, raw_body) -> bool` | 验证智齿签名：`X-Sobot-Signature: sha256={HMAC-SHA256(secret, timestamp + "." + body)}`，**同时校验时间戳防重放**（允许 ±300 秒偏差） |
| `parse_incoming(raw_body) -> dict` | 解析智齿 `message.receive` 事件，提取 conversation/sender/message/extra，仅处理文本消息（非文本消息降级为提示文本）；返回 `skip` 字段标识是否跳过非消息事件 |
| `async send_reply(external_session_id, content, sources, fallback, msg_type="text")` | 调用 `POST {API_BASE}/api/open/v1/message/send` 推送回复，自动判断 content_type（markdown/text），失败抛 `AdapterSendError` |
| `async transfer_to_human(external_session_id, reason, skill_group_id)` | 调用 `POST {API_BASE}/api/open/v1/conversation/transfer` 触发转人工 |
| `async close_session(external_session_id)` | 关闭/结束会话 |
| `async send_typing_indicator(external_session_id)` | 发送"正在输入"状态（提升用户体验） |
| `async mark_read(external_session_id, message_id)` | 标记消息已读 |
| `_auth_headers() -> dict` | 构建智齿 API 认证头（Bearer Token + X-App-Key） |
| `_build_final_content(content, sources, fallback) -> str` | 组装最终回复文本（回答 + 引用来源 + 兜底提示） |
| `_has_markdown(text) -> bool` | 简单判断文本是否含 Markdown 语法 |
| `_type_label(msg_type) -> str` | 消息类型中文标签（图片/文件/语音/视频/富文本） |

**签名验证规则（防重放）**:

```
Header: X-Sobot-Signature = "sha256=" + HMAC-SHA256(secret, timestamp + "." + body)
Header: X-Sobot-Timestamp = unix_timestamp_ms

校验：
1. 时间戳偏差 ≤ 300 秒
2. HMAC-SHA256 比对（hmac.compare_digest 防时序攻击）
```

**智齿 Webhook 消息格式（解析示例）**:

```json
{
  "event": "message.receive",
  "timestamp": 1700000000000,
  "data": {
    "conversation": {"id": "conv_abc123", "type": "online", "channel": "web", "status": "active"},
    "sender": {"id": "visitor_u001", "name": "张三", "type": "visitor", "phone": "138****1234"},
    "message": {"id": "msg_xyz789", "type": "text", "content": "怎么生成水墨画？"},
    "extra": {"page_url": "https://example.com/product", "custom_fields": {"vip_level": "gold"}}
  }
}
```

---

### 11.5 通用适配器 GenericAdapter

**文件**: `app/adapters/platforms/generic_adapter.py`

**职责**: 兜底适配方案，适用于尚未开发专用适配器的平台、自定义 Webhook 对接、内部系统调用。

**特性**:
- 签名规则：`HMAC-SHA256(WEBHOOK_HMAC_SECRET, body)`
- 回复方式：通过请求中指定的 `callback_url` 回调推送结果
- 消息格式：扁平 JSON `{session_id, user_id, message, callback_url, channel}`

**关键差异**: `send_reply` 签名比专用适配器多一个 `callback_url` 参数——回复目标在请求时动态指定，而非由适配器内部硬编码 API 地址。

---

### 11.6 适配器注册工厂

**文件**: `app/adapters/platforms/__init__.py`

**职责**: 平台名称 → 适配器实例的注册表与单例工厂。

```python
_ADAPTER_REGISTRY: dict[str, type[BaseAdapter]] = {
    "zhibo": ZhiboAdapter,
    "generic": GenericAdapter,
    # 后续新增：qiyu/udesk/chatwoot/zendesk
}
_ADAPTER_INSTANCES: dict[str, BaseAdapter] = {}  # 单例缓存


def get_adapter(platform: str) -> Optional[BaseAdapter]:
    """根据平台名获取适配器实例（单例）；未注册则返回 GenericAdapter"""
    ...

def list_adapters() -> list[dict]:
    """列出所有已注册的适配器（platform + display_name）"""
    ...
```

**扩展新平台的步骤**:
1. 在 `platforms/` 下新建 `<platform>_adapter.py` 继承 `BaseAdapter`
2. 实现三个抽象方法
3. 在 `__init__.py` 的 `_ADAPTER_REGISTRY` 注册 `{platform_name: AdapterClass}`

---

### 11.7 Webhook 统一路由

**文件**: `app/adapters/webhook_router.py`

**路由前缀**: `/api/v1/webhook`

**核心接口**:

| HTTP | 路径 | 功能 |
|------|------|------|
| POST | `/{platform}` | 统一 Webhook 接收入口（智齿/七鱼/Chatwoot/generic 等） |
| GET | `/health` | Webhook 健康检查（返回启用状态 + 已注册平台列表） |

**`receive_webhook` 处理流程（9 步）**:

```
Step 0: 检查 settings.WEBHOOK_ENABLED，未启用返回 503
Step 1: get_adapter(platform) 获取适配器（未注册 → 404）
Step 2: 读取 raw_body
Step 3: adapter.verify_signature(headers, raw_body)（失败 → 403）
Step 4: adapter.parse_incoming(raw_body)（异常 → 400）
Step 5: parsed.skip=True → 返回 {"status": "ignored"}（跳过非消息事件）
Step 6: 防重复处理（基于 message_id，内存缓存 _processed_messages，TTL 5 分钟）
Step 7: session_mapper.get_or_create(...) 映射/创建内部会话
Step 8: background_tasks.add_task(_process_and_reply, ...) 异步处理（不阻塞响应）
Step 9: 立即返回 202 {"status": "accepted", "platform", "internal_session_id"}
```

**`_process_and_reply` 异步处理逻辑**:

```
1. 若 adapter 支持 send_typing_indicator → 发送"正在输入"
2. 调用 ChatService.handle_message_sync(session_id, message, history=[])
3. 若 result.fallback.show_transfer=True:
   a. 先 send_reply 发送回答 + 兜底提示
   b. 若 adapter 支持 transfer_to_human → 调用平台转人工接口
4. 否则正常 send_reply
5. 异常时发送兜底错误消息 + 转人工提示
```

**防重复机制**: `_processed_messages: dict[str, float]`（message_id → 处理时间戳），TTL 300 秒，重复推送返回 `{"status": "duplicate"}`。

---

### 11.8 会话映射器 SessionMapper

**文件**: `app/adapters/session_mapper.py`

**职责**: 管理外部平台会话与内部 `chat_sessions.session_id` 的双向映射。

**核心方法**:

| 方法 | 作用 |
|------|------|
| `async get_or_create(platform, external_session_id, external_user_id, external_user_name, channel_type, metadata) -> str` | **主入口**：先查 active 映射，命中则返回已有 internal_session_id；未命中则生成新 UUID + 插入 ChannelSession + commit |
| `async close_session(platform, external_session_id)` | 关闭会话映射（status='closed'） |
| `async get_by_internal_id(internal_session_id) -> Optional[ChannelSession]` | 根据内部会话 ID 反查外部平台信息 |

**实现要点**: 使用 `get_async_session()` 异步生成器获取 DB Session，`select(ChannelSession).where(platform=..., external_session_id=..., status='active')` 查询，`scalar_one_or_none()` 取唯一结果。

---

### 11.9 渠道会话表 ChannelSession

**文件**: `app/models/channel_session.py`

**表名**: `channel_sessions`

**完整 ORM 定义**:

```python
from sqlalchemy import Column, BigInteger, String, DateTime, JSON, UniqueConstraint
from sqlalchemy.sql import func
from app.core.database import Base


class ChannelSession(Base):
    """外部平台会话 ↔ 内部会话映射"""
    __tablename__ = "channel_sessions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # 外部平台信息
    platform = Column(String(32), nullable=False, index=True)       # zhibo/qiyu/udesk/zendesk/chatwoot
    external_session_id = Column(String(128), nullable=False)        # 平台侧会话ID
    external_user_id = Column(String(128), nullable=True)           # 平台侧用户ID
    external_user_name = Column(String(128), nullable=True)          # 平台侧用户名

    # 内部映射
    internal_session_id = Column(String(36), nullable=False, index=True)  # 对应 chat_sessions.session_id

    # 渠道元数据
    channel_type = Column(String(32), nullable=True)                # web/app/wechat/douyin/xiaohongshu
    metadata = Column(JSON, nullable=True)                          # 平台透传的额外信息

    # 状态
    status = Column(String(16), default="active")                    # active/closed/transferred

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('platform', 'external_session_id', name='uk_platform_session'),
    )
```

**字段说明**: 详见 [4.2.8 ChannelSession](#428-channelsession---channel_sessions-表--渠道会话映射)。

---

### 11.10 OpenAI 兼容端点

**文件**: `app/adapters/openai_compat.py`

**路由前缀**: `/api/v1/openai`

**职责**: 反向暴露一个 OpenAI 兼容的 `/v1/chat/completions` 端点，使 Dify / FastGPT / Chatwoot 等支持 OpenAI API 的系统可直接对接。

**请求模型**:

```python
class OpenAIChatRequest(BaseModel):
    model: str = "ai-customer-agent"
    messages: list[dict]
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    metadata: Optional[dict] = None  # 扩展字段（可选 session_id）
```

**核心接口**:

| HTTP | 路径 | 功能 |
|------|------|------|
| POST | `/chat/completions` | OpenAI 兼容对话接口（支持流式与非流式） |

**处理流程**:

```
1. 验证 API Key（Header: X-API-Key 或 Authorization: Bearer）
2. 提取最后一条 user 消息作为输入
3. 从 req.metadata.session_id 复用或生成新 session_id
4. 调用 ChatService:
   - stream=True → StreamingResponse(_stream_openai_format(...), text/event-stream)
   - stream=False → handle_message_sync() 一次性返回
5. 输出 OpenAI 格式响应
```

**流式输出格式（OpenAI SSE chunk）**:

```json
{
  "id": "chatcmpl-xxxx",
  "object": "chat.completion.chunk",
  "created": 1700000000,
  "model": "ai-customer-agent",
  "choices": [{
    "index": 0,
    "delta": {"content": "您可以通过..."},
    "finish_reason": null
  }]
}
```

**结束标记**: `data: [DONE]\n\n`

**非流式响应**: 标准 OpenAI `chat.completion` 对象，含 `choices[0].message.content` 与 `usage` 字段。

---

### 11.11 JS Widget SDK 与服务端

#### 11.11.1 Widget 服务端

**文件**: `app/adapters/widget/widget_server.py`

**路由前缀**: `/api/v1/widget`

| HTTP | 路径 | 功能 |
|------|------|------|
| GET | `/embed.js` | 返回 Widget JS SDK（带 1 小时浏览器缓存） |
| GET | `/chat` | 返回 iframe 聊天页面（需 `app_key` 参数验证） |
| POST | `/session` | 创建 Widget 匿名会话（返回 `widget_xxxx` 格式 session_id，TTL 86400） |

**CORS 配置**: Widget 路由独立 CORS 中间件，`allow_origins=["*"]`，`expose_headers=["X-Session-Id"]`，允许任意域名嵌入。

**认证方式**: 通过 `X-Widget-App-Key` Header 或 `app_key` query 参数验证，合法 key 列表来自 `settings.WIDGET_APP_KEYS`。

#### 11.11.2 Widget JS SDK

**文件**: `app/adapters/widget/static/chat-widget.js`

**版本**: v1.0.0

**全局 API**: `window.AIChatWidget`

| 方法 | 作用 |
|------|------|
| `init(userConfig)` | 初始化 Widget（合并默认配置 → 校验 appKey → 注入样式 → 渲染 DOM → 绑定事件） |
| `open()` / `close()` | 打开/关闭聊天窗口 |
| `sendMessage(text)` | 程序化发送消息 |
| `getState()` | 获取当前状态副本 |
| `setConfig(key, value)` | 动态修改配置 |
| `destroy()` | 销毁 Widget（移除 DOM 与样式） |

**默认配置（部分）**:

```javascript
const DEFAULTS = {
  appKey: "",                                    // 必填
  apiBase: "",                                  // 自动推断（embed.js 地址）
  position: "bottom-right",                     // bottom-right | bottom-left
  theme: {
    primaryColor: "#409EFF",
    backgroundColor: "#FFFFFF",
    textColor: "#303133",
    borderRadius: "12px",
  },
  bubbleText: "AI 客服",
  welcomeMessage: "您好！我是AI智能客服，有什么可以帮您？",
  maxWidth: "400px",
  maxHeight: "600px",
  autoOpen: false,
  autoOpenDelay: 3000,
  onOpen / onClose / onMessage / onError: null, // 生命周期回调
};
```

**SSE 流式接收实现**: 基于原生 `fetch + ReadableStream`（非 EventSource，因需支持 POST + 自定义 Header），按 `data: ` 前缀切行解析，分发 `answer` / `source` / `fallback` / `done` / `error` 事件，支持 `AbortController` 中断。

**移动端适配**: `@media (max-width: 480px)` 全屏覆盖（width/height: 100%, border-radius: 0）。

#### 11.11.3 第三方网站嵌入示例

```html
<!-- 方式一：JS SDK（悬浮气泡，推荐） -->
<script src="https://your-agent-domain.com/api/v1/widget/embed.js"></script>
<script>
  AIChatWidget.init({
    appKey: 'YOUR_APP_KEY',
    position: 'bottom-right',
    welcomeMessage: '您好！我是AI出图产品的智能客服，请问有什么可以帮您？',
  });
</script>

<!-- 方式二：iframe 嵌入（固定区域） -->
<iframe
  src="https://your-agent-domain.com/api/v1/widget/chat?app_key=YOUR_APP_KEY"
  style="width: 400px; height: 600px; border: none; border-radius: 12px;">
</iframe>
```

---

### 11.12 管理后台渠道管理

#### 11.12.1 后端 API

**文件**: `app/routers/admin_channel.py`

**路由前缀**: `/api/v1/admin/channels`

| HTTP | 路径 | 功能 |
|------|------|------|
| GET | `/overview` | 渠道总览统计（今日消息数/活跃渠道/平均响应时间/转人工率） |
| GET | `/configs` | 获取所有渠道配置列表 |
| POST | `/configs` | 保存/更新渠道配置 |
| PUT | `/{platform}/status` | 启用/停用渠道 |
| POST | `/{platform}/test` | 测试渠道连接（返回 success + 错误信息） |
| GET | `/conversations` | 会话记录列表（支持 platform/status/keyword 筛选 + 分页） |
| GET | `/conversations/{session_id}/messages` | 会话消息详情 |
| GET | `/webhook-logs` | Webhook 请求日志（支持 platform/status 筛选 + 分页） |

#### 11.12.2 前端页面

**文件**: `frontend/src/views/admin/ChannelManagement.vue`

**页面结构（4 Tab）**:

```
渠道管理页面
├── Tab 1: 渠道总览（Dashboard）
│   ├── 4 张统计卡片（今日总消息/活跃渠道/平均响应时间/转人工率）
│   └── 各渠道状态卡片
├── Tab 2: 渠道配置（Configuration）
│   ├── 渠道列表（启用/禁用开关）
│   ├── 新增渠道对话框（platform/api_token/webhook_secret/remark）
│   └── 渠道详情编辑表单（API Token/Webhook Secret/App Key + Webhook URL 复制）
├── Tab 3: 会话记录（Conversations）
│   ├── 筛选器（平台/状态/时间范围/关键词）
│   ├── 会话列表表格 + 分页
│   └── 会话详情抽屉（消息时间线）
└── Tab 4: Webhook 日志（Logs）
    ├── 日志筛选 + 列表 + 分页
    └── 日志详情对话框（JSON 展示 Request/Response）
```

#### 11.12.3 前端 API 封装

**文件**: `frontend/src/api/channel.js`

导出函数：`getChannelOverview` / `getChannelConfigs` / `saveChannelConfig` / `toggleChannelStatus` / `testChannelConnection` / `getConversations` / `getConversationMessages` / `getWebhookLogs`。

---

### 11.13 ChatService 同步方法扩展

**文件**: `app/services/chat_service.py`（在现有 ChatService 中新增方法）

**新增方法**: `handle_message_sync` —— 非流式处理入口，供 Webhook 适配器与 OpenAI 兼容端点调用。

```python
async def handle_message_sync(
    self, session_id: str, message: str, history: list
) -> dict:
    """
    非流式处理（供 Webhook / OpenAI 兼容端点调用）
    内部复用 handle_message_stream，但收集完整结果后一次性返回
    """
    full_answer = ""
    sources = []
    fallback = None
    intent = None
    tokens_used = 0

    async for event in self.handle_message_stream(session_id, message, history):
        if event.type == "answer":
            full_answer += event.content
        elif event.type == "source":
            sources = event.sources
        elif event.type == "fallback":
            fallback = event.data
        elif event.type == "done":
            pass  # 结束

    return {
        "answer": full_answer,
        "intent": intent,
        "sources": sources,
        "fallback": fallback,
        "tokens_used": tokens_used,
    }
```

**设计要点**: 复用现有 `handle_message_stream` 异步生成器，仅做事件收集，**不重复实现意图识别 / RAG / LLM 调用逻辑**，保证流式与非流式行为一致。

---

### 11.14 渠道适配层数据流时序

**Webhook 模式完整时序**:

```
第三方平台(智齿)        Agent 后端                    ChatService 核心
     │                      │                              │
     │──POST /webhook/zhibo─▶│                            │
     │  {conversation_id,    │                              │
     │   message, sender}    │                              │
     │                      │──verify_signature()           │
     │                      │──parse_incoming()             │
     │                      │──防重复检查(message_id)        │
     │                      │──session_mapper.get_or_create()│
     │◀──202 Accepted───────│                              │
     │                      │                              │
     │                      │──background_task:             │
     │                      │  send_typing_indicator()     │
     │                      │──handle_message_sync()───────▶│
     │                      │                              │──IntentService.classify()
     │                      │                              │──RAGService.retrieve()
     │                      │                              │──LLMService.generate()
     │                      │                              │──MemoryService.save()
     │                      │◀──{answer, sources, fallback}─│
     │                      │                              │
     │                      │──adapter.send_reply()         │
     │◀──POST /message/send─│  {content: "您可以...",       │
     │  content_type: md}   │   content_type: "markdown"}  │
     │                      │                              │
     │                      │  [若 fallback.show_transfer] │
     │                      │──adapter.transfer_to_human()  │
     │◀──POST /conversation/transfer─│                     │
     │                      │                              │
     │──渲染回复给用户       │                              │
```

**OpenAI 兼容模式时序**:

```
Dify/Chatwoot           Agent 后端                    ChatService 核心
     │                      │                              │
     │──POST /openai/chat/──▶│                            │
     │  completions          │                              │
     │  {messages, stream}   │                              │
     │  Header: X-API-Key    │                              │
     │                      │──验证 API Key                 │
     │                      │──提取最后一条 user 消息        │
     │                      │──生成/复用 session_id         │
     │                      │                              │
     │                      │  [stream=true]               │
     │                      │──handle_message_stream()─────▶│
     │◀──SSE: chunk──────────│  {delta: {content: "..."}}   │
     │◀──SSE: chunk──────────│                              │
     │◀──SSE: [DONE]─────────│                              │
     │                      │                              │
     │                      │  [stream=false]              │
     │                      │──handle_message_sync()───────▶│
     │◀──JSON: chat.completion─│  {choices:[{message:{...}}]}│
```

---

### 11.15 渠道适配层新增配置

在 `system_configs` 表或 `.env` 中预置以下嵌入相关配置：

| config_key / 环境变量 | 默认值 | 说明 |
|-----------|--------|------|
| `WEBHOOK_ENABLED` | `true` | 是否启用 Webhook 接收 |
| `WEBHOOK_HMAC_SECRET` | *(随机生成)* | 通用 Webhook 签名验证密钥 |
| `OPENAI_COMPAT_ENABLED` | `true` | 是否启用 OpenAI 兼容端点 |
| `OPENAI_COMPAT_API_KEY` | *(随机生成)* | OpenAI 兼容端点的 API Key |
| `WIDGET_ENABLED` | `true` | 是否启用 JS Widget |
| `WIDGET_APP_KEYS` | `[]` | Widget 授权的 app_key 列表（逗号分隔） |
| `ZHIBO_API_BASE` | `https://api.sobot.com` | 智齿 API 地址 |
| `ZHIBO_API_TOKEN` | *(加密存储)* | 智齿 API Token |
| `ZHIBO_WEBHOOK_SECRET` | *(加密存储)* | 智齿 Webhook 签名密钥 |
| `ZHIBO_APP_KEY` | — | 智齿 App Key |
| `CHATWOOT_API_BASE` | — | Chatwoot 地址 |
| `CHATWOOT_ACCESS_TOKEN` | *(加密存储)* | Chatwoot Token |

---

### 11.16 各平台对接配置指南

#### 11.16.1 智齿科技

```
Step 1: 智齿后台 → 机器人管理 → 自定义机器人 → 配置 Webhook URL
        URL: https://your-domain.com/api/v1/webhook/zhibo
Step 2: 智齿后台 → 开放平台 → 获取 API Token，填入 ZHIBO_API_TOKEN
Step 3: 配置转人工规则（Agent 返回 fallback.show_transfer=true 时触发转接）
Step 4: 测试对话
```

#### 11.16.2 Chatwoot（开源）

```
方式一: Webhook
  Chatwoot → Settings → Integrations → Webhook
  URL: https://your-domain.com/api/v1/webhook/chatwoot
  Events: message_created

方式二: OpenAI 兼容（推荐）
  Chatwoot → Settings → Integrations → Custom AI
  API URL: https://your-domain.com/api/v1/openai/chat/completions
  API Key: 你的 OPENAI_COMPAT_API_KEY
```

#### 11.16.3 Dify

```
Step 1: Dify 创建「自定义模型」→ 模型类型: Chat
Step 2: API URL: https://your-domain.com/api/v1/openai/chat/completions
Step 3: API Key: 你的 OPENAI_COMPAT_API_KEY
Step 4: 模型名称: ai-customer-agent
Step 5: 创建应用 → 选择该模型 → 发布
```

---

### 11.17 渠道适配层集成检查表

- [x] `.env` 新增 `ZHIBO_API_TOKEN`、`ZHIBO_WEBHOOK_SECRET`、`ZHIBO_APP_KEY` ✅ 2026-08-17
- [x] `.env` 新增 `WEBHOOK_ENABLED`、`WEBHOOK_HMAC_SECRET` ✅ 2026-08-17
- [x] `.env` 新增 `WIDGET_APP_KEYS`（逗号分隔）✅ 2026-08-17
- [x] `main.py` 注册 `webhook_router`、`widget_server`、`admin_channel` 路由 ✅ 2026-08-17
- [x] `main.py` 为 Widget 路由添加独立 CORS 中间件 ✅ 2026-08-17（全局 CORS + 响应级 Access-Control-Allow-Origin 头已覆盖 Widget 嵌入需求）
- [x] 数据库执行 `channel_sessions` 建表迁移 ✅ 2026-08-17（alembic/versions/0001_initial.py 已含 channel_sessions 表 DDL，执行 `alembic upgrade head` 即建表）
- [x] 前端路由注册 `/admin/channels` → `ChannelManagement.vue` ✅ 2026-08-17（router/index.ts + AdminLayout 菜单 + 4 Tab 页面 + api/channel.ts）
- [ ] 智齿后台配置 Webhook URL 并测试（⚠️ 运行时任务，需智齿平台账号）
- [ ] 测试页面引入 Widget JS 验证对话流程（⚠️ 运行时任务，需启动前后端服务）
- [ ] 管理后台验证渠道配置 CRUD、会话记录查看、日志查看（⚠️ 运行时任务，需启动服务并登录 admin 账号）

---

## 附录：非功能需求汇总

| 类别 | 指标目标 | 实现手段 |
|------|---------|---------|
| **响应时间** | 知识库检索 + LLM 调用整体 ≤ 5s | 流式 SSE 首 token ≤ 1s；Milvus 索引优化；Redis 缓存配置 |
| **并发能力** | 初期支持 50 并发用户 | FastAPI async；SQLAlchemy 连接池(20+40)；Redis 连接池(50) |
| **可用性** | 服务可用率 ≥ 99% | Docker Compose 重启策略 always；健康检查端点；异常兜底回复 |
| **安全性** | 对话数据加密存储，不外泄 | HTTPS；JWT 认证；API Key Fernet 加密存储；MySQL TLS；Redis 密码；CORS 白名单 |
| **扩展性** | 多模型可热切换、知识库可水平扩展 | ModelConfig 表 + LLMService 动态客户端；Milvus 集群版（后续） |
| **可维护性** | 配置无需重启即可生效 | ConfigService DB + Redis 缓存，后台管理页面直接编辑 system_configs |
| **渠道扩展性** 🆕 | 新增第三方客服平台无需改动 Agent 核心 | 渠道适配层 BaseAdapter 抽象 + 注册工厂；新平台仅需实现 3 个方法 + 注册 |

---

> 文档状态: V2.1 完整版（合并渠道适配层 + 锁定 Python 版本）
> 编写日期: 2026-08-17
> 修订记录:
> - V1.0 (2026-08-17): 结构化初稿，覆盖核心 Agent 架构
> - V2.0 (2026-08-17): 合并「渠道嵌入方案」与「适配器完整实现」，新增第 11 章渠道适配层，更新目录结构/数据模型/依赖关系/运行配置，构成项目唯一权威 Code Wiki
> - V2.1 (2026-08-17): 按客户强制要求锁定后端语言为 `python-3.13.15-amd64`，同步更新技术栈、架构图、依赖表、前置依赖、Docker 基础镜像说明
