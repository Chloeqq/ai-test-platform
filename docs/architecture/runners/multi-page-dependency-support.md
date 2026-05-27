# YAML 执行器多页面与依赖支持设计

> **问题**: 当前 YAML 执行器不支持多页面流转、用例间依赖、API+UI 混合场景
> **创建日期**: 2026-03-21
> **优先级**: P1
> **文档性质**: 目标态增强设计，当前应拆解后分阶段落地

---

## 0.1 当前实施入口

如果当前要推进“多页面 Web Runner”，应优先阅读：

- [multi-page-web-runner-plan.md](./multi-page-web-runner-plan.md)

这份文档保留为更大范围的需求池/蓝图参考，不再作为当前直接实施稿。

---

## 0. 现实边界说明（2026-03-21）

这份文档当前把 4 类能力揉在了一起：

1. Web 多页面流转
2. 用例间依赖
3. API + UI 混合执行
4. 依赖顺序与调度

结合当前仓库实现，这 4 类问题的成熟度并不一致：

- 最接近当前主链现实的是“Web 多页面流转”
- “用例间依赖”更适合编排层，而不是先压到 Runner YAML
- “API + UI 混合执行”目前缺少成熟 API Runner 支撑
- “依赖顺序与调度”本质上属于 execution planner / orchestrator 侧

因此，本文件更适合作为需求池和蓝图参考，而不是当前一次性直接实施的开发稿。

## 1. 当前架构限制分析

### 1.1 当前执行流程

```
TestCase (single page)
    ↓
YamlExecutor (绑定单个 Page Object)
    ↓
Playwright Page (单浏览器上下文)
    ↓
Steps 执行 (仅当前页面的元素)
```

### 1.2 限制根因

| 限制 | 根因 | 影响 |
|------|------|------|
| 单页面绑定 | `executor.__init__` 只接收一个 `page_name` | 无法跨页面 |
| 无状态管理 | 步骤间仅通过 `context` 传递变量 | 用例间无法共享状态 |
| 无依赖解析 | TestCase 之间独立加载 | 无法建立依赖链 |
| Runner 单一 | 一个 TestCase 只能指定一个 `runner` | 无法混合 API+UI |

---

## 2. 多页面流转支持

### 2.1 方案 A: 多 Page 对象注入（推荐）

**YAML Schema 扩展**:

```yaml
version: v5  # 升级版本号

id: TC-CHECKOUT-001
title: 完整购物流程
module: ecommerce

execution:
  runner: playwright
  
  # 新增：支持多个页面
  pages:
    - name: login
      page_object: login
    - name: product
      page_object: product
    - name: product-detail
      page_object: product_detail
    - name: cart
      page_object: cart
    - name: checkout
      page_object: checkout
  
  # 新增：页面流转定义
  flow:
    - from: login
      action: login
      navigate_to: product
      on_success:
        next_page: product
        wait_for: product_menu
    
    - from: product
      action: click
      target: first_product
      navigate_to: product-detail
      on_success:
        next_page: product-detail
        wait_for: add_to_cart_button
    
    - from: product-detail
      action: click
      target: add_to_cart
      stay_on_page: true
      on_success:
        expect: cart_count_updated
    
    - from: product-detail
      action: click
      target: cart_icon
      navigate_to: cart
      on_success:
        next_page: cart
    
    - from: cart
      action: click
      target: checkout_button
      navigate_to: checkout
      on_success:
        next_page: checkout
  
  variables:
    expected_total: "199.00"
  
  steps:
    # 步骤自动根据 flow 执行
```

**执行器改造**:

```python
# runners/web-playwright-python/runner/multi_page_executor.py

from playwright.sync_api import Page
from typing import Dict, List, Optional

class MultiPageExecutor:
    """多页面执行器"""
    
    def __init__(self, page: Page, base_url: str, username: str, password: str):
        self.page = page
        self.base_url = base_url
        self.username = username
        self.password = password
        
        # 新增：页面注册表
        self.page_registry: Dict[str, PageContext] = {}
        self.current_page: Optional[str] = None
        
        # 新增：状态管理
        self.state: Dict[str, any] = {}
        self.outputs: Dict[str, any] = {}
    
    def register_page(self, name: str, page_object: dict):
        """注册页面"""
        self.page_registry[name] = PageContext(
            name=name,
            page_object=page_object,
            elements=page_object.get('elements', {})
        )
    
    def navigate_to(self, page_name: str, wait_for: str = None):
        """切换到指定页面"""
        if page_name not in self.page_registry:
            raise ValueError(f"Page not registered: {page_name}")
        
        page_context = self.page_registry[page_name]
        
        # 验证当前页面是否匹配
        if wait_for:
            element = page_context.elements.get(wait_for)
            if element:
                locator = self._resolve_locator(element)
                locator.wait_for(state='visible', timeout=5000)
        
        self.current_page = page_name
    
    def execute_flow(self, flow: List[dict], context: dict):
        """执行页面流转"""
        for step in flow:
            from_page = step.get('from')
            action = step.get('action')
            target = step.get('target')
            next_page = step.get('navigate_to')
            on_success = step.get('on_success', {})
            
            # 切换到源页面
            if from_page and from_page != self.current_page:
                self.navigate_to(from_page)
            
            # 执行动作
            current_page_context = self.page_registry.get(from_page)
            self._execute_action(action, target, current_page_context, context)
            
            # 处理成功后的行为
            if on_success:
                if on_success.get('next_page'):
                    wait_for = on_success.get('wait_for')
                    self.navigate_to(on_success['next_page'], wait_for)
                
                if on_success.get('expect'):
                    self._verify_expectation(on_success['expect'], context)
    
    def execute_steps(self, steps: List[dict], context: dict):
        """执行步骤（支持跨页面）"""
        for step in steps:
            page_override = step.get('page')  # 允许步骤指定页面
            
            if page_override and page_override != self.current_page:
                self.navigate_to(page_override)
            
            self._execute_step(step, context)
    
    def _execute_action(self, action: str, target: str, page_context: 'PageContext', context: dict):
        """执行单个动作"""
        # 复用现有的 action 执行逻辑
        pass
    
    def _verify_expectation(self, expectation: str, context: dict):
        """验证预期结果"""
        # 例如：验证购物车数量更新
        pass
    
    def set_state(self, key: str, value: any):
        """设置状态"""
        self.state[key] = value
        self.outputs[key] = value
    
    def get_state(self, key: str, default: any = None) -> any:
        """获取状态"""
        return self.state.get(key, default)


class PageContext:
    """页面上下文"""
    def __init__(self, name: str, page_object: dict, elements: dict):
        self.name = name
        self.page_object = page_object
        self.elements = elements
```

---

### 2.2 方案 B: 测试套件编排（备选）

**YAML Schema**:

```yaml
# test-suite.yaml
version: v5

id: SUITE-CHECKOUT-001
title: 购物流程测试套件

# 定义套件内的测试用例
test_cases:
  - case_id: TC-LOGIN-001
    outputs:
      - auth_token
  
  - case_id: tc-product-001
    depends_on: TC-LOGIN-001
    inputs:
      auth_token: "{{ TC-LOGIN-001.outputs.auth_token }}"
    outputs:
      - selected_product_id
  
  - case_id: TC-CART-001
    depends_on: tc-product-001
    inputs:
      product_id: "{{ tc-product-001.outputs.selected_product_id }}"
  
  - case_id: TC-CHECKOUT-001
    depends_on: TC-CART-001

# 执行策略
execution_strategy:
  mode: sequential  # sequential/parallel
  stop_on_failure: true
  cleanup_on_exit: true
```

---

## 3. 用例间依赖支持

### 3.1 依赖定义 Schema

```yaml
# TC-001: 创建用户
version: v5
id: TC-USER-CREATE-001
title: 创建测试用户

execution:
  runner: playwright
  page: user-management
  steps:
    - action: click
      target: create_user_button
    - action: fill
      target: username_input
      value: "test_user_{{ timestamp }}"
    - action: click
      target: submit_button
    - action: assert_visible
      target: success_message

# 新增：输出定义
outputs:
  user_id:
    source: response  # 从响应中提取
    extractor: "css:.user-card[data-id]"
    attribute: "data-id"
  
  username:
    source: step
    step_index: 2
    extractor: "input_value"

---

# TC-002: 创建订单（依赖 TC-001）
version: v5
id: TC-ORDER-CREATE-001
title: 为用户创建订单

# 新增：依赖定义
depends_on:
  - case_id: TC-USER-CREATE-001
    required: true  # 必须成功
    outputs:
      - user_id
      - username

execution:
  runner: playwright
  page: order-management
  
  # 新增：输入映射
  inputs:
    target_user_id: "{{ TC-USER-CREATE-001.outputs.user_id }}"
    target_username: "{{ TC-USER-CREATE-001.outputs.username }}"
  
  steps:
    - action: click
      target: create_order_button
    - action: fill
      target: user_id_input
      value: "{{ target_user_id }}"
    - action: fill
      target: username_display
      value: "{{ target_username }}"
```

