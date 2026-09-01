# AI Customer Frontend - Vue3 + Vite 多阶段构建
# ---------------------------------------------------------------------------
# Build:
#   docker build -t your-dockerhub-username/ai-customer-frontend:20260901-xxxx \
#       --build-arg VITE_API_BASE_URL=http://backend:8000 ./ai-customer-frontend
# Run:
#   docker run --rm -p 80:80 your-dockerhub-username/ai-customer-frontend:20260901-xxxx

# ---------------------------- Stage 1: builder ----------------------------
FROM node:20-alpine AS builder

WORKDIR /build

# 先装依赖(利用 layer cache)
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# 拷贝源码并构建
COPY . .

# 构建时通过 VITE_API_BASE_URL 注入后端地址
# 生产环境通过 nginx 反代 /api/* 到 backend service,所以默认走相对路径
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

# ---------------------------- Stage 2: runtime ----------------------------
FROM nginx:1.27-alpine AS runtime

# nginx 配置:静态文件 + 反代 /api 到 backend
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 拷贝前端构建产物
COPY --from=builder /build/dist /usr/share/nginx/html

# 版本元数据
ARG APP_VERSION=latest
ENV APP_VERSION=${APP_VERSION}

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O- http://localhost/ || exit 1

EXPOSE 80