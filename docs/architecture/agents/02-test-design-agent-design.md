# Test Design Agent 详细设计

> **状态**: 🔄 L2 → L4 提升中
> **优先级**: P1
> **目标成熟度**: L4（企业级）
> **预计完成**: 2026-04-18（4 周）
> **当前准确率**: ~75%
> **目标准确率**: > 85%

---

## 1. Agent 概述

### 1.1 职责定义

Test Design Agent 负责基于结构化需求设计测试点和测试场景，建立需求→测试点→用例的可追溯链路。

**核心职责**:
- 从需求规格生成测试点计划
- 设计正常/异常/边界测试场景
- 分配测试优先级（P0/P1/P2）
- 建立需求→测试点→用例追溯
- 识别覆盖缺口和冗余
- 输出去重后的测试点集合

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **场景完整** | 正常流、异常流、边界流全覆盖 |
| **可追溯** | 每个测试点可追溯到需求实体和规则 |
| **优先级驱动** | 基于风险和业务价值分配优先级 |
| **去重** | 自动识别并合并相似测试点 |
| **覆盖可见** | 覆盖矩阵清晰展示覆盖状态 |

### 1.3 在平台中的位置

```
Requirement Parser → [Test Design] → Script Generation
       ↓                    ↓              ↓
  需求规格            测试点计划        可执行脚本
                       ↓
                 追溯链路
```

### 1.4 当前实现状态与卡点

当前仓库里的 `agents/test-design-agent/src/agent.py` 已经不只是“基于需求文本拼 YAML”，而是已经开始消费测试点置信度、`requires_review`、`suggestion`、`review_reason`、`dependent_elements` 这套中间层。

这说明 Test Design Agent 的合理定位不是“纯生成器”，而是：

- 基于需求与页面语义生成测试点
- 继承页面分析和页面对象的置信度
- 把低置信度点显性化
- 输出可追溯的 review_summary
- 对回归场景优先使用稳定模板

当前卡点和下一步重点，不在“更会编故事”，而在下面三点：

1. 让测试点成为独立资产层，而不是临时中间结果。
2. 让测试点和页面元素、页面对象建立显式依赖。
3. 让 P0 / P1 测试点默认进入人工复核，而不是默认自动放行。

对企业级回归测试来说，稳定性比场景丰富度更重要。

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      Test Design Agent                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Requirement │  │   Test       │  │   Scenario   │          │
│  │   Analyzer   │→ │   Point      │→ │   Designer   │          │
│  │              │  │   Generator  │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         ↑                ↑                   ↓                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Traceability│  │  Coverage    │  │   Output     │          │
│  │   Builder     │← │   Analyzer   │← │   Assembler  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         ↓                                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Test Point Registry                          │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐  │  │
│  │  │ Test Point │  │  Priority  │  │   Deduplication    │  │  │
│  │  │   Store    │  │  Assigner  │  │     Engine         │  │  │
│  │  └────────────┘  └────────────┘  └────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────┐
                    │  Test Point     │
                    │  Plan +         │
                    │  Traceability   │
                    └─────────────────┘
```

### 2.2 模块划分

说明：以下模块划分用于表达目标模块边界，不代表当前仓库已全部存在；真实实现请以 `1.4 当前实现状态与卡点` 和实际目录为准。

当前仓库实际存在的核心入口：

- `agents/test-design-agent/src/agent.py`
- `agents/test-design-agent/src/index.py`
- `agents/test-design-agent/src/schema.py`
- `agents/test-design-agent/src/test_points.py`
- `agents/test-design-agent/src/tools/`
- `agents/test-design-agent/src/utils/`

| 模块 | 文件路径 | 职责 |
|------|---------|------|
| `agent.py` | `agents/test-design-agent/src/agent.py` | Agent 主入口 |
| `requirement_analyzer.py` | `agents/test-design-agent/src/requirement_analyzer.py` | 需求分析 |
| `test_point_generator.py` | `agents/test-design-agent/src/test_point_generator.py` | 测试点生成 |
| `scenario_designer.py` | `agents/test-design-agent/src/scenario_designer.py` | 场景设计 |
| `priority_assigner.py` | `agents/test-design-agent/src/priority_assigner.py` | 优先级分配 |
| `deduplication_engine.py` | `agents/test-design-agent/src/deduplication_engine.py` | 去重引擎 |
| `traceability_builder.py` | `agents/test-design-agent/src/traceability_builder.py` | 追溯构建 |
| `coverage_analyzer.py` | `agents/test-design-agent/src/coverage_analyzer.py` | 覆盖分析 |

---

## 3. 输入输出契约

### 3.1 输入 Schema

```python
# agents/test-design-agent/src/schema.py

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime

class TestPointType(str, Enum):
    FUNCTIONAL = "functional"
    PERFORMANCE = "performance"
    SECURITY = "security"
    COMPATIBILITY = "compatibility"
    USABILITY = "usability"

class TestScenarioType(str, Enum):
    HAPPY_PATH = "happy_path"
    ALTERNATIVE = "alternative"
    EXCEPTION = "exception"
    BOUNDARY = "boundary"
    ERROR = "error"

