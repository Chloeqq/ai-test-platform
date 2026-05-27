# Script Generation Agent 详细设计

> **状态**: ⏳ L3 → L4 提升中
> **优先级**: P2
> **目标成熟度**: L4（企业级）
> **预计完成**: 2026-05-09（3 周）
> **当前准确率**: ~85%
> **目标准确率**: > 90%

---

## 1. Agent 概述

### 1.1 职责定义

Script Generation Agent 负责将测试点转换为可执行的测试脚本，支持多种测试框架（Playwright/API/Appium），并保证代码质量和可维护性。

**核心职责**:
- 从测试点生成可执行脚本
- 支持多种测试框架（Playwright/API/Appium）
- 遵循编码规范和最佳实践
- 集成静态检查（lint/type）
- 代码质量评分
- 组件复用推荐

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **可执行优先** | 生成的代码必须可执行，通过语法检查 |
| **规范遵循** | 严格遵循团队编码规范 |
| **组件复用** | 优先使用现有页面对象和可复用组件 |
| **可维护性** | 代码清晰、可读、易修改 |
| **质量可度量** | 输出代码质量评分和改進建议 |

### 1.3 在平台中的位置

```
Test Design → [Script Generation] → Execution
     ↓              ↓                   ↓
  测试点计划      可执行脚本        执行结果
                     ↓
               质量评分
```

### 1.4 当前实现状态与卡点

当前仓库里的 `agents/script-generation-agent/src/agent.py` 已经可运行，但它更接近“稳定的 Playwright Python 模板生成器”，而不是完整的多框架脚本平台。

当前实际能力：

- 只支持 Playwright Python
- 直接把 case / steps 渲染成可执行脚本
- 脚本结构确定，便于回归场景落地

当前卡点：

1. 还没有真正覆盖 API / Appium 等框架。
2. 代码质量评分、复用推荐、静态检查目前是轻量化能力。
3. 生成脚本仍然强依赖上游 case / page object 质量。

下一步优先级建议：

1. 先把 Playwright Python 的稳定性和可维护性继续做实。
2. 再扩展第二框架，不要一开始就全框架铺开。
3. 把脚本生成和执行门禁、证据回流串成闭环。

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                   Script Generation Agent                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Test       │  │   Template   │  │   Code       │          │
│  │   Point      │→ │   Selector   │→ │   Generator  │          │
│  │   Analyzer   │  │              │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         ↑                ↑                   ↓                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Quality    │  │  Component   │  │   Static     │          │
│  │   Scorer     │← │   Reuse      │← │   Checker    │          │
│  │              │  │   Recommender│  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         ↓                                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Framework-Specific Generators                │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐  │  │
│  │  │ Playwright │  │    API     │  │      Appium        │  │  │
│  │  │ Generator  │  │  Generator │  │     Generator      │  │  │
│  │  └────────────┘  └────────────┘  └────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────┐
                    │  Generated      │
                    │  Script +       │
                    │  Quality Report │
                    └─────────────────┘
```

### 2.2 模块划分

说明：以下模块划分用于表达目标模块边界，不代表当前仓库已全部存在；真实实现请以 `1.4 当前实现状态与卡点` 和实际目录为准。

当前仓库实际存在的核心入口：

- `agents/script-generation-agent/src/agent.py`
- `agents/script-generation-agent/src/index.py`
- `agents/script-generation-agent/src/schema.py`
- `agents/script-generation-agent/src/templates/`
- `agents/script-generation-agent/src/tools/`
- `agents/script-generation-agent/src/utils/`

| 模块 | 文件路径 | 职责 |
|------|---------|------|
| `agent.py` | `agents/script-generation-agent/src/agent.py` | Agent 主入口 |
| `test_point_analyzer.py` | `agents/script-generation-agent/src/test_point_analyzer.py` | 测试点分析 |
| `template_selector.py` | `agents/script-generation-agent/src/template_selector.py` | 模板选择 |
| `code_generator.py` | `agents/script-generation-agent/src/code_generator.py` | 代码生成核心 |
| `generators/` | `agents/script-generation-agent/src/generators/` | 框架特定生成器 |
| `component_recommender.py` | `agents/script-generation-agent/src/component_recommender.py` | 组件推荐 |
| `static_checker.py` | `agents/script-generation-agent/src/static_checker.py` | 静态检查 |
| `quality_scorer.py` | `agents/script-generation-agent/src/quality_scorer.py` | 质量评分 |

---

## 3. 输入输出契约

### 3.1 输入 Schema

```python
# agents/script-generation-agent/src/schema.py

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime

class TestFramework(str, Enum):
    PLAYWRIGHT_PYTHON = "playwright_python"
    PLAYWRIGHT_TS = "playwright_typescript"
    API_PYTEST = "api_pytest"
    APPIUM_PYTHON = "appium_python"

class CodingStandard(str, Enum):
    PEP8 = "pep8"
    GOOGLE = "google"
    CUSTOM = "custom"

class TestPointRef(BaseModel):
    """测试点引用"""
    test_point_id: str
    title: str
    test_steps: List[str]
    expected_results: List[str]
    priority: str

class PageObjectRef(BaseModel):
    """页面对象引用"""
    page_object_id: str
    name: str
    locators: Dict[str, str]
    methods: List[str]

class ScriptGenerationInput(BaseModel):
    """Agent 输入"""
    request_id: str
    test_points: List[TestPointRef]
    page_objects: Optional[List[PageObjectRef]] = None
    target_framework: TestFramework = TestFramework.PLAYWRIGHT_PYTHON
    coding_standard: CodingStandard = CodingStandard.PEP8
    reusable_components: Optional[List[Dict]] = None  # 可复用组件库
    output_dir: Optional[str] = None
    generate_tests: bool = True
    generate_fixtures: bool = True
    
    class Config:
        schema_extra = {
            "example": {
                "request_id": "script-gen-001",
                "test_points": [
                    {
                        "test_point_id": "tp-001",
                        "title": "用户登录",
                        "test_steps": ["打开登录页", "输入用户名", "输入密码", "点击登录"],
                        "priority": "P0"
                    }
                ],
                "target_framework": "playwright_python"
            }
        }

class CodeQualityIssue(BaseModel):
    """代码质量问题"""
    issue_id: str
    type: str  # error/warning/info
    rule: str
    message: str
    line: int
    column: int
    suggestion: Optional[str] = None

class GeneratedScript(BaseModel):
    """生成的脚本"""
    script_id: str
    test_point_id: str
    file_path: str
    content: str
    language: str
    framework: str
    line_count: int
    character_count: int

class QualityReport(BaseModel):
    """质量报告"""
    overall_score: float  # 0-100
    readability_score: float
    maintainability_score: float
    testability_score: float
    performance_score: float
    issues: List[CodeQualityIssue]
    suggestions: List[str]
    component_reuse_rate: float

class ScriptGenerationOutput(BaseModel):
    """Agent 输出"""
    request_id: str
    generated_scripts: List[GeneratedScript]
    quality_report: QualityReport
    validation_results: Dict[str, Any] = {
        "syntax_check": True,
        "type_check": True,
        "lint_check": True,
        "dry_run": False
    }
    generation_confidence: float
    warnings: List[str] = []
    processing_time_ms: int
    agent_version: str
    model_used: str
    timestamp: datetime
    
    class Config:
        schema_extra = {
            "example": {
                "request_id": "script-gen-001",
                "generated_scripts": [
                    {
                        "script_id": "script-001",
                        "file_path": "tests/test_login.py",
                        "content": "def test_login():...",
                        "line_count": 25
                    }
                ],
                "quality_report": {
                    "overall_score": 85.0,
                    "component_reuse_rate": 0.6
                },
                "generation_confidence": 0.9
            }
        }
```

---

## 4. 核心功能实现

说明：本章代码块主要用于表达目标实现方式和模块边界，不代表这些模块文件已在当前仓库落地；当前真实实现仍以 `src/agent.py`、`src/schema.py`、模板和工具目录为主。

### 4.1 测试点分析器

```python
# agents/script-generation-agent/src/test_point_analyzer.py

from typing import List, Dict, Any

