# ruff: noqa: E402
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import Request


WEB_UI_ROOT = Path(__file__).resolve().parents[2]
if str(WEB_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_UI_ROOT))

from app.services import ui_shell_service


def _build_request(
    path: str,
    *,
    query_string: str = "",
    headers: dict[str, str] | None = None,
) -> Request:
    raw_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("latin-1"),
        "query_string": query_string.encode("latin-1"),
        "headers": raw_headers,
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
        "root_path": "",
    }
    return Request(scope)


def test_build_base_context_marks_active_navigation_and_header_user() -> None:
    request = _build_request("/cases/review", headers={"x-user-name": "alice"})

    context = ui_shell_service.build_base_context(request, "case_reviews")

    assert context["user_name"] == "alice"
    assert context["user_initial"] == "A"
    case_section = next(item for item in context["nav_sections"] if item["key"] == "case_center")
    review_child = next(item for item in case_section["children"] if item["key"] == "case_reviews")
    assert case_section["active"] is True
    assert case_section["open"] is True
    assert review_child["active"] is True


def test_build_active_filters_renders_multi_values_with_labels() -> None:
    request = _build_request(
        "/quality/failure-clusters",
        query_string="severity=high,critical&cluster_id=CL-001&empty=",
    )

    filters = ui_shell_service.build_active_filters(
        request,
        {
            "severity": "严重级别",
            "cluster_id": "聚类",
        },
    )

    assert filters == [
        {"key": "severity", "label": "严重级别", "value": "high / critical"},
        {"key": "cluster_id", "label": "聚类", "value": "CL-001"},
    ]


def test_safe_next_path_rejects_external_redirects() -> None:
    assert ui_shell_service.safe_next_path("/ai-generation/history") == "/ai-generation/history"
    assert ui_shell_service.safe_next_path("http://example.com") == "/ai-generation"
    assert ui_shell_service.safe_next_path("//example.com") == "/ai-generation"