class Priority(str, Enum):
    P0 = "P0"  # 阻塞性，必须测试
    P1 = "P1"  # 重要，应该测试
    P2 = "P2"  # 一般，可以测试
    P3 = "P3"  # 低优先级，可选测试

class TestPoint(BaseModel):
    """测试点"""
    test_point_id: str
    title: str
    description: str
    type: TestPointType
    priority: Priority
    preconditions: List[str] = []
    test_steps: List[str] = []
    expected_results: List[str] = []
    related_entities: List[str] = []  # 关联的实体 ID
    related_rules: List[str] = []  # 关联的规则 ID
    related_requirements: List[str] = []  # 关联的需求 ID
    tags: List[str] = []
    confidence: float
    requires_review: bool = False

class TestScenario(BaseModel):
    """测试场景"""
    scenario_id: str
    title: str
    type: TestScenarioType
    test_points: List[str]  # 测试点 ID 列表
    description: str
    business_flow: str

class CoverageGap(BaseModel):
    """覆盖缺口"""
    gap_id: str
    description: str
    type: str  # entity/rule/requirement
    related_item_id: str
    severity: str  # high/medium/low
    suggestion: str

class TraceabilityLink(BaseModel):
    """追溯链路"""
    source_type: str  # requirement/entity/rule
    source_id: str
    target_type: str  # test_point
    target_id: str
    link_strength: float  # 0-1

class TestDesignInput(BaseModel):
    """Agent 输入"""
    request_id: str
    requirement_spec: Dict[str, Any]  # 来自 Requirement Parser
    existing_test_points: Optional[List[Dict]] = None  # 现有测试点（去重用）
    page_objects: Optional[List[Dict]] = None  # 可用页面对象
    coverage_goals: Optional[Dict[str, Any]] = {
        "entity_coverage": 0.9,
        "rule_coverage": 0.85,
        "requirement_coverage": 1.0
    }
    constraints: Optional[Dict[str, Any]] = {
        "max_test_points": 100,
        "time_budget_hours": 40,
        "priority_distribution": {"P0": 0.2, "P1": 0.5, "P2": 0.3}
    }
    
    class Config:
        schema_extra = {
            "example": {
                "request_id": "test-design-001",
                "requirement_spec": {
                    "spec_id": "spec-001",
                    "entities": [...],
                    "rules": [...],
                    "test_intents": [...]
                },
                "coverage_goals": {
                    "entity_coverage": 0.9
                }
            }
        }

class TestPointPlan(BaseModel):
    """测试点计划"""
    plan_id: str
    title: str
    version: str
    summary: str
    test_points: List[TestPoint]
    scenarios: List[TestScenario]
    coverage_matrix: Dict[str, Any]
    traceability: List[TraceabilityLink]
    gaps: List[CoverageGap]
    statistics: Dict[str, Any]
    design_confidence: float
    requires_review: bool
    metadata: Dict[str, Any]

class TestDesignOutput(BaseModel):
    """Agent 输出"""
    request_id: str
    test_point_plan: TestPointPlan
    design_details: Dict[str, Any] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "processing_stages": []
    }
    warnings: List[str] = []
    processing_time_ms: int
    agent_version: str
    model_used: str
    timestamp: datetime
    
    class Config:
        schema_extra = {
            "example": {
                "request_id": "test-design-001",
                "test_point_plan": {
                    "plan_id": "plan-001",
                    "test_points": [...],
                    "design_confidence": 0.85
                },
                "processing_time_ms": 5678
            }
        }
```

---

## 4. 核心功能实现

说明：本章代码块主要用于表达目标实现方式和模块边界，不代表这些模块文件已在当前仓库全部存在；当前真实可运行实现仍以 `src/agent.py`、`src/schema.py`、`src/test_points.py` 及 `src/tools/` 为主。

### 4.1 需求分析器

```python
# agents/test-design-agent/src/requirement_analyzer.py

from typing import Dict, List, Any