class TestPointAnalyzer:
    """测试点分析器"""
    
    def analyze(self, test_points: List[Dict]) -> List[Dict]:
        """分析测试点，提取脚本生成所需信息"""
        analyzed = []
        
        for tp in test_points:
            analyzed.append({
                'test_point_id': tp['test_point_id'],
                'title': tp['title'],
                'complexity': self._calculate_complexity(tp),
                'action_types': self._identify_actions(tp),
                'assertion_points': self._identify_assertions(tp),
                'page_objects_needed': self._identify_page_objects(tp),
                'data_requirements': self._identify_data_requirements(tp),
                'priority': tp.get('priority', 'P1')
            })
        
        return analyzed
    
    def _calculate_complexity(self, tp: Dict) -> float:
        """计算测试点复杂度"""
        step_count = len(tp.get('test_steps', []))
        assertion_count = len(tp.get('expected_results', []))
        
        # 复杂度公式
        complexity = step_count * 0.3 + assertion_count * 0.4
        
        # 特殊动作增加复杂度
        special_actions = ['upload', 'download', 'iframe', 'popup', 'drag']
        for step in tp.get('test_steps', []):
            if any(action in step.lower() for action in special_actions):
                complexity += 0.5
        
        return min(10.0, complexity)
    
    def _identify_actions(self, tp: Dict) -> List[Dict]:
        """识别测试动作"""
        actions = []
        action_map = {
            '打开': 'navigate',
            '点击': 'click',
            '输入': 'fill',
            '选择': 'select',
            '上传': 'upload',
            '等待': 'wait',
            '断言': 'assert',
            '验证': 'assert'
        }
        
        for step in tp.get('test_steps', []):
            for keyword, action_type in action_map.items():
                if keyword in step:
                    actions.append({
                        'step': step,
                        'action_type': action_type,
                        'target': self._extract_target(step)
                    })
                    break
        
        return actions
    
    def _identify_assertions(self, tp: Dict) -> List[Dict]:
        """识别断言点"""
        assertions = []
        
        for result in tp.get('expected_results', []):
            assertion_type = self._classify_assertion(result)
            assertions.append({
                'description': result,
                'type': assertion_type
            })
        
        return assertions
    
    def _classify_assertion(self, result: str) -> str:
        """分类断言类型"""
        if '可见' in result or '显示' in result:
            return 'visibility'
        elif '包含' in result or '等于' in result:
            return 'text'
        elif 'URL' in result or '地址' in result:
            return 'url'
        elif '数量' in result or '个数' in result:
            return 'count'
        else:
            return 'custom'
    
    def _extract_target(self, step: str) -> str:
        """提取动作目标"""
        # 简单实现，实际应该用 NLP
        keywords = ['按钮', '输入框', '链接', '菜单', '页面']
        for kw in keywords:
            if kw in step:
                return kw
        return 'unknown'
    
    def _identify_page_objects(self, tp: Dict) -> List[str]:
        """识别需要的页面对象"""
        # 从测试步骤中提取页面名称
        pages = set()
        for step in tp.get('test_steps', []):
            if '登录' in step:
                pages.add('LoginPage')
            elif '首页' in step or '主页' in step:
                pages.add('HomePage')
        return list(pages)
    
    def _identify_data_requirements(self, tp: Dict) -> List[Dict]:
        """识别数据需求"""
        data_reqs = []
        
        for step in tp.get('test_steps', []):
            if '用户名' in step or '账号' in step:
                data_reqs.append({'type': 'username', 'required': True})
            if '密码' in step:
                data_reqs.append({'type': 'password', 'required': True})
            if '邮箱' in step or 'email' in step:
                data_reqs.append({'type': 'email', 'required': True})
        
        return data_reqs
```

### 4.2 模板选择器

```python
# agents/script-generation-agent/src/template_selector.py

from typing import List, Dict, Any, Optional

class TemplateSelector:
    """模板选择器"""
    
    def __init__(self):
        self.templates = self._load_templates()
    
    def select(self, analyzed_tp: Dict, framework: str) -> Optional[Dict]:
        """为测试点选择最合适的模板"""
        action_types = analyzed_tp.get('action_types', [])
        assertion_types = analyzed_tp.get('assertion_points', [])
        
        # 计算每个模板的匹配度
        best_match = None
        best_score = 0
        
        for template in self.templates:
            if template['framework'] != framework:
                continue
            
            score = self._calculate_match_score(template, action_types, assertion_types)
            if score > best_score:
                best_score = score
                best_match = template
        
        return best_match
    
    def _load_templates(self) -> List[Dict]:
        """加载模板库"""
        return [
            {
                'id': 'tpl-login-001',
                'name': '登录测试模板',
                'framework': 'playwright_python',
                'action_patterns': ['navigate', 'fill', 'click'],
                'assertion_patterns': ['visibility', 'url'],
                'template_path': 'templates/login_test.py.j2',
                'variables': ['username', 'password', 'expected_url']
            },
            {
                'id': 'tpl-search-001',
                'name': '搜索测试模板',
                'framework': 'playwright_python',
                'action_patterns': ['navigate', 'fill', 'click', 'wait'],
                'assertion_patterns': ['text', 'count'],
                'template_path': 'templates/search_test.py.j2',
                'variables': ['search_query', 'expected_results']
            },
            {
                'id': 'tpl-api-001',
                'name': 'API 测试模板',
                'framework': 'api_pytest',
                'action_patterns': ['request'],
                'assertion_patterns': ['status', 'response'],
                'template_path': 'templates/api_test.py.j2',
                'variables': ['endpoint', 'method', 'payload', 'expected_status']
            }
        ]
    
    def _calculate_match_score(self, template: Dict, 
                               action_types: List[Dict],
                               assertion_types: List[Dict]) -> float:
        """计算模板匹配分数"""
        score = 0.0
        
        template_actions = set(template.get('action_patterns', []))
        template_assertions = set(template.get('assertion_patterns', []))
        
        actual_actions = set(a['action_type'] for a in action_types)
        actual_assertions = set(a['type'] for a in assertion_types)
        
        # 动作匹配度 (50%)
        if template_actions:
            action_overlap = len(template_actions & actual_actions)
            action_score = action_overlap / len(template_actions)
            score += action_score * 0.5
        
        # 断言匹配度 (50%)
        if template_assertions:
            assertion_overlap = len(template_assertions & actual_assertions)
            assertion_score = assertion_overlap / len(template_assertions)
            score += assertion_score * 0.5
        
        return score
