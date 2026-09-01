# AI Customer Backend - FastAPI + Gunicorn + Uvicorn workers
# Multi-stage: builder (wheels) + runtime (slim)
# ---------------------------------------------------------------------------
# Build:
#   docker build -t your-dockerhub-username/ai-customer-backend:20260901-xxxx \
#       --build-arg APP_VERSION=20260901-xxxx ./ai-customer-backend
# Run (example):
#   docker run --rm -p 8000:8000 --env-file .env.production \
#       your-dockerhub-username/ai-customer-backend:20260901-xxxx

# ---------------------------- Stage 1: builder ----------------------------
FROM python:3.11-slim AS builder

# 编译依赖:pymupdf / cryptography 等需要 build-base / libssl / libffi
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libssl-dev \
        libffi-dev \
        libmariadb-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# 先装依赖(利用 layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --user -r requirements.txt \
    && pip install --no-cache-dir --user gunicorn

# ---------------------------- Stage 2: runtime -----------------------------
FROM python:3.11-slim AS runtime

# 运行时依赖(只装 lib,不装 -dev)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libmariadb3 \
        libffi8 \
        libssl3 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户(记忆约束:Docker 容器必须以非 root 用户运行)
RUN groupadd -r app && useradd -r -g app -d /app -s /usr/sbin/nologin app

WORKDIR /app

# 拷贝 builder 阶段安装的依赖
COPY --from=builder /root/.local /home/app/.local
ENV PATH=/home/app/.local/bin:$PATH \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# 拷贝应用源码
COPY --chown=app:app . /app

# 数据目录(降级模式下的 SQLite / Milvus Lite / 本地文件)
RUN mkdir -p /app/data && chown -R app:app /app/data
VOLUME ["/app/data"]

USER app

EXPOSE 8000

# 健康检查:FastAPI /health 端点
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# 容器入口:
#   1. 先跑 alembic 迁移(应用层加锁,在 alembic/env.py 内实现,不需要额外脚本)
#   2. 然后 Gunicorn + Uvicorn workers 启动(记忆约束:backend 用 Gunicorn + Uvicorn workers)
# Worker 数量按 CPU 2*core+1,Gunicorn 自动检测
ARG APP_VERSION=latest
ENV APP_VERSION=${APP_VERSION}
ENTRYPOINT ["sh", "-c"]
CMD ["alembic upgrade head && exec gunicorn app.main:app \
    --bind 0.0.0.0:8000 \
    --workers $(python -c 'import os;print(2*os.cpu_count()+1 if os.cpu_count() else 3)') \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout 90 \
    --graceful-timeout 30 \
    --keep-alive 5 \
    --access-logfile - \
    --error-logfile -"]