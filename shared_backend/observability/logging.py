"""结构化 JSON 日志、request_id 上下文与敏感字段脱敏。"""
from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
from datetime_compat import UTC
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

_REQUEST_ID_CTX: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
_CONFIGURED_SERVICES: set[str] = set()
_SENSITIVE_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "authorization",
    "jwt",
    "bearer",
}


def set_request_id(request_id: str) -> None:
    """在当前异步上下文中设置 request_id，供日志 Filter 注入。"""
    _REQUEST_ID_CTX.set(str(request_id or "").strip())


def get_request_id() -> str:
    """读取当前上下文的 request_id。"""
    return str(_REQUEST_ID_CTX.get("") or "").strip()


def _is_sensitive_key(key: str) -> bool:
    lowered = str(key or "").strip().lower()
    return any(marker in lowered for marker in _SENSITIVE_KEYS)


def redact_sensitive_payload(value: Any, *, max_depth: int = 4) -> Any:
    """递归脱敏 dict 中含 password/token 等键的值。"""
    if max_depth <= 0:
        return "…"
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                redacted[str(key)] = "***"
            else:
                redacted[str(key)] = redact_sensitive_payload(item, max_depth=max_depth - 1)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive_payload(item, max_depth=max_depth - 1) for item in value]
    if isinstance(value, tuple):
        return [redact_sensitive_payload(item, max_depth=max_depth - 1) for item in value]
    if isinstance(value, set):
        return [redact_sensitive_payload(item, max_depth=max_depth - 1) for item in sorted(value, key=str)]
    return value


def summarize_log_value(value: Any, *, max_length: int = 4000) -> str:
    """将任意值转为可写日志的短字符串（JSON + 截断）。"""
    if value is None:
        return ""
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8", errors="replace")
        except Exception:
            value = repr(value)
    if isinstance(value, str):
        text = value.strip()
    else:
        try:
            redacted = redact_sensitive_payload(value)
            text = json.dumps(redacted, ensure_ascii=False, default=str)
        except Exception:
            text = str(value)
    if len(text) > max_length:
        return text[: max_length - 1] + "…"
    return text


def summarize_http_context(
    *,
    method: str,
    path: str,
    query: str = "",
    client: str = "",
    request_id: str = "",
    status_code: int | None = None,
    duration_ms: float | None = None,
    payload: Any = None,
    error: Any = None,
) -> str:
    """拼装 HTTP 请求/响应的结构化日志摘要行。"""
    parts: list[str] = [
        f"method={str(method or '-').strip() or '-'}",
        f"path={str(path or '-').strip() or '-'}",
    ]
    query_text = str(query or "").strip()
    if query_text:
        parts.append(f"query={query_text}")
    client_text = str(client or "").strip()
    if client_text:
        parts.append(f"client={client_text}")
    request_id_text = str(request_id or "").strip()
    if request_id_text:
        parts.append(f"request_id={request_id_text}")
    if status_code is not None:
        parts.append(f"status={status_code}")
    if duration_ms is not None and duration_ms >= 0:
        parts.append(f"duration_ms={duration_ms:.2f}")
    if payload is not None:
        parts.append(f"payload={summarize_log_value(payload)}")
    if error is not None:
        parts.append(f"error={summarize_log_value(error)}")
    return " ".join(parts)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


class _RequestContextFilter(logging.Filter):
    def __init__(self, service_name: str) -> None:
        super().__init__()
        self.service_name = str(service_name or "").strip() or "unknown-service"
        self.app_env = str(os.getenv("APP_ENV", "dev")).strip() or "dev"

    def filter(self, record: logging.LogRecord) -> bool:
        request_id = get_request_id()
        record.request_id = request_id or "-"
        record.service = self.service_name
        record.app_env = self.app_env
        return True


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "service": getattr(record, "service", "unknown-service"),
            "app_env": getattr(record, "app_env", "dev"),
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(*, service_name: str) -> None:
    """按服务名配置根 logger（JSON/文本、轮转文件、request_id 字段）。"""
    normalized_service = str(service_name or "").strip() or "unknown-service"
    if normalized_service in _CONFIGURED_SERVICES:
        return

    log_level = str(os.getenv("LOG_LEVEL", "INFO")).strip().upper() or "INFO"
    log_format = str(os.getenv("LOG_FORMAT", "json")).strip().lower()
    use_json = log_format == "json"

    request_filter = _RequestContextFilter(normalized_service)
    formatter: logging.Formatter
    if use_json:
        formatter = _JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s [%(service)s] [%(request_id)s] %(name)s: %(message)s"
        )

    handlers: list[logging.Handler] = []
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.addFilter(request_filter)
    stream_handler.setFormatter(formatter)
    handlers.append(stream_handler)

    log_file_path = str(os.getenv("LOG_FILE_PATH", "")).strip()
    if log_file_path:
        log_path = Path(log_file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        max_bytes = int(str(os.getenv("LOG_FILE_MAX_BYTES", "10485760")).strip() or "10485760")
        backup_count = int(str(os.getenv("LOG_FILE_BACKUP_COUNT", "5")).strip() or "5")
        file_handler = RotatingFileHandler(
            filename=str(log_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.addFilter(request_filter)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
    for handler in handlers:
        root_logger.addHandler(handler)

    for logger_name in ("uvicorn.error", "uvicorn.access", "werkzeug"):
        logger = logging.getLogger(logger_name)
        logger.setLevel(log_level)
        logger.propagate = True
        for handler in list(logger.handlers):
            logger.removeHandler(handler)

    if _env_bool("LOG_SQLALCHEMY", False):
        logging.getLogger("sqlalchemy.engine").setLevel("INFO")

    _CONFIGURED_SERVICES.add(normalized_service)
