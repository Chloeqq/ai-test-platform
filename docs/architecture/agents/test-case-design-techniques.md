# 测试用例设计能力补充设计

> **适用 Agent**: Test Design Agent
> **补充内容**: 边界值分析、等价类划分、错误推测等测试技术
> **创建日期**: 2026-03-21
> **文档性质**: 目标态补充设计，需结合当前实现进度理解

---

## 0. 现实边界与本次校正（2026-03-21）

这份文档最初更偏“目标态长稿”，如果直接拿来指导开发，容易让人误以为 `test-design-agent` 已经具备完整的经典测试设计技术能力。结合当前仓库实现，先明确以下边界：

- 当前已落地的是“确定性测试点生成 + 置信度/告警/review 语义 + traceability/review_summary 企业化输出”。
- 当前未落地的是本文列出的独立技术模块，例如 `boundary_value_analyzer.py`、`equivalence_partitioner.py`、`error_guessing_engine.py`、`cause_effect_graph.py`、`state_transition_tester.py`、`orthogonal_array_designer.py`。
- 当前 `test-design-agent` 的强项是基于 `requirement_spec`、`test_intents`、稳定页面 target 和规则映射，生成可执行且可审核的测试点与用例草稿；不是完整的“企业级测试技术引擎”。
- 后续补齐这类能力时，应继续遵守平台总边界：
  - 工程事实：规则和校验器优先
  - 业务推理：AI 辅助
  - 高风险决策：人工兜底
  - pass/fail：必须由确定性断言决定，不能由 AI 判定

### 0.1 当前代码证据

当前仓库中可以直接对应到的真实实现入口：

- `agents/test-design-agent/src/agent.py`
- `agents/test-design-agent/src/test_points.py`
- `agents/test-design-agent/tests/test_enterprise_design.py`

这些文件已经表明当前 Agent 具备：

- `build_test_point_plan(...)`：基于步骤生成 `confidence / warnings / requires_review / suggestion / review_reason / dependent_elements`
- `design_bundle(...)`：输出 `case / test_points / traceability / review_summary / confidence / requires_review`
- `requirement_spec.test_intents -> step` 的确定性映射
- 稳定页面基线注入、target 校验、执行步骤标准化

但这些文件并不包含本文 2.2 中列出的经典测试设计技术模块。

## 1. 当前状态分析

### 1.1 已有能力

当前 Test Design Agent 的真实已落地能力包含：

| 能力 | 状态 | 说明 |
|------|------|------|
| 测试点生成 | ✅ 已实现 | `build_test_point_plan(...)` 可从步骤生成测试点 |
| 用例/测试点一体化输出 | ✅ 已实现 | `design_bundle(...)` 输出 `case + test_points + traceability + review_summary` |
| review 语义 | ✅ 已实现 | 已输出 `confidence / warnings / requires_review / suggestion / review_reason` |
| 元素依赖追踪 | ✅ 已实现 | 已输出 `dependent_elements`，可接确认点治理 |
| 基线约束 | ✅ 已实现 | 对稳定页面注入固定步骤前缀并校验 target |
| requirement_spec 驱动 | ✅ 部分实现 | 已支持 `test_intents` 到测试点/步骤映射，但还不够细颗粒度 |
| 经典测试技术 | ⚠️ 尚未实现 | 边界值、等价类、状态转换等仅在文档中存在 |

### 1.2 缺失能力

| 能力 | 状态 | 说明 |
|------|------|------|
| **边界值分析** | ❌ 未实现 | 当前没有独立模块，也没有字段约束驱动的边界值生成 |
| **等价类划分** | ❌ 未实现 | 当前没有字段级有效/无效等价类资产 |
| **因果图分析** | ❌ 缺失 | 未设计条件组合分析 |
| **状态转换测试** | ❌ 缺失 | 未设计状态机测试 |
| **错误推测** | ❌ 缺失 | 未设计基于经验的测试 |
| **正交实验设计** | ❌ 缺失 | 未设计多因素组合优化 |
| **字段约束输入层** | ❌ 缺失 | 经典测试技术依赖字段 schema/约束，当前主链仍偏 page/intents/steps |
| **技术覆盖统计** | ❌ 缺失 | 当前 `review_summary` 关注 review 风险，不统计 boundary/equivalence 覆盖度 |

### 1.3 与当前项目进度对照

| 维度 | 当前状态 | 结论 |
|------|----------|------|
| URL 驱动主链 | 已推进到确认点、风险评估、review_state 持久化 | Test Design Agent 已进入主链，但主要承担“稳定生成 + review”职责 |
| 防幻觉约束 | 已明确要求规则优先、AI 辅助、人工兜底 | 经典测试技术实现必须走确定性算法，不应先做纯 LLM 生成 |
| 页面分析 | 正在往规则优先模型拆分 | 测试设计后续应正式消费结构化页面/字段信息，而不是只看 requirement 文本 |
| 测试点治理 | 已有 review_summary / dependent_elements / pending review | 适合把边界值/等价类产出的低置信度点纳入现有确认点 |
| 企业级回归 | 主链已有一定基础，但测试点资产层仍薄 | 经典测试技术应优先补“高确定性、高复用”的能力，不宜一次全上 |

