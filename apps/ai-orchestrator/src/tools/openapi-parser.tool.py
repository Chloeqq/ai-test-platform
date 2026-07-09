# mypy: ignore-errors
"""OpenAPI 规范解析工具：提取端点、参数约束与页面候选。"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any


# 路径/摘要关键词 → 内部页面代码
PAGE_KEYWORD_MAPPING: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("returnapply", ("return-apply", "refund", "return", "after-sale")),
    ("order", ("order", "orders")),
    ("product", ("product", "products", "catalog", "goods")),
    ("billing", ("billing", "bill", "invoice")),
    ("payment", ("payment", "payments", "pay")),
    ("permission", ("permission", "role", "auth")),
)


def _normalize_segment(value: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "", str(value or "").strip().lower())


def _build_endpoint_id(method: str, path: str) -> str:
    normalized_method = _normalize_segment(method) or "get"
    normalized_path = "-".join(
        segment
        for segment in (_normalize_segment(part) for part in str(path or "").strip("/").split("/"))
        if segment
    ) or "root"
    return f"{normalized_method}.{normalized_path}"


def _page_candidates_from_text(text: str) -> list[str]:
    lowered = str(text or "").strip().lower()
    matches: list[str] = []
    for page, keywords in PAGE_KEYWORD_MAPPING:
        if any(keyword in lowered for keyword in keywords):
            matches.append(page)
    seen: set[str] = set()
    ordered: list[str] = []
    for item in matches:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _operation_type(method: str, summary: str, operation_id: str, path: str) -> str:
    lowered = f"{method} {summary} {operation_id} {path}".lower()
    if any(token in lowered for token in ("approve", "audit", "review", "审核", "审批")):
        return "approval"
    if method.lower() == "get":
        return "query"
    if method.lower() in {"post", "put", "patch"} and any(token in lowered for token in ("batch", "bulk", "批量")):
        return "batch_write"
    if method.lower() in {"post", "put", "patch", "delete"}:
        return "mutation"
    return "query"


def _iter_schema_properties(
    schema: dict[str, Any] | None,
    *,
    location: str,
    method: str,
    path: str,
) -> list[dict[str, Any]]:
    raw_schema = schema if isinstance(schema, dict) else {}
    properties = raw_schema.get("properties") if isinstance(raw_schema.get("properties"), dict) else {}
    required_fields = {
        str(item).strip()
        for item in (raw_schema.get("required") or [])
        if str(item).strip()
    }
    items: list[dict[str, Any]] = []
    for name, payload in properties.items():
        if not isinstance(payload, dict):
            continue
        items.append(
            {
                "name": str(name).strip(),
                "title": str(payload.get("title", "")).strip() or str(payload.get("description", "")).strip() or str(name).strip(),
                "in": location,
                "method": method,
                "path": path,
                "type": str(payload.get("type", "")).strip(),
                "format": str(payload.get("format", "")).strip(),
                "minimum": payload.get("minimum"),
                "maximum": payload.get("maximum"),
                "enum": payload.get("enum") if isinstance(payload.get("enum"), list) else [],
                "required": str(name).strip() in required_fields,
            }
        )
    return items


def parse_openapi_spec(openapi_spec: dict[str, Any] | None, *, openapi_url: str = "", max_endpoints: int = 20) -> dict[str, Any]:
    """解析 OpenAPI 文档，输出端点列表、页面候选与参数约束（供多源编排使用）。"""
    spec = openapi_spec if isinstance(openapi_spec, dict) else {}
    paths = spec.get("paths") if isinstance(spec.get("paths"), dict) else {}
    endpoint_rows: list[dict[str, Any]] = []
    resource_counter: Counter[str] = Counter()
    page_candidates: list[str] = []
    parameter_constraints: list[dict[str, Any]] = []

    for path, operations in list(paths.items())[:max_endpoints]:
        if not isinstance(operations, dict):
            continue
        normalized_path = str(path or "").strip()
        if not normalized_path:
            continue
        path_segments = [
            _normalize_segment(segment)
            for segment in normalized_path.strip("/").split("/")
            if segment and not segment.startswith("{")
        ]
        if path_segments:
            resource_counter.update(path_segments[-2:] if len(path_segments) > 1 else path_segments)
        page_candidates.extend(_page_candidates_from_text(" ".join(path_segments)))
        for method, operation in operations.items():
            method_value = str(method or "").strip().lower()
            if method_value not in {"get", "post", "put", "delete", "patch"}:
                continue
            payload = operation if isinstance(operation, dict) else {}
            summary = str(payload.get("summary", "")).strip()
            operation_id = str(payload.get("operationId", "")).strip()
            endpoint_id = _build_endpoint_id(method_value, normalized_path)
            operation_type = _operation_type(method_value, summary, operation_id, normalized_path)
            endpoint_rows.append(
                {
                    "endpoint_id": endpoint_id,
                    "path": normalized_path,
                    "method": method_value.upper(),
                    "summary": summary,
                    "operation_id": operation_id,
                    "operation_type": operation_type,
                    "tags": [str(item).strip() for item in (payload.get("tags") or []) if str(item).strip()][:5],
                }
            )
            page_candidates.extend(_page_candidates_from_text(f"{normalized_path} {summary} {operation_id}"))
            parameters = payload.get("parameters") if isinstance(payload.get("parameters"), list) else []
            for parameter in parameters[:10]:
                if not isinstance(parameter, dict):
                    continue
                schema = parameter.get("schema") if isinstance(parameter.get("schema"), dict) else {}
                parameter_constraints.append(
                    {
                        "name": str(parameter.get("name", "")).strip(),
                        "title": str(parameter.get("description", "")).strip() or str(parameter.get("name", "")).strip(),
                        "in": str(parameter.get("in", "")).strip(),
                        "method": method_value.upper(),
                        "path": normalized_path,
                        "type": str(schema.get("type", "")).strip(),
                        "format": str(schema.get("format", "")).strip(),
                        "minimum": schema.get("minimum"),
                        "maximum": schema.get("maximum"),
                        "enum": schema.get("enum") if isinstance(schema.get("enum"), list) else [],
                        "required": bool(parameter.get("required", False)),
                        "source_id": endpoint_id,
                        "constraint_kind": "parameter",
                    }
                )
            request_body = payload.get("requestBody") if isinstance(payload.get("requestBody"), dict) else {}
            request_content = request_body.get("content") if isinstance(request_body.get("content"), dict) else {}
            for mime_type, content_payload in list(request_content.items())[:3]:
                if not isinstance(content_payload, dict):
                    continue
                parameter_constraints.extend(
                    [
                        {
                            **item,
                            "content_type": str(mime_type).strip(),
                            "source_id": endpoint_id,
                            "constraint_kind": "request_body",
                        }
                        for item in _iter_schema_properties(
                            content_payload.get("schema") if isinstance(content_payload.get("schema"), dict) else {},
                            location="body",
                            method=method_value.upper(),
                            path=normalized_path,
                        )
                    ]
                )
            responses = payload.get("responses") if isinstance(payload.get("responses"), dict) else {}
            for status_code, response_payload in list(responses.items())[:3]:
                if not isinstance(response_payload, dict):
                    continue
                response_content = response_payload.get("content") if isinstance(response_payload.get("content"), dict) else {}
                for mime_type, content_payload in list(response_content.items())[:2]:
                    if not isinstance(content_payload, dict):
                        continue
                    parameter_constraints.extend(
                        [
                            {
                                **item,
                                "content_type": str(mime_type).strip(),
                                "response_status": str(status_code).strip(),
                                "source_id": endpoint_id,
                                "constraint_kind": "response_body",
                            }
                            for item in _iter_schema_properties(
                                content_payload.get("schema") if isinstance(content_payload.get("schema"), dict) else {},
                                location="response",
                                method=method_value.upper(),
                                path=normalized_path,
                            )
                        ]
                    )

    most_common_resources = [item for item, _count in resource_counter.most_common(5)]
    return {
        "source": "openapi",
        "openapi_url": str(openapi_url or "").strip(),
        "api_title": str((spec.get("info") or {}).get("title", "")).strip() if isinstance(spec.get("info"), dict) else "",
        "endpoint_count": len(endpoint_rows),
        "endpoints": endpoint_rows,
        "resource_candidates": most_common_resources,
        "page_candidates": list(dict.fromkeys(page_candidates))[:5],
        "parameter_constraints": [item for item in parameter_constraints if item.get("name")][:20],
        "changed_areas": sorted(
            {
                area
                for area in (
                    "api_contract",
                    "approval_flow" if any(row.get("operation_type") == "approval" for row in endpoint_rows) else "",
                    "query_flow" if any(row.get("operation_type") == "query" for row in endpoint_rows) else "",
                    "mutation_flow" if any(row.get("operation_type") in {"mutation", "batch_write"} for row in endpoint_rows) else "",
                )
                if area
            }
        ),
        "risk_signals": [
            signal
            for signal in [
                {"code": "api_contract_present", "severity": "medium", "detail": f"endpoint_count={len(endpoint_rows)}"} if endpoint_rows else None,
                {"code": "approval_api_present", "severity": "high", "detail": "approval endpoints detected"}
                if any(row.get("operation_type") == "approval" for row in endpoint_rows)
                else None,
                {"code": "request_body_constraints_present", "severity": "medium", "detail": "request/response schema fields detected"}
                if any(item.get("constraint_kind") in {"request_body", "response_body"} for item in parameter_constraints)
                else None,
            ]
            if signal
        ],
        "design_input_fragments": [
            f"{row['method']} {row['path']}" + (f" - {row['summary']}" if row.get("summary") else "")
            for row in endpoint_rows[:8]
        ],
    }