class RequirementAnalyzer:
    """需求分析器"""
    
    def analyze(self, requirement_spec: Dict) -> Dict[str, Any]:
        """分析需求规格，提取测试设计所需信息"""
        return {
            'entities': self._analyze_entities(requirement_spec),
            'rules': self._analyze_rules(requirement_spec),
            'test_intents': self._analyze_test_intents(requirement_spec),
            'complexity_score': self._calculate_complexity(requirement_spec),
            'risk_areas': self._identify_risk_areas(requirement_spec)
        }
    
    def _analyze_entities(self, spec: Dict) -> List[Dict]:
        """分析实体，确定测试重点"""
        entities = spec.get('entities', [])
        analyzed = []
        
        for entity in entities:
            analyzed.append({
                'entity_id': entity['entity_id'],
                'name': entity['name'],
                'type': entity['type'],
                'attribute_count': len(entity.get('attributes', [])),
                'relationship_count': len(entity.get('relationships', [])),
                'test_complexity': self._estimate_entity_complexity(entity),
                'critical_attributes': self._identify_critical_attributes(entity)
            })
        
        return analyzed
    
    def _analyze_rules(self, spec: Dict) -> List[Dict]:
        """分析规则，确定验证点"""
        rules = spec.get('rules', [])
        analyzed = []
        
        for rule in rules:
            analyzed.append({
                'rule_id': rule['rule_id'],
                'description': rule['description'],
                'type': rule.get('type', 'validation'),
                'condition_count': len(rule.get('conditions', [])),
                'action_count': len(rule.get('actions', [])),
                'priority': rule.get('priority', 'normal'),
                'testable': self._is_rule_testable(rule)
            })
        
        return analyzed
    
    def _analyze_test_intents(self, spec: Dict) -> List[Dict]:
        """分析测试意图"""
        intents = spec.get('test_intents', [])
        return [
            {
                'intent_id': intent['intent_id'],
                'description': intent['description'],
                'type': intent.get('type', 'functional'),
                'priority': intent.get('priority', 'P1'),
                'acceptance_criteria_count': len(intent.get('acceptance_criteria', []))
            }
            for intent in intents
        ]
    
    def _calculate_complexity(self, spec: Dict) -> float:
        """计算需求复杂度"""
        entity_count = len(spec.get('entities', []))
        rule_count = len(spec.get('rules', []))
        ambiguity_count = len(spec.get('ambiguities', []))
        
        # 复杂度公式
        complexity = (
            entity_count * 0.3 +
            rule_count * 0.4 +
            ambiguity_count * 0.3
        )
        
        return min(10.0, complexity)
    
    def _identify_risk_areas(self, spec: Dict) -> List[Dict]:
        """识别风险区域"""
        risks = []
        
        # 风险 1: 高歧义实体
        for entity in spec.get('entities', []):
            if entity.get('confidence', 1.0) < 0.7:
                risks.append({
                    'type': 'low_confidence_entity',
                    'item_id': entity['entity_id'],
                    'description': f'实体 {entity["name"]} 置信度低',
                    'severity': 'medium'
                })
        
        # 风险 2: 高影响歧义
        for ambiguity in spec.get('ambiguities', []):
            if ambiguity.get('impact') == 'high':
                risks.append({
                    'type': 'high_impact_ambiguity',
                    'item_id': ambiguity['ambiguity_id'],
                    'description': ambiguity['description'],
                    'severity': 'high'
                })
        
        return risks
    
    def _estimate_entity_complexity(self, entity: Dict) -> float:
        """估算实体测试复杂度"""
        attr_count = len(entity.get('attributes', []))
        rel_count = len(entity.get('relationships', []))
        
        return min(1.0, (attr_count * 0.1 + rel_count * 0.2))
    
    def _identify_critical_attributes(self, entity: Dict) -> List[str]:
        """识别关键属性"""
        critical = []
        for attr in entity.get('attributes', []):
            if attr.get('required') or attr.get('type') in ['password', 'payment', 'id']:
                critical.append(attr['name'])
        return critical
    
    def _is_rule_testable(self, rule: Dict) -> bool:
        """判断规则是否可测试"""
        conditions = rule.get('conditions', [])
        actions = rule.get('actions', [])
        
        # 有明确条件和动作的规则可测试
        return len(conditions) > 0 and len(actions) > 0
```

### 4.2 测试点生成器

```python
# agents/test-design-agent/src/test_point_generator.py

from typing import List, Dict, Any
from .schemas import TestPoint, TestPointType, Priority

