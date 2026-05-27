from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from shared_backend.case_ids import build_case_id, match_case_id, next_case_sequence, normalize_case_id
from sqlalchemy import func, select
from sqlalchemy.orm import Session
import yaml

from app.models.test_case import TestCase, TestCaseStep


class WorkbenchGenerationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def collect_existing_case_ids(self, *, assets_cases_root: Path) -> list[str]:
        items: list[str] = []
        db_case_ids = self.db.execute(select(TestCase.case_id)).scalars().all()
        for raw_case_id in db_case_ids:
            normalized_case_id = normalize_case_id(str(raw_case_id or "").strip(), fallback="").strip()
            if normalized_case_id and match_case_id(normalized_case_id):
                items.append(normalized_case_id)
        if assets_cases_root.exists():
            for path in assets_cases_root.rglob("*.yaml"):
                normalized_case_id = normalize_case_id(path.stem, fallback="").strip()
                if normalized_case_id and match_case_id(normalized_case_id):
                    items.append(normalized_case_id)
        deduped: list[str] = []
        for value in items:
            if value not in deduped:
                deduped.append(value)
        return deduped

    def allocate_case_id(
        self,
        *,
        requested_case_id: str,
        project: str,
        page: str,
        module: str,
        ai_cases_root: Path,
        existing_case_ids: list[str] | None = None,
    ) -> str:
        requested = normalize_case_id(requested_case_id, fallback="").strip() if str(requested_case_id).strip() else ""
        assets_root = ai_cases_root.resolve().parent
        all_existing_case_ids: list[str] = []
        seen_case_ids: set[str] = set()
        if assets_root.exists():
            for path in assets_root.rglob("*.yaml"):
                normalized_path_case_id = normalize_case_id(path.stem, fallback="").strip()
                if normalized_path_case_id and match_case_id(normalized_path_case_id) and normalized_path_case_id not in seen_case_ids:
                    seen_case_ids.add(normalized_path_case_id)
                    all_existing_case_ids.append(normalized_path_case_id)
        for item in existing_case_ids or []:
            value = normalize_case_id(str(item or "").strip(), fallback="").strip()
            if value and match_case_id(value) and value not in seen_case_ids:
                seen_case_ids.add(value)
                all_existing_case_ids.append(value)
        if requested and match_case_id(requested):
            return requested
        sequence = next_case_sequence(
            existing_case_ids=all_existing_case_ids,
            page=page,
            module=module,
            project=project,
            case_type="FN",
            source="AI",
        )
        return build_case_id(
            project=project,
            page=page,
            module=module,
            case_type="FN",
            source="AI",
            sequence=sequence,
        )

    def _next_case_id_for_conflict(self, current_case_id: str, existing_case_ids: list[str]) -> str:
        normalized_current_case_id = normalize_case_id(str(current_case_id or "").strip(), fallback="").strip()
        matched = match_case_id(normalized_current_case_id)
        if not matched:
            return normalized_current_case_id
        sequence = next_case_sequence(
            existing_case_ids=existing_case_ids,
            page=matched.group("page"),
            module=matched.group("module"),
            project=matched.group("project"),
            client=matched.group("client"),
            page_code=matched.group("page"),
            module_code=matched.group("module"),
            case_type=matched.group("case_type"),
            source=matched.group("source"),
        )
        return build_case_id(
            page=matched.group("page"),
            module=matched.group("module"),
            sequence=sequence,
            project=matched.group("project"),
            client=matched.group("client"),
            page_code=matched.group("page"),
            module_code=matched.group("module"),
            case_type=matched.group("case_type"),
            source=matched.group("source"),
        )

    def sync_generated_case_item(
        self,
        *,
        result: dict[str, Any],
        payload: Any,
        selected_candidate: dict[str, Any] | None,
        write_case_yaml: Callable[..., str],
        save_case_state: Callable[[str, dict[str, Any], Any], dict[str, Any]],
        append_history: Callable[[dict[str, Any]], None],
        now_iso: Callable[[], str],
        ai_cases_root: Path,
        http_exception_cls: Any,
    ) -> dict[str, Any]:
        from app.services import test_case_service

        _ = selected_candidate
        item_raw = result.get("item")
        item: dict[str, Any] = item_raw if isinstance(item_raw, dict) else {}
        if not isinstance(item_raw, dict):
            result["item"] = item
        yaml_content = str(item.get("yaml_content", "")).strip()
        if not yaml_content:
            return item
        case_yaml = yaml.safe_load(yaml_content) or {}
        if not isinstance(case_yaml, dict):
            return item
        source_path = str(item.get("path", "")).strip()
        try:
            synchronized = test_case_service.upsert_test_case_from_workbench(
                self.db,
                project_code=payload.project,
                case_yaml=case_yaml,
                source_path=source_path,
            )
        except http_exception_cls as exc:
            detail_text = str(getattr(exc, "detail", "")).lower()
            if int(getattr(exc, "status_code", 0) or 0) != 409 or "case_id already exists" not in detail_text:
                raise
            current_case_id = normalize_case_id(str(case_yaml.get("id", "")).strip(), fallback="").strip()
            retry_case_id = self._next_case_id_for_conflict(
                current_case_id,
                self.collect_existing_case_ids(assets_cases_root=ai_cases_root.parent),
            )
            if not retry_case_id or retry_case_id == current_case_id:
                raise
            old_path = Path(source_path).resolve() if source_path else None
            retry_path = ai_cases_root / f"{retry_case_id}.yaml"
            case_yaml["id"] = retry_case_id
            final_text = write_case_yaml(retry_path, case_yaml)
            state_entry = save_case_state(payload.project, case_yaml, retry_path)
            item["case_id"] = retry_case_id
            item["path"] = str(retry_path.resolve())
            item["yaml_content"] = final_text
            item["state"] = state_entry
            append_history(
                {
                    "timestamp": now_iso(),
                    "action": "generate_case_retry_on_conflict",
                    "case_id": retry_case_id,
                    "replaced_case_id": current_case_id,
                    "path": str(retry_path.resolve()),
                    "previous_path": str(old_path) if old_path else "",
                }
            )
            synchronized = test_case_service.upsert_test_case_from_workbench(
                self.db,
                project_code=payload.project,
                case_yaml=case_yaml,
                source_path=str(retry_path.resolve()),
            )
        item["synced_case"] = {
            "id": synchronized.id,
            "case_id": synchronized.case_id,
            "project_code": synchronized.project_code,
        }
        return item

    def find_test_case_by_case_id(self, case_business_id: str) -> TestCase | None:
        return self.db.execute(select(TestCase).where(TestCase.case_id == case_business_id)).scalar_one_or_none()

    def count_case_step_rows(self, *, case_db_id: int) -> int:
        count = self.db.execute(select(func.count(TestCaseStep.id)).where(TestCaseStep.case_id == int(case_db_id))).scalar_one()
        return int(count or 0)
