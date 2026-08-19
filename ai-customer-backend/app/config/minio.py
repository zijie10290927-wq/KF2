"""MinIO Client 连接与 Bucket 管理。

降级策略：MinIO 服务未启动 / SDK 缺失 / 连接失败时，
自动切换到本地文件系统（``<backend>/data/minio_local``），
保证知识库上传、重新索引、RAG 流水线无需真实 MinIO 即可运行。
"""

import logging
import os
from pathlib import Path
from typing import Optional

from app.config.settings import settings

logger = logging.getLogger(__name__)


def _safe_mkdir(p: Path) -> None:
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception as e:  # pragma: no cover
        logger.warning("mkdir %s failed: %s", p, e)


def _local_root() -> Path:
    """本地降级存储根目录：<backend>/data/minio_local。"""
    root = Path(__file__).resolve().parent.parent.parent / "data" / "minio_local"
    _safe_mkdir(root)
    return root


def _object_path(bucket: str, object_name: str) -> Path:
    """将 (bucket, object_name) 映射到本地文件路径。"""
    # 替换 Windows 不安全字符
    safe_obj = object_name.lstrip("/").replace("..", "__")
    target = _local_root() / bucket / safe_obj
    _safe_mkdir(target.parent)
    return target


class MinioClientWrapper:
    """MinIO 客户端单例封装：延迟初始化 + Bucket 自动创建 + 本地文件系统降级。"""

    def __init__(self) -> None:
        self._client: Optional[object] = None
        self._degraded: bool = False  # True 时走本地文件系统

    # ------------------------------------------------------------------ #
    # 客户端初始化（连接失败自动降级）
    # ------------------------------------------------------------------ #
    @property
    def client(self) -> object:
        """获取底层 minio.Minio 客户端；若不可用则抛错（调用方捕获后走降级）。"""
        if self._degraded:
            raise RuntimeError("MinIO degraded: use local filesystem fallback")
        if self._client is None:
            self._init_client()
        if self._client is None:
            self._degraded = True
            raise RuntimeError("MinIO client not initialized, use local filesystem fallback")
        return self._client

    def _tcp_probe_ok(self, host: str, port: int, timeout: float = 1.2) -> bool:
        """用 socket TCP connect 快速判断 MinIO 端口是否在监听。

        minio SDK 底层 urllib3 默认重试 5 次，每次可达数秒；
        先用原生 socket 探测可以在 ~1.2s 内把不可达端口判定为失败。
        """
        import socket
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    def _init_client(self) -> None:
        # Step 1: socket 快速探测（避免 minio SDK 的 urllib3 Retry 总阻塞 20+ 秒）
        try:
            host = settings.MINIO_HOST or "localhost"
            port = int(settings.MINIO_PORT or 9000)
            if not self._tcp_probe_ok(host, port, timeout=1.2):
                logger.warning(
                    "MinIO tcp probe %s:%s timed out — degrade to local filesystem", host, port,
                )
                self._client = None
                self._degraded = True
                return
        except Exception as e:
            logger.warning("MinIO tcp probe failed: %s — degrade", e)
            self._client = None
            self._degraded = True
            return

        # Step 2: 端口可达 → 初始化真正的 minio client 并做一次轻量 list_buckets
        try:
            from minio import Minio
            from minio.api import _DEFAULT_USER_AGENT as _  # noqa: F401 (keep import ordering)
            from urllib3 import PoolManager, Timeout
            from urllib3.util import Retry

            # 配置短超时 + 禁用重试，避免卡死
            timeout = Timeout(connect=2.0, read=3.0)
            retry = Retry(
                total=0, connect=0, read=0, redirect=0,
                backoff_factor=0,
            )
            http_client = PoolManager(
                timeout=timeout,
                retries=retry,  # type: ignore[arg-type]
                maxsize=10,
            )
            cli = Minio(
                f"{host}:{port}",
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
                http_client=http_client,
            )
            try:
                cli.list_buckets()  # type: ignore[attr-defined]
            except Exception as e:
                logger.warning("MinIO list_buckets failed: %s — degrade", e)
                self._client = None
                self._degraded = True
                return
            self._client = cli
            logger.info("MinIO client initialized: %s:%s", host, port)
        except Exception as e:
            logger.warning("MinIO init failed: %s — degrade to local filesystem", e)
            self._client = None
            self._degraded = True

    # ------------------------------------------------------------------ #
    # Bucket
    # ------------------------------------------------------------------ #
    def ensure_bucket(self, bucket: Optional[str] = None) -> None:
        """不存在则创建 bucket（MinIO）或目录（本地降级）。"""
        bucket = bucket or settings.MINIO_BUCKET
        if not self._degraded:
            try:
                cli = self.client
                if not cli.bucket_exists(bucket):
                    cli.make_bucket(bucket)
                    logger.info("MinIO bucket '%s' created", bucket)
                return
            except Exception as e:
                logger.warning("MinIO ensure_bucket failed: %s — degrade", e)
                self._degraded = True
        _safe_mkdir(_local_root() / bucket)
        logger.info("Local filesystem bucket ready (degraded): %s", bucket)

    # ------------------------------------------------------------------ #
    # 上传 / 下载 / 删除
    # ------------------------------------------------------------------ #
    def upload_file(self, bucket: str, object_name: str, file_path: str) -> None:
        """上传本地文件（路径）到存储。"""
        if not self._degraded:
            try:
                from minio.error import S3Error
                self.client.fput_object(bucket, object_name, file_path)
                return
            except Exception as e:
                logger.warning("MinIO upload_file failed: %s — degrade", e)
                self._degraded = True
        import shutil
        shutil.copy(file_path, _object_path(bucket, object_name))

    def put_object_bytes(
        self,
        bucket: str,
        object_name: str,
        data: bytes,
        length: int,
        content_type: str = "application/octet-stream",
    ) -> None:
        """上传字节流（用于文档原文件上传）。"""
        if not self._degraded:
            try:
                from io import BytesIO
                from minio.error import S3Error
                self.client.put_object(
                    bucket, object_name, BytesIO(data), length, content_type=content_type
                )
                return
            except Exception as e:
                logger.warning("MinIO put_object_bytes failed: %s — degrade", e)
                self._degraded = True
        _object_path(bucket, object_name).write_bytes(data)

    def get_presigned_url(self, bucket: str, object_name: str, expires_days: int = 7) -> str:
        """生成下载地址（降级时返回本地 file:// path 字符串，兜底）。"""
        if not self._degraded:
            try:
                from datetime import timedelta
                return self.client.presigned_get_object(
                    bucket, object_name, expires=timedelta(days=expires_days)
                )
            except Exception as e:
                logger.warning("MinIO presigned failed: %s — degrade", e)
                self._degraded = True
        p = _object_path(bucket, object_name)
        return p.as_uri()

    def delete_object(self, bucket: str, object_name: str) -> None:
        """删除对象。"""
        if not self._degraded:
            try:
                self.client.remove_object(bucket, object_name)
                return
            except Exception as e:
                logger.warning("MinIO delete failed: %s — degrade", e)
                self._degraded = True
        p = _object_path(bucket, object_name)
        try:
            if p.exists():
                p.unlink()
        except Exception as e:  # pragma: no cover
            logger.warning("Local delete failed: %s", e)

    def get_object_bytes(self, bucket: str, object_name: str) -> bytes:
        """下载对象为字节流（失败返回空 bytes）。"""
        if not self._degraded:
            try:
                response = self.client.get_object(bucket, object_name)
                try:
                    return response.read()
                finally:
                    try:
                        response.close()
                        response.release_conn()
                    except Exception:
                        pass
            except Exception as e:
                logger.warning("MinIO get_object_bytes failed: %s — degrade", e)
                self._degraded = True
        p = _object_path(bucket, object_name)
        if p.exists():
            try:
                return p.read_bytes()
            except Exception as e:
                logger.error("Local get_object_bytes failed: %s", e)
                return b""
        logger.warning("Local object not found: bucket=%s path=%s", bucket, object_name)
        return b""


# 全局单例
minio_client = MinioClientWrapper()