class TestPointGenerator:
    """测试点生成器"""
    
    def generate(self, analyzed_requirement: Dict) -> List[TestPoint]:
        """从分析后的需求生成测试点"""
        test_points = []
        test_point_id_counter = 0
        
        # 1. 从实体生成测试点
        for entity in analyzed_requirement['entities']:
            entity_tps = self._generate_entity_test_points(entity)
            for tp in entity_tps:
                tp['test_point_id'] = f"tp-{test_point_id_counter:03d}"
                test_points.append(tp)
                test_point_id_counter += 1
        
        # 2. 从规则生成测试点
        for rule in analyzed_requirement['rules']:
            rule_tps = self._generate_rule_test_points(rule)
            for tp in rule_tps:
                tp['test_point_id'] = f"tp-{test_point_id_counter:03d}"
                test_points.append(tp)
                test_point_id_counter += 1
        
        # 3. 从测试意图生成测试点
        for intent in analyzed_requirement['test_intents']:
            intent_tps = self._generate_intent_test_points(intent)
            for tp in intent_tps:
                tp['test_point_id'] = f"tp-{test_point_id_counter:03d}"
                test_points.append(tp)
                test_point_id_counter += 1
        
        return [TestPoint(**tp) for tp in test_points]
    
    def _generate_entity_test_points(self, entity: Dict) -> List[Dict]:
        """从实体生成测试点"""
        test_points = []
        
        # 1. CRUD 测试点
        test_points.append({
            'title': f'创建{entity["name"]}实体',
            'description': f'验证可以成功创建{entity["name"]}',
            'type': TestPointType.FUNCTIONAL,
            'priority': Priority.P0,
            'test_steps': [
                f'进入{entity["name"]}创建页面',
                '填写必填字段',
                '提交表单',
                '验证创建成功'
            ],
            'related_entities': [entity['entity_id']],
            'confidence': 0.9
        })
        
        test_points.append({
            'title': f'查询{entity["name"]}实体',
            'description': f'验证可以查询到{entity["name"]}',
            'type': TestPointType.FUNCTIONAL,
            'priority': Priority.P0,
            'test_steps': [
                f'进入{entity["name"]}列表页面',
                '执行查询',
                '验证查询结果'
            ],
            'related_entities': [entity['entity_id']],
            'confidence': 0.9
        })
        
        # 2. 关键属性测试点
        for attr in entity.get('critical_attributes', []):
            test_points.append({
                'title': f'验证{entity["name"]}.{attr}字段',
                'description': f'验证{attr}字段的输入验证',
                'type': TestPointType.FUNCTIONAL,
                'priority': Priority.P1,
                'test_steps': [
                    f'进入{entity["name"]}编辑页面',
                    f'输入{attr}的有效值',
                    '提交并验证',
                    f'输入{attr}的无效值',
                    '验证错误提示'
                ],
                'related_entities': [entity['entity_id']],
                'confidence': 0.85
            })
        
        return test_points
    
    def _generate_rule_test_points(self, rule: Dict) -> List[Dict]:
        """从规则生成测试点"""
        test_points = []
        
        if not rule.get('testable', True):
            return test_points
        
        # 1. 规则满足测试点
        test_points.append({
            'title': f'验证规则：{rule["rule_id"]}',
            'description': rule['description'],
            'type': TestPointType.FUNCTIONAL,
            'priority': self._map_priority(rule.get('priority', 'normal')),
            'test_steps': [
                '设置满足规则条件的环境',
                '执行触发规则的操作',
                '验证规则动作执行'
            ],
            'related_rules': [rule['rule_id']],
            'confidence': 0.8
        })
        
        # 2. 规则违反测试点
        test_points.append({
            'title': f'验证规则违反：{rule["rule_id"]}',
            'description': f'验证违反规则{rule["rule_id"]}时的处理',
            'type': TestPointType.FUNCTIONAL,
            'priority': Priority.P1,
            'test_steps': [
                '设置违反规则条件的环境',
                '执行触发规则的操作',
                '验证错误处理'
            ],
            'related_rules': [rule['rule_id']],
            'confidence': 0.75
        })
        
        return test_points
    
    def _generate_intent_test_points(self, intent: Dict) -> List[Dict]:
        """从测试意图生成测试点"""
        test_points = []
        
        # 为每个验收标准生成测试点
        for i, criterion in enumerate(intent.get('acceptance_criteria', [])):
            test_points.append({
                'title': f'验收标准 {i+1}: {intent["intent_id"]}',
                'description': criterion,
                'type': self._map_type(intent.get('type', 'functional')),
                'priority': self._map_priority(intent.get('priority', 'P1')),
                'test_steps': [
                    '准备测试环境',
                    '执行测试操作',
                    '验证验收标准满足'
                ],
                'related_requirements': [intent['intent_id']],
                'confidence': 0.85
            })
        
        return test_points
    
    def _map_priority(self, rule_priority: str) -> Priority:
        """映射规则优先级到测试优先级"""
        mapping = {
            'critical': Priority.P0,
            'high': Priority.P0,
            'normal': Priority.P1,
            'low': Priority.P2
        }
        return mapping.get(rule_priority, Priority.P1)
    
    def _map_type(self, intent_type: str) -> TestPointType:
        """映射意图类型到测试点类型"""
        mapping = {
            'functional': TestPointType.FUNCTIONAL,
            'performance': TestPointType.PERFORMANCE,
            'security': TestPointType.SECURITY,
            'compatibility': TestPointType.COMPATIBILITY
        }
        return mapping.get(intent_type, TestPointType.FUNCTIONAL)
```

### 4.3 场景设计器

```python
# agents/test-design-agent/src/scenario_designer.py

from typing import List, Dict
from .schemas import TestPoint, TestScenario, TestScenarioType

class ScenarioDesigner:
    """场景设计器"""
    
    def design(self, test_points: List[TestPoint]) -> List[TestScenario]:
        """将测试点组织成测试场景"""
        scenarios = []
        scenario_id_counter = 0
        
        # 1. 正常流场景
        happy_path_tps = [tp for tp in test_points if tp.priority.value == 'P0']
        if happy_path_tps:
            scenarios.append(TestScenario(
                scenario_id=f"scn-{scenario_id_counter:03d}",
                title="正常业务流程",
                type=TestScenarioType.HAPPY_PATH,
                test_points=[tp.test_point_id for tp in happy_path_tps],
                description="验证主要业务流程的正常执行",
                business_flow=self._describe_flow(happy_path_tps)
            ))
            scenario_id_counter += 1
        
        # 2. 异常流场景
        exception_tps = [tp for tp in test_points if '异常' in tp.title or '错误' in tp.title]
        if exception_tps:
            scenarios.append(TestScenario(
                scenario_id=f"scn-{scenario_id_counter:03d}",
                title="异常处理流程",
                type=TestScenarioType.EXCEPTION,
                test_points=[tp.test_point_id for tp in exception_tps],
                description="验证系统在异常情况下的处理",
                business_flow=self._describe_flow(exception_tps)
            ))
            scenario_id_counter += 1
        
        # 3. 边界场景
        boundary_tps = [tp for tp in test_points if '边界' in tp.title or '最大' in tp.title or '最小' in tp.title]
        if boundary_tps:
            scenarios.append(TestScenario(
                scenario_id=f"scn-{scenario_id_counter:03d}",
                title="边界值场景",
                type=TestScenarioType.BOUNDARY,
                test_points=[tp.test_point_id for tp in boundary_tps],
                description="验证边界条件下的系统行为",
                business_flow=self._describe_flow(boundary_tps)
            ))
            scenario_id_counter += 1
        
        return scenarios
    
    def _describe_flow(self, test_points: List[TestPoint]) -> str:
        """描述业务流程"""
        steps = []
        for tp in test_points[:5]:  # 限制步骤数量
            steps.extend(tp.test_steps[:2])
        return ' → '.join(steps[:10])
