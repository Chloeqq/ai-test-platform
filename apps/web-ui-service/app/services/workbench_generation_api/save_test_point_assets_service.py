from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from shared_backend.case_ids import normalize_case_id

from shared_backend.type_utils import dict_value as _dict_value, str_value as _normalized_text

from app.services import workbench_asset_service, workbench_state_store

from .context import WorkbenchContext
from . import preview_store


def _list_text(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for raw in value:
        text = _normalized_text(raw)
        if text and text not in items:
            items.append(text)
    return items


def _existing_test_point_asset_ids(project: str) -> list[str]:
    state_root = workbench_state_store.WEB_UI_STATE_ROOT / "test-points"
    project_dir = workbench_asset_service.state_project_dir(project, state_root=state_root)
    ids: list[str] = []
    for folder in (project_dir, project_dir / "plans"):
        if not folder.exists():
            continue
        for path in folder.glob("*.json"):
            case_id = _normalized_text(path.stem)
            if case_id and case_id not in ids:
                ids.append(case_id)
    return ids


def _preview_requirement(preview_id: str) -> tuple[str, dict[str, Any]]:
    normalized_preview_id = _normalized_text(preview_id)
    if not normalized_preview_id:
        return "", {}
    snapshot = preview_store.load_preview_snapshot(normalized_preview_id)
    preview_payload = _dict_value(snapshot.get("preview_payload"))
    item = _dict_value(preview_payload.get("item"))
    requirement_spec = _dict_value(item.get("requirement_spec"))
    requirement = (
        _normalized_text(requirement_spec.get("normalized_requirement"))
        or _normalized_text(requirement_spec.get("raw_requirement"))
        or _normalized_text(item.get("normalized_requirement"))
        or _normalized_text(item.get("raw_requirement"))
        or _normalized_text(snapshot.get("effective_requirement"))
    )
    return requirement, requirement_spec


def _candidate_snapshot(candidate: dict[str, Any]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for key in (
        "intent_id",
        "title",
        "summary",
        "intent_type",
        "priority",
        "precondition",
        "steps",
        "steps_hint",
        "expected",
        "expected_result",
        "scene_type",
        "test_data_type",
        "involved_elements",
        "involved_element_codes",
        "tags",
        "review_status",
        "review_note",
        "reviewed_at",
        "reviewed_by",
        "data",
    ):
        value = candidate.get(key)
        if isinstance(value, dict):
            if value:
                snapshot[key] = value
            continue
        if isinstance(value, list):
            rows = _list_text(value)
            if rows:
                snapshot[key] = rows
            continue
        text = _normalized_text(value)
        if text:
            snapshot[key] = text
    return snapshot


_LOGIN_ELEMENT_RULES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("username_input", "用户名输入框", "username", ("用户名输入框", "账号输入框", "用户名", "账号")),
    ("password_input", "密码输入框", "password", ("密码输入框", "密码")),
    ("login_button", "登录按钮", "", ("登录按钮", "登录")),
    ("home_menu", "首页菜单", "", ("首页菜单", "首页", "工作台首页")),
)


def _login_element_from_text(text: str) -> tuple[str, str, str] | None:
    """从测试点自然语言中识别登录页元素，避免把候选步骤长期停留在 candidate_step。"""
    normalized = _normalized_text(text)
    for element_code, element_name, data_key, aliases in _LOGIN_ELEMENT_RULES:
        if any(alias in normalized for alias in aliases):
            return element_code, element_name, data_key
    return None


def _input_value_from_text(text: str) -> tuple[bool, Any]:
    """只提取步骤文本中明确写出的输入值；不在代码里猜账号、密码或边界值。"""
    normalized = _normalized_text(text)
    if any(token in normalized for token in ("清空", "留空", "为空", "空值", "双空")):
        return True, ""
    if "空格" in normalized:
        return True, " "
    quoted = re.search(r"[\"“'‘](.*?)[\"”'’]", normalized)
    if quoted is not None:
        return True, quoted.group(1)
    matched = re.search(r"(?:输入|填写)(?:正确账号|正确密码|账号|密码|用户名)?\s*([A-Za-z0-9_@.\-]+)\s*$", normalized)
    if matched is not None:
        return True, matched.group(1)
    return False, None


def _data_ref_for_element(element_code: str, fallback_key: str) -> str:
    if element_code == "username_input":
        return "username"
    if element_code == "password_input":
        return "password"
    normalized = _normalized_text(fallback_key or element_code)
    return normalized.removesuffix("_input") if normalized else "input_value"


def _append_unique(items: list[str], value: str) -> None:
    normalized = _normalized_text(value)
    if normalized and normalized not in items:
        items.append(normalized)


def _canonical_login_involved_elements(involved_elements: list[str], involved_codes: list[str]) -> list[str]:
    """登录页结构化后以 element_code 为准，中文元素名只作为识别输入，不再混入正式字段。"""
    canonical: list[str] = []
    for element_code in involved_codes:
        _append_unique(canonical, element_code)
    for raw_element in involved_elements:
        normalized = _normalized_text(raw_element)
        if not normalized or normalized in canonical:
            continue
        matched = _login_element_from_text(normalized)
        if matched is None:
            continue
        element_code = matched[0]
        if element_code not in canonical:
            canonical.append(element_code)
    return canonical


def _structured_steps_from_candidate(
    *,
    candidate: dict[str, Any],
    steps: list[str],
    expected: str,
) -> tuple[list[dict[str, Any]], list[str], dict[str, dict[str, Any]], list[str], list[str]]:
    """将候选测试点步骤治理成 DSL V1.1 可消费的结构化步骤、steps_hint 与 data。"""
    structured_steps: list[dict[str, Any]] = []
    steps_hint: list[str] = []
    data: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    involved_codes: list[str] = []

    for raw_step in steps:
        step_text = _normalized_text(raw_step)
        if not step_text:
            continue
        element = _login_element_from_text(step_text)
        if any(token in step_text for token in ("输入", "填写", "清空", "留空")) and element is not None:
            element_code, element_name, data_key_hint = element
            has_value, value = _input_value_from_text(step_text)
            data_ref = _data_ref_for_element(element_code, data_key_hint)
            step: dict[str, Any] = {
                "action": "input",
                "target": f"element:{element_code}",
                "target_name": element_name,
                "data_ref": data_ref,
                "raw_text": step_text,
            }
            if has_value:
                step["value"] = value
                data[data_ref] = {"source_type": "inline", "value": value}
                # steps_hint 是当前直接编译器的稳定输入；空字符串可以表达，纯空格暂时不能安全表达。
                if value == " ":
                    warnings.append(f"{element_name} 的空格输入需要后续由 DSL 数据引用执行，当前 steps_hint 无法无损表达纯空格。")
                else:
                    _append_unique(steps_hint, f"input:{element_name}={value}")
            else:
                warnings.append(f"{element_name} 输入步骤缺少明确测试数据：{step_text}")
            structured_steps.append(step)
            _append_unique(involved_codes, element_code)
            continue

        if "点击" in step_text and element is not None:
            element_code, element_name, _data_key = element
            structured_steps.append(
                {
                    "action": "click",
                    "target": f"element:{element_code}",
                    "target_name": element_name,
                    "raw_text": step_text,
                }
            )
            _append_unique(steps_hint, f"click:{element_name}")
            _append_unique(involved_codes, element_code)
            continue

        if any(token in step_text for token in ("刷新", "访问首页", "进入首页")):
            structured_steps.append(
                {
                    "action": "goto",
                    "value": "#/home",
                    "raw_text": step_text,
                }
            )
            _append_unique(steps_hint, "goto:#/home")
            continue

        structured_steps.append(
            {
                "action": "candidate_step",
                "target": "",
                "value": step_text,
                "raw_text": step_text,
            }
        )
        warnings.append(f"步骤仍需人工结构化：{step_text}")

    expected_text = _normalized_text(expected)
    if any(token in expected_text for token in ("成功登录", "跳转到首页", "首页菜单可见", "进入首页")):
        structured_steps.append(
            {
                "action": "assert_visible",
                "target": "element:home_menu",
                "target_name": "首页菜单",
                "raw_text": expected_text or "校验首页菜单可见",
            }
        )
        _append_unique(steps_hint, "assert:首页菜单")
        _append_unique(involved_codes, "home_menu")
    elif any(token in expected_text for token in ("提示", "错误", "请输入", "失败", "拦截", "登录页面", "登录页")):
        structured_steps.append(
            {
                "action": "assert_url",
                "value": "#/login",
                "raw_text": expected_text or "校验仍停留在登录页",
            }
        )
        _append_unique(steps_hint, "assert_url:#/login")

    if not structured_steps:
        fallback = _normalized_text(candidate.get("summary") or candidate.get("title"))
        if fallback:
            structured_steps.append({"action": "candidate_step", "target": "", "value": fallback, "raw_text": fallback})
            warnings.append("缺少可结构化步骤。")

    return structured_steps, steps_hint, data, warnings, involved_codes


def _fallback_precondition(candidate: dict[str, Any], *, point_type: str, expected: str) -> str:
    """补齐业务级前置条件；不补账号密码、不补环境地址。"""
    precondition = _normalized_text(candidate.get("precondition"))
    if precondition:
        return precondition
    merged = " ".join(
        _normalized_text(candidate.get(key))
        for key in ("title", "summary", "expected", "expected_result")
    )
    if "已登录" in merged:
        return "用户已登录并处于首页。"
    if "未登录" in merged or "拦截" in merged:
        return "用户未登录。"
    if point_type in {"functional", "negative", "boundary", "format", "interaction_exception"} or "登录" in merged or expected:
        return "用户未登录，处于登录页面。"
    return "未维护。"


def _build_point(candidate: dict[str, Any], *, index: int) -> dict[str, Any]:
    intent_id = _normalized_text(candidate.get("intent_id")) or f"candidate-{index:02d}"
    title = _normalized_text(candidate.get("title")) or intent_id
    summary = _normalized_text(candidate.get("summary")) or title
    steps = _list_text(candidate.get("steps"))
    involved_elements = _list_text(candidate.get("involved_elements"))
    expected = _normalized_text(candidate.get("expected") or candidate.get("expected_result"))
    point_type = _normalized_text(candidate.get("intent_type")) or "functional"
    precondition = _fallback_precondition(candidate, point_type=point_type, expected=expected)
    action = "candidate"
    if point_type in {"boundary", "negative", "abnormal"}:
        action = "review"
    point_steps, steps_hint, data, structure_warnings, involved_codes = _structured_steps_from_candidate(
        candidate=candidate,
        steps=steps or [summary],
        expected=expected,
    )
    warnings: list[str] = []
    warnings.extend(structure_warnings)
    if not steps:
        warnings.append("缺少结构化步骤。")
    if not involved_elements:
        warnings.append("缺少涉及元素。")
    involved_elements = _canonical_login_involved_elements(involved_elements, involved_codes)
    return {
        "key": intent_id,
        "intent_id": intent_id,
        "point_type": point_type,
        "action": action,
        "description": summary,
        "step_index": index,
        "dependencies": [],
        "source_ids": [intent_id],
        "steps": point_steps,
        "steps_hint": steps_hint,
        "data": data,
        "warnings": warnings,
        "requires_review": bool(warnings),
        "involved_elements": involved_elements,
        "expected_result": expected,
        "precondition": precondition,
        "tags": _list_text(candidate.get("tags")),
        "priority": _normalized_text(candidate.get("priority")) or "P1",
        "confidence": 0.8 if steps else 0.6,
        "metadata": {
            "candidate_snapshot": _candidate_snapshot(candidate),
            "traceability": {
                "source_ids": [intent_id],
                "intent_ids": [intent_id],
            },
            "dsl_v1_1_structuring": {
                "data_keys": sorted(data.keys()),
                "steps_hint_count": len(steps_hint),
                "has_precondition": bool(precondition and precondition != "未维护。"),
            },
        },
    }


def _coverage_matrix_from_requirement_spec(
    requirement_spec: dict[str, Any],
    *,
    points: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    point_by_intent = {
        _normalized_text(point.get("intent_id")): _normalized_text(point.get("key"))
        for point in points
        if isinstance(point, dict) and _normalized_text(point.get("intent_id")) and _normalized_text(point.get("key"))
    }
    raw_rows = requirement_spec.get("coverage_matrix")
    rows: list[dict[str, Any]] = []
    if isinstance(raw_rows, list):
        for index, raw_row in enumerate(raw_rows, start=1):
            if not isinstance(raw_row, dict):
                continue
            intent_ids = _list_text(raw_row.get("intent_ids"))
            point_keys = [point_by_intent[intent_id] for intent_id in intent_ids if point_by_intent.get(intent_id)]
            rows.append(
                {
                    "row_id": _normalized_text(raw_row.get("row_id")) or f"coverage-row-{index:02d}",
                    "traceability_status": _normalized_text(raw_row.get("traceability_status")) or "covered",
                    "source_ids": _list_text(raw_row.get("source_ids")),
                    "intent_ids": intent_ids,
                    "point_keys": point_keys,
                    "changed_areas": _list_text(raw_row.get("changed_areas")),
                    "explanation": _normalized_text(raw_row.get("explanation")),
                }
            )
    if rows:
        return rows
    intent_ids = _list_text(
        [
            str(point.get("intent_id", "")).strip()
            for point in points
            if isinstance(point, dict) and str(point.get("intent_id", "")).strip()
        ]
    )
    point_keys = _list_text(
        [
            str(point.get("key", "")).strip()
            for point in points
            if isinstance(point, dict) and str(point.get("key", "")).strip()
        ]
    )
    if not intent_ids and not point_keys:
        return []
    return [
        {
            "row_id": "selected-intents",
            "traceability_status": "covered",
            "source_ids": ["source-01"],
            "intent_ids": intent_ids,
            "point_keys": point_keys,
            "changed_areas": [],
            "explanation": "derived from selected test intents",
        }
    ]


def _intent_type_distribution(candidates: list[dict[str, Any]]) -> dict[str, int]:
    distribution: dict[str, int] = {}
    for candidate in candidates:
        intent_type = _normalized_text(candidate.get("intent_type")) or "functional"
        distribution[intent_type] = int(distribution.get(intent_type, 0) or 0) + 1
    return dict(sorted(distribution.items()))


def _find_existing_page_asset_for_upsert(project: str, page: str, existing_case_ids: list[str]) -> str:
    """在已有资产中查找同页面资产，返回其 case_id 以支持 upsert 而非重复创建。"""
    import re
    normalized_project = _normalized_text(project)
    normalized_page = _normalized_text(page)
    if not normalized_project or not normalized_page:
        return ""
    # case_id 格式: {project}-web-{page}-{type}-{source}-{seq}
    # 匹配同 project 同 page 的资产
    page_prefix = f"{normalized_project}-web-{normalized_page}-"
    for case_id in sorted(existing_case_ids, key=lambda cid: _normalized_text(cid)):
        if _normalized_text(case_id).startswith(page_prefix):
            return _normalized_text(case_id)
    return ""


def _first_candidate_title(candidates: list[dict[str, Any]], *, page: str) -> str:
    for candidate in candidates:
        title = _normalized_text(candidate.get("title")) or _normalized_text(candidate.get("summary"))
        if title:
            return title
    return f"{page} 测试点资产集" if page else "测试点资产集"


class SaveTestPointAssetsService:
    def __init__(self, *, context: WorkbenchContext) -> None:
        self._context = context

    def execute(self, payload: Any) -> dict[str, Any]:
        context = self._context
        runtime = context.runtime
        repository = context.repository
        runtime.ensure_dirs()

        project = _normalized_text(getattr(payload, "project", "")) or "mall"
        page = runtime.normalize_page_slug(_normalized_text(getattr(payload, "page", "")))
        if not page:
            raise runtime.HTTPException(
                status_code=runtime.status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="page must not be empty",
            )

        requirement_text = _normalized_text(getattr(payload, "requirement", ""))
        input_sources = [item for item in (getattr(payload, "input_sources", None) or []) if isinstance(item, dict)]
        openapi_spec = getattr(payload, "openapi_spec", None)
        openapi_spec = openapi_spec if isinstance(openapi_spec, dict) else {}
        has_multisource_inputs = context.generation.has_multisource_inputs(
            input_sources=input_sources,
            openapi_spec=openapi_spec,
            prd_text=getattr(payload, "prd_text", ""),
            prd_url=getattr(payload, "prd_url", ""),
            user_story=getattr(payload, "user_story", ""),
            git_diff=getattr(payload, "git_diff", ""),
            git_diff_path=getattr(payload, "git_diff_path", ""),
            openapi_url=getattr(payload, "openapi_url", ""),
            defect_ticket=getattr(payload, "defect_ticket", ""),
            runtime_logs=getattr(payload, "runtime_logs", ""),
        )
        effective_requirement = context.generation.resolve_effective_requirement(
            requirement_text=requirement_text,
            normalized_page=page,
            multisource_enabled=has_multisource_inputs,
        )

        raw_candidates = [item for item in list(getattr(payload, "selected_candidates", []) or []) if isinstance(item, dict)]
        selected_intent_ids = [
            _normalized_text(item)
            for item in list(getattr(payload, "selected_intent_ids", []) or [])
            if _normalized_text(item)
        ]
        preview_id = _normalized_text(getattr(payload, "preview_id", ""))
        preview_requirement, requirement_spec = _preview_requirement(preview_id)
        if preview_requirement:
            effective_requirement = preview_requirement

        raw_candidates = preview_store.resolve_selected_candidates(
            preview_id=preview_id,
            selected_intent_ids=selected_intent_ids,
            fallback_candidates=raw_candidates,
        )
        batch_candidates = context.candidate_normalizer.normalize_candidates(raw_candidates)
        if len(batch_candidates) > 200:
            raise runtime.HTTPException(
                status_code=runtime.status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="selected_candidates exceeds max size 200",
            )
        if not batch_candidates:
            return {
                "message": "no selected candidates to save",
                "count": 0,
                "items": [],
            }

        requested_case_id = _normalized_text(getattr(payload, "case_id", ""))
        existing_case_ids = repository.collect_existing_case_ids(assets_cases_root=runtime.AI_CASES_ROOT.parent)
        for case_id in _existing_test_point_asset_ids(project):
            if case_id not in existing_case_ids:
                existing_case_ids.append(case_id)
        # Reuse existing asset for the same page when no explicit case_id is requested
        if not requested_case_id:
            existing_page_asset_id = _find_existing_page_asset_for_upsert(project, page, existing_case_ids)
            if existing_page_asset_id:
                requested_case_id = existing_page_asset_id
        candidate_case_id = repository.allocate_case_id(
            requested_case_id=requested_case_id,
            project=project,
            page=page,
            module=page,
            ai_cases_root=runtime.AI_CASES_ROOT,
            existing_case_ids=existing_case_ids,
        )
        points = [_build_point(candidate, index=index) for index, candidate in enumerate(batch_candidates, start=1)]
        selected_ids = [
            _normalized_text(candidate.get("intent_id"))
            for candidate in batch_candidates
            if _normalized_text(candidate.get("intent_id"))
        ]
        involved_elements = _list_text(
            [
                element
                for point in points
                for element in _list_text(point.get("involved_elements"))
            ]
        )
        plan_title = _first_candidate_title(batch_candidates, page=page)
        asset_title = f"{page} 页面测试点资产集" if page else "测试点资产集"
        parse_confidence = requirement_spec.get("parse_confidence")
        try:
            confidence = float(parse_confidence) if parse_confidence is not None else 0.8
        except (TypeError, ValueError):
            confidence = 0.8
        plan = {
            "version": "TestPointPlanV1",
            "project": project,
            "case_id": candidate_case_id,
            "page": page,
            "title": plan_title,
            "priority": _normalized_text(requirement_spec.get("priority")) or _normalized_text(getattr(payload, "priority", "")) or "P1",
            "source_type": "selection_save",
            "requirement": [effective_requirement] if effective_requirement else [],
            "generated_at": runtime.now_iso(),
            "points": points,
            "coverage": {
                "status": "full",
                "coverage_ratio": 1.0 if points else 0.0,
                "generated_case_count": len(points),
                "expected_case_count": len(points),
                "missing_scenarios": [],
                "covered_scenarios": selected_ids,
            },
            "review_summary": {
                "total_points": len(points),
                "mainline_point_count": len(points),
                "design_only_point_count": 0,
                "technique_distribution": _intent_type_distribution(batch_candidates),
            },
            "metadata": {
                "saved_by": "web-ui-service",
                "origin": "selection_save",
                "preview_id": preview_id,
                "asset_title": asset_title,
                "selected_intent_ids": selected_ids,
                "selected_candidates": [_candidate_snapshot(candidate) for candidate in batch_candidates],
                "coverage_matrix": _coverage_matrix_from_requirement_spec(requirement_spec, points=points),
                "requirement_source": "preview.normalized_requirement" if preview_requirement else "payload.requirement",
                "normalized_requirement": effective_requirement,
                "parse_confidence": parse_confidence,
            },
            "involved_elements": involved_elements,
            "confidence": max(0.0, min(1.0, confidence)),
            "warnings": [],
            "requires_review": False,
        }
        plan_path = runtime.save_test_point_plan(
            project=project,
            case_id=candidate_case_id,
            page=page,
            page_url="",
            requirement=effective_requirement,
            plan=plan,
            # 保存“测试点资产”时必须写入 test-points 事实源目录。
            # runtime 默认绑定 generated-cases，是为了生成正式用例时不覆盖源资产；
            # 这里显式覆盖 state_root，避免详情页读取 TEST_POINTS_ROOT 时拿到空资产。
            state_root=workbench_state_store.WEB_UI_STATE_ROOT / "test-points",
        )
        asset_path = workbench_asset_service.state_case_file(
            project,
            candidate_case_id,
            state_root=workbench_state_store.WEB_UI_STATE_ROOT / "test-points",
        )
        asset = workbench_asset_service.load_test_point_asset_with_root(
            project,
            candidate_case_id,
            state_root=workbench_state_store.WEB_UI_STATE_ROOT / "test-points",
        )
        # Sync test points to DB (per-point records)
        try:
            db_synced = repository.sync_test_points(
                project_code=project,
                page_code=page,
                points=points,
            )
        except Exception:
            db_synced = 0
        # Sync asset bundle to DB (test_point_assets table)
        try:
            from app.services import test_point_asset_store
            if isinstance(asset, dict) and asset.get("asset_id"):
                test_point_asset_store.save_asset(repository.db, project=project, bundle=asset)
        except Exception:
            pass
        runtime.append_history(
            {
                "timestamp": runtime.now_iso(),
                "action": "save_test_point_asset",
                "case_id": candidate_case_id,
                "page": page,
                "project": project,
                "path": str(asset_path.resolve()),
                "plan_path": str(Path(plan_path).resolve()),
                "intent_count": len(selected_ids) or len(points),
            }
        )

        return {
            "message": "saved 1 test point asset",
            "count": 1,
            "items": [
                {
                    "case_id": candidate_case_id,
                    "project": project,
                    "page": page,
                    "title": asset_title,
                    "intent_ids": selected_ids,
                    "intent_count": len(selected_ids) or len(points),
                    "plan_path": str(Path(plan_path).resolve()),
                    "asset_path": str(asset_path.resolve()),
                    "asset": asset,
                }
            ],
        }