```

### 4.3 代码生成器

```python
# agents/script-generation-agent/src/code_generator.py

from typing import List, Dict, Any
from jinja2 import Environment, FileSystemLoader

class CodeGenerator:
    """代码生成器"""
    
    def __init__(self, template_dir: str = 'templates'):
        self.env = Environment(loader=FileSystemLoader(template_dir))
    
    def generate(self, template: Dict, context: Dict) -> str:
        """基于模板生成代码"""
        template_path = template.get('template_path')
        if not template_path:
            return self._generate_from_scratch(context)
        
        try:
            tmpl = self.env.get_template(template_path)
            return tmpl.render(**context)
        except Exception:
            return self._generate_from_scratch(context)
    
    def _generate_from_scratch(self, context: Dict) -> str:
        """从零生成代码（无模板时）"""
        framework = context.get('framework', 'playwright_python')
        
        if framework == 'playwright_python':
            return self._generate_playwright_python(context)
        elif framework == 'api_pytest':
            return self._generate_api_pytest(context)
        elif framework == 'appium_python':
            return self._generate_appium_python(context)
        
        return "# Unsupported framework"
    
    def _generate_playwright_python(self, context: Dict) -> str:
        """生成 Playwright Python 代码"""
        lines = [
            'import pytest',
            'from playwright.sync_api import Page, expect',
            '',
            f'# Test: {context.get("title", "Untitled")}',
            f'# Test Point ID: {context.get("test_point_id", "")}',
            '',
            'def test_main(page: Page):',
        ]
        
        # 生成测试步骤
        indent = '    '
        for i, action in enumerate(context.get('actions', [])):
            code = self._action_to_code(action, 'page')
            lines.append(f'{indent}# Step {i+1}: {action.get("step", "")}')
            lines.append(f'{indent}{code}')
        
        # 生成断言
        lines.append(f'{indent}')
        lines.append(f'{indent}# Assertions')
        for assertion in context.get('assertions', []):
            code = self._assertion_to_code(assertion, 'page')
            lines.append(f'{indent}{code}')
        
        return '\n'.join(lines)
    
    def _action_to_code(self, action: Dict, page_var: str) -> str:
        """将动作转换为代码"""
        action_type = action.get('action_type', '')
        target = action.get('target', '')
        
        if action_type == 'navigate':
            return f'{page_var}.goto("https://example.com")'
        elif action_type == 'click':
            return f'{page_var}.click("{target}")'
        elif action_type == 'fill':
            return f'{page_var}.fill("{target}", "value")'
        elif action_type == 'wait':
            return f'{page_var}.wait_for_load_state("networkidle")'
        
        return f'# TODO: Implement {action_type}'
    
    def _assertion_to_code(self, assertion: Dict, page_var: str) -> str:
        """将断言转换为代码"""
        assertion_type = assertion.get('type', '')
        
        if assertion_type == 'visibility':
            return f'expect({page_var}.locator("target")).to_be_visible()'
        elif assertion_type == 'text':
            return f'expect({page_var}.locator("target")).to_contain_text("expected")'
        elif assertion_type == 'url':
            return f'expect({page_var}).to_have_url("https://example.com")'
        
        return f'# TODO: Implement assertion'
    
    def _generate_api_pytest(self, context: Dict) -> str:
        """生成 API pytest 代码"""
        lines = [
            'import pytest',
            'import requests',
            '',
            f'# Test: {context.get("title", "Untitled")}',
            '',
            'def test_api_endpoint():',
            '    # Setup',
            '    url = "https://api.example.com/endpoint"',
            '    headers = {"Content-Type": "application/json"}',
            '    payload = {}',
            '',
            '    # Execute',
            '    response = requests.post(url, json=payload, headers=headers)',
            '',
            '    # Assert',
            '    assert response.status_code == 200',
        ]
        return '\n'.join(lines)
    
    def _generate_appium_python(self, context: Dict) -> str:
        """生成 Appium Python 代码"""
        lines = [
            'import pytest',
            'from appium import webdriver',
            '',
            f'# Test: {context.get("title", "Untitled")}',
            '',
            'def test_mobile(driver: webdriver.Remote):',
            '    # Mobile test steps',
            '    pass',
        ]
        return '\n'.join(lines)