### 1.4 当前卡点

真正限制本文落地的，不是算法示例本身，而是上游输入和资产层还不够稳定：

1. 当前 `test-design-agent` 更擅长消费 `test_intents`、页面 target、步骤提示，而不是字段级业务约束。
2. 没有统一的“字段约束/参数约束 schema”，边界值和等价类就缺少稳定输入。
3. 测试点中间资产层还不够强，导致“经典测试技术输出”缺少长期复用的位置。
4. 当前 URL 驱动主链的重点仍是页面分析、确认点、风险治理闭环，不能让 Test Design 一次引入过多高不确定性逻辑。
5. 结果验证仍必须保持确定性断言主导，因此这里新增的能力应服务于“测试点设计更完整”，而不是把 AI 变成裁判。

---

## 2. 补充设计：测试用例设计技术模块

### 2.1 模块架构

```
┌─────────────────────────────────────────────────────────────────┐
│              Test Case Design Techniques                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Boundary   │  │ Equivalence  │ │  Cause-Effect │          │
│  │   Value      │  │   Class      │ │     Graph     │          │
│  │   Analyzer   │  │   Partition  │ │     Analyzer  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │    State     │  │    Error     │ │   Orthogonal  │          │
│  │  Transition  │  │  Guessing    │ │     Array     │          │
│  │   Tester     │  │   Engine     │ │   Designer    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────┐
                    │  Test Cases     │
                    │  (Detailed)     │
                    └─────────────────┘
```

### 2.2 新增模块划分

说明：下面的模块路径代表建议中的目标拆分方案，当前仓库里这些文件大多还不存在，不能视为已实现。

| 模块 | 文件路径 | 职责 |
|------|---------|------|
| `boundary_value_analyzer.py` | `agents/test-design-agent/src/boundary_value_analyzer.py` | 边界值分析 |
| `equivalence_partitioner.py` | `agents/test-design-agent/src/equivalence_partitioner.py` | 等价类划分 |
| `cause_effect_graph.py` | `agents/test-design-agent/src/cause_effect_graph.py` | 因果图分析 |
| `state_transition_tester.py` | `agents/test-design-agent/src/state_transition_tester.py` | 状态转换测试 |
| `error_guessing_engine.py` | `agents/test-design-agent/src/error_guessing_engine.py` | 错误推测 |
| `orthogonal_array_designer.py` | `agents/test-design-agent/src/orthogonal_array_designer.py` | 正交实验设计 |

---

## 3. 核心功能详细设计

### 3.1 边界值分析器

