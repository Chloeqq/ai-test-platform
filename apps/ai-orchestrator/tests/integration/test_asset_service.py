import sys
from pathlib import Path

import pytest


pytestmark = [pytest.mark.integration]


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = PROJECT_ROOT / "apps" / "ai-orchestrator" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from asset_service import AssetService
from orchestrator_service import OrchestratorValidationError


def test_scaffold_page_assets_accepts_element_templates(tmp_path: Path):
    service = AssetService(repo_root=PROJECT_ROOT)
    service.page_objects_root = tmp_path / "assets" / "page-objects" / "web"
    service.test_cases_root = tmp_path / "assets" / "test-cases"

    result = service.scaffold_page_assets(
        page="catalog",
        title="商品目录",
        requirement="商品目录页面展示",
        elements=[
            {
                "name": "catalog_search_input",
                "locator_type": "css",
                "locator_value": "input[name='keyword']",
                "description": "搜索输入框",
            },
            {
                "name": "catalog_search_button",
                "locator_type": "role",
                "role": "button",
                "locator_value": "搜索",
            },
            {
                "name": "catalog_search_entry",
                "locator_type": "role",
                "role": "menuitem",
                "locator_value": "商品目录查询",
                "smoke_role": "menu",
            },
            {
                "name": "catalog_results_panel",
                "locator_type": "css",
                "locator_value": ".catalog-results",
                "smoke_role": "assert",
            },
        ],
    )

    page_object = result["page_object"]
    assert "catalog_menu" in page_object["elements"]
    assert "catalog_title" in page_object["elements"]
    assert page_object["elements"]["catalog_search_input"]["locator_type"] == "css"
    assert page_object["elements"]["catalog_search_button"]["role"] == "button"
    assert result["test_case"]["execution"]["steps"] == [
        {"action": "login"},
        {"action": "click", "target": "catalog_search_entry"},
        {"action": "wait_for", "target": "catalog_results_panel"},
        {"action": "assert_visible", "target": "catalog_results_panel"},
    ]
    assert Path(result["page_object_path"]).exists()
    assert Path(result["test_case_path"]).exists()


def test_scaffold_page_assets_accepts_built_in_template(tmp_path: Path):
    service = AssetService(repo_root=PROJECT_ROOT)
    service.page_objects_root = tmp_path / "assets" / "page-objects" / "web"
    service.test_cases_root = tmp_path / "assets" / "test-cases"

    result = service.scaffold_page_assets(
        page="catalog",
        title="商品目录",
        requirement="商品目录页面展示",
        template="catalog",
    )

    assert result["test_case"]["execution"]["steps"] == [
        {"action": "login"},
        {"action": "click", "target": "catalog_search_entry"},
        {"action": "wait_for", "target": "catalog_results_panel"},
        {"action": "assert_visible", "target": "catalog_results_panel"},
    ]


def test_scaffold_page_assets_rejects_invalid_role_locator_templates(tmp_path: Path):
    service = AssetService(repo_root=PROJECT_ROOT)
    service.page_objects_root = tmp_path / "assets" / "page-objects" / "web"
    service.test_cases_root = tmp_path / "assets" / "test-cases"

    with pytest.raises(OrchestratorValidationError, match="elements\\[\\]\\.role must not be empty"):
        service.scaffold_page_assets(
            page="catalog",
            title="商品目录",
            requirement="商品目录页面展示",
            elements=[
                {
                    "name": "catalog_search_button",
                    "locator_type": "role",
                    "locator_value": "搜索",
                }
            ],
        )


def test_scaffold_page_assets_rejects_duplicate_smoke_roles(tmp_path: Path):
    service = AssetService(repo_root=PROJECT_ROOT)
    service.page_objects_root = tmp_path / "assets" / "page-objects" / "web"
    service.test_cases_root = tmp_path / "assets" / "test-cases"

    with pytest.raises(OrchestratorValidationError, match="smoke_role 'menu' is duplicated"):
        service.scaffold_page_assets(
            page="catalog",
            title="商品目录",
            requirement="商品目录页面展示",
            elements=[
                {
                    "name": "catalog_entry_a",
                    "locator_type": "role",
                    "role": "menuitem",
                    "locator_value": "目录A",
                    "smoke_role": "menu",
                },
                {
                    "name": "catalog_entry_b",
                    "locator_type": "role",
                    "role": "menuitem",
                    "locator_value": "目录B",
                    "smoke_role": "menu",
                },
            ],
        )


def test_list_scaffold_templates_returns_descriptions():
    service = AssetService(repo_root=PROJECT_ROOT)

    result = service.list_scaffold_templates()

    assert result["templates"]
    assert any(template["name"] == "catalog" for template in result["templates"])
    assert all("summary" in template for template in result["templates"])


def test_get_scaffold_template_returns_details():
    service = AssetService(repo_root=PROJECT_ROOT)

    result = service.get_scaffold_template("catalog")

    assert result["template"]["name"] == "catalog"
    assert result["template"]["recommended_title"] == "商品目录"
    assert result["template"]["elements_count"] == 3
