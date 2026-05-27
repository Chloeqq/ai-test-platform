from pathlib import Path

import pytest
import yaml

from runner.yaml_executor import YamlExecutor


pytestmark = [pytest.mark.contract]


class DummyPage:
    pass


def _write_page_object(root: Path, page_name: str, elements: dict) -> None:
    path = root / f"{page_name}.page-object.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "page": page_name,
                "elements": elements,
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )


def test_yaml_executor_supports_step_page_override_and_page_object_cache(tmp_path, monkeypatch):
    page_objects_root = tmp_path / "page-objects"
    _write_page_object(
        page_objects_root,
        "product",
        {
            "product_menu": {
                "locator_type": "text",
                "locator_value": "商品列表",
            }
        },
    )
    _write_page_object(
        page_objects_root,
        "product/detail",
        {
            "detail_title": {
                "locator_type": "text",
                "locator_value": "商品详情",
            }
        },
    )

    executed_steps = []
    loaded_paths = []

    def fake_load_yaml_file(path: Path):
        loaded_paths.append(path)
        with open(path, "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)

    def fake_resolve_locator(_page, element):
        return {"locator_value": element["locator_value"]}

    def fake_handler(**kwargs):
        executed_steps.append(
            {
                "step": kwargs["step"],
                "locator": kwargs["locator"],
                "context": kwargs["context"],
            }
        )

    monkeypatch.setattr("runner.yaml_executor.PAGE_OBJECTS_ROOT", page_objects_root)
    monkeypatch.setattr("runner.yaml_executor.load_yaml_file", fake_load_yaml_file)
    monkeypatch.setattr("runner.yaml_executor.resolve_locator", fake_resolve_locator)
    monkeypatch.setitem(
        __import__("runner.yaml_executor", fromlist=["ACTION_DEFINITIONS"]).ACTION_DEFINITIONS,
        "click",
        {"handler": fake_handler, "requires_target": True},
    )
    monkeypatch.setitem(
        __import__("runner.yaml_executor", fromlist=["ACTION_DEFINITIONS"]).ACTION_DEFINITIONS,
        "assert_visible",
        {"handler": fake_handler, "requires_target": True},
    )

    executor = YamlExecutor(page=DummyPage(), username="u", password="p", base_url="http://localhost")
    executor.execute(
        {
            "id": "TC-MULTI-PAGE-001",
            "execution": {
                "runner": "playwright",
                "page": "product",
                "variables": {"detail_name": "{{item.name}}"},
                "steps": [
                    {"action": "click", "target": "product_menu"},
                    {"action": "assert_visible", "page": "product/detail", "target": "detail_title"},
                    {"action": "assert_visible", "page": "product/detail", "target": "detail_title"},
                ],
            },
            "_data": {"item": {"name": "测试商品"}},
        }
    )

    assert [item["step"]["target"] for item in executed_steps] == [
        "product_menu",
        "detail_title",
        "detail_title",
    ]
    assert executed_steps[0]["locator"]["locator_value"] == "商品列表"
    assert executed_steps[1]["locator"]["locator_value"] == "商品详情"
    assert executed_steps[0]["context"]["detail_name"] == "测试商品"
    assert loaded_paths.count(page_objects_root / "product.page-object.yaml") == 1
    assert loaded_paths.count(page_objects_root / "product/detail.page-object.yaml") == 1


def test_yaml_executor_reports_step_and_page_for_missing_target(tmp_path, monkeypatch):
    page_objects_root = tmp_path / "page-objects"
    _write_page_object(
        page_objects_root,
        "product",
        {
            "product_menu": {
                "locator_type": "text",
                "locator_value": "商品列表",
            }
        },
    )
    _write_page_object(
        page_objects_root,
        "product/detail",
        {
            "detail_title": {
                "locator_type": "text",
                "locator_value": "商品详情",
            }
        },
    )

    monkeypatch.setattr("runner.yaml_executor.PAGE_OBJECTS_ROOT", page_objects_root)
    monkeypatch.setattr("runner.yaml_executor.resolve_locator", lambda _page, element: element)

    executor = YamlExecutor(page=DummyPage(), username="u", password="p", base_url="http://localhost")

    with pytest.raises(ValueError, match="Step 1 references missing target 'missing_button' on page 'product/detail'"):
        executor.execute(
            {
                "id": "TC-MULTI-PAGE-ERR-001",
                "execution": {
                    "runner": "playwright",
                    "page": "product",
                    "variables": {},
                    "steps": [
                        {"action": "click", "page": "product/detail", "target": "missing_button"},
                    ],
                },
            }
        )