```python
# agents/test-design-agent/src/boundary_value_analyzer.py

from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class BoundaryValue:
    """边界值"""
    value: Any
    type: str  # min/min-1/min+1/max/max-1/max+1/null/empty
    description: str
    expected_result: str

class BoundaryValueAnalyzer:
    """边界值分析器"""
    
    # 常见类型的边界值定义
    BOUNDARY_DEFINITIONS = {
        'integer': {
            'boundaries': ['min', 'min+1', 'nominal', 'max-1', 'max'],
            'special': ['null', 'non_integer', 'negative']
        },
        'string': {
            'boundaries': ['empty', 'min_length', 'min+1', 'nominal', 'max-1', 'max'],
            'special': ['null', 'oversized', 'special_chars', 'unicode']
        },
        'date': {
            'boundaries': ['min_date', 'min+1day', 'today', 'max-1day', 'max_date'],
            'special': ['null', 'invalid_format', 'leap_year', 'weekend']
        },
        'array': {
            'boundaries': ['empty', 'single', 'nominal', 'max-1', 'max'],
            'special': ['null', 'oversized', 'mixed_types']
        },
        'decimal': {
            'boundaries': ['min', 'min+epsilon', 'nominal', 'max-epsilon', 'max'],
            'special': ['null', 'negative', 'zero', 'precision_overflow']
        }
    }
    
    def analyze(self, field_definition: Dict) -> List[BoundaryValue]:
        """分析字段的边界值"""
        field_type = field_definition.get('type', 'string')
        constraints = field_definition.get('constraints', {})
        
        boundaries = []
        
        # 1. 标准边界值
        standard = self._generate_standard_boundaries(field_type, constraints)
        boundaries.extend(standard)
        
        # 2. 特殊边界值
        special = self._generate_special_boundaries(field_type, constraints)
        boundaries.extend(special)
        
        # 3. 业务边界值
        business = self._generate_business_boundaries(field_definition)
        boundaries.extend(business)
        
        return boundaries
    
    def _generate_standard_boundaries(self, field_type: str, 
                                       constraints: Dict) -> List[BoundaryValue]:
        """生成标准边界值"""
        boundaries = []
        definition = self.BOUNDARY_DEFINITIONS.get(field_type, {})
        
        if field_type == 'integer':
            min_val = constraints.get('min', 0)
            max_val = constraints.get('max', 100)
            
            boundaries.extend([
                BoundaryValue(min_val, 'min', f'最小值 {min_val}', '成功'),
                BoundaryValue(min_val - 1, 'min-1', f'最小值减 1 {min_val-1}', '失败'),
                BoundaryValue(int((min_val + max_val) / 2), 'nominal', f'中间值', '成功'),
                BoundaryValue(max_val + 1, 'max+1', f'最大值加 1 {max_val+1}', '失败'),
                BoundaryValue(max_val, 'max', f'最大值 {max_val}', '成功'),
            ])
        
        elif field_type == 'string':
            min_len = constraints.get('min_length', 1)
            max_len = constraints.get('max_length', 100)
            
            boundaries.extend([
                BoundaryValue('', 'empty', '空字符串', '失败' if constraints.get('required') else '成功'),
                BoundaryValue('a' * min_len, 'min_length', f'最小长度 {min_len}', '成功'),
                BoundaryValue('a' * (min_len + 1), 'min+1', f'最小长度 +1', '成功'),
                BoundaryValue('a' * int((min_len + max_len) / 2), 'nominal', '中间长度', '成功'),
                BoundaryValue('a' * (max_len - 1), 'max-1', f'最大长度 -1', '成功'),
                BoundaryValue('a' * max_len, 'max_length', f'最大长度 {max_len}', '成功'),
                BoundaryValue('a' * (max_len + 1), 'oversized', f'超最大长度 {max_len+1}', '失败'),
            ])
        
        elif field_type == 'date':
            from datetime import datetime, timedelta
            min_date = constraints.get('min_date', datetime(2000, 1, 1))
            max_date = constraints.get('max_date', datetime(2099, 12, 31))
            
            boundaries.extend([
                BoundaryValue(min_date, 'min_date', f'最小日期', '成功'),
                BoundaryValue(min_date + timedelta(days=1), 'min+1day', f'最小日期 +1 天', '成功'),
                BoundaryValue(datetime.now(), 'today', '今天', '成功'),
                BoundaryValue(max_date - timedelta(days=1), 'max-1day', f'最大日期 -1 天', '成功'),
                BoundaryValue(max_date, 'max_date', f'最大日期', '成功'),
            ])
        
        elif field_type == 'decimal':
            min_val = constraints.get('min', 0.0)
            max_val = constraints.get('max', 999.99)
            precision = constraints.get('precision', 2)
            epsilon = 10 ** (-precision)
            
            boundaries.extend([
                BoundaryValue(min_val, 'min', f'最小值 {min_val}', '成功'),
                BoundaryValue(min_val + epsilon, 'min+epsilon', f'最小值+最小精度', '成功'),
                BoundaryValue((min_val + max_val) / 2, 'nominal', '中间值', '成功'),
                BoundaryValue(max_val - epsilon, 'max-epsilon', f'最大值 - 最小精度', '成功'),
                BoundaryValue(max_val, 'max', f'最大值 {max_val}', '成功'),
                BoundaryValue(max_val + epsilon, 'max+epsilon', f'最大值 + 最小精度', '失败'),
            ])
        
        return boundaries
    
    def _generate_special_boundaries(self, field_type: str,
                                     constraints: Dict) -> List[BoundaryValue]:
        """生成特殊边界值"""
        boundaries = []
        
        if field_type in ['integer', 'decimal']:
            if not constraints.get('positive_only'):
                boundaries.append(
                    BoundaryValue(-1, 'negative', '负数值', '失败' if constraints.get('positive_only') else '成功')
                )
            boundaries.append(
                BoundaryValue(0, 'zero', '零值', '成功')
            )
        
        elif field_type == 'string':
            boundaries.extend([
                BoundaryValue(None, 'null', 'NULL 值', '失败' if constraints.get('required') else '成功'),
                BoundaryValue('<script>alert(1)</script>', 'special_chars', 'XSS 测试', '失败'),
                BoundaryValue("'; DROP TABLE users;--", 'sql_injection', 'SQL 注入测试', '失败'),
                BoundaryValue('你好世界🎉', 'unicode', 'Unicode 字符', '成功'),
            ])
        
        elif field_type == 'date':
            boundaries.extend([
                BoundaryValue(None, 'null', 'NULL 日期', '失败' if constraints.get('required') else '成功'),
                BoundaryValue('2024-02-29', 'leap_year', '闰年日期', '成功'),
                BoundaryValue('invalid-date', 'invalid_format', '无效格式', '失败'),
            ])
        
        return boundaries
    
    def _generate_business_boundaries(self, field_definition: Dict) -> List[BoundaryValue]:
        """生成业务边界值"""
        boundaries = []
        business_rules = field_definition.get('business_rules', [])
        
        for rule in business_rules:
            if rule.get('type') == 'range':
                boundaries.append(
                    BoundaryValue(rule['threshold'], 'business_threshold', 
                                f'业务阈值 {rule["threshold"]}', rule['expected'])
                )
            elif rule.get('type') == 'format':
                boundaries.append(
                    BoundaryValue(rule['invalid_example'], 'business_invalid',
                                f'业务无效格式', '失败')
                )
        
        return boundaries
```

