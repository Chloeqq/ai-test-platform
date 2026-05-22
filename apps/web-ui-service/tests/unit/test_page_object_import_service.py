from __future__ import annotations

from app.services.page_object_import_service import _element_name, parse_data_testid_guidelines


def test_parse_data_testid_guidelines_prefers_chinese_heading_for_page_name() -> None:
    markdown = """# data-testid

## 3. 已落地清单（首批高频核心页面）

### 订单物流弹窗 `src/views/oms/order/components/logisticsDialog.vue`

- 弹窗：`order-logistics-dialog`

### 优惠券领取详情 `src/views/sms/coupon/history.vue`

- 容器：`coupon-history-page`

## 4. 待落地清单
"""

    rows = parse_data_testid_guidelines(markdown)
    by_code = {row.page_code: row for row in rows}

    assert by_code["order-logistics"].page_name == "订单物流弹窗"
    assert by_code["coupon-history"].page_name == "优惠券领取详情"


def test_parse_data_testid_guidelines_handles_level_four_route_shell_headings() -> None:
    markdown = """# data-testid

## 3. 已落地清单（首批高频核心页面）

### 运行态查漏补缺

#### add/update 路由壳页面

- 商品：`product-add-page`、`product-update-page`
- 品牌：`brand-add-page`、`brand-update-page`
- 菜单：`menu-add-page`、`menu-update-page`

## 4. 待落地清单
"""

    rows = parse_data_testid_guidelines(markdown)
    by_code = {row.page_code: row for row in rows}

    assert by_code["product-add"].page_name == "商品新增页"
    assert by_code["product-update"].page_name == "商品编辑页"
    assert by_code["brand-add"].page_name == "品牌新增页"
    assert by_code["brand-update"].page_name == "品牌编辑页"
    assert by_code["menu-add"].page_name == "菜单新增页"
    assert by_code["menu-update"].page_name == "菜单编辑页"


def test_parse_data_testid_guidelines_groups_layout_shell_elements() -> None:
    markdown = """# data-testid

## 3. 已落地清单（首批高频核心页面）

### 登录与布局

- `src/views/normal/login/index.vue`
  - `login-page`、`login-username-input`、`login-submit-btn`
- `src/views/layout/components/Sidebar/SidebarItem.vue`
  - `sidebar-menu-<routeName>`、`sidebar-submenu-<routeName>`、`sidebar-link-<routeName>`
- `src/views/layout/components/Navbar.vue`
  - `breadcrumb-item-<routeName>`、`hamburger-toggle-btn`

## 4. 待落地清单
"""

    rows = parse_data_testid_guidelines(markdown)
    by_code = {row.element_code: row for row in rows}

    assert by_code["login-submit-btn"].page_code == "login"
    assert by_code["login-submit-btn"].page_name == "登录页"
    assert by_code["sidebar-menu-routename"].page_code == "layout"
    assert by_code["sidebar-menu-routename"].page_name == "全局布局"
    assert by_code["breadcrumb-item-routename"].page_code == "layout"
    assert by_code["hamburger-toggle-btn"].page_code == "layout"


def test_import_element_name_prefers_chinese_semantics() -> None:
    markdown = """# data-testid

## 3. 已落地清单（首批高频核心页面）

### 登录与布局

- `src/views/normal/login/index.vue`
  - `login-username-input`、`login-password-input`、`login-submit-btn`
- `src/views/layout/components/Sidebar/SidebarItem.vue`
  - `sidebar-link-<routeName>`、`sidebar-submenu-<routeName>`
- `src/views/pms/product/index.vue`
  - `product-search-keyword-input`

## 4. 待落地清单
"""

    rows = parse_data_testid_guidelines(markdown)
    names = {row.element_code: _element_name(row) for row in rows}

    assert names["login-username-input"] == "用户名输入框"
    assert names["login-password-input"] == "密码输入框"
    assert names["login-submit-btn"] == "登录按钮"
    assert names["sidebar-link-routename"] == "侧边栏外链菜单项"
    assert names["sidebar-submenu-routename"] == "侧边栏父级子菜单"
    assert names["product-search-keyword-input"] == "搜索关键词输入框"