```

### 4.4 去重引擎

```python
# agents/test-design-agent/src/deduplication_engine.py

from typing import List, Dict
from .schemas import TestPoint
import hashlib

class DeduplicationEngine:
    """测试点去重引擎"""
    
    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold
    
    def deduplicate(self, test_points: List[TestPoint], 
                   existing_points: List[Dict] = None) -> List[TestPoint]:
        """去重测试点"""
        if not test_points:
            return []
        
        # 1. 计算每个测试点的指纹
        fingerprint_map = {}
        for tp in test_points:
            fp = self._calculate_fingerprint(tp)
            if fp not in fingerprint_map:
                fingerprint_map[fp] = []
            fingerprint_map[fp].append(tp)
        
        # 2. 合并相似测试点
        deduplicated = []
        for fp, similar_tps in fingerprint_map.items():
            if len(similar_tps) == 1:
                deduplicated.append(similar_tps[0])
            else:
                # 合并相似测试点
                merged = self._merge_test_points(similar_tps)
                deduplicated.append(merged)
        
        # 3. 与现有测试点对比
        if existing_points:
            deduplicated = self._filter_existing(deduplicated, existing_points)
        
        return deduplicated
    
    def _calculate_fingerprint(self, tp: TestPoint) -> str:
        """计算测试点指纹"""
        # 基于标题和描述的关键信息
        content = f"{tp.title}:{tp.description}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _merge_test_points(self, similar_tps: List[TestPoint]) -> TestPoint:
        """合并相似测试点"""
        # 选择第一个作为基础
        base = similar_tps[0]
        
        # 合并测试步骤
        all_steps = []
        for tp in similar_tps:
            all_steps.extend(tp.test_steps)
        
        # 去重步骤
        unique_steps = list(dict.fromkeys(all_steps))
        
        # 创建合并后的测试点
        return TestPoint(
            test_point_id=base.test_point_id,
            title=base.title,
            description=base.description,
            type=base.type,
            priority=base.priority,
            preconditions=base.preconditions,
            test_steps=unique_steps,
            expected_results=base.expected_results,
            related_entities=list(set(base.related_entities)),
            related_rules=list(set(base.related_rules)),
            related_requirements=list(set(base.related_requirements)),
            tags=list(set(base.tags)),
            confidence=base.confidence,
            requires_review=any(tp.requires_review for tp in similar_tps)
        )
    
    def _filter_existing(self, new_points: List[TestPoint], 
                        existing_points: List[Dict]) -> List[TestPoint]:
        """过滤已存在的测试点"""
        existing_fps = set()
        for ep in existing_points:
            content = f"{ep.get('title', '')}:{ep.get('description', '')}"
            fp = hashlib.md5(content.encode()).hexdigest()
            existing_fps.add(fp)
        
        filtered = []
        for tp in new_points:
            fp = self._calculate_fingerprint(tp)
            if fp not in existing_fps:
                filtered.append(tp)
        
        return filtered
```

### 4.5 追溯构建器

```python
# agents/test-design-agent/src/traceability_builder.py

from typing import List, Dict
from .schemas import TestPoint, TraceabilityLink

class TraceabilityBuilder:
    """追溯链路构建器"""
    
    def build(self, test_points: List[TestPoint]) -> List[TraceabilityLink]:
        """构建需求→测试点追溯链路"""
        links = []
        
        for tp in test_points:
            # 1. 实体→测试点链路
            for entity_id in tp.related_entities:
                links.append(TraceabilityLink(
                    source_type='entity',
                    source_id=entity_id,
                    target_type='test_point',
                    target_id=tp.test_point_id,
                    link_strength=0.9
                ))
            
            # 2. 规则→测试点链路
            for rule_id in tp.related_rules:
                links.append(TraceabilityLink(
                    source_type='rule',
                    source_id=rule_id,
                    target_type='test_point',
                    target_id=tp.test_point_id,
                    link_strength=0.85
                ))
            
            # 3. 需求→测试点链路
            for req_id in tp.related_requirements:
                links.append(TraceabilityLink(
                    source_type='requirement',
                    source_id=req_id,
                    target_type='test_point',
                    target_id=tp.test_point_id,
                    link_strength=0.95
                ))
        
        return links
