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

import json
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
from .hooks import get_page_hook
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
        if not project:
            raise runtime.HTTPException(
                status_code=runtime.status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="project must not be empty and no default project is available",
            )
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
        page_hook = get_page_hook(page)

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

        # ── 幂等检查：同 preview_id 已保存 → 直接返回已有资产 ──
        from app.services import test_point_asset_store as tpa_store
        if preview_id:
            existing_asset_id = tpa_store.find_asset_id_by_preview_id(
                repository.db, project=project, preview_id=preview_id,
            )
            if existing_asset_id:
                LOGGER.info(
                    "preview_id %s already saved as %s, returning existing asset",
                    preview_id, existing_asset_id,
                )
                existing_asset = tpa_store.load_asset(
                    repository.db, project=project, asset_id=existing_asset_id,
                )
                return {
                    "message": "already saved (idempotent)",
                    "count": 1,
                    "items": [
                        {
                            "case_id": existing_asset_id,
                            "project": project,
                            "page": page,
                            "title": (existing_asset or {}).get("title", _c.asset_title_for_page(page)),
                            "intent_ids": selected_intent_ids,
                            "intent_count": len(selected_intent_ids),
                            "plan_path": (existing_asset or {}).get("plan_path", ""),
                            "asset_path": "",
                            "asset": existing_asset,
                        }
                    ],
                }

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
            "requires_review": False,
        }

        # ── 持久化 Step 1：DB 写入（事实源，原子事务） ──
        # test_points 和 test_point_assets 必须在同一事务中，
        # 任意一条失败即全部回滚，杜绝 DB 层部分写入。
        from app.services import test_point_asset_store
        bundle = _build_asset_bundle(
            plan=plan,
            case_id=candidate_case_id,
            page=page,
            point_count=len(points),
            intent_count=len(selected_ids) or len(points),
        )
        try:
            repository.sync_test_points(
                project_code=project,
                page_code=page,
                points=points,
            )
            test_point_asset_store.save_asset(
                db=repository.db, project=project, bundle=bundle,
            )
            repository.db.commit()
            LOGGER.info(
                "test point asset saved to DB: project=%s case_id=%s points=%d",
                project, candidate_case_id, len(points),
            )
        except Exception:
            repository.db.rollback()
            LOGGER.error(
                "test point asset DB write failed for %s/%s, rolled back",
                project, candidate_case_id, exc_info=True,
            )
            raise

        # ── 持久化 Step 2：文件写入（缓存，失败不阻断） ──
        # 文件是 DB 的可重建缓存，写入失败仅记日志。
        plan_path_str = ""
        asset_path_str = ""
        state_root = workbench_state_store.WEB_UI_STATE_ROOT / "test-points"
        try:
            plan_path = runtime.save_test_point_plan(
                project=project,
                case_id=candidate_case_id,
                page=page,
                page_url="",
                requirement=effective_requirement,
                plan=plan,
                state_root=state_root,
            )
            plan_path_str = str(Path(plan_path).resolve())
        except Exception:
            LOGGER.warning(
                "test point plan file write failed for %s/%s (data is in DB)",
                project, candidate_case_id, exc_info=True,
            )
        try:
            asset_path = workbench_asset_service.state_case_file(
                project, candidate_case_id, state_root=state_root,
            )
            asset_path_str = str(asset_path.resolve())
        except Exception:
            LOGGER.warning(
                "test point asset file write failed for %s/%s (data is in DB)",
                project, candidate_case_id, exc_info=True,
            )

        # ── 操作历史记录（失败不阻断） ──
        try:
            runtime.append_history(
                {
                    "timestamp": runtime.now_iso(),
                    "action": "save_test_point_asset",
                    "case_id": candidate_case_id,
                    "page": page,
                    "project": project,
                    "path": asset_path_str,
                    "plan_path": plan_path_str,
                    "intent_count": len(selected_ids) or len(points),
                }
            )
        except Exception:
            LOGGER.warning(
                "history append failed for %s/%s",
                project, candidate_case_id, exc_info=True,
            )

        # ── 清理：已保存的 preview 不再需要保留 ──
        if preview_id:
            try:
                preview_store.delete_preview_snapshot(preview_id)
            except Exception:
                pass
        # 顺手清理 7 天以上旧 preview
        try:
            preview_store.cleanup_expired_previews(max_age_days=7)
        except Exception:
            pass

        # Phase 5.1: 追加 quality snapshot
        try:
            from app.services.workbench_asset_views import append_quality_snapshot
            # 从已保存的 asset 文件读取真实 version（bundle.version 固定为 1）
            actual_version = 1
            if asset_path_str:
                try:
                    asset_payload = json.loads(Path(asset_path_str).read_text(encoding="utf-8"))
                    actual_version = int(asset_payload.get("version", 1) or 1)
                except Exception:
                    pass
            snapshot_asset = {
                "project": project,
                "asset_id": candidate_case_id,
                "version": actual_version,
                "source_type": source_type,
                "plan": {"points": points},
                "warnings": [],
            }
            append_quality_snapshot(snapshot_asset, trigger="ai_save")
        except Exception:
            LOGGER.warning(
                "quality snapshot append failed for %s/%s",
                project, candidate_case_id, exc_info=True,
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
                    "plan_path": plan_path_str,
                    "asset_path": asset_path_str,
                    "asset": bundle,
                }
            ],
        }


# ── 内置函数 ──────────────────────────────────────────────────────────────

def _build_asset_bundle(
    *,
    plan: dict[str, Any],
    case_id: str,
    page: str,
    point_count: int,
    intent_count: int,
) -> dict[str, Any]:
    """在内存中构造 asset bundle，不依赖文件 I/O。

    DB 写入需要此 bundle 作为 raw_payload，包含完整的 plan 数据。
    """
    return {
        "asset_id": case_id,
        "page": page,
        "title": _c.asset_title_for_page(page),
        "priority": plan.get("priority", _c.DEFAULT_PRIORITY),
        "source_type": plan.get("source_type", _c.SOURCE_TYPE_SELECTION_SAVE),
        "status": "active",
        "point_count": point_count,
        "intent_count": intent_count,
        "requires_review": plan.get("requires_review", False),
        "version": 1,
        "plan": plan,
    }


# _get_page_hook 已迁移至 hooks/__init__.py 的 PAGE_HOOK_REGISTRY 注册表模式
# 新增页面 Hook: 继承 PageHook → 注册到 PAGE_HOOK_REGISTRY → 无需改本文件