### 3.2 等价类划分器

```python
# agents/test-design-agent/src/equivalence_partitioner.py

from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class EquivalenceClass:
    """等价类"""
    class_id: str
    type: str  # valid/invalid
    description: str
    representative_value: Any
    coverage: List[str]  # 覆盖的条件

class EquivalencePartitioner:
    """等价类划分器"""
    
    def partition(self, field_definition: Dict) -> List[EquivalenceClass]:
        """对字段进行等价类划分"""
        classes = []
        field_type = field_definition.get('type', 'string')
        constraints = field_definition.get('constraints', {})
        
        # 1. 有效等价类
        valid_classes = self._generate_valid_classes(field_type, constraints)
        classes.extend(valid_classes)
        
        # 2. 无效等价类
        invalid_classes = self._generate_invalid_classes(field_type, constraints)
        classes.extend(invalid_classes)
        
        return classes
    
    def _generate_valid_classes(self, field_type: str, 
                                constraints: Dict) -> List[EquivalenceClass]:
        """生成有效等价类"""
        classes = []
        class_id = 0
        
        if field_type == 'integer':
            min_val = constraints.get('min', 0)
            max_val = constraints.get('max', 100)
            
            # 有效范围
            if max_val - min_val > 10:
                classes.extend([
                    EquivalenceClass(
                        f'valid-{class_id}', 'valid',
                        f'范围内较小值 ({min_val}-{min_val+10})',
                        min_val + 5,
                        ['range_valid']
                    ),
                    EquivalenceClass(
                        f'valid-{class_id+1}', 'valid',
                        f'范围内中间值 ({int((min_val+max_val)/2)})',
                        int((min_val + max_val) / 2),
                        ['range_valid']
                    ),
                    EquivalenceClass(
                        f'valid-{class_id+2}', 'valid',
                        f'范围内较大值 ({max_val-10}-{max_val})',
                        max_val - 5,
                        ['range_valid']
                    )
                ])
            else:
                classes.append(
                    EquivalenceClass(
                        f'valid-{class_id}', 'valid',
                        f'有效范围 ({min_val}-{max_val})',
                        int((min_val + max_val) / 2),
                        ['range_valid']
                    )
                )
        
        elif field_type == 'string':
            # 有效长度
            min_len = constraints.get('min_length', 1)
            max_len = constraints.get('max_length', 100)
            
            classes.append(
                EquivalenceClass(
                    f'valid-{class_id}', 'valid',
                    f'有效长度 ({min_len}-{max_len}字符)',
                    'a' * int((min_len + max_len) / 2),
                    ['length_valid']
                )
            )
            
            # 有效格式
            if constraints.get('pattern'):
                classes.append(
                    EquivalenceClass(
                        f'valid-{class_id+1}', 'valid',
                        '符合正则模式',
                        self._generate_pattern_example(constraints['pattern']),
                        ['pattern_valid']
                    )
                )
            
            # 有效字符集
            if constraints.get('charset') == 'alphanumeric':
                classes.append(
                    EquivalenceClass(
                        f'valid-{class_id+2}', 'valid',
                        '字母数字组合',
                        'abc123',
                        ['charset_valid']
                    )
                )
        
        elif field_type == 'email':
            classes.extend([
                EquivalenceClass(
                    f'valid-{class_id}', 'valid',
                    '标准邮箱格式',
                    'user@example.com',
                    ['email_valid']
                ),
                EquivalenceClass(
                    f'valid-{class_id+1}', 'valid',
                    '带点邮箱',
                    'user.name@example.com',
                    ['email_valid']
                ),
                EquivalenceClass(
                    f'valid-{class_id+2}', 'valid',
                    '带加号邮箱',
                    'user+tag@example.com',
                    ['email_valid']
                )
            ])
        
        return classes
    
    def _generate_invalid_classes(self, field_type: str,
                                  constraints: Dict) -> List[EquivalenceClass]:
        """生成无效等价类"""
        classes = []
        class_id = 100
        
        if field_type == 'integer':
            min_val = constraints.get('min', 0)
            max_val = constraints.get('max', 100)
            
            classes.extend([
                EquivalenceClass(
                    f'invalid-{class_id}', 'invalid',
                    f'小于最小值 (<{min_val})',
                    min_val - 1,
                    ['range_invalid']
                ),
                EquivalenceClass(
                    f'invalid-{class_id+1}', 'invalid',
                    f'大于最大值 (>{max_val})',
                    max_val + 1,
                    ['range_invalid']
                ),
                EquivalenceClass(
                    f'invalid-{class_id+2}', 'invalid',
                    '非整数值',
                    'abc',
                    ['type_invalid']
                )
            ])
        
        elif field_type == 'string':
            min_len = constraints.get('min_length', 1)
            max_len = constraints.get('max_length', 100)
            
            classes.extend([
                EquivalenceClass(
                    f'invalid-{class_id}', 'invalid',
                    f'长度不足 (<{min_len})',
                    '' if min_len > 0 else 'a',
                    ['length_invalid']
                ),
                EquivalenceClass(
                    f'invalid-{class_id+1}', 'invalid',
                    f'长度超限 (>{max_len})',
                    'a' * (max_len + 1),
                    ['length_invalid']
                ),
                EquivalenceClass(
                    f'invalid-{class_id+2}', 'invalid',
                    '包含特殊字符',
                    '<script>',
                    ['charset_invalid']
                )
            ])
        
        elif field_type == 'email':
            classes.extend([
                EquivalenceClass(
                    f'invalid-{class_id}', 'invalid',
                    '缺少@符号',
                    'userexample.com',
                    ['email_invalid']
                ),
                EquivalenceClass(
                    f'invalid-{class_id+1}', 'invalid',
                    '缺少域名',
                    'user@',
                    ['email_invalid']
                ),
                EquivalenceClass(
                    f'invalid-{class_id+2}', 'invalid',
                    '缺少用户名',
                    '@example.com',
                    ['email_invalid']
                ),
                EquivalenceClass(
                    f'invalid-{class_id+3}', 'invalid',
                    '包含空格',
                    'user name@example.com',
                    ['email_invalid']
                )
            ])
        
        return classes
    
    def _generate_pattern_example(self, pattern: str) -> str:
        """根据正则生成示例"""
        # 简化实现
        if r'\d' in pattern:
            return '123'
        elif r'[a-z]' in pattern:
            return 'abc'
        return 'example'
```

