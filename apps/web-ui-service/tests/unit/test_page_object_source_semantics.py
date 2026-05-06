from __future__ import annotations

import json
from pathlib import Path

from app.services.page_object_source_semantics import build_source_semantic_catalog

MALL_SOURCE_TERMS = {
    "商品货号": "product_sn",
    "商品分类": "product_category",
    "商品品牌": "product_brand",
    "商品列表": "product_list",
    "商品名称": "product_name",
}


def test_source_semantic_catalog_extracts_router_buttons_and_table_columns(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "mall-admin-web"
    source_root.mkdir()
    (source_root / "router.ts").write_text(
        """
        export const routes = [
          {
            path: '/pms',
            meta: { title: '商品', icon: 'product' },
            children: [
              { path: 'product', meta: { title: '商品列表', icon: 'product-list' } }
            ]
          }
        ]
        """,
        encoding="utf-8",
    )
    (source_root / "product.vue").write_text(
        """
        <template>
          <el-button @click="handleSearchList()">查询搜索</el-button>
          <el-button @click="handleResetSearch()">重置</el-button>
          <el-form-item label="输入搜索：">
            <el-input placeholder="商品名称" />
          </el-form-item>
          <el-table-column label="商品货号" prop="productSn" />
        </template>
        <script setup lang="ts">
        const columns = [
          { label: '商品名称', prop: 'name' },
          { label: '上架', value: 1 }
        ]
        </script>
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("PAGE_OBJECT_SOURCE_ROOTS", str(source_root))

    catalog = build_source_semantic_catalog(
        page_code="product",
        route="/pms/product",
        semantic_terms=MALL_SOURCE_TERMS,
    )

    menu_hint = catalog.match(locator_type="role", locator_value="商品列表", role="menuitem")
    assert menu_hint is not None
    assert menu_hint.business_type == "menu"
    assert menu_hint.business_domain == "navigation"

    button_hint = catalog.match(locator_type="role", locator_value="查询搜索", role="button")
    assert button_hint is not None
    assert button_hint.code_seed == "search_button"
    assert button_hint.business_type == "button"

    reset_hint = catalog.match(locator_type="role", locator_value="重置", role="button")
    assert reset_hint is not None
    assert reset_hint.code_seed == "reset_button"

    static_column_hint = catalog.match(locator_type="text", locator_value="商品货号")
    assert static_column_hint is not None
    assert static_column_hint.code_seed == "product_sn_column"
    assert static_column_hint.business_domain == "table"

    dynamic_column_hint = catalog.match(locator_type="text", locator_value="商品名称")
    assert dynamic_column_hint is not None
    assert dynamic_column_hint.code_seed == "name_column"

    placeholder_hint = catalog.match(locator_type="placeholder", locator_value="商品名称")
    assert placeholder_hint is not None
    assert placeholder_hint.code_seed == "product_name_input"
    assert placeholder_hint.name == "商品名称输入框"

    option_hint = catalog.match(locator_type="text", locator_value="上架")
    assert option_hint is None


def test_source_semantic_catalog_extracts_password_toggle_hint(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "mall-admin-web"
    source_root.mkdir()
    (source_root / "login.vue").write_text(
        """
        <template>
          <el-form-item label="密码" prop="password">
            <el-input show-password placeholder="请输入密码" />
          </el-form-item>
        </template>
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("PAGE_OBJECT_SOURCE_ROOTS", str(source_root))

    catalog = build_source_semantic_catalog(page_code="login", route="/login")

    password_hint = catalog.match(locator_type="placeholder", locator_value="请输入密码")
    assert password_hint is not None
    assert password_hint.code_seed == "password_input"
    assert password_hint.business_type == "input"

    toggle_hint = catalog.find_by_business_type("password_toggle")
    assert toggle_hint is not None
    assert toggle_hint.code_seed == "password_toggle"
    assert toggle_hint.name == "密码显隐切换"


def test_source_semantic_catalog_uses_locator_context_for_ambiguous_text(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "mall-admin-web"
    source_root.mkdir()
    (source_root / "product.vue").write_text(
        """
        <template>
          <el-form-item label="商品货号" prop="productSn">
            <el-input placeholder="商品货号" />
          </el-form-item>
          <el-table-column label="商品货号" prop="productSn" />
        </template>
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("PAGE_OBJECT_SOURCE_ROOTS", str(source_root))

    catalog = build_source_semantic_catalog(
        page_code="product",
        route="/pms/product",
        semantic_terms=MALL_SOURCE_TERMS,
    )

    input_hint = catalog.match(locator_type="placeholder", locator_value="商品货号")
    assert input_hint is not None
    assert input_hint.code_seed == "product_sn_input"
    assert input_hint.business_type == "input"

    column_hint = catalog.match(locator_type="text", locator_value="商品货号")
    assert column_hint is not None
    assert column_hint.code_seed == "product_sn_column"
    assert column_hint.business_domain == "table"


def test_source_semantic_catalog_uses_project_specific_roots_without_cross_project_fallback(
    monkeypatch,
    tmp_path: Path,
) -> None:
    mall_root = tmp_path / "mall-admin-web"
    atp_root = tmp_path / "atp-web"
    global_root = tmp_path / "global-web"
    mall_root.mkdir()
    atp_root.mkdir()
    global_root.mkdir()

    (mall_root / "product.vue").write_text(
        """
        <template>
          <el-form-item label="商品名称">
            <el-input placeholder="商品名称" />
          </el-form-item>
        </template>
        """,
        encoding="utf-8",
    )
    (atp_root / "product.vue").write_text(
        """
        <template>
          <el-form-item label="项目名称" prop="projectName">
            <el-input placeholder="项目名称" />
          </el-form-item>
        </template>
        """,
        encoding="utf-8",
    )
    (global_root / "product.vue").write_text(
        """
        <template>
          <el-form-item label="全局名称" prop="globalName">
            <el-input placeholder="全局名称" />
          </el-form-item>
        </template>
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("PAGE_OBJECT_SOURCE_ROOTS", str(global_root))
    monkeypatch.setenv(
        "PAGE_OBJECT_SOURCE_ROOTS_BY_PROJECT",
        json.dumps({"mall": str(mall_root), "atp": [str(atp_root)]}),
    )

    mall_catalog = build_source_semantic_catalog(
        project_code="mall",
        page_code="product",
        route="/pms/product",
        semantic_terms=MALL_SOURCE_TERMS,
    )
    mall_hint = mall_catalog.match(locator_type="placeholder", locator_value="商品名称")
    assert mall_hint is not None
    assert mall_hint.code_seed == "product_name_input"
    assert mall_catalog.match(locator_type="placeholder", locator_value="项目名称") is None

    atp_catalog = build_source_semantic_catalog(project_code="atp", page_code="product", route="/pms/product")
    atp_hint = atp_catalog.match(locator_type="placeholder", locator_value="项目名称")
    assert atp_hint is not None
    assert atp_hint.code_seed == "project_name_input"
    assert atp_catalog.match(locator_type="placeholder", locator_value="商品名称") is None

    fallback_catalog = build_source_semantic_catalog(page_code="product", route="/pms/product")
    fallback_hint = fallback_catalog.match(locator_type="placeholder", locator_value="全局名称")
    assert fallback_hint is not None
    assert fallback_hint.code_seed == "global_name_input"

    unconfigured_project_catalog = build_source_semantic_catalog(
        project_code="crm",
        page_code="product",
        route="/pms/product",
    )
    assert len(unconfigured_project_catalog) == 0


def test_source_semantic_catalog_disables_enhancement_when_project_mapping_is_malformed(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "mall-admin-web"
    source_root.mkdir()
    (source_root / "product.vue").write_text(
        """
        <template>
          <el-form-item label="商品名称">
            <el-input placeholder="商品名称" />
          </el-form-item>
        </template>
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("PAGE_OBJECT_SOURCE_ROOTS", str(source_root))
    monkeypatch.setenv("PAGE_OBJECT_SOURCE_ROOTS_BY_PROJECT", '{"mall":')

    catalog = build_source_semantic_catalog(project_code="mall", page_code="product", route="/pms/product")
    assert len(catalog) == 0


def test_source_semantic_catalog_accepts_explicit_roots_terms_and_cache(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "custom-web"
    source_root.mkdir()
    (source_root / "product.vue").write_text(
        """
        <template>
          <el-form-item label="商家自定义字段">
            <el-input placeholder="商家自定义字段" />
          </el-form-item>
        </template>
        """,
        encoding="utf-8",
    )

    first_catalog = build_source_semantic_catalog(
        project_code="custom",
        page_code="product",
        route="/pms/product",
        source_roots=[str(source_root)],
        semantic_terms={"商家自定义字段": "merchant_custom_field"},
    )
    second_catalog = build_source_semantic_catalog(
        project_code="custom",
        page_code="product",
        route="/pms/product",
        source_roots=[str(source_root)],
        semantic_terms={"商家自定义字段": "merchant_custom_field"},
    )

    hint = first_catalog.match(locator_type="placeholder", locator_value="商家自定义字段")
    assert hint is not None
    assert hint.code_seed == "merchant_custom_field_input"
    assert first_catalog is second_catalog