```

### 4.4 组件推荐器

```python
# agents/script-generation-agent/src/component_recommender.py

from typing import List, Dict, Any, Optional

class ComponentRecommender:
    """组件推荐器"""
    
    def __init__(self, component_library: List[Dict] = None):
        self.component_library = component_library or []
    
    def recommend(self, context: Dict) -> List[Dict]:
        """推荐可复用的组件"""
        recommendations = []
        
        # 1. 页面对象推荐
        page_objects = context.get('page_objects_needed', [])
        for po in self.component_library:
            if po.get('type') == 'page_object':
                if po.get('name') in page_objects:
                    recommendations.append({
                        'component_id': po['id'],
                        'name': po['name'],
                        'type': 'page_object',
                        'reuse_reason': f'匹配需要的页面对象',
                        'import_statement': self._generate_import(po)
                    })
        
        # 2. 工具函数推荐
        actions = context.get('actions', [])
        for action in actions:
            for util in self.component_library:
                if util.get('type') == 'utility':
                    if self._matches_action(util, action):
                        recommendations.append({
                            'component_id': util['id'],
                            'name': util['name'],
                            'type': 'utility',
                            'reuse_reason': f'支持{action.get("action_type")}动作',
                            'import_statement': self._generate_import(util)
                        })
        
        return recommendations
    
    def _matches_action(self, util: Dict, action: Dict) -> bool:
        """判断工具函数是否匹配动作"""
        supported_actions = util.get('supported_actions', [])
        return action.get('action_type') in supported_actions
    
    def _generate_import(self, component: Dict) -> str:
        """生成导入语句"""
        module = component.get('module', 'utils')
        name = component.get('name', '')
        return f'from {module} import {name}'
    
    def calculate_reuse_rate(self, recommendations: List[Dict], 
                            total_components: int) -> float:
        """计算组件复用率"""
        if total_components == 0:
            return 0.0
        
        return len(recommendations) / total_components
```

### 4.5 静态检查器

```python
# agents/script-generation-agent/src/static_checker.py

import ast
import subprocess
from typing import Dict, List, Any

class StaticChecker:
    """静态检查器"""
    
    def check(self, code: str, language: str = 'python') -> Dict[str, Any]:
        """执行静态检查"""
        results = {
            'syntax_check': {'passed': True, 'errors': []},
            'type_check': {'passed': True, 'errors': []},
            'lint_check': {'passed': True, 'errors': []}
        }
        
        if language == 'python':
            results['syntax_check'] = self._check_syntax_python(code)
            results['lint_check'] = self._check_lint_python(code)
        
        return results
    
    def _check_syntax_python(self, code: str) -> Dict:
        """Python 语法检查"""
        try:
            ast.parse(code)
            return {'passed': True, 'errors': []}
        except SyntaxError as e:
            return {
                'passed': False,
                'errors': [{
                    'type': 'syntax',
                    'message': str(e),
                    'line': e.lineno,
                    'column': e.offset
                }]
            }
    
    def _check_lint_python(self, code: str) -> Dict:
        """Python Lint 检查"""
        errors = []
        
        try:
            # 使用 pycodestyle 检查
            import pycodestyle
            
            # 将代码写入临时文件
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_path = f.name
            
            style = pycodestyle.StyleGuide(quiet=True)
            checker = pycodestyle.Checker(temp_path, report=None)
            
            # 捕获错误
            import io
            import sys
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            
            checker.check_all()
            
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout
            
            # 解析输出
            for line in output.strip().split('\n'):
                if line:
                    parts = line.split(':')
                    if len(parts) >= 3:
                        errors.append({
                            'type': 'lint',
                            'message': parts[2].strip(),
                            'line': int(parts[1]),
                            'column': int(parts[2].split()[0]) if parts[2].split()[0].isdigit() else 0
                        })
            
            import os
            os.unlink(temp_path)
            
        except Exception as e:
            errors.append({
                'type': 'lint',
                'message': f'Lint check failed: {str(e)}',
                'line': 0,
                'column': 0
            })
        
        return {
            'passed': len(errors) == 0,
            'errors': errors
        }
```

### 4.6 质量评分器

```python
# agents/script-generation-agent/src/quality_scorer.py

from typing import Dict, List, Any

