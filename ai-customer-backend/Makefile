.PHONY: dev install migrate migrate-new seed test lint clean docker-up docker-down

# 启动本地开发服务
dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 安装依赖
install:
	pip install -r requirements.txt

# 执行数据库迁移
migrate:
	alembic upgrade head

# 生成迁移脚本
migrate-new:
	@read -p "Migration message: " msg; alembic revision --autogenerate -m "$$msg"

# 运行单元测试
test:
	pytest tests/ -v

# 代码检查
lint:
	ruff check app/

# Docker 启动
docker-up:
	docker-compose up -d --build

# Docker 停止
docker-down:
	docker-compose down