```

### 4.6 覆盖分析器

```python
# agents/test-design-agent/src/coverage_analyzer.py

from typing import List, Dict
from .schemas import TestPoint, TraceabilityLink, CoverageGap

class CoverageAnalyzer:
    """覆盖分析器"""
    
    def analyze(self, test_points: List[TestPoint], 
               links: List[TraceabilityLink],
               requirement_spec: Dict,
               coverage_goals: Dict) -> Dict:
        """分析测试覆盖"""
        return {
            'entity_coverage': self._analyze_entity_coverage(test_points, links, requirement_spec),
            'rule_coverage': self._analyze_rule_coverage(test_points, links, requirement_spec),
            'requirement_coverage': self._analyze_requirement_coverage(test_points, links, requirement_spec),
            'gaps': self._identify_gaps(test_points, links, requirement_spec, coverage_goals),
            'statistics': self._calculate_statistics(test_points)
        }
    
    def _analyze_entity_coverage(self, test_points: List, links: List, spec: Dict) -> Dict:
        """分析实体覆盖"""
        entities = spec.get('entities', [])
        covered_entities = set()
        
        for link in links:
            if link.source_type == 'entity':
                covered_entities.add(link.source_id)
        
        total = len(entities)
        covered = len(covered_entities)
        
        return {
            'total': total,
            'covered': covered,
            'coverage_rate': covered / total if total > 0 else 0,
            'uncovered': [e['entity_id'] for e in entities if e['entity_id'] not in covered_entities]
        }
    
    def _analyze_rule_coverage(self, test_points: List, links: List, spec: Dict) -> Dict:
        """分析规则覆盖"""
        rules = spec.get('rules', [])
        covered_rules = set()
        
        for link in links:
            if link.source_type == 'rule':
                covered_rules.add(link.source_id)
        
        total = len(rules)
        covered = len(covered_rules)
        
        return {
            'total': total,
            'covered': covered,
            'coverage_rate': covered / total if total > 0 else 0,
            'uncovered': [r['rule_id'] for r in rules if r['rule_id'] not in covered_rules]
        }
    
    def _analyze_requirement_coverage(self, test_points: List, links: List, spec: Dict) -> Dict:
        """分析需求覆盖"""
        intents = spec.get('test_intents', [])
        covered_intents = set()
        
        for link in links:
            if link.source_type == 'requirement':
                covered_intents.add(link.source_id)
        
        total = len(intents)
        covered = len(covered_intents)
        
        return {
            'total': total,
            'covered': covered,
            'coverage_rate': covered / total if total > 0 else 0,
            'uncovered': [i['intent_id'] for i in intents if i['intent_id'] not in covered_intents]
        }
    
    def _identify_gaps(self, test_points: List, links: List, 
                      spec: Dict, goals: Dict) -> List[CoverageGap]:
        """识别覆盖缺口"""
        gaps = []
        gap_id_counter = 0
        
        # 检查实体覆盖缺口
        entity_coverage = self._analyze_entity_coverage(test_points, links, spec)
        if entity_coverage['coverage_rate'] < goals.get('entity_coverage', 0.9):
            for uncovered_id in entity_coverage['uncovered']:
                gaps.append(CoverageGap(
                    gap_id=f"gap-{gap_id_counter:03d}",
                    description=f'实体 {uncovered_id} 无测试覆盖',
                    type='entity',
                    related_item_id=uncovered_id,
                    severity='high',
                    suggestion=f'为实体 {uncovered_id} 添加测试点'
                ))
                gap_id_counter += 1
        
        # 检查规则覆盖缺口
        rule_coverage = self._analyze_rule_coverage(test_points, links, spec)
        if rule_coverage['coverage_rate'] < goals.get('rule_coverage', 0.85):
            for uncovered_id in rule_coverage['uncovered']:
                gaps.append(CoverageGap(
                    gap_id=f"gap-{gap_id_counter:03d}",
                    description=f'规则 {uncovered_id} 无测试覆盖',
                    type='rule',
                    related_item_id=uncovered_id,
                    severity='medium',
                    suggestion=f'为规则 {uncovered_id} 添加验证测试点'
                ))
                gap_id_counter += 1
        
        return gaps
    
    def _calculate_statistics(self, test_points: List) -> Dict:
        """计算统计信息"""
        priority_dist = {}
        type_dist = {}
        
        for tp in test_points:
            # 优先级分布
            p = tp.priority.value
            priority_dist[p] = priority_dist.get(p, 0) + 1
            
            # 类型分布
            t = tp.type.value
            type_dist[t] = type_dist.get(t, 0) + 1
        
        return {
            'total_test_points': len(test_points),
            'priority_distribution': priority_dist,
            'type_distribution': type_dist,
            'average_confidence': sum(tp.confidence for tp in test_points) / len(test_points) if test_points else 0
        }
```

---

## 5. Agent 主实现

```python
# agents/test-design-agent/src/agent.py

import time
from datetime import datetime
from typing import Dict, Any