class QualityScorer:
    """代码质量评分器"""
    
    def score(self, code: str, static_results: Dict, 
              recommendations: List[Dict]) -> Dict[str, Any]:
        """计算代码质量分数"""
        return {
            'overall_score': self._calculate_overall(code, static_results, recommendations),
            'readability_score': self._calculate_readability(code),
            'maintainability_score': self._calculate_maintainability(code),
            'testability_score': self._calculate_testability(code),
            'performance_score': self._calculate_performance(code),
            'issues': self._collect_issues(static_results),
            'suggestions': self._generate_suggestions(code, static_results),
            'component_reuse_rate': self._calculate_reuse_rate(recommendations)
        }
    
    def _calculate_overall(self, code: str, static_results: Dict, 
                          recommendations: List) -> float:
        """计算总体分数"""
        readability = self._calculate_readability(code)
        maintainability = self._calculate_maintainability(code)
        testability = self._calculate_testability(code)
        
        # 静态检查扣分
        lint_errors = len(static_results.get('lint_check', {}).get('errors', []))
        syntax_errors = len(static_results.get('syntax_check', {}).get('errors', []))
        
        penalty = syntax_errors * 20 + lint_errors * 2
        
        # 组件复用奖励
        reuse_bonus = len(recommendations) * 3
        
        overall = (readability + maintainability + testability) / 3 - penalty + reuse_bonus
        return max(0, min(100, overall))
    
    def _calculate_readability(self, code: str) -> float:
        """计算可读性分数"""
        lines = code.split('\n')
        
        # 代码长度适中
        length_score = 100 if 10 <= len(lines) <= 100 else max(50, 100 - abs(len(lines) - 50))
        
        # 注释比例
        comment_lines = sum(1 for line in lines if line.strip().startswith('#'))
        comment_ratio = comment_lines / len(lines) if lines else 0
        comment_score = 100 if 0.1 <= comment_ratio <= 0.3 else max(50, 100 - abs(comment_ratio - 0.2) * 200)
        
        # 行长度
        long_lines = sum(1 for line in lines if len(line) > 120)
        line_length_score = max(50, 100 - long_lines * 5)
        
        return (length_score + comment_score + line_length_score) / 3
    
    def _calculate_maintainability(self, code: str) -> float:
        """计算可维护性分数"""
        # 函数数量
        func_count = code.count('def ')
        
        # 函数长度（简单估算）
        avg_func_length = len(code.split('\n')) / max(func_count, 1)
        func_length_score = 100 if avg_func_length <= 50 else max(50, 100 - (avg_func_length - 50))
        
        # 重复代码检测（简化）
        duplication_score = 100  # TODO: 实现重复代码检测
        
        return (func_length_score + duplication_score) / 2
    
    def _calculate_testability(self, code: str) -> float:
        """计算可测试性分数"""
        # 是否有断言
        has_assertions = 'assert' in code or 'expect' in code
        assertion_score = 100 if has_assertions else 0
        
        # 是否有测试数据
        has_test_data = 'test_' in code or 'fixture' in code
        data_score = 80 if has_test_data else 50
        
        # 是否隔离依赖
        has_mock = 'mock' in code or 'Mock' in code
        mock_score = 90 if has_mock else 70
        
        return (assertion_score + data_score + mock_score) / 3
    
    def _calculate_performance(self, code: str) -> float:
        """计算性能分数"""
        # 检查常见性能问题
        score = 100
        
        # 循环中的数据库查询（简化检测）
        if 'for ' in code and ('query' in code or 'request' in code):
            score -= 20
        
        # 大列表操作
        if 'while True' in code:
            score -= 30
        
        return max(0, score)
    
    def _collect_issues(self, static_results: Dict) -> List[Dict]:
        """收集所有问题"""
        issues = []
        
        for check_type, result in static_results.items():
            if isinstance(result, dict):
                for error in result.get('errors', []):
                    issues.append(error)
        
        return issues
    
    def _generate_suggestions(self, code: str, static_results: Dict) -> List[str]:
        """生成改进建议"""
        suggestions = []
        
        # 基于静态检查结果
        if not static_results.get('syntax_check', {}).get('passed', True):
            suggestions.append('修复语法错误')
        
        lint_errors = static_results.get('lint_check', {}).get('errors', [])
        if len(lint_errors) > 5:
            suggestions.append('代码风格问题较多，建议运行格式化工具')
        
        # 基于代码内容
        if len(code.split('\n')) > 200:
            suggestions.append('代码文件过长，建议拆分为多个文件')
        
        if 'TODO' in code or 'FIXME' in code:
            suggestions.append('代码中包含待办标记，建议完成实现')
        
        return suggestions
    
    def _calculate_reuse_rate(self, recommendations: List[Dict]) -> float:
        """计算组件复用率"""
        # 简化实现
        return min(1.0, len(recommendations) * 0.2)