### 3.3 错误推测引擎

```python
# agents/test-design-agent/src/error_guessing_engine.py

from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class ErrorGuess:
    """错误推测"""
    guess_id: str
    description: str
    category: str  # common/edge_case/security/performance
    test_input: Any
    expected_behavior: str
    likelihood: str  # high/medium/low
    source: str  # 经验来源

class ErrorGuessingEngine:
    """错误推测引擎"""
    
    # 常见错误模式库
    COMMON_ERRORS = {
        'null_handling': [
            {
                'description': 'NULL 值未处理',
                'test_input': None,
                'expected': '友好的错误提示或默认值',
                'likelihood': 'high'
            }
        ],
        'empty_input': [
            {
                'description': '空字符串未处理',
                'test_input': '',
                'expected': '验证提示或默认值',
                'likelihood': 'high'
            }
        ],
        'special_characters': [
            {
                'description': '特殊字符导致 SQL 注入',
                'test_input': "'; DROP TABLE users;--",
                'expected': '参数化查询，无 SQL 执行',
                'likelihood': 'medium'
            },
            {
                'description': '特殊字符导致 XSS',
                'test_input': '<script>alert(1)</script>',
                'expected': 'HTML 转义，无脚本执行',
                'likelihood': 'medium'
            }
        ],
        'boundary_overflow': [
            {
                'description': '数组越界',
                'test_input': 'index = length',
                'expected': '边界检查，无异常',
                'likelihood': 'medium'
            }
        ],
        'concurrent_access': [
            {
                'description': '并发修改导致数据不一致',
                'test_input': 'simultaneous_updates',
                'expected': '锁机制或乐观锁',
                'likelihood': 'medium'
            }
        ],
        'resource_exhaustion': [
            {
                'description': '大量数据导致内存溢出',
                'test_input': 'large_dataset',
                'expected': '分页或流式处理',
                'likelihood': 'low'
            }
        ]
    }
    
    # 按功能类型的错误模式
    FEATURE_SPECIFIC_ERRORS = {
        'login': [
            {
                'description': '密码明文传输',
                'category': 'security',
                'test_input': 'check_network_traffic',
                'expected': '密码加密传输',
                'likelihood': 'medium'
            },
            {
                'description': '登录失败次数无限制',
                'category': 'security',
                'test_input': 'multiple_failed_attempts',
                'expected': '账户锁定或验证码',
                'likelihood': 'medium'
            },
            {
                'description': 'Session 固定攻击',
                'category': 'security',
                'test_input': 'reuse_session_id',
                'expected': 'Session ID 更新',
                'likelihood': 'low'
            }
        ],
        'search': [
            {
                'description': 'SQL 注入',
                'category': 'security',
                'test_input': "' OR '1'='1",
                'expected': '参数化查询',
                'likelihood': 'medium'
            },
            {
                'description': '特殊字符搜索',
                'category': 'edge_case',
                'test_input': '%_\\',
                'expected': '正确转义',
                'likelihood': 'high'
            },
            {
                'description': '超长搜索词',
                'category': 'edge_case',
                'test_input': 'a' * 10000,
                'expected': '截断或友好提示',
                'likelihood': 'medium'
            }
        ],
        'file_upload': [
            {
                'description': '文件类型绕过',
                'category': 'security',
                'test_input': 'malicious.exe renamed to .jpg',
                'expected': '内容检测，不仅是扩展名',
                'likelihood': 'medium'
            },
            {
                'description': '超大文件上传',
                'category': 'edge_case',
                'test_input': 'file > max_size',
                'expected': '拒绝并提示',
                'likelihood': 'high'
            },
            {
                'description': '文件名包含路径遍历',
                'category': 'security',
                'test_input': '../../../etc/passwd',
                'expected': '文件名清理',
                'likelihood': 'medium'
            }
        ],
        'payment': [
            {
                'description': '金额精度丢失',
                'category': 'edge_case',
                'test_input': '0.1 + 0.2',
                'expected': '正确的金额计算',
                'likelihood': 'medium'
            },
            {
                'description': '负数金额',
                'category': 'edge_case',
                'test_input': '-100',
                'expected': '拒绝负数',
                'likelihood': 'high'
            },
            {
                'description': '并发支付',
                'category': 'edge_case',
                'test_input': 'duplicate_payment_request',
                'expected': '幂等处理',
                'likelihood': 'medium'
            }
        ]
    }
    
    def guess(self, feature_type: str, field_definitions: List[Dict]) -> List[ErrorGuess]:
        """基于经验推测可能的错误"""
        guesses = []
        guess_id = 0
        
        # 1. 通用错误模式
        for category, errors in self.COMMON_ERRORS.items():
            for error in errors:
                guesses.append(ErrorGuess(
                    guess_id=f'guess-{guess_id}',
                    description=error['description'],
                    category=category,
                    test_input=error['test_input'],
                    expected_behavior=error['expected'],
                    likelihood=error['likelihood'],
                    source='common_patterns'
                ))
                guess_id += 1
        
        # 2. 功能特定错误
        feature_errors = self.FEATURE_SPECIFIC_ERRORS.get(feature_type, [])
        for error in feature_errors:
            guesses.append(ErrorGuess(
                guess_id=f'guess-{guess_id}',
                description=error['description'],
                category=error.get('category', 'edge_case'),
                test_input=error['test_input'],
                expected_behavior=error['expected'],
                likelihood=error['likelihood'],
                source=f'feature_{feature_type}'
            ))
            guess_id += 1
        
        # 3. 字段特定错误
        for field in field_definitions:
            field_guesses = self._analyze_field_errors(field, guess_id)
            guesses.extend(field_guesses)
            guess_id += len(field_guesses)
        
        # 按可能性排序
        guesses.sort(key=lambda x: {'high': 3, 'medium': 2, 'low': 1}.get(x.likelihood, 0), 
                    reverse=True)
        
        return guesses
    
    def _analyze_field_errors(self, field: Dict, base_id: int) -> List[ErrorGuess]:
        """分析字段可能的错误"""
        guesses = []
        field_name = field.get('name', 'unknown')
        field_type = field.get('type', 'string')
        
        # 必填字段
        if field.get('required'):
            guesses.append(ErrorGuess(
                guess_id=f'guess-{base_id}',
                description=f'{field_name} 必填校验绕过',
                category='common',
                test_input={'field': field_name, 'value': ''},
                expected_behavior='拒绝空值',
                likelihood='medium',
                source='field_analysis'
            ))
        
        # 数值字段
        if field_type in ['integer', 'decimal']:
            guesses.append(ErrorGuess(
                guess_id=f'guess-{base_id+1}',
                description=f'{field_name} 精度问题',
                category='edge_case',
                test_input={'field': field_name, 'value': '0.1 + 0.2'},
                expected_behavior='正确的浮点运算',
                likelihood='medium',
                source='field_analysis'
            ))
        
        return guesses
```

