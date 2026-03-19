# Page Object 更新日志

## 2026-03-17 更新

### 问题背景
初始测试用例使用了基于 role 的定位器，但 mall-admin-web 实际页面结构与预期不符，导致大量元素找不到。

### 更新内容

#### 1. login.page-object.yaml
**变更**: 根据实际登录页面结构更新
- `username_input`: placeholder="请输入用户名"
- `password_input`: placeholder="请输入密码"
- `login_button`: role="button", name="登录"
- `login_title`: text="mall-admin-web"

**测试结果**: ✅ 登录测试通过

---

#### 2. home.page-object.yaml (新增)
**新增元素**:
- `home_menu`: text="首页"
- `sidebar`: css=".el-menu--vertical"
- `navbar`: css=".navbar"
- `avatar`: css=".user-avatar"
- `logout_menu`: text="退出"

---

#### 3. product.page-object.yaml
**变更**: 从 role 改为 text/css 混合定位
- `product_menu`: css=".el-menu--vertical .el-submenu__title:has-text("商品")"
- `product_list_submenu`: text="商品列表"
- `product_overview`: text="商品总览"
- `product_table`: css=".el-table"

**问题**: 菜单项文本匹配到多个元素（7 个），需要使用更精确的 CSS 选择器

---

#### 4. order.page-object.yaml
**变更**: 使用 text 定位器
- `order_menu`: text="订单"
- `order_list`: text="订单列表"
- `order_table`: css=".el-table"

---

#### 5. permission.page-object.yaml
**变更**: 使用 text 定位器
- `permission_menu`: text="权限"
- `user_list`: text="用户列表"
- `permission_table`: css=".el-table"

---

## 已知问题

### 1. 菜单项定位不精确
**问题**: `get_by_text("商品")` 匹配到 7 个元素
**原因**: 侧边栏有多级菜单，多个菜单项包含相同文本

**解决方案**:
```yaml
# 使用 CSS 选择器精确定位父菜单
product_menu:
  locator_type: css
  locator_value: .el-menu--vertical .el-submenu__title:has-text("商品")

# 或者直接点击子菜单
product_list_submenu:
  locator_type: text
  locator_value: 商品列表
```

### 2. 表格元素超时
**问题**: `.el-table` 等待超时
**原因**: 
- 页面可能需要展开子菜单后才显示表格
- 页面加载需要时间

**解决方案**:
- 先点击子菜单进入具体页面
- 增加等待时间或使用更具体的选择器

---

## 下一步优化

### 1. 使用 Playwright Codegen 录制
```bash
npx playwright codegen http://localhost:5173
```
录制实际操作，生成准确的定位器。

### 2. 添加智能等待
在 `yaml_executor.py` 中添加页面加载等待逻辑。

### 3. 使用测试 ID
在 mall-admin-web 组件中添加 `data-testid` 属性：
```vue
<el-menu-item data-testid="product-menu">商品</el-menu-item>
```

然后在 page-object 中：
```yaml
product_menu:
  locator_type: testid
  locator_value: product-menu
```

---

## 测试状态

| 测试用例 | 状态 | 说明 |
|---------|------|------|
| 管理员登录验证 | ✅ 通过 | 登录功能正常 |
| 商品总览页面加载 | 🟡 调试中 | 菜单定位需优化 |
| 订单列表页面加载 | 🔴 失败 | 菜单定位问题 |
| 权限管理页面加载 | 🔴 失败 | 菜单定位问题 |
| 商品搜索功能验证 | 🔴 失败 | 依赖商品页面 |

---

## 相关文件

- Page Objects: `/assets/page-objects/web/*.page-object.yaml`
- Test Cases: `/assets/test-cases/smoke/*.yaml`
- Executor: `/runners/web-playwright-python/runner/yaml_executor.py`
- Locator Resolver: `/runners/web-playwright-python/runner/locator_resolver.py`