```

---

## 5. Agent 主实现

```python
# agents/script-generation-agent/src/agent.py

import time
from datetime import datetime
from typing import Dict, Any

from .schemas import (
    ScriptGenerationInput,
    ScriptGenerationOutput,
    GeneratedScript,
    QualityReport
)
from .test_point_analyzer import TestPointAnalyzer
from .template_selector import TemplateSelector
from .code_generator import CodeGenerator
from .component_recommender import ComponentRecommender
from .static_checker import StaticChecker
from .quality_scorer import QualityScorer

class ScriptGenerationAgent:
    """Script Generation Agent 主类"""
    
    VERSION = "0.1.0"
    MODEL_USED = "qwen-3.5-plus"
    
    def __init__(self, component_library: list = None):
        self.analyzer = TestPointAnalyzer()
        self.template_selector = TemplateSelector()
        self.code_generator = CodeGenerator()
        self.component_recommender = ComponentRecommender(component_library)
        self.static_checker = StaticChecker()
        self.quality_scorer = QualityScorer()
        self.token_usage = {'prompt': 0, 'completion': 0}
    
    async def generate(self, input_data: ScriptGenerationInput) -> ScriptGenerationOutput:
        """生成脚本"""
        start_time = time.time()
        
        # Stage 1: 测试点分析
        analyzed_points = self.analyzer.analyze(input_data.test_points)
        
        # Stage 2: 为每个测试点生成脚本
        generated_scripts = []
        all_recommendations = []
        
        for analyzed_tp in analyzed_points:
            # 选择模板
            template = self.template_selector.select(
                analyzed_tp,
                input_data.target_framework.value
            )
            
            # 准备上下文
            context = self._prepare_context(analyzed_tp, input_data)
            
            # 生成代码
            code = self.code_generator.generate(template, context)
            
            # 组件推荐
            recommendations = self.component_recommender.recommend(context)
            all_recommendations.extend(recommendations)
            
            # 静态检查
            static_results = self.static_checker.check(
                code,
                self._get_language(input_data.target_framework)
            )
            
            # 创建脚本对象
            script = GeneratedScript(
                script_id=f"script-{analyzed_tp['test_point_id']}",
                test_point_id=analyzed_tp['test_point_id'],
                file_path=f"tests/test_{analyzed_tp['test_point_id']}.py",
                content=code,
                language=self._get_language(input_data.target_framework),
                framework=input_data.target_framework.value,
                line_count=len(code.split('\n')),
                character_count=len(code)
            )
            
            generated_scripts.append(script)
        
        # Stage 3: 质量评分
        all_code = '\n\n'.join(s.content for s in generated_scripts)
        quality_data = self.quality_scorer.score(
            all_code,
            static_results,
            all_recommendations
        )
        
        quality_report = QualityReport(**quality_data)
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        return ScriptGenerationOutput(
            request_id=input_data.request_id,
            generated_scripts=generated_scripts,
            quality_report=quality_report,
            validation_results=static_results,
            generation_confidence=self._calculate_confidence(quality_report),
            warnings=self._generate_warnings(quality_report),
            processing_time_ms=processing_time_ms,
            agent_version=self.VERSION,
            model_used=self.MODEL_USED,
            timestamp=datetime.now()
        )
    
    def _prepare_context(self, analyzed_tp: Dict, input_data: ScriptGenerationInput) -> Dict:
        """准备生成上下文"""
        return {
            'test_point_id': analyzed_tp['test_point_id'],
            'title': analyzed_tp['title'],
            'actions': analyzed_tp.get('action_types', []),
            'assertions': analyzed_tp.get('assertion_points', []),
            'page_objects': input_data.page_objects,
            'framework': input_data.target_framework.value,
            'data_requirements': analyzed_tp.get('data_requirements', [])
        }
    
    def _get_language(self, framework) -> str:
        """获取编程语言"""
        if 'python' in framework.value:
            return 'python'
        elif 'typescript' in framework.value:
            return 'typescript'
        return 'python'
    
    def _calculate_confidence(self, quality_report: QualityReport) -> float:
        """计算生成置信度"""
        # 基于质量报告计算置信度
        score = quality_report.overall_score
        
        if score >= 80:
            return 0.9
        elif score >= 60:
            return 0.75
        elif score >= 40:
            return 0.6
        else:
            return 0.4
    
    def _generate_warnings(self, quality_report: QualityReport) -> list:
        """生成警告"""
        warnings = []
        
        if quality_report.overall_score < 60:
            warnings.append(f'代码质量评分较低 ({quality_report.overall_score:.1f})')
        
        if quality_report.component_reuse_rate < 0.3:
            warnings.append('组件复用率较低，建议增加可复用组件')
        
        if len(quality_report.issues) > 10:
            warnings.append(f'代码问题较多 ({len(quality_report.issues)}个)')
        
        return warnings