### 3.2 依赖解析器实现

```python
# runners/web-playwright-python/runner/dependency_resolver.py

from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class TestCaseOutput:
    """测试用例输出"""
    case_id: str
    outputs: Dict[str, Any]
    status: str  # passed/failed/skipped

class DependencyResolver:
    """依赖解析器"""
    
    def __init__(self):
        self.outputs: Dict[str, TestCaseOutput] = {}
        self.execution_order: List[str] = []
    
    def register_test_case(self, test_case: dict):
        """注册测试用例"""
        case_id = test_case.get('id')
        depends_on = test_case.get('depends_on', [])
        
        # 构建依赖图
        for dep in depends_on:
            dep_case_id = dep.get('case_id')
            # 验证依赖是否存在
            if dep_case_id not in self.outputs:
                raise ValueError(f"Dependency not found: {dep_case_id}")
        
        # 添加到执行顺序（拓扑排序）
        self._add_to_execution_order(case_id, depends_on)
    
    def get_execution_order(self) -> List[str]:
        """获取执行顺序"""
        return self.execution_order
    
    def store_output(self, case_id: str, outputs: Dict[str, Any], status: str):
        """存储用例输出"""
        self.outputs[case_id] = TestCaseOutput(
            case_id=case_id,
            outputs=outputs,
            status=status
        )
    
    def resolve_inputs(self, test_case: dict) -> Dict[str, Any]:
        """解析输入变量"""
        inputs = test_case.get('inputs', {})
        resolved = {}
        
        for key, value in inputs.items():
            if isinstance(value, str) and value.startswith('{{'):
                # 解析引用：{{ TC-XXX.outputs.xxx }}
                resolved[key] = self._resolve_reference(value)
            else:
                resolved[key] = value
        
        return resolved
    
    def _resolve_reference(self, ref: str) -> Any:
        """解析引用"""
        # {{ TC-USER-CREATE-001.outputs.user_id }}
        ref = ref.strip('{} ').strip()
        parts = ref.split('.')
        
        if len(parts) >= 3 and parts[1] == 'outputs':
            case_id = parts[0]
            output_key = parts[2]
            
            if case_id not in self.outputs:
                raise ValueError(f"Reference to unknown case: {case_id}")
            
            case_output = self.outputs[case_id]
            if case_output.status != 'passed':
                raise ValueError(f"Dependency case failed: {case_id}")
            
            return case_output.outputs.get(output_key)
        
        raise ValueError(f"Invalid reference format: {ref}")
    
    def _add_to_execution_order(self, case_id: str, depends_on: List[dict]):
        """添加到执行顺序（拓扑排序）"""
        # 简化实现：先添加依赖，再添加自己
        for dep in depends_on:
            dep_case_id = dep.get('case_id')
            if dep_case_id not in self.execution_order:
                # 递归添加依赖
                pass  # TODO: 实现递归
        
        if case_id not in self.execution_order:
            self.execution_order.append(case_id)
```

---

## 4. API + UI 混合执行支持

### 4.1 多 Runner 支持 Schema

