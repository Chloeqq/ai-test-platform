from __future__ import annotations

import io
import logging
from functools import lru_cache

from app.core.config import get_settings

LOGGER = logging.getLogger(__name__)

try:
    from minio import Minio
    from minio.error import S3Error
    from urllib3.exceptions import HTTPError as _Urllib3HTTPError
except Exception:  # pragma: no cover - keep local env resilient before deps refresh
    Minio = None  # type: ignore[assignment,misc]

    class S3Error(Exception):  # type: ignore[no-redef]
        pass

    class _Urllib3HTTPError(Exception):  # type: ignore[no-redef]
        pass


# 存储不可用时向上传播的具体异常类型（Service 层据此降级为 503）
StorageError = (S3Error, _Urllib3HTTPError, OSError)


@lru_cache(maxsize=1)
def get_minio_client() -> "Minio | None":
    """返回 MinIO 单例；未启用/依赖缺失/初始化失败均返回 None。

    仿 redis_client.get_redis_client：仅创建 client，不做任何网络 I/O
    （建桶惰性执行，见 ensure_bucket），保证「未启用」与「连不上」可区分。
    """
    settings = get_settings()
    if not settings.minio_enabled or Minio is None:
        return None
    if not settings.minio_endpoint:
        LOGGER.warning("minio enabled but MINIO_ENDPOINT is empty; disabling storage")
        return None
    try:
        return Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key or None,
            secret_key=settings.minio_secret_key or None,
            secure=settings.minio_secure,
            region=settings.minio_region or None,
        )
    except (ValueError, S3Error, _Urllib3HTTPError) as exc:
        LOGGER.warning("minio init failed: %s", exc)
        return None


def ensure_bucket(client: "Minio", bucket: str) -> None:
    """惰性幂等建桶。已存在则跳过；并发/已属己抛的 BucketAlreadyOwnedByYou 视为成功。"""
    try:
        if client.bucket_exists(bucket):
            return
        client.make_bucket(bucket, location=get_settings().minio_region or None)
    except S3Error as exc:
        code = getattr(exc, "code", "") or ""
        if code in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
            return
        raise


def upload_bytes(client: "Minio", object_key: str, data: bytes, content_type: str) -> None:
    """上传字节到 requirement bucket；调用前确保桶存在。失败抛 StorageError。"""
    bucket = get_settings().minio_requirement_bucket
    ensure_bucket(client, bucket)
    client.put_object(
        bucket,
        object_key,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type or "application/octet-stream",
    )


def download_bytes(client: "Minio", object_key: str) -> bytes:
    """从 requirement bucket 下载对象字节。失败抛 StorageError。"""
    bucket = get_settings().minio_requirement_bucket
    response = None
    try:
        response = client.get_object(bucket, object_key)
        return response.read()
    finally:
        if response is not None:
            response.close()
            response.release_conn()


def ping_minio(client: "Minio | None" = None) -> bool:
    """健康检查：能列出 bucket 即视为连通。未配置/异常返回 False。"""
    if client is None:
        client = get_minio_client()
    if client is None:
        return False
    try:
        client.list_buckets()
        return True
    except (S3Error, _Urllib3HTTPError, OSError) as exc:
        LOGGER.warning("minio ping failed: %s", exc)
        return False
