from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Callable

from shared_backend.case_ids import build_case_id, match_case_id, next_case_sequence, normalize_case_id
from sqlalchemy import func, select
from sqlalchemy.orm import Session
import yaml

from app.models.page_object import PageElement, PageObject, PageObjectRef
from app.models.test_case import TestCase, TestCaseStep


class WorkbenchGenerationUnitOfWork(AbstractContextManager["WorkbenchGenerationUnitOfWork"]):
    def __init__(self, db: Session) -> None:
        self.db = db

    def __enter__(self) -> "WorkbenchGenerationUnitOfWork":
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
        if exc_type is None:
            self.db.commit()
        else:
            self.db.rollback()
        return False


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
        if requested and match_case_id(requested) and requested not in seen_case_ids:
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

    def _extract_case_element_targets(self, case: TestCase) -> list[str]:
        steps = case.test_steps if isinstance(case.test_steps, list) else []
        targets: list[str] = []
        for raw in steps:
            step = raw if isinstance(raw, dict) else {}
            target = str(step.get("target") or "").strip()
            if target.startswith("element:"):
                target = str(target.removeprefix("element:")).strip()
            if not target:
                continue
            if target.startswith(("http://", "https://", "/", "#")):
                continue
            if ":" in target:
                prefix = str(target.split(":", 1)[0]).strip().lower()
                if prefix in {"css", "xpath", "text", "role", "id", "name", "url"}:
                    continue
            if target not in targets:
                targets.append(target)
        return targets

    def bind_case_page_object_refs(self, case: TestCase) -> dict[str, int]:
        case_business_id = str(case.case_id or "").strip()
        if not case_business_id:
            return {"linked_ref_count": 0, "skipped_ref_count": 0}
        page_object = self.db.execute(
            select(PageObject).where(
                PageObject.project_code == str(case.project_code or "").strip(),
                PageObject.client == str(case.client or "").strip(),
                PageObject.page_code == str(case.page_code or "").strip(),
            )
        ).scalar_one_or_none()
        if page_object is None:
            return {"linked_ref_count": 0, "skipped_ref_count": 0}
        elements = self.db.execute(select(PageElement).where(PageElement.page_object_id == int(page_object.id))).scalars().all()
        element_by_code = {str(item.element_code or "").strip(): item for item in elements if str(item.element_code or "").strip()}
        linked = 0
        skipped = 0
        with WorkbenchGenerationUnitOfWork(self.db):
            for target in self._extract_case_element_targets(case):
                element = element_by_code.get(target)
                if element is None:
                    skipped += 1
                    continue
                existing = self.db.execute(
                    select(PageObjectRef).where(
                        PageObjectRef.page_element_id == int(element.id),
                        PageObjectRef.reference_type == "test_case",
                        PageObjectRef.reference_key == case_business_id,
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    skipped += 1
                    continue
                self.db.add(
                    PageObjectRef(
                        page_element_id=int(element.id),
                        reference_type="test_case",
                        reference_key=case_business_id,
                        source="full-chain",
                        created_by="full-chain",
                    )
                )
                linked += 1
        return {"linked_ref_count": linked, "skipped_ref_count": skipped}
