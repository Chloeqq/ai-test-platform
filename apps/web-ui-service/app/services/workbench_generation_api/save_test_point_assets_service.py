"""保存测试点资产（TestPointPlanV1）的入口 Service。

职责编排：
1. 参数校验（project / page 非空）
2. 需求解析（preview 快照优先，回退到 payload requirement）
3. 页面对象加载（DB → YAML → 默认映射）
4. 候选测试点加载与标准化
5. case_id 分配（upsert 逻辑）
6. 测试点编译（通过 compilation.point_builder）
7. TestPointPlan 构造
8. 持久化（文件写入 + DB 同步 + 操作历史记录）
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from shared_backend.type_utils import str_value as _normalized_text, as_text_list

from app.services import workbench_asset_service, workbench_state_store

from .context import WorkbenchContext
from . import preview_store
from . import constants as _c

from .elements import load_page_config, ElementResolver
from .hooks.login_password_visibility import LoginPasswordVisibilityHook
from .compilation import build_point
from .assets import (
    preview_requirement,
    candidate_snapshot,
    existing_test_point_asset_ids,
    find_existing_page_asset_for_upsert,
    coverage_matrix_from_requirement_spec,
    intent_type_distribution,
    first_candidate_title,
)

LOGGER = logging.getLogger(__name__)


class SaveTestPointAssetsService:
    """保存测试点资产（TestPointPlanV1）的入口 Service。"""

    def __init__(self, *, context: WorkbenchContext) -> None:
        self._context = context

    def execute(self, payload: Any) -> dict[str, Any]:
        context = self._context
        runtime = context.runtime
        repository = context.repository
        runtime.ensure_dirs()

        # ── 参数校验 ──
        project = _normalized_text(getattr(payload, "project", "")) or context.default_project
        page = runtime.normalize_page_slug(_normalized_text(getattr(payload, "page", "")))
        if not page:
            raise runtime.HTTPException(
                status_code=runtime.status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="page must not be empty",
            )

        # ── DB 加载页面对象 → PageConfig + ElementResolver ──
        page_config = load_page_config(repository.db, project=project, page=page)
        resolver = ElementResolver(page_config.alias_map)

        # ── 加载页面 Hook ──
        page_hook = _get_page_hook(page)

        # ── 需求解析 ──
        requirement_text = _normalized_text(getattr(payload, "requirement", ""))
        input_sources = [
            item for item in (getattr(payload, "input_sources", None) or [])
            if isinstance(item, dict)
        ]
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

        # ── 候选测试点加载 ──
        raw_candidates = [
            item for item in list(getattr(payload, "selected_candidates", []) or [])
            if isinstance(item, dict)
        ]
        selected_intent_ids = [
            _normalized_text(item)
            for item in list(getattr(payload, "selected_intent_ids", []) or [])
            if _normalized_text(item)
        ]
        preview_id = _normalized_text(getattr(payload, "preview_id", ""))
        preview_req_text, requirement_spec = preview_requirement(preview_id)
        if preview_req_text:
            effective_requirement = preview_req_text

        raw_candidates = preview_store.resolve_selected_candidates(
            preview_id=preview_id,
            selected_intent_ids=selected_intent_ids,
            fallback_candidates=raw_candidates,
        )
        batch_candidates = context.candidate_normalizer.normalize_candidates(raw_candidates)
        if len(batch_candidates) > _c.MAX_CANDIDATES:
            raise runtime.HTTPException(
                status_code=runtime.status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"selected_candidates exceeds max size {_c.MAX_CANDIDATES}",
            )
        if not batch_candidates:
            return {"message": "no selected candidates to save", "count": 0, "items": []}

        # ── case_id 分配（支持 upsert） ──
        requested_case_id = _normalized_text(getattr(payload, "case_id", ""))
        existing_case_ids = repository.collect_existing_case_ids(
            assets_cases_root=runtime.AI_CASES_ROOT.parent,
        )
        for case_id in existing_test_point_asset_ids(project):
            if case_id not in existing_case_ids:
                existing_case_ids.append(case_id)
        if not requested_case_id:
            existing_page_asset_id = find_existing_page_asset_for_upsert(
                project, page, existing_case_ids,
            )
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

        # ── 测试点编译（通过 compilation 模块，注入 resolver + page_hook） ──
        points = [
            build_point(candidate, index=index, resolver=resolver, page_hook=page_hook, page_config=page_config)
            for index, candidate in enumerate(batch_candidates, start=1)
        ]
        selected_ids = [
            _normalized_text(candidate.get("intent_id"))
            for candidate in batch_candidates
            if _normalized_text(candidate.get("intent_id"))
        ]
        involved_elements = as_text_list(
            [
                element
                for point in points
                for element in as_text_list(point.get("involved_elements"))
            ]
        )

        # ── Plan 构造 ──
        plan_title = first_candidate_title(batch_candidates, page=page)
        parse_confidence = requirement_spec.get("parse_confidence")
        try:
            confidence = (
                float(parse_confidence)
                if parse_confidence is not None
                else _c.DEFAULT_CONFIDENCE_WITH_STEPS
            )
        except (TypeError, ValueError):
            confidence = _c.DEFAULT_CONFIDENCE_WITH_STEPS

        plan = {
            "version": "TestPointPlanV1",
            "project": project,
            "case_id": candidate_case_id,
            "page": page,
            "title": plan_title,
            "priority": (
                _normalized_text(requirement_spec.get("priority"))
                or _normalized_text(getattr(payload, "priority", ""))
                or _c.DEFAULT_PRIORITY
            ),
            "source_type": _c.SOURCE_TYPE_SELECTION_SAVE,
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
                "technique_distribution": intent_type_distribution(batch_candidates),
            },
            "metadata": {
                "saved_by": os.getenv("SERVICE_NAME", _c.SAVED_BY),
                "origin": _c.SOURCE_TYPE_SELECTION_SAVE,
                "preview_id": preview_id,
                "asset_title": _c.asset_title_for_page(page),
                "selected_intent_ids": selected_ids,
                "selected_candidates": [
                    candidate_snapshot(c) for c in batch_candidates
                ],
                "coverage_matrix": coverage_matrix_from_requirement_spec(
                    requirement_spec, points=points,
                ),
                "requirement_source": (
                    "preview.normalized_requirement" if preview_req_text
                    else "payload.requirement"
                ),
                "normalized_requirement": effective_requirement,
                "parse_confidence": parse_confidence,
            },
            "involved_elements": involved_elements,
            "confidence": max(0.0, min(1.0, confidence)),
            "warnings": [],
            "requires_review": False,
        }

        # ── 持久化：文件写入 ──
        plan_path = runtime.save_test_point_plan(
            project=project,
            case_id=candidate_case_id,
            page=page,
            page_url="",
            requirement=effective_requirement,
            plan=plan,
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

        # ── 持久化：DB 同步（降级不阻断） ──
        try:
            db_synced = repository.sync_test_points(
                project_code=project,
                page_code=page,
                points=points,
            )
        except Exception:
            db_synced = 0
        try:
            from app.services import test_point_asset_store
            if isinstance(asset, dict) and asset.get("asset_id"):
                test_point_asset_store.save_asset(
                    repository.db, project=project, bundle=asset,
                )
        except Exception:
            LOGGER.warning(
                "test point asset DB write-through failed for %s/%s",
                project, candidate_case_id, exc_info=True,
            )

        # ── 操作历史记录 ──
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
                    "title": _c.asset_title_for_page(page),
                    "intent_ids": selected_ids,
                    "intent_count": len(selected_ids) or len(points),
                    "plan_path": str(Path(plan_path).resolve()),
                    "asset_path": str(asset_path.resolve()),
                    "asset": asset,
                }
            ],
        }


# ── 内置函数 ──────────────────────────────────────────────────────────────

def _get_page_hook(page: str) -> LoginPasswordVisibilityHook | None:
    """根据 page code 返回对应的 PageHook，无匹配则返回 None。"""
    if page == LoginPasswordVisibilityHook().page_code:
        return LoginPasswordVisibilityHook()
    return None