```

---

## 6. 测试策略

说明：以下测试文件名和代码片段是建议补齐的测试形态，不代表当前仓库已经存在对应 `tests/` 文件；阅读时请把它视作目标测试蓝图。

### 6.1 单元测试

```python
# agents/script-generation-agent/tests/test_code_generator.py

import pytest
from src.code_generator import CodeGenerator

class TestCodeGenerator:
    def test_generate_playwright_python(self):
        generator = CodeGenerator()
        context = {
            'test_point_id': 'tp-001',
            'title': '用户登录测试',
            'actions': [
                {'action_type': 'navigate', 'target': 'login_page'},
                {'action_type': 'fill', 'target': 'username'},
                {'action_type': 'click', 'target': 'login_button'}
            ],
            'assertions': [
                {'type': 'url', 'expected': 'https://example.com/home'}
            ],
            'framework': 'playwright_python'
        }
        
        code = generator._generate_playwright_python(context)
        
        assert 'import pytest' in code
        assert 'def test_main' in code
        assert 'page.goto' in code
        assert 'page.click' in code
        assert 'expect' in code
```

### 6.2 Golden Test Set

```python
# agents/script-generation-agent/tests/golden_tests.py

import pytest
from src.agent import ScriptGenerationAgent
from src.schemas import ScriptGenerationInput, TestPointRef

GOLDEN_TEST_CASES = [
    {
        'name': '简单登录脚本生成',
        'input': ScriptGenerationInput(
            request_id='golden-sg-001',
            test_points=[
                TestPointRef(
                    test_point_id='tp-001',
                    title='用户登录',
                    test_steps=['打开登录页', '输入用户名', '输入密码', '点击登录'],
                    expected_results=['跳转到首页'],
                    priority='P0'
                )
            ],
            target_framework='playwright_python'
        ),
        'expected': {
            'min_scripts': 1,
            'min_quality_score': 60,
            'syntax_must_pass': True
        }
    }
]

@pytest.mark.parametrize('test_case', GOLDEN_TEST_CASES)
@pytest.mark.asyncio
async def test_golden_cases(test_case):
    agent = ScriptGenerationAgent()
    output = await agent.generate(test_case['input'])
    
    assert len(output.generated_scripts) >= test_case['expected']['min_scripts']
    assert output.quality_report.overall_score >= test_case['expected']['min_quality_score']
    assert output.validation_results['syntax_check']['passed'] == test_case['expected']['syntax_must_pass']
```

---

## 7. 实施计划

### Phase 1: 基础框架（Week 1）

| 任务 | 预计 | 状态 |
|------|------|------|
| 项目结构搭建 | 1 天 | ⏳ |
| 输入输出 Schema 定义 | 1 天 | ⏳ |
| 测试点分析器实现 | 2 天 | ⏳ |
| 代码生成器实现 | 2 天 | ⏳ |

### Phase 2: 核心能力（Week 2）

| 任务 | 预计 | 状态 |
|------|------|------|
| 模板选择器实现 | 2 天 | ⏳ |
| 组件推荐器实现 | 2 天 | ⏳ |
| 静态检查器实现 | 2 天 | ⏳ |
| 质量评分器实现 | 2 天 | ⏳ |
| Agent 主逻辑 | 2 天 | ⏳ |

### Phase 3: 企业级能力（Week 3）

| 任务 | 预计 | 状态 |
|------|------|------|
| 多框架支持完善 | 2 天 | ⏳ |
| Golden Test Set 建立 | 2 天 | ⏳ |
| 监控指标接入 | 1 天 | ⏳ |
| 文档完善 | 1 天 | ⏳ |
| 验收测试 | 1 天 | ⏳ |

---

## 8. 验收标准

### 功能验收

- [ ] 支持 3 种以上测试框架
- [ ] 代码语法正确率 > 98%
- [ ] 规范符合率 > 95%
- [ ] 组件复用率 > 60%
- [ ] 首跑通过率 > 85%

### 质量验收

- [ ] 单元测试覆盖率 > 85%
- [ ] Golden Test Set 通过率 > 85%
- [ ] P95 延迟 < 5s
- [ ] 代码质量评分 > 80

### 运维验收

- [ ] 结构化日志输出
- [ ] Prometheus 指标接入
- [ ] 告警规则配置
- [ ] 灰度发布流程验证

---

*文档版本：1.0*
*创建日期：2026-03-21*
*最后更新：2026-03-21*
*维护团队：AI Test Platform Core Team*
