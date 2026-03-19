from pathlib import Path

import pytest

from runner.asset_toolkit import (
    add_page_element,
    build_test_case,
    create_page_object,
    describe_scaffold_template,
    list_page_elements,
    list_scaffold_templates,
    load_scaffold_template,
    load_scaffold_template_metadata,
    scaffold_page_assets,
    save_page_object,
    save_test_case,
    sync_test_case_steps,
)
from runner.yaml_loader import load_yaml_file


pytestmark = [pytest.mark.contract]


def test_create_and_extend_page_object(tmp_path: Path):
    output_dir = tmp_path / "page-objects"

    page_object = create_page_object("catalog", description="商品目录页")
    save_page_object(page_object, output_dir=output_dir)
    add_page_element(
        page="catalog",
        element_name="catalog_menu",
        locator_type="role",
        locator_value="商品目录",
        role="menuitem",
        output_dir=output_dir,
    )

    saved = load_yaml_file(output_dir / "catalog.page-object.yaml")
    assert saved["page"] == "catalog"
    assert "catalog_menu" in saved["elements"]
    assert list_page_elements("catalog", output_dir=output_dir) == ["catalog_menu"]


def test_build_and_save_smoke_case_from_page_object(tmp_path: Path):
    page_dir = tmp_path / "page-objects"
    case_dir = tmp_path / "cases"

    save_page_object(
        {
            "page": "catalog",
            "elements": {
                "catalog_menu": {
                    "locator_type": "role",
                    "role": "menuitem",
                    "locator_value": "商品目录",
                },
                "catalog_list_title": {
                    "locator_type": "text",
                    "locator_value": "目录列表",
                },
            },
        },
        output_dir=page_dir,
    )

    test_case = build_test_case(
        kind="smoke",
        page="catalog",
        case_id="TC-CATALOG-001",
        title="目录页面加载",
        description="验证目录页面可正常打开",
        requirement="目录页面展示",
        page_objects_dir=page_dir,
    )
    path = save_test_case(test_case, kind="smoke", output_dir=case_dir)

    saved = load_yaml_file(path)
    assert saved["id"] == "TC-CATALOG-001"
    assert saved["execution"]["steps"] == [
        {"action": "login"},
        {"action": "click", "target": "catalog_menu"},
        {"action": "wait_for", "target": "catalog_list_title"},
        {"action": "assert_visible", "target": "catalog_list_title"},
    ]


def test_build_test_case_requires_explicit_targets_when_inference_fails(tmp_path: Path):
    page_dir = tmp_path / "page-objects"
    save_page_object(
        {
            "page": "search",
            "elements": {
                "keyword_input": {
                    "locator_type": "css",
                    "locator_value": "input[name='keyword']",
                }
            },
        },
        output_dir=page_dir,
    )

    with pytest.raises(ValueError, match="Could not infer menu target"):
        build_test_case(
            kind="smoke",
            page="search",
            case_id="TC-SEARCH-001",
            title="搜索页",
            description="验证搜索页",
            requirement="搜索页面展示",
            page_objects_dir=page_dir,
        )


def test_sync_test_case_rewrites_steps_but_preserves_metadata(tmp_path: Path):
    page_dir = tmp_path / "page-objects"
    case_path = tmp_path / "cases" / "TC-CATALOG-001.yaml"

    save_page_object(
        {
            "page": "catalog",
            "elements": {
                "catalog_menu": {
                    "locator_type": "role",
                    "role": "menuitem",
                    "locator_value": "商品目录",
                },
                "catalog_table": {
                    "locator_type": "css",
                    "locator_value": ".catalog-table",
                },
            },
        },
        output_dir=page_dir,
    )

    save_test_case(
        {
            "version": "v4",
            "id": "TC-CATALOG-001",
            "title": "旧目录用例",
            "module": "catalog",
            "priority": "P1",
            "tags": ["smoke", "catalog"],
            "owner": "qa-team",
            "status": "automated",
            "description": "原始描述",
            "requirement": ["原始需求"],
            "data": {},
            "execution": {
                "runner": "playwright",
                "page": "catalog",
                "variables": {},
                "steps": [
                    {"action": "login"},
                    {"action": "click", "target": "old_menu"},
                ],
            },
        },
        kind="smoke",
        output_dir=case_path.parent,
    )

    sync_test_case_steps(
        test_case_path=case_path,
        page_objects_dir=page_dir,
    )

    synced = load_yaml_file(case_path)
    assert synced["title"] == "旧目录用例"
    assert synced["description"] == "原始描述"
    assert synced["execution"]["steps"] == [
        {"action": "login"},
        {"action": "click", "target": "catalog_menu"},
        {"action": "wait_for", "target": "catalog_table"},
        {"action": "assert_visible", "target": "catalog_table"},
    ]


def test_scaffold_page_assets_uses_smoke_role_targets(tmp_path: Path):
    page_dir = tmp_path / "page-objects"
    case_dir = tmp_path / "cases"

    result = scaffold_page_assets(
        page="catalog",
        title="商品目录",
        requirement="商品目录页面展示",
        elements=[
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
        page_objects_dir=page_dir,
        test_cases_dir=case_dir,
    )

    assert result["test_case"]["execution"]["steps"] == [
        {"action": "login"},
        {"action": "click", "target": "catalog_search_entry"},
        {"action": "wait_for", "target": "catalog_results_panel"},
        {"action": "assert_visible", "target": "catalog_results_panel"},
    ]
    assert Path(result["page_object_path"]).exists()
    assert Path(result["test_case_path"]).exists()


def test_scaffold_page_assets_rejects_duplicate_smoke_roles(tmp_path: Path):
    with pytest.raises(ValueError, match="smoke_role 'menu' is duplicated"):
        scaffold_page_assets(
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
            page_objects_dir=tmp_path / "page-objects",
            test_cases_dir=tmp_path / "cases",
        )


def test_list_and_load_scaffold_templates():
    templates = list_scaffold_templates()

    assert "catalog" in templates
    assert "list" in templates
    assert "detail" in templates

    catalog_template = load_scaffold_template("catalog")
    assert catalog_template[0]["smoke_role"] == "menu"
    assert catalog_template[1]["smoke_role"] == "assert"
    metadata = load_scaffold_template_metadata("catalog")
    assert metadata["page_type"] == "catalog"
    assert metadata["recommended_title"] == "商品目录"


def test_describe_scaffold_template_includes_metadata_and_elements():
    details = describe_scaffold_template("detail")

    assert details["name"] == "detail"
    assert details["page_type"] == "detail"
    assert details["elements_count"] == 3
    assert details["elements"][0]["smoke_role"] == "menu"


def test_scaffold_page_assets_can_use_built_in_template(tmp_path: Path):
    result = scaffold_page_assets(
        page="catalog",
        title="商品目录",
        requirement="商品目录页面展示",
        template="catalog",
        page_objects_dir=tmp_path / "page-objects",
        test_cases_dir=tmp_path / "cases",
    )

    assert result["test_case"]["execution"]["steps"] == [
        {"action": "login"},
        {"action": "click", "target": "catalog_search_entry"},
        {"action": "wait_for", "target": "catalog_results_panel"},
        {"action": "assert_visible", "target": "catalog_results_panel"},
    ]