---

## 4. 与现有 Test Design Agent 的集成

### 4.1 集成点

```python
# agents/test-design-agent/src/test_point_generator.py (增强版)

from .boundary_value_analyzer import BoundaryValueAnalyzer
from .equivalence_partitioner import EquivalencePartitioner
from .error_guessing_engine import ErrorGuessingEngine

class TestPointGenerator:
    """测试点生成器（增强版）"""
    
    def __init__(self):
        self.boundary_analyzer = BoundaryValueAnalyzer()
        self.equivalence_partitioner = EquivalencePartitioner()
        self.error_guessing = ErrorGuessingEngine()
    
    def generate(self, analyzed_requirement: Dict) -> List[TestPoint]:
        """生成测试点（包含测试技术）"""
        test_points = []
        
        # 原有逻辑：从实体/规则/意图生成测试点
        test_points.extend(self._generate_entity_test_points(...))
        test_points.extend(self._generate_rule_test_points(...))
        test_points.extend(self._generate_intent_test_points(...))
        
        # 新增：边界值测试点
        for entity in analyzed_requirement['entities']:
            for field in entity.get('attributes', []):
                boundary_tps = self._generate_boundary_test_points(field)
                test_points.extend(boundary_tps)
        
        # 新增：等价类测试点
        for entity in analyzed_requirement['entities']:
            for field in entity.get('attributes', []):
                equiv_tps = self._generate_equivalence_test_points(field)
                test_points.extend(equiv_tps)
        
        # 新增：错误推测测试点
        feature_type = self._infer_feature_type(analyzed_requirement)
        error_tps = self._generate_error_guessing_test_points(
            feature_type,
            [f for e in analyzed_requirement['entities'] for f in e.get('attributes', [])]
        )
        test_points.extend(error_tps)
        
        return test_points
    
    def _generate_boundary_test_points(self, field: Dict) -> List[TestPoint]:
        """生成边界值测试点"""
        boundaries = self.boundary_analyzer.analyze(field)
        test_points = []
        
        for boundary in boundaries:
            test_points.append(TestPoint(
                test_point_id=f"tp-boundary-{field['name']}-{boundary.type}",
                title=f"边界值测试：{field['name']} - {boundary.description}",
                description=f"验证{field['name']}在{boundary.description}时的行为",
                type=TestPointType.FUNCTIONAL,
                priority=Priority.P1 if boundary.type in ['min', 'max'] else Priority.P2,
                test_steps=[
                    f'设置{field["name"]}为{boundary.value}',
                    '提交表单',
                    f'验证{boundary.expected_result}'
                ],
                expected_results=[boundary.expected_result],
                related_entities=[field.get('entity_id')],
                confidence=0.85,
                tags=['boundary_value', field['name']]
            ))
        
        return test_points
    
    def _generate_equivalence_test_points(self, field: Dict) -> List[TestPoint]:
        """生成等价类测试点"""
        classes = self.equivalence_partitioner.partition(field)
        test_points = []
        
        for eq_class in classes:
            test_points.append(TestPoint(
                test_point_id=f"tp-equiv-{field['name']}-{eq_class.class_id}",
                title=f"等价类测试：{field['name']} - {eq_class.description}",
                description=f"验证{field['name']}在{eq_class.description}时的行为",
                type=TestPointType.FUNCTIONAL,
                priority=Priority.P1 if eq_class.type == 'valid' else Priority.P2,
                test_steps=[
                    f'设置{field["name"]}为{eq_class.representative_value}',
                    '提交表单',
                    f'验证{"成功" if eq_class.type == "valid" else "失败提示"}'
                ],
                expected_results=[eq_class.type == 'valid'],
                related_entities=[field.get('entity_id')],
                confidence=0.8,
                tags=['equivalence_class', field['name'], eq_class.type]
            ))
        
        return test_points
    
    def _generate_error_guessing_test_points(self, feature_type: str,
                                             fields: List[Dict]) -> List[TestPoint]:
        """生成错误推测测试点"""
        guesses = self.error_guessing.guess(feature_type, fields)
        test_points = []
        
        # 只选择高可能性的错误推测
        high_likelihood = [g for g in guesses if g.likelihood == 'high']
        
        for guess in high_likelihood[:10]:  # 限制数量
            test_points.append(TestPoint(
                test_point_id=f"tp-error-{guess.guess_id}",
                title=f"错误推测：{guess.description}",
                description=guess.description,
                type=TestPointType.FUNCTIONAL,
                priority=Priority.P2,
                test_steps=[
                    f'输入：{guess.test_input}',
                    '执行操作',
                    f'验证：{guess.expected_behavior}'
                ],
                expected_results=[guess.expected_behavior],
                confidence=0.7,
                tags=['error_guessing', guess.category]
            ))
        
        return test_points
```