```yaml
version: v5

id: TC-MIXED-001
title: API 准备 + UI 验证 + API 清理

execution:
  # 新增：分阶段执行
  phases:
    - name: setup
      runner: api
      base_url: http://api.example.com
      steps:
        - action: post
          url: /api/users
          body:
            username: "test_user"
            email: "test@example.com"
          outputs:
            user_id: "$.data.id"
            username: "$.data.username"
        
        - action: post
          url: /api/products
          body:
            name: "Test Product"
            price: 99.99
          outputs:
            product_id: "$.data.id"
    
    - name: verify_ui
      runner: playwright
      page: dashboard
      variables:
        expected_user: "{{ setup.outputs.username }}"
      steps:
        - action: login
        - action: navigate
          url: /dashboard
        - action: assert_visible
          target: welcome_message
          expected_text: "Welcome, {{ expected_user }}"
        - action: assert_visible
          target: product_list
        - action: assert_text
          target: product_1_name
          expected: "Test Product"
    
    - name: validate_db
      runner: api
      base_url: http://api.example.com
      steps:
        - action: get
          url: /api/users/{{ setup.outputs.user_id }}
          assertions:
            - type: json_path
              path: "$.data.status"
              expected: "active"
    
    - name: cleanup
      runner: api
      base_url: http://api.example.com
      steps:
        - action: delete
          url: /api/users/{{ setup.outputs.user_id }}
        - action: delete
          url: /api/products/{{ setup.outputs.product_id }}

# 跨阶段输出共享
outputs:
  user_id: "{{ setup.outputs.user_id }}"
  product_id: "{{ setup.outputs.product_id }}"
```

### 4.2 多 Runner 执行器

```python
# runners/web-playwright-python/runner/multi_runner_executor.py

from typing import Dict, List, Any
from playwright.sync_api import Page

class MultiRunnerExecutor:
    """多 Runner 执行器"""
    
    def __init__(self, page: Page, config: dict):
        self.page = page
        self.config = config
        self.phase_outputs: Dict[str, Dict[str, Any]] = {}
        self.global_outputs: Dict[str, Any] = {}
    
    def execute_phases(self, phases: List[dict], global_context: dict):
        """执行多个阶段"""
        for phase in phases:
            phase_name = phase.get('name', 'unnamed')
            runner_type = phase.get('runner')
            
            # 解析阶段输入（引用之前阶段的输出）
            phase_context = self._resolve_phase_inputs(phase, global_context)
            
            # 根据 runner 类型选择执行器
            if runner_type == 'playwright':
                phase_output = self._execute_playwright_phase(phase, phase_context)
            elif runner_type == 'api':
                phase_output = self._execute_api_phase(phase, phase_context)
            else:
                raise ValueError(f"Unsupported runner: {runner_type}")
            
            # 存储阶段输出
            self.phase_outputs[phase_name] = phase_output
            
            # 检查是否继续
            if phase.get('stop_on_failure', True) and phase_output.get('status') == 'failed':
                break
        
        # 生成最终输出
        return self._generate_final_outputs(global_context)
    
    def _resolve_phase_inputs(self, phase: dict, global_context: dict) -> dict:
        """解析阶段输入"""
        context = dict(global_context)
        
        # 合并之前阶段的输出
        for phase_name, outputs in self.phase_outputs.items():
            context[phase_name] = {'outputs': outputs}
        
        # 解析 variables 中的引用
        variables = phase.get('variables', {})
        for key, value in variables.items():
            if isinstance(value, str) and value.startswith('{{'):
                context[key] = self._resolve_reference(value, context)
            else:
                context[key] = value
        
        return context
    
    def _execute_playwright_phase(self, phase: dict, context: dict) -> dict:
        """执行 Playwright 阶段"""
        from .yaml_executor import YamlExecutor
        
        executor = YamlExecutor(
            page=self.page,
            username=context.get('username', ''),
            password=context.get('password', ''),
            base_url=context.get('base_url', '')
        )
        
        # 执行步骤
        steps = phase.get('steps', [])
        for step in steps:
            # 复用现有执行逻辑
            pass
        
        return {'status': 'passed', 'outputs': {}}
    
    def _execute_api_phase(self, phase: dict, context: dict) -> dict:
        """执行 API 阶段"""
        import requests
        
        base_url = phase.get('base_url', '')
        steps = phase.get('steps', [])
        outputs = {}
        
        for step in steps:
            action = step.get('action')
            url = base_url + step.get('url', '')
            
            if action == 'get':
                response = requests.get(url)
            elif action == 'post':
                body = step.get('body', {})
                resolved_body = self._resolve_body(body, context)
                response = requests.post(url, json=resolved_body)
            elif action == 'delete':
                response = requests.delete(url)
            else:
                continue
            
            # 提取输出
            step_outputs = step.get('outputs', {})
            for output_key, extractor in step_outputs.items():
                outputs[output_key] = self._extract_from_response(response, extractor)
            
            # 验证断言
            assertions = step.get('assertions', [])
            for assertion in assertions:
                self._verify_assertion(response, assertion, context)
        
        return {'status': 'passed', 'outputs': outputs}
    
    def _resolve_reference(self, ref: str, context: dict) -> Any:
        """解析引用"""
        ref = ref.strip('{} ').strip()
        parts = ref.split('.')
        
        value = context
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                raise ValueError(f"Cannot resolve: {ref}")
        
        return value
    
    def _extract_from_response(self, response: requests.Response, extractor: str) -> Any:
        """从响应提取数据"""
        if extractor.startswith('$.'):
            # JSONPath 提取
            import jsonpath_ng
            jsonpath = jsonpath_ng.parse(extractor)
            data = response.json()
            matches = jsonpath.find(data)
            return matches[0].value if matches else None
        return None
    
    def _generate_final_outputs(self, global_context: dict) -> dict:
        """生成最终输出"""
        final_outputs = {}
        
        # 解析 outputs 定义
        outputs_def = self.config.get('outputs', {})
        for key, extractor in outputs_def.items():
            if isinstance(extractor, str) and extractor.startswith('{{'):
                final_outputs[key] = self._resolve_reference(extractor, {
                    **global_context,
                    **self.phase_outputs
                })
            else:
                final_outputs[key] = extractor
        
        return final_outputs
```

