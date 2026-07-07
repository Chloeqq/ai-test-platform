"""存量资产查询 — 扫描已有测试点资产，支持 upsert 去重。"""

from __future__ import annotations

from pathlib import Path

from shared_backend.type_utils import str_value as _normalized_text

from app.services import workbench_asset_service, workbench_state_store


def existing_test_point_asset_ids(project: str) -> list[str]:
    """从状态存储目录扫描已有测试点资产的 case_id 列表。"""
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


def find_existing_page_asset_for_upsert(
    project: str, page: str, existing_case_ids: list[str],
) -> str:
    """在已有资产中查找同页面的现有资产 case_id，支持 upsert 而非重复创建。

    case_id 格式: {project}-web-{page}-{type}-{source}-{seq}
    """
    normalized_project = _normalized_text(project)
    normalized_page = _normalized_text(page)
    if not normalized_project or not normalized_page:
        return ""
    page_prefix = f"{normalized_project}-web-{normalized_page}-"
    for case_id in sorted(existing_case_ids, key=lambda cid: _normalized_text(cid)):
        if _normalized_text(case_id).startswith(page_prefix):
            return _normalized_text(case_id)
    return ""