### 4.2 输出增强

```python
# 测试点计划输出增加测试技术覆盖统计

class TestPointPlan(BaseModel):
    """测试点计划（增强版）"""
    plan_id: str
    test_points: List[TestPoint]
    
    # 新增：测试技术覆盖统计
    technique_coverage: Dict[str, Any] = {
        'boundary_value': {'count': 0, 'coverage_rate': 0},
        'equivalence_class': {'count': 0, 'coverage_rate': 0},
        'error_guessing': {'count': 0, 'coverage_rate': 0},
        'cause_effect': {'count': 0, 'coverage_rate': 0},
        'state_transition': {'count': 0, 'coverage_rate': 0}
    }
    
    # 新增：测试技术分布
    technique_distribution: Dict[str, int] = {
        'boundary_value': 0,
        'equivalence_class': 0,
        'error_guessing': 0,
        'normal_flow': 0,
        'exception_flow': 0
    }
```

---

## 5. 验收标准补充

### 5.1 边界值分析验收

- [ ] 支持 5 种以上数据类型的边界值生成
- [ ] 边界值覆盖率 100%（min/min+1/nominal/max-1/max）
- [ ] 特殊值（null/空/特殊字符）覆盖
- [ ] 业务边界值识别

### 5.2 等价类划分验收

- [ ] 有效/无效等价类完整划分
- [ ] 每个等价类有代表性值
- [ ] 等价类无重叠
- [ ] 覆盖所有输入条件

### 5.3 错误推测验收

- [ ] 常见错误模式库包含 20+ 模式
- [ ] 功能特定错误覆盖 5+ 功能类型
- [ ] 高可能性错误 100% 覆盖
- [ ] 安全相关错误优先