---

## 5. 实施计划

### Phase 1: 多页面支持（Week 1-2）

| 任务 | 预计 | 状态 |
|------|------|------|
| YAML Schema v5 设计 | 1 天 | ⏳ |
| MultiPageExecutor 实现 | 3 天 | ⏳ |
| Page 注册和导航 | 2 天 | ⏳ |
| Flow 执行引擎 | 3 天 | ⏳ |
| 向后兼容 v4 | 1 天 | ⏳ |

### Phase 2: 依赖支持（Week 3-4）

| 任务 | 预计 | 状态 |
|------|------|------|
| DependencyResolver 实现 | 3 天 | ⏳ |
| 输出提取器 | 2 天 | ⏳ |
| 输入引用解析 | 2 天 | ⏳ |
| 拓扑排序执行 | 2 天 | ⏳ |
| 循环依赖检测 | 1 天 | ⏳ |

### Phase 3: 多 Runner 支持（Week 5-6）

| 任务 | 预计 | 状态 |
|------|------|------|
| API Runner 实现 | 3 天 | ⏳ |
| Phase 执行引擎 | 3 天 | ⏳ |
| 跨阶段变量传递 | 2 天 | ⏳ |
| 清理机制 | 2 天 | ⏳ |

---

## 6. 向后兼容

### v4 → v5 迁移指南

```yaml
# v4 (当前)
execution:
  page: login
  steps:
    - action: login

# v5 (多页面)
execution:
  pages:
    - name: login
      page_object: login
  flow:
    - from: login
      action: login

# v5 仍然支持 v4 简写
execution:
  page: login  # ✅ 兼容，自动转换为单页面 flow
  steps:
    - action: login
```

---

## 7. 示例用例

### 完整购物流程

```yaml
version: v5
id: TC-CHECKOUT-FULL-001
title: 完整购物流程测试

execution:
  runner: playwright
  
  pages:
    - name: login
      page_object: login
    - name: product
      page_object: product
    - name: cart
      page_object: cart
    - name: checkout
      page_object: checkout
  
  flow:
    - from: login
      action: login
      navigate_to: product
    
    - from: product
      action: click
      target: first_product
      navigate_to: product-detail
    
    - from: product-detail
      action: click
      target: add_to_cart
      on_success:
        expect: cart_count_updated
    
    - from: product-detail
      action: click
      target: cart_icon
      navigate_to: cart
    
    - from: cart
      action: click
      target: checkout_button
      navigate_to: checkout
    
    - from: checkout
      action: fill
      target: address_input
      value: "测试地址"
    
    - action: click
      target: submit_order_button
    
    - action: assert_visible
      target: order_success_message
  
  outputs:
    order_id:
      source: response
      extractor: "css:.order-id"
```

---

*文档版本：1.0*
*创建日期：2026-03-21*
*维护团队：AI Test Platform Core Team*
