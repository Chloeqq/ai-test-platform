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

_REQUEST_ID_CTX: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
_CONFIGURED_SERVICES: set[str] = set()


def set_request_id(request_id: str) -> None:
    _REQUEST_ID_CTX.set(str(request_id or "").strip())


def get_request_id() -> str:
    return str(_REQUEST_ID_CTX.get("") or "").strip()


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