from .schemas import (
    TestDesignInput,
    TestDesignOutput,
    TestPointPlan
)
from .requirement_analyzer import RequirementAnalyzer
from .test_point_generator import TestPointGenerator
from .scenario_designer import ScenarioDesigner
from .deduplication_engine import DeduplicationEngine
from .traceability_builder import TraceabilityBuilder
from .coverage_analyzer import CoverageAnalyzer

class TestDesignAgent:
    """Test Design Agent 主类"""
    
    VERSION = "0.1.0"
    MODEL_USED = "qwen-3.5-plus"
    
    def __init__(self):
        self.analyzer = RequirementAnalyzer()
        self.generator = TestPointGenerator()
        self.designer = ScenarioDesigner()
        self.deduplicator = DeduplicationEngine()
        self.traceability_builder = TraceabilityBuilder()
        self.coverage_analyzer = CoverageAnalyzer()
        self.token_usage = {'prompt': 0, 'completion': 0}
    
    async def design(self, input_data: TestDesignInput) -> TestDesignOutput:
        """设计测试"""
        start_time = time.time()
        processing_stages = []
        
        # Stage 1: 需求分析
        analyzed = self.analyzer.analyze(input_data.requirement_spec)
        processing_stages.append({
            'stage': 'requirement_analysis',
            'status': 'completed',
            'entity_count': len(analyzed['entities']),
            'rule_count': len(analyzed['rules'])
        })
        
        # Stage 2: 测试点生成
        test_points = self.generator.generate(analyzed)
        processing_stages.append({
            'stage': 'test_point_generation',
            'status': 'completed',
            'test_point_count': len(test_points)
        })
        
        # Stage 3: 去重
        deduplicated_points = self.deduplicator.deduplicate(
            test_points,
            input_data.existing_test_points
        )
        processing_stages.append({
            'stage': 'deduplication',
            'status': 'completed',
            'removed_count': len(test_points) - len(deduplicated_points)
        })
        
        # Stage 4: 场景设计
        scenarios = self.designer.design(deduplicated_points)
        processing_stages.append({
            'stage': 'scenario_design',
            'status': 'completed',
            'scenario_count': len(scenarios)
        })
        
        # Stage 5: 追溯构建
        links = self.traceability_builder.build(deduplicated_points)
        processing_stages.append({
            'stage': 'traceability_building',
            'status': 'completed',
            'link_count': len(links)
        })
        
        # Stage 6: 覆盖分析
        coverage = self.coverage_analyzer.analyze(
            deduplicated_points,
            links,
            input_data.requirement_spec,
            input_data.coverage_goals or {}
        )
        processing_stages.append({
            'stage': 'coverage_analysis',
            'status': 'completed',
            'gap_count': len(coverage['gaps'])
        })
        
        # Stage 7: 组装计划
        plan = TestPointPlan(
            plan_id=f"plan-{input_data.request_id}",
            title=input_data.requirement_spec.get('title', 'Test Plan'),
            version="1.0",
            summary=self._generate_summary(deduplicated_points),
            test_points=deduplicated_points,
            scenarios=scenarios,
            coverage_matrix=coverage,
            traceability=links,
            gaps=coverage['gaps'],
            statistics=coverage['statistics'],
            design_confidence=self._calculate_confidence(deduplicated_points, coverage),
            requires_review=self._requires_review(deduplicated_points, coverage),
            metadata={
                'source_spec_id': input_data.requirement_spec.get('spec_id'),
                'constraints': input_data.constraints
            }
        )
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        return TestDesignOutput(
            request_id=input_data.request_id,
            test_point_plan=plan,
            design_details={
                'input_tokens': self.token_usage['prompt'],
                'output_tokens': self.token_usage['completion'],
                'processing_stages': processing_stages
            },
            warnings=self._generate_warnings(plan),
            processing_time_ms=processing_time_ms,
            agent_version=self.VERSION,
            model_used=self.MODEL_USED,
            timestamp=datetime.now()
        )
    
    def _generate_summary(self, test_points) -> str:
        """生成计划摘要"""
        return f"共 {len(test_points)} 个测试点，覆盖 {len(set(tp.related_entities for tp in test_points))} 个实体"
    
    def _calculate_confidence(self, test_points, coverage) -> float:
        """计算设计置信度"""
        if not test_points:
            return 0.0
        
        avg_confidence = sum(tp.confidence for tp in test_points) / len(test_points)
        coverage_rate = coverage['statistics'].get('average_confidence', 0)
        
        return (avg_confidence + coverage_rate) / 2
    
    def _requires_review(self, test_points, coverage) -> bool:
        """判断是否需要人工审核"""
        # 有覆盖缺口
        if len(coverage['gaps']) > 0:
            return True
        
        # 置信度过低
        if self._calculate_confidence(test_points, coverage) < 0.7:
            return True
        
        # P0 比例异常
        p0_count = sum(1 for tp in test_points if tp.priority.value == 'P0')
        if p0_count > len(test_points) * 0.5:
            return True
        
        return False
    
    def _generate_warnings(self, plan: TestPointPlan) -> list:
        """生成警告"""
        warnings = []
        
        if plan.statistics['total_test_points'] == 0:
            warnings.append('未生成任何测试点')
        
        if len(plan.gaps) > 5:
            warnings.append(f'覆盖缺口较多 ({len(plan.gaps)}个)')
        
        if plan.design_confidence < 0.7:
            warnings.append(f'设计置信度较低 ({plan.design_confidence:.2f})')
        
        return warnings
