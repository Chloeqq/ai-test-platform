"""Workbench API 纯工具函数。

不依赖任何 service、DB、或外部 API。仅做数据转换、文件读写、格式处理。
从 facade.py 提取出来，供 facade 和各个 domain service 共用。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from shared_backend.datetime_compat import UTC
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# 时间工具
# ---------------------------------------------------------------------------

def to_utc(value: datetime | None) -> datetime:
    """将时间值统一转换为 UTC，空值使用当前 UTC 时间。"""
    if not value:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def parse_iso_datetime(value: str) -> datetime | None:
    """解析 ISO 时间字符串，并统一返回带 UTC 时区的 datetime。"""
    text = str(value or "").strip()
    if not text:
        return None
    parsed_text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(parsed_text)
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def utc_now() -> datetime:
    """返回当前 UTC 时间，供运行态和报表时间戳复用。"""
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# 字符串 / 类型转换
# ---------------------------------------------------------------------------

def text(value: Any) -> str:
    """将任意值转为 stripped 字符串，空值返回 ''。"""
    return str(value or "").strip()


def text_list(value: Any) -> list[str]:
    """清洗列表中的字符串，去重并过滤空串。"""
    items: list[str] = []
    if not isinstance(value, (list, tuple)):
        return items
    seen: set[str] = set()
    for item in value:
        normalized = str(item or "").strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            items.append(normalized)
    if not items and isinstance(value, str):
        items = [value.strip()]
    return items


def normalize_optional_project_code(value: Any) -> str:
    """标准化可选 project 字段（空值 → 空串，非空 → 小写）。"""
    return str(value or "").strip().lower()


def normalize_generation_case_source(value: Any) -> str:
    """标准化生成用例来源：只接受已知来源，未知默认 'ai'。"""
    text_value = str(value or "").strip().lower()
    if text_value == "generated_requirement":
        return "generated_requirement"
    if text_value in {"openapi", "api"}:
        return "openapi"
    return text_value if text_value else "ai"


def normalize_test_point_review_status(value: Any) -> str:
    """标准化测试点审核状态，兼容语义别名。"""
    text_value = str(value or "").strip().lower()
    mapping: dict[str, str] = {
        "approve": "approved",
        "reject": "rejected",
        "pass": "approved",
        "fail": "rejected",
        "ok": "approved",
        "no": "rejected",
        "yes": "approved",
        "accept": "approved",
        "deny": "rejected",
        "reviewed": "reviewed",
        "acknowledged": "reviewed",
        "confirmed": "reviewed",
    }
    return mapping.get(text_value, text_value)


def validate_test_point_review_status(value: Any) -> str:
    """校验审核状态是否为有效值，无效返回 'pending'。"""
    valid = {"pending", "reviewed", "approved", "rejected"}
    normalized = normalize_test_point_review_status(value)
    return normalized if normalized in valid else "pending"


def python_literal(value: Any) -> str:
    """将值转成 Python 字面量（不处理复杂类型）。"""
    if isinstance(value, str):
        return f'"{value}"'
    return str(value)


def safe_python_identifier(value: Any, *, fallback: str = "intent") -> str:
    """确保输入能用作 Python 函数/变量名，必要时回退到 fallback。"""
    text_value = str(value or fallback).strip().replace(" ", "_").replace("-", "_")
    text_value = "".join(ch for ch in text_value if ch.isalnum() or ch == "_")
    if not text_value or text_value[0].isdigit():
        return fallback
    return text_value.lower()


# ---------------------------------------------------------------------------
# 文件 I/O
# ---------------------------------------------------------------------------

def read_json_file(path: Path) -> dict[str, Any]:
    """读取 JSON 文件，文件不存在或解析失败返回空 dict。"""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return {}


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    """原子写入 JSON 文件（先写临时文件再 rename）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    tmp_path.replace(path)


# ---------------------------------------------------------------------------
# DB 工具
# ---------------------------------------------------------------------------

def safe_rollback_or_invalidate(db: Session) -> None:
    """安全回滚数据库 session，失败时仅在当前事务标记失效。"""
    try:
        db.rollback()
    except Exception:
        try:
            db.invalidate()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Dashboard 降级工具
# ---------------------------------------------------------------------------

def build_empty_trend(now: datetime) -> list[dict[str, Any]]:
    """构造无执行数据时使用的 24 小时趋势占位。"""
    base = (now - timedelta(hours=23)).replace(minute=0, second=0, microsecond=0)
    return [
        {
            "hour": (base + timedelta(hours=i)).strftime("%H:%M"),
            "pass_rate": 0.0,
            "execution_count": 0,
        }
        for i in range(24)
    ]


def default_overview(now: datetime, reason: str) -> dict[str, Any]:
    """构造 dashboard 概览异常降级时的默认响应。"""
    trend = build_empty_trend(now)
    return {
        "as_of": now.isoformat(),
        "risk": {
            "score": 0,
            "level": "数据不可用",
            "summary": "暂无可用执行数据，已启用降级视图。",
            "detail_url": "/quality/trends",
        },
        "summary": {
            "pass_rate_24h": 0.0,
            "execution_count_24h": 0,
            "intercepted_last10": 0,
            "pending_issues": 0,
            "as_of": now.isoformat(),
        },
        "trend_24h": trend,
        "top_flaky": [],
        "gate_last10": [],
        "pending_issues": [],
    }


# ---------------------------------------------------------------------------
# 路径安全
# ---------------------------------------------------------------------------

def is_within(path: Path, root: Path) -> bool:
    """判断 path 是否在 root 子目录内，防止路径遍历攻击。"""
    try:
        resolved_path = path.resolve()
        resolved_root = root.resolve()
        return resolved_path.is_relative_to(resolved_root)
    except Exception:
        try:
            resolved_path = os.path.abspath(str(path))
            resolved_root = os.path.abspath(str(root))
            return os.path.commonpath([resolved_path, resolved_root]) == resolved_root
        except Exception:
            return False
