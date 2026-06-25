"""generate_pipeline 编排与页面解析 —— 提取自 generate_pipeline.py。"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Callable, Protocol
import yaml
from sqlalchemy.exc import OperationalError

# SessionLocal imported from .generate_pipeline
from app.models.page_object import PageElement, PageObject
from app.repositories.page_object_repository import PageObjectRepository

from ..debug import debug_enabled, log_debug_event
from shared_backend.observability import summarize_http_context
from shared_backend.execution_compiler import ExecutionCompilerError, compile_execution_steps
from shared_backend.element_binding import build_element_alias_map
from shared_backend.intent_mapping import resolve_explicit_step
from shared_backend.schemas.contracts import normalize_test_point_plan_v1
from shared_backend.schemas.validator import ContractValidator
from shared_backend.type_utils import str_value as _normalized_text

from .generate_pipeline_precondition import compile_preconditions


# 从上游模块导入（无循环：File 1→File 2→File 3 单向依赖）
from .generate_pipeline import (
    SessionLocal,  # noqa: E402
    _normalized_text, _LOGGER, _YAML_PAGE_OBJECT_ROOT,
    _normalized_key, _normalize_json_list, _is_qualified_formal_element,
    _element_display_name, _infer_element_aliases, _list_text,
    _extract_selected_intent_ids, _execution_intent_ids,
    _find_candidate_snapshot_by_intent, _candidate_steps,
    _normalize_candidate_snapshot, _point_type_from_intent_type,
    _candidate_identity, _direct_candidate_requirement_lines,
    _scope_points_to_selected_intents, _filter_requirement_spec_by_selected_intents,
    _is_precondition_point, _looks_like_password_toggle_element,
    _intent_product_metadata,
)
from .generate_pipeline_format import (  # noqa: E402
    _product_description, _product_page_load_expected, _product_element_name,
    _product_locator, _product_element_meta, _trusted_page_url,
    _product_step_expected, _format_product_execution_steps,
    _append_login_success_assertion, _step_element_code,
    _normalize_dsl_data_sources, _enrich_dsl_v1_1_data_bindings,
    _normalize_step_locators,
    _normalize_top_level_assertion, _assertion_signature,
    _normalize_dsl_v1_1_assertions, _is_ai_automated_case,
    _validate_dsl_v1_1_minimum_contract, _enrich_product_case_yaml_v1_1,
    _normalized_data_source_type, _normalize_data_source_entry,
)

def _svc():
    """惰性查找主模块，支持测试 monkeypatch。"""
    from . import generate_pipeline as _svc_mod
    return _svc_mod

def _format_product_case_yaml(
    *,
    case_yaml: dict[str, Any],
    payload: Any,
    page: str,
    page_url: str,
    page_object: dict[str, Any],
    test_points: list[dict[str, Any]],
    candidate_snapshots: list[dict[str, Any]],
    requirement_spec: dict[str, Any] | None,
    selected_intent_ids: list[str],
    effective_requirement: str,
) -> dict[str, Any]:
    execution_payload = case_yaml.get("execution") if isinstance(case_yaml.get("execution"), dict) else {}
    compiled_steps = execution_payload.get("steps") if isinstance(execution_payload.get("steps"), list) else []
    intent_ids = _execution_intent_ids(
        selected_intent_ids=selected_intent_ids,
        execution_payload=execution_payload,
        compiled_steps=compiled_steps,
        test_points=test_points,
    )
    primary_intent_id = intent_ids[0] if intent_ids else ""
    intent_meta = _intent_product_metadata(
        intent_id=primary_intent_id,
        case_yaml=case_yaml,
        candidate_snapshots=candidate_snapshots,
        requirement_spec=requirement_spec,
        test_points=test_points,
        effective_requirement=effective_requirement,
    ) if primary_intent_id else {
        "intent_id": "",
        "title": _normalized_text(case_yaml.get("title")),
        "type": "functional",
        "precondition": "",
        "expected": _normalized_text(case_yaml.get("expected_result")),
        "source_asset_id": "",
        "source_asset_title": _normalized_text(effective_requirement),
    }
    expected_by_intent = {
        intent_id: _intent_product_metadata(
            intent_id=intent_id,
            case_yaml=case_yaml,
            candidate_snapshots=candidate_snapshots,
            requirement_spec=requirement_spec,
            test_points=test_points,
            effective_requirement=effective_requirement,
        ).get("expected", "")
        for intent_id in intent_ids
    }
    expected = _normalized_text(intent_meta.get("expected")) or _normalized_text(case_yaml.get("expected_result"))
    title = _normalized_text(case_yaml.get("title")) or _normalized_text(intent_meta.get("title")) or _normalized_text(getattr(payload, "title", "")) or "AI生成用例"
    priority = _normalized_text(case_yaml.get("priority")) or _normalized_text(getattr(payload, "priority", "")) or "P1"
    tags = [item for item in case_yaml.get("tags", []) if _normalized_text(item)] if isinstance(case_yaml.get("tags"), list) else []
    product_yaml: dict[str, Any] = {
        "version": "v1",
        "id": _normalized_text(case_yaml.get("id")),
        "project": _normalized_text(case_yaml.get("project")) or _normalized_text(getattr(payload, "project", "")) or "mall",
        "module": page or _normalized_text(case_yaml.get("module")) or "product",
        "title": title,
        "priority": priority,
        "tags": tags or ["ai-generated"],
        "owner": _normalized_text(case_yaml.get("owner")) or "qa-team",
        "status": _normalized_text(case_yaml.get("status")) or "automated",
        "description": _product_description(title, expected),
        "requirement": {
            "intent_id": _normalized_text(intent_meta.get("intent_id")) or primary_intent_id,
            "title": _normalized_text(intent_meta.get("title")) or title,
            "type": _normalized_text(intent_meta.get("type")) or "functional",
            "precondition": _normalized_text(intent_meta.get("precondition")),
            "source_asset_id": _normalized_text(intent_meta.get("source_asset_id")),
        },
        "data": case_yaml.get("data") if isinstance(case_yaml.get("data"), dict) else {},
        "execution": {
            "runner": _normalized_text(execution_payload.get("runner")) or "playwright",
            "page": page or _normalized_text(execution_payload.get("page")) or "product",
            "page_url": page_url,
            "variables": execution_payload.get("variables") if isinstance(execution_payload.get("variables"), dict) else {},
            "steps": _format_product_execution_steps(
                compiled_steps=compiled_steps,
                page=page,
                page_url=page_url,
                page_object=page_object,
                expected_by_intent=expected_by_intent,
            ),
            "selected_intent_ids": intent_ids,
        },
        "expected_result": expected,
    }
    product_yaml = _enrich_product_case_yaml_v1_1(product_yaml, page=page)
    if not product_yaml["requirement"]["precondition"]:
        product_yaml["requirement"].pop("precondition", None)
    # 确保 data 中每个有值的字段都有对应的 input 步骤和变量绑定
    _ensure_data_steps_and_variables(product_yaml, page, page_object)
    # 根据 precondition 关键词自动路由到数据池
    _apply_pool_routing(product_yaml)

    # V2.0: 编译结构化 preconditions 块为 setup 步骤
    preconditions = case_yaml.get("preconditions") if isinstance(case_yaml, dict) else None
    if isinstance(preconditions, list) and preconditions:
        product_yaml.setdefault("preconditions", preconditions)
        setup_steps = compile_preconditions(
            product_yaml=product_yaml,
            page_object=page_object,
        )
        if setup_steps:
            steps = product_yaml["execution"]["steps"]
            product_yaml["execution"]["steps"] = setup_steps + steps

    # V2.5a: Locator 归一化 — 用 page object 的正式定义覆盖 AI 生成的 locator
    _normalize_step_locators(
        steps=product_yaml["execution"]["steps"],
        page_object=page_object,
    )

    return product_yaml


def _apply_pool_routing(product_yaml: dict[str, Any]) -> None:
    """根据 precondition 关键词，自动将 inline data 改为 pool 引用。

    例: precondition 含"锁定" → username/password 路由到 login_accounts:locked_user
    """
    precondition = _normalized_text(
        product_yaml.get("requirement", {}).get("precondition", "")
    ).lower()
    if not precondition:
        return
    data = product_yaml.get("data") if isinstance(product_yaml.get("data"), dict) else {}

    routing: dict[str, tuple[str, str]] = {}
    if any(w in precondition for w in ("锁定", "lock", "locked")):
        routing = {"username": ("login_accounts", "locked_user"),
                   "password": ("login_accounts", "locked_user")}
    elif any(w in precondition for w in ("禁用", "disabled", "forbidden")):
        routing = {"username": ("login_accounts", "disabled_user"),
                   "password": ("login_accounts", "disabled_user")}

    for key, (pool_name, item_key) in routing.items():
        if key in data:
            data[key] = {"source_type": "pool", "pool_name": pool_name, "key": item_key}


def _ensure_data_steps_and_variables(
    product_yaml: dict[str, Any], page: str, page_object: dict[str, Any],
) -> None:
    """保证 data 里每个有值的字段都在 steps 中有对应 input 步骤。"""
    data = product_yaml.get("data") if isinstance(product_yaml.get("data"), dict) else {}
    if not data:
        return
    exec_block = product_yaml.get("execution")
    if not isinstance(exec_block, dict):
        return
    steps = exec_block.get("steps") if isinstance(exec_block.get("steps"), list) else []
    variables = exec_block.get("variables") if isinstance(exec_block.get("variables"), dict) else {}
    elements = page_object.get("elements") if isinstance(page_object, dict) else {}

    step_targets = {
        _normalized_text(s.get("target", "")).removeprefix("element:") if isinstance(s, dict) else ""
        for s in steps
    }

    for data_key, raw_entry in data.items():
        if not isinstance(raw_entry, dict):
            continue
        raw_value = raw_entry.get("value")
        if raw_value is None or str(raw_value).strip() == "":
            continue

        element_code = _infer_element_code_from_data_key(data_key)
        var_name = f"login_{data_key}"

        if element_code in step_targets:
            continue  # 步骤已存在
        if element_code not in elements:
            continue  # 无对应页面元素
        if var_name in variables:
            continue  # 变量已存在

        em = elements[element_code]
        loc_type = _normalized_text(em.get("type") or em.get("locator_type"))
        loc_val = _normalized_text(em.get("selector") or em.get("locator_value"))
        if not loc_type or not loc_val:
            continue

        # 在 goto 之后插入 input 步骤
        goto_idx = next((i for i, s in enumerate(steps) if isinstance(s, dict) and _normalized_text(s.get("action", "")).lower() == "goto"), -1)
        insert_at = goto_idx + 1 if goto_idx >= 0 else 0
        new_step = {
            "action": "input",
            "target": f"element:{element_code}",
            "locator_type": loc_type,
            "locator_value": loc_val,
            "target_name": _normalized_text(em.get("name") or element_code),
            "value": f"{{{{{var_name}}}}}",
            "expected_result": "",
        }
        steps.insert(insert_at, new_step)
        variables[var_name] = f"{{{{{data_key}}}}}"

    exec_block["variables"] = variables


def _infer_element_code_from_data_key(data_key: str) -> str:
    return {"username": "username_input", "password": "password_input"}.get(data_key, data_key)


def _attach_point_expected_results(compiled_steps: list[dict[str, Any]], test_points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expected_by_intent: dict[str, str] = {}
    for point in test_points:
        if not isinstance(point, dict):
            continue
        intent_id = _normalized_text(point.get("intent_id") or point.get("key"))
        expected = _normalized_text(point.get("expected_result") or point.get("expected"))
        if intent_id and expected:
            expected_by_intent[intent_id] = expected
    if not expected_by_intent:
        return compiled_steps

    last_step_index_by_intent: dict[str, int] = {}
    for index, step in enumerate(compiled_steps):
        if not isinstance(step, dict):
            continue
        intent_id = _normalized_text(step.get("intent_id"))
        action = _normalized_text(step.get("action")).lower()
        if not intent_id or intent_id == "__page_entry__" or action in {"goto", "login"}:
            continue
        if intent_id in expected_by_intent:
            last_step_index_by_intent[intent_id] = index

    for intent_id, index in last_step_index_by_intent.items():
        step = compiled_steps[index]
        if not _normalized_text(step.get("expected_result") or step.get("expected")):
            step["expected_result"] = expected_by_intent[intent_id]
    return compiled_steps


def _build_direct_candidate_orchestrator_result(
    *,
    payload: Any,
    normalized_page: str,
    effective_requirement: str,
    candidate_snapshots: list[dict[str, Any]],
    selected_candidate: dict[str, Any] | None,
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    if isinstance(selected_candidate, dict) and selected_candidate:
        candidates.append(_normalize_candidate_snapshot(selected_candidate))
    candidates.extend(candidate_snapshots)
    candidate = next((item for item in candidates if _list_text(item.get("steps_hint"))), None)
    if not candidate:
        return None

    page = _normalized_text(normalized_page or getattr(payload, "page", "")) or "product"
    page_object = _svc().resolve_page_object(str(getattr(payload, "project", "") or ""), page)
    alias_map = build_element_alias_map(page_object)
    intent_id, title = _candidate_identity(candidate)
    steps: list[dict[str, Any]] = []
    involved_codes: list[str] = []
    for index, hint in enumerate(_list_text(candidate.get("steps_hint"))):
        action, target, value = resolve_explicit_step(
            steps_hint=[hint],
            page=page,
            page_element_alias_map=alias_map,
        )
        step: dict[str, Any] = {
            "action": action,
            "target": target or "",
            "raw_text": hint,
            "description": hint,
        }
        if value is not None:
            step["value"] = value
        if action == "assert_metric" and value is not None:
            step["metric_rule"] = value
            step["rule"] = value
        steps.append(step)
        if target and target not in involved_codes:
            involved_codes.append(target)

    if not steps:
        return None

    candidate_codes = _list_text(candidate.get("involved_element_codes")) or involved_codes
    if not candidate_codes:
        candidate_codes = involved_codes
    expected = _normalized_text(candidate.get("expected") or candidate.get("expected_result"))
    priority = _normalized_text(candidate.get("priority")) or _normalized_text(getattr(payload, "priority", "")) or "P1"
    intent_type = _normalized_text(candidate.get("intent_type")) or "functional"
    point = {
        "key": intent_id,
        "intent_id": intent_id,
        "point_type": _point_type_from_intent_type(intent_type),
        "action": _normalized_text(steps[0].get("action")) or "candidate",
        "description": title,
        "priority": priority,
        "expected_result": expected,
        "dependencies": [],
        "source_ids": [intent_id],
        "steps": steps,
        "involved_elements": candidate_codes,
        "metadata": {
            "candidate_snapshot": candidate,
            "traceability": {
                "intent_ids": [intent_id],
                "source_ids": [intent_id],
                "origin": "selected_candidate_direct_compile",
            },
        },
    }
    precondition = _normalized_text(candidate.get("precondition"))
    if precondition:
        point["precondition"] = precondition

    requirement_spec = {
        "project": _normalized_text(getattr(payload, "project", "")) or "mall",
        "page": page,
        "raw_requirement": effective_requirement,
        "design_input": effective_requirement,
        "source_type": "test_point_asset",
        "priority": priority,
        "parse_confidence": 1.0,
        "test_intents": [
            {
                "intent_id": intent_id,
                "title": title,
                "summary": _normalized_text(candidate.get("summary")) or title,
                "intent_type": intent_type,
                "priority": priority,
                "expected_result": expected,
                "steps_hint": _list_text(candidate.get("steps_hint")),
                "involved_elements": candidate_codes,
                "quality_gate": {"decision": "allow", "blockers": []},
            }
        ],
        "quality_gate": {"decision": "allow", "blockers": []},
    }
    case_yaml = {
        "version": "v4",
        "id": _normalized_text(getattr(payload, "case_id", "")),
        "project": _normalized_text(getattr(payload, "project", "")) or "mall",
        "module": page,
        "title": _normalized_text(getattr(payload, "title", "")) or title,
        "priority": priority,
        "tags": [item for item in getattr(payload, "tags", []) if _normalized_text(item)] or ["ai-generated"],
        "owner": "qa-team",
        "status": "automated",
        "description": _normalized_text(candidate.get("summary")) or title,
        "requirement": _direct_candidate_requirement_lines(candidate, intent_id=intent_id, title=title),
        "data": {},
        "execution": {
            "runner": "playwright",
            "page": page,
            "variables": {},
            "steps": [],
            "selected_intent_ids": [intent_id],
        },
        "expected_result": expected,
    }
    return {
        "requirement_spec": requirement_spec,
        "case": case_yaml,
        "test_points": {
            "version": "TestPointPlanV1",
            "project": _normalized_text(getattr(payload, "project", "")) or "mall",
            "case_id": _normalized_text(getattr(payload, "case_id", "")),
            "page": page,
            "source_type": "selected_candidate_direct_compile",
            "requirement": [effective_requirement or title],
            "points": [point],
            "metadata": {
                "build_source": "selected_candidate.steps_hint",
                "selected_intent_ids": [intent_id],
            },
        },
        "direct_compile": True,
    }


def _extract_candidate_snapshots(*, payload: Any, selected_candidate: dict[str, Any] | None) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _append(raw: Any) -> None:
        if not isinstance(raw, dict):
            return
        normalized = _normalize_candidate_snapshot(raw)
        intent_id = _normalized_text(normalized.get("intent_id"))
        title = _normalized_text(normalized.get("title"))
        identity = intent_id or f"title:{title}"
        if not identity:
            return
        if identity in seen:
            return
        seen.add(identity)
        snapshots.append(normalized)

    selected_candidates_raw = getattr(payload, "selected_candidates", None)
    if isinstance(selected_candidates_raw, list):
        for item in selected_candidates_raw:
            _append(item)
    if isinstance(selected_candidate, dict):
        _append(selected_candidate)
    return snapshots


def _enrich_test_points_with_candidate_snapshots(
    *,
    points: list[dict[str, Any]],
    candidate_snapshots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not points or not candidate_snapshots:
        return points
    by_intent_id: dict[str, dict[str, Any]] = {}
    for candidate in candidate_snapshots:
        intent_id = _normalized_text(candidate.get("intent_id"))
        if intent_id:
            by_intent_id[intent_id] = candidate
    if not by_intent_id:
        return points

    enriched: list[dict[str, Any]] = []
    for raw_point in points:
        if not isinstance(raw_point, dict):
            continue
        point = dict(raw_point)
        intent_id = _normalized_text(point.get("intent_id"))
        candidate = by_intent_id.get(intent_id)
        if not candidate:
            enriched.append(point)
            continue
        point["point_type"] = _normalized_text(candidate.get("intent_type")) or _normalized_text(point.get("point_type")) or "functional"
        point["description"] = _normalized_text(candidate.get("summary")) or _normalized_text(candidate.get("title")) or _normalized_text(point.get("description"))
        point["precondition"] = _normalized_text(candidate.get("precondition")) or _normalized_text(point.get("precondition"))
        point["expected_result"] = _normalized_text(candidate.get("expected")) or _normalized_text(point.get("expected_result"))
        point["priority"] = _normalized_text(candidate.get("priority")) or _normalized_text(point.get("priority")) or "P1"
        candidate_element_codes = _list_text(candidate.get("involved_element_codes"))
        candidate_elements = _list_text(candidate.get("involved_elements"))
        if candidate_element_codes:
            point["involved_elements"] = candidate_element_codes
            point["involved_element_aliases"] = candidate_elements
        elif candidate_elements:
            point["involved_elements"] = candidate_elements
        existing_steps = point.get("steps") if isinstance(point.get("steps"), list) else []
        has_executable_steps = any(
            isinstance(step, dict)
            and _normalized_text(step.get("action"))
            and _normalized_text(step.get("action")).lower() != "candidate_step"
            for step in existing_steps
        )
        candidate_steps = _list_text(candidate.get("steps"))
        if candidate_steps and not has_executable_steps:
            point["steps"] = [
                {
                    "action": "candidate_step",
                    "target": "",
                    "value": row,
                    "raw_text": row,
                }
                for row in candidate_steps
            ]
        candidate_steps_hint = _list_text(candidate.get("steps_hint"))
        if candidate_steps_hint:
            point["steps_hint"] = candidate_steps_hint
        point_metadata = point.get("metadata") if isinstance(point.get("metadata"), dict) else {}
        point["metadata"] = {
            **point_metadata,
            "candidate_snapshot": candidate,
        }
        enriched.append(point)
    return enriched


def _resolve_page_object_from_db(project: str, page: str) -> dict[str, Any] | None:
    """Attempt to load page object elements from the database. Returns None on miss."""
    try:
        page_object, elements = _load_page_object_from_db(project, page)
        if page_object is None:
            return None
    except OperationalError:
        _LOGGER.warning("DB page-object lookup connection failed for %s/%s; retrying once", project, page, exc_info=True)
        try:
            page_object, elements = _load_page_object_from_db(project, page)
            if page_object is None:
                return None
        except ExecutionCompilerError:
            raise
        except Exception as exc:
            _LOGGER.debug("DB page-object lookup retry failed for %s/%s", project, page, exc_info=True)
            raise ExecutionCompilerError(
                code="page_object_db_lookup_failed",
                message="page object DB lookup failed",
                reason=f"{project}/web/{page}: {type(exc).__name__}",
                stage="resolve_page_object",
            ) from exc
    except ExecutionCompilerError:
        raise
    except Exception as exc:
        _LOGGER.debug("DB page-object lookup failed for %s/%s", project, page, exc_info=True)
        raise ExecutionCompilerError(
            code="page_object_db_lookup_failed",
            message="page object DB lookup failed",
            reason=f"{project}/web/{page}: {type(exc).__name__}",
            stage="resolve_page_object",
        ) from exc
    if not elements:
        raise ExecutionCompilerError(
            code="page_object_empty_elements",
            message="page object has no formal elements",
            reason=f"{project}/web/{page} has no page_elements rows",
            stage="resolve_page_object",
        )
    mapping: dict[str, dict[str, Any]] = {}
    for element in elements:
        if not _is_qualified_formal_element(element):
            continue
        code = _normalized_text(getattr(element, "element_code", ""))
        selector = _normalized_text(getattr(element, "locator_value", ""))
        if not code or not selector:
            continue
        role = _normalized_text(getattr(element, "role", ""))
        element_name = _normalized_text(getattr(element, "element_name", ""))
        business_type = _normalized_text(getattr(element, "business_type", "")).lower()
        aliases_json = _normalize_json_list(getattr(element, "aliases_json", []))
        semantic_tags_json = _normalize_json_list(getattr(element, "semantic_tags_json", []))
        aliases = _infer_element_aliases(
            page=page,
            element_code=code,
            element_name=element_name,
            locator_value=selector,
            role=role,
            business_type=business_type,
            aliases=aliases_json,
        )
        mapping[code] = {
            "selector": selector,
            "type": _normalized_text(getattr(element, "locator_type", "")) or "css",
            "role": role,
            "name": _element_display_name(
                page=page,
                element_code=code,
                element_name=element_name,
                locator_value=selector,
                role=role,
            ),
            "aliases": aliases,
            "business_type": business_type,
            "business_domain": _normalized_text(getattr(element, "business_domain", "")).lower(),
            "semantic_tags": semantic_tags_json,
            "review_status": _normalized_text(getattr(element, "review_status", "")).lower(),
            "stability_level": _normalized_text(getattr(element, "stability_level", "")).lower(),
            "status": _normalized_text(getattr(element, "status", "")).lower() or "active",
        }
    if page == "login":
        success_element = _load_cross_page_data_testid_element(
            project=project,
            element_code="home-page",
            preferred_pages=("home", "layout"),
        )
        if success_element is not None and "home-page" not in mapping:
            mapping["home-page"] = success_element
    if not mapping:
        raise ExecutionCompilerError(
            code="page_object_empty_elements",
            message="page object has no qualified elements for test point mapping",
            reason=(
                f"{project}/web/{page} has {len(elements)} formal element(s), "
                "but none match status=active + review_status=approved + stability_level in high/medium"
            ),
            stage="resolve_page_object",
        )
    # Governance path must not reintroduce legacy YAML-only elements once a DB
    # page object exists. YAML fallback is only for pages not yet modeled in DB.
    return {"page": page, "page_url": _normalized_text(getattr(page_object, "page_url", "")), "elements": mapping}


def _load_cross_page_data_testid_element(
    *,
    project: str,
    element_code: str,
    preferred_pages: tuple[str, ...],
) -> dict[str, Any] | None:
    """登录成功后会跳到首页，成功态断言允许引用首页的已治理 data-testid。"""
    # 合法例外：生成管线无 db Session 可透传，需独立 Session 做跨页 data-testid 查询
    normalized_code = _normalized_text(element_code)
    if not normalized_code:
        return None
    try:
        with _svc().SessionLocal() as db:
            repo = PageObjectRepository(db)
            row = repo.find_element_by_testid_across_pages(
                project, list(preferred_pages), normalized_code
            )
    except Exception:
        _LOGGER.debug("cross-page data-testid lookup failed for %s/%s", project, normalized_code, exc_info=True)
        return None
    if row is None or not _is_qualified_formal_element(row):
        return None
    selector = _normalized_text(getattr(row, "locator_value", ""))
    if not selector:
        return None
    return {
        "selector": selector,
        "type": "data-testid",
        "role": _normalized_text(getattr(row, "role", "")),
        "name": _element_display_name(
            page="home",
            element_code=normalized_code,
            element_name=_normalized_text(getattr(row, "element_name", "")),
            locator_value=selector,
            role=_normalized_text(getattr(row, "role", "")),
        ),
        "aliases": _infer_element_aliases(
            page="home",
            element_code=normalized_code,
            element_name=_normalized_text(getattr(row, "element_name", "")),
            locator_value=selector,
            role=_normalized_text(getattr(row, "role", "")),
            business_type=_normalized_text(getattr(row, "business_type", "")).lower(),
            aliases=_normalize_json_list(getattr(row, "aliases_json", [])),
        ),
        "business_type": _normalized_text(getattr(row, "business_type", "")).lower(),
        "business_domain": _normalized_text(getattr(row, "business_domain", "")).lower(),
        "semantic_tags": _normalize_json_list(getattr(row, "semantic_tags_json", [])),
        "review_status": _normalized_text(getattr(row, "review_status", "")).lower(),
        "stability_level": _normalized_text(getattr(row, "stability_level", "")).lower(),
        "status": _normalized_text(getattr(row, "status", "")).lower() or "active",
    }


def _load_page_object_from_db(project: str, page: str) -> tuple[PageObject | None, list[PageElement]]:
    # 合法例外：生成管线无 db Session 可透传，回退到 YAML asset 前的 DB 查询需独立 Session
    with _svc().SessionLocal() as db:
        repo = PageObjectRepository(db)
        page_object = repo.get_by_identity(project, "web", page)
        if page_object is None:
            return None, []
        elements = repo.list_elements_by_page_object_id(int(page_object.id), order_by_id=True)
        return page_object, elements


def _resolve_page_object_from_assets(page: str) -> dict[str, Any] | None:
    asset_path = _YAML_PAGE_OBJECT_ROOT / f"{page}.page-object.yaml"
    if not asset_path.exists():
        return None
    try:
        raw = yaml.safe_load(asset_path.read_text(encoding="utf-8")) or {}
    except Exception:
        _LOGGER.debug("asset page-object lookup failed for %s", page, exc_info=True)
        return None
    if not isinstance(raw, dict):
        return None
    elements_raw = raw.get("elements")
    if not isinstance(elements_raw, dict):
        return None
    mapping: dict[str, dict[str, Any]] = {}
    for code, item in elements_raw.items():
        element_code = _normalized_text(code)
        if not element_code:
            continue
        selector = ""
        locator_type = "css"
        role = ""
        if isinstance(item, dict):
            selector = _normalized_text(item.get("locator_value") or item.get("selector"))
            locator_type = _normalized_text(item.get("locator_type")) or "css"
            role = _normalized_text(item.get("role"))
            name = _normalized_text(item.get("element_name") or item.get("name"))
            aliases_raw = item.get("aliases")
        elif isinstance(item, str):
            selector = _normalized_text(item)
            name = ""
            aliases_raw = []
        if not selector:
            continue
        aliases: list[str] = []
        if isinstance(aliases_raw, list):
            aliases = [_normalized_text(value) for value in aliases_raw if _normalized_text(value)]
        elif isinstance(aliases_raw, str):
            alias_value = _normalized_text(aliases_raw)
            if alias_value:
                aliases = [alias_value]
        aliases = _infer_element_aliases(
            page=page,
            element_code=element_code,
            element_name=name,
            locator_value=selector,
            role=role,
            aliases=aliases,
        )
        name = _element_display_name(
            page=page,
            element_code=element_code,
            element_name=name,
            locator_value=selector,
            role=role,
        )
        mapping[element_code] = {
            "selector": selector,
            "type": locator_type,
            "role": role,
            "name": name,
            "aliases": aliases,
        }
    return {"page": page, "elements": mapping} if mapping else None



    db_result = _svc()._resolve_page_object_from_db(normalized_project, normalized_page)
    if db_result is not None:
        return db_result

    if strict_governance:
        raise ExecutionCompilerError(
            code="page_object_not_governed",
            message="page object is not governed for test point mapping",
            reason=(
                f"{normalized_project}/web/{normalized_page} has no governed DB page object; "
                "YAML fallback is disabled for new test point mapping"
            ),
            stage="resolve_page_object",
        )


def resolve_page_object(project: str, page: str, *, strict_governance: bool = True) -> dict[str, Any]:
    """Pipeline 的页面对象解析（Shared Path）。

    先查 DB（通过 _load_page_object_from_db），失败则回退到 YAML asset。
    返回 {page, page_url, elements}。
    对应的 orchestrator 入口是 OrchestratorService._resolve_page_object()，
    对应的 facade 入口是 facade._page_object_generation_context()。
    """
    normalized_project = _normalized_text(project)
    normalized_page = _normalized_text(page).lower()
    if not normalized_project or not normalized_page:
        raise ExecutionCompilerError(
            code="page_object_not_found",
            message="page object identity is required",
            reason="project/page is empty",
            stage="resolve_page_object",
        )

    db_result = _svc()._resolve_page_object_from_db(normalized_project, normalized_page)
    if db_result is not None:
        return db_result

    if strict_governance:
        raise ExecutionCompilerError(
            code="page_object_not_governed",
            message="page object is not governed for test point mapping",
            reason=(
                f"{normalized_project}/web/{normalized_page} has no governed DB page object; "
                "YAML fallback is disabled for new test point mapping"
            ),
            stage="resolve_page_object",
        )

    asset_result = _svc()._resolve_page_object_from_assets(normalized_page)
    if asset_result is not None:
        return asset_result

    raise ExecutionCompilerError(
        code="page_object_not_found",
        message="page object not found in DB",
        reason=f"{normalized_project}/web/{normalized_page}",
        stage="resolve_page_object",
    )