```

---

## 6. 测试策略

说明：以下测试代码既包含目标补强方向，也包含推荐的 Golden Set 形态；当前仓库里真实存在的测试请优先看 `agents/test-design-agent/tests/test_enterprise_design.py` 与 `agents/test-design-agent/tests/test_stable_generation_rules.py`。

### 6.1 单元测试

```python
# agents/test-design-agent/tests/test_test_point_generator.py

import pytest
from src.test_point_generator import TestPointGenerator

class TestTestPointGenerator:
    def test_generate_entity_test_points(self):
        generator = TestPointGenerator()
        entity = {
            'entity_id': 'ent-001',
            'name': '用户',
            'type': 'user',
            'critical_attributes': ['username', 'password']
        }
        
        test_points = generator._generate_entity_test_points(entity)
        
        assert len(test_points) >= 2
        assert any('创建' in tp['title'] for tp in test_points)
        assert any('查询' in tp['title'] for tp in test_points)
    
    def test_generate_rule_test_points(self):
        generator = TestPointGenerator()
        rule = {
            'rule_id': 'rule-001',
            'description': '用户年龄必须大于 18 岁',
            'testable': True,
            'priority': 'high'
        }
        
        test_points = generator._generate_rule_test_points(rule)
        
        assert len(test_points) >= 1
        assert any('规则' in tp['title'] for tp in test_points)
```

### 6.2 Golden Test Set

```python
# agents/test-design-agent/tests/golden_tests.py

import pytest
from src.agent import TestDesignAgent
from src.schemas import TestDesignInput

GOLDEN_TEST_CASES = [
    {
        'name': '简单需求测试设计',
        'input': TestDesignInput(
            request_id='golden-td-001',
            requirement_spec={
                'spec_id': 'spec-001',
                'title': '用户登录',
                'entities': [
                    {'entity_id': 'ent-001', 'name': '用户', 'type': 'user'}
                ],
                'rules': [],
                'test_intents': []
            }
        ),
        'expected': {
            'min_test_points': 2,
            'min_scenarios': 1,
            'min_confidence': 0.6
        }
    }
]

@pytest.mark.parametrize('test_case', GOLDEN_TEST_CASES)
@pytest.mark.asyncio
async def test_golden_cases(test_case):
    agent = TestDesignAgent()
    output = await agent.design(test_case['input'])
    
    assert len(output.test_point_plan.test_points) >= test_case['expected']['min_test_points']
    assert len(output.test_point_plan.scenarios) >= test_case['expected']['min_scenarios']
    assert output.test_point_plan.design_confidence >= test_case['expected']['min_confidence']
```

---

## 7. 实施计划

### Phase 1: 基础框架（Week 1-2）

| 任务 | 预计 | 状态 |
|------|------|------|
| 项目结构搭建 | 2 天 | ⏳ |
| 输入输出 Schema 定义 | 2 天 | ⏳ |
| 需求分析器实现 | 2 天 | ⏳ |
| 测试点生成器实现 | 3 天 | ⏳ |
| 单元测试框架 | 1 天 | ⏳ |

### Phase 2: 核心能力（Week 3-4）

| 任务 | 预计 | 状态 |
|------|------|------|
| 场景设计器实现 | 2 天 | ⏳ |
| 去重引擎实现 | 2 天 | ⏳ |
| 追溯构建器实现 | 2 天 | ⏳ |
| 覆盖分析器实现 | 2 天 | ⏳ |
| Agent 主逻辑 | 3 天 | ⏳ |
| 集成测试 | 2 天 | ⏳ |

### Phase 3: 企业级能力（Week 5-6）

| 任务 | 预计 | 状态 |
|------|------|------|
| 测试点中间层完善 | 3 天 | ⏳ |
| Golden Test Set 建立 | 2 天 | ⏳ |
| 监控指标接入 | 2 天 | ⏳ |
| 文档完善 | 2 天 | ⏳ |
| 验收测试 | 1 天 | ⏳ |

---

## 8. 验收标准

### 功能验收

- [ ] 测试点生成覆盖率 > 90%
- [ ] 场景完整性 > 85%
- [ ] 优先级分配与人工一致性 > 85%
- [ ] 去重后重复率 < 5%
- [ ] 追溯 100% 可追溯

### 质量验收

- [ ] 单元测试覆盖率 > 85%
- [ ] Golden Test Set 通过率 > 85%
- [ ] P95 延迟 < 10s
- [ ] 设计置信度校准 > 0.70

### 运维验收

- [ ] 结构化日志输出
- [ ] Prometheus 指标接入
- [ ] 告警规则配置
- [ ] 灰度发布流程验证

---

*文档版本：1.0*
*创建日期：2026-03-21*
*最后更新：2026-03-21*
*维护团队：AI Quality Assurance Platform Core Team*
