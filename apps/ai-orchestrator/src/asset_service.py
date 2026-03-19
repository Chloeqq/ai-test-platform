import sys
from pathlib import Path
from typing import Any

from orchestrator_service import OrchestratorValidationError


class AssetService:
    def __init__(self, repo_root: Path | None = None):
        self.repo_root = repo_root or Path(__file__).resolve().parents[3]
        self.runner_root = self.repo_root / "runners" / "web-playwright-python"
        self.page_objects_root = self.repo_root / "assets" / "page-objects" / "web"
        self.test_cases_root = self.repo_root / "assets" / "test-cases"

    def create_page_object(self, page: str, description: str = "") -> dict[str, Any]:
        if not page.strip():
            raise OrchestratorValidationError("page must not be empty")

        self._ensure_runner_import_path()
        from runner.asset_toolkit import create_page_object, save_page_object

        page_object = create_page_object(page=page, description=description)
        path = save_page_object(page_object, output_dir=self.page_objects_root)
        return {
            "page_object": page_object,
            "path": str(path),
        }

    def add_page_element(
        self,
        page: str,
        element_name: str,
        locator_type: str,
        locator_value: str,
        role: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        if not page.strip():
            raise OrchestratorValidationError("page must not be empty")
        if not element_name.strip():
            raise OrchestratorValidationError("name must not be empty")
        if not locator_value.strip():
            raise OrchestratorValidationError("locator_value must not be empty")

        self._ensure_runner_import_path()
        from runner.asset_toolkit import add_page_element, load_page_object_for_edit

        path = add_page_element(
            page=page,
            element_name=element_name,
            locator_type=locator_type,
            locator_value=locator_value,
            role=role,
            description=description,
            output_dir=self.page_objects_root,
        )
        page_object = load_page_object_for_edit(page, output_dir=self.page_objects_root)
        return {
            "page_object": page_object,
            "path": str(path),
        }

    def sync_test_case(
        self,
        file_path: str,
        menu_target: str | None = None,
        assert_target: str | None = None,
    ) -> dict[str, Any]:
        if not file_path.strip():
            raise OrchestratorValidationError("file must not be empty")

        target_path = Path(file_path)
        if not target_path.is_absolute():
            target_path = self.repo_root / target_path

        if not str(target_path).startswith(str(self.test_cases_root)):
            raise OrchestratorValidationError("file must be under assets/test-cases")

        self._ensure_runner_import_path()
        from runner.asset_toolkit import load_test_case_for_edit, sync_test_case_steps

        path = sync_test_case_steps(
            test_case_path=target_path,
            menu_target=menu_target,
            assert_target=assert_target,
            page_objects_dir=self.page_objects_root,
        )
        test_case = load_test_case_for_edit(path)
        return {
            "test_case": test_case,
            "path": str(path),
        }

    def scaffold_page_assets(
        self,
        page: str,
        title: str,
        requirement: str,
        description: str = "",
        priority: str = "P1",
        menu_label: str | None = None,
        assert_label: str | None = None,
        template: str | None = None,
        elements: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self._ensure_runner_import_path()
        from runner.asset_toolkit import scaffold_page_assets

        try:
            return scaffold_page_assets(
                page=page,
                title=title,
                requirement=requirement,
                description=description,
                priority=priority,
                menu_label=menu_label,
                assert_label=assert_label,
                template=template,
                elements=elements,
                page_objects_dir=self.page_objects_root,
                test_cases_dir=self.test_cases_root / "smoke",
            )
        except ValueError as exc:
            raise OrchestratorValidationError(str(exc)) from exc

    def list_scaffold_templates(self) -> dict[str, Any]:
        self._ensure_runner_import_path()
        from runner.asset_toolkit import describe_scaffold_template, list_scaffold_templates

        templates = [
            describe_scaffold_template(template_name)
            for template_name in list_scaffold_templates()
        ]
        return {"templates": templates}

    def get_scaffold_template(self, template_name: str) -> dict[str, Any]:
        if not template_name.strip():
            raise OrchestratorValidationError("template must not be empty")

        self._ensure_runner_import_path()
        from runner.asset_toolkit import describe_scaffold_template

        try:
            return {"template": describe_scaffold_template(template_name)}
        except ValueError as exc:
            raise OrchestratorValidationError(str(exc)) from exc

    def _ensure_runner_import_path(self) -> None:
        if str(self.runner_root) not in sys.path:
            sys.path.insert(0, str(self.runner_root))