---

## 6. 实施建议

### 6.1 优先级

| 测试技术 | 优先级 | 预计工作量 | ROI |
|---------|--------|-----------|-----|
| 边界值分析 | P0 | 3-5 天 | 高 |
| 等价类划分 | P0 | 3-5 天 | 高 |
| 错误推测 | P1 | 4-6 天 | 中 |
| 状态转换 | P1 | 4-6 天 | 中 |
| 因果图 | P2 | 5-7 天 | 中 |
| 正交实验 | P2 | 5-7 天 | 低 |

### 6.2 集成策略

1. **Phase 0：先补输入约束层**
   - 先定义 `field_definitions / parameter_constraints / source_ids` 的统一输入结构。
   - 优先复用 `requirement_spec` 和 OpenAPI schema，不直接依赖自由文本。
   - 输出先继续挂接到当前 `TestPointPlanV1`，不要一开始就大改主链。
2. **Phase 1：优先落地边界值分析和等价类划分**
   - 这两类最确定、最适合确定性实现。
   - 优先服务表单、搜索、API 参数、金额/数量/日期等结构化输入。
   - 生成结果必须进入现有 `confidence / warnings / requires_review / dependent_elements` 语义。
3. **Phase 2：补错误推测与有限状态转换**
   - 错误推测应基于规则库和历史缺陷库，默认 `requires_review=True`。
   - 状态转换只对“显式状态机场景”启用，例如审批、订单、启停、上下架；不对所有页面泛化。
4. **Phase 3：最后考虑因果图和正交实验**
   - 只在输入足够结构化、且有明显多条件组合爆炸问题时启用。
   - 不建议在当前 URL 驱动主链里过早上这两项。

### 6.3 建议的完善计划

#### P0：把经典测试技术接到当前可运行主链

目标：不是先做“六大模块齐全”，而是先把最有价值、最确定的两类能力接入现有 `test-design-agent`。

建议顺序：

1. 定义结构化输入
   - 在 `requirement_spec` 中补充可选的 `field_definitions` / `parameter_constraints`。
   - 明确字段类型、范围、长度、是否必填、业务阈值、来源。
2. 新增 technique metadata
   - 在测试点上增加 `technique_type`、`technique_source`、`technique_confidence`。
   - 让现有 `review_summary` 能按 technique 汇总。
3. 先做确定性 `boundary + equivalence`
   - 优先从 OpenAPI 参数、表单字段约束、页面输入控件元数据生成。
   - 结果通过 `_build_points_from_requirement_spec(...)` 合流，而不是旁路生成另一套格式。
4. 增加回归测试
   - 至少覆盖：数字区间、字符串长度、日期、金额、枚举值、必填/非必填。
   - 验证输出不仅存在，而且能正确带上 `requires_review / suggestion / source_ids / dependent_elements`。

#### P1：让这些技术真正服务企业级测试设计

1. 错误推测规则库
   - 基于历史缺陷和常见模式做规则库，不走“自由发挥式”AI。
   - 输出默认低于边界值/等价类的置信度，并建议人工抽样复核。
2. 技术覆盖统计
   - 在 `TestPointPlan` 中增加 `technique_distribution / technique_coverage`。
   - 用来评估一个页面或接口当前是否只覆盖了 happy path。
3. 有限状态转换
   - 只支持明确状态集和转移边的场景。
   - 输出要能解释“状态来源”和“缺口状态”。

#### P2：再做高复杂度设计技术

1. 因果图
   - 适用于复杂规则表、资格判定、营销规则、审批条件。
   - 需要先有规则条件 DSL 或结构化决策表。
2. 正交实验
   - 适用于组合空间很大的参数集。
   - 前提是已有稳定的参数分类和重要性权重，否则容易生成“看起来专业但不贴业务”的组合。

### 6.4 当前阶段不建议立即做的事

- 不建议先创建 6 个独立模块文件再回头想怎么接主链。
- 不建议让 LLM 自由生成边界值、等价类和状态图，再由系统勉强接收。
- 不建议把错误推测直接转成自动执行用例且默认放行。
- 不建议在缺少结构化字段输入时就推进因果图/正交实验，这样大概率文档很漂亮、落地很虚。

### 6.5 验收口径（按当前项目现实修正）

完成这份文档对应的第一阶段，不应以“6 个模块文件都存在”作为验收，而应以以下标准验收：

- `test-design-agent` 能消费结构化字段约束，而不只消费 requirement 文本。
- `design_bundle(...)` 生成的测试点中，已经能明确区分 `normal / boundary / equivalence`。
- 新增测试点能复用当前 `confidence / warnings / requires_review / review_summary / dependent_elements` 治理链路。
- 低置信度或高风险技术点能进入现有确认点体系，而不是另起一套人工审核机制。
- 单元测试能覆盖典型输入类型，并保证输出稳定可回归。

---

*文档版本：1.1*
*创建日期：2026-03-21*
*维护团队：AI Test Platform Core Team*
