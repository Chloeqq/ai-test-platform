# Failure Triage Agent 详细设计

> **状态**: ⏳ L3 → L4 提升中
> **优先级**: P2
> **目标成熟度**: L4（企业级）
> **预计完成**: 2026-04-25（2 周）
> **当前准确率**: ~85%
> **目标准确率**: > 90%

---

## 1. Agent 概述

### 1.1 职责定义

Failure Triage Agent 负责对失败进行分类路由，确定责任团队、严重程度、队列优先级，并自动创建/更新缺陷票据。

**核心职责**:
- 严重程度判定（critical/major/minor）
- 责任团队路由
- 队列优先级排序
- 升级识别
- 票据自动创建/更新
- 路由可解释性

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **准确路由** | 路由准确率 > 85%，减少转手 |
| **严重性保守** | 宁可高估严重性，不可低估 |
| **可解释** | 每个路由决策都有依据 |
| **自动化** | 票据自动创建，减少人工 |
| **升级及时** | 识别需要升级的场景 |

### 1.3 在平台中的位置

```
Failure Analysis → [Failure Triage] → Ticket System
       ↓              ↓                    ↓
   失败分析      责任分配            Jira/GitHub
   报告          严重程度            自动创建/更新
```

### 1.4 当前实现状态与卡点

当前仓库里的 `agents/failure-triage-agent/src/agent.py` 已经是可运行实现，因此这份文档不应被理解为“从零设计一个还不存在的 Agent”。

更准确的理解方式是：

1. 当前已经具备基础的分级、路由、责任建议和聚类相关输出。
2. 当前更像“可用的分诊与路由器”，还不是完整的企业级缺陷协同中心。
3. 这个 Agent 的质量高度依赖上游 `failure-analysis-agent` 的分类和归因质量。
4. 后续最值得补的不是把它做得更复杂，而是先把下面几件事压实：
   - 路由依据可解释
   - 严重程度与业务上下文绑定
   - 票据系统集成与幂等更新
   - 与失败聚类、历史案例的稳定联动

这意味着本文应被视为：

**“已部分落地的 Failure Triage Agent 的企业级增强设计稿”**，而不是“当前已全部满足的实现说明”。

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Failure Triage Agent                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Failure    │  │   Severity   │  │  Ownership   │          │
│  │   Analyzer   │→ │   Assessor   │→ │   Resolver   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         ↑                ↑                   ↓                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Ticket     │  │   Priority   │  │  Escalation  │          │
│  │   Creator    │← │   Assigner   │← │   Detector   │          │
│  │              │  │              │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         ↓                                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Integration Adapters                         │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐  │  │
│  │  │   Jira     │  │   GitHub   │  │      Custom        │  │  │
│  │  │  Adapter   │  │   Adapter  │  │      Adapter       │  │  │
│  │  └────────────┘  └────────────┘  └────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────┐
                    │  Triage Report  │
                    │  + Ticket Info  │
                    └─────────────────┘
```

### 2.2 模块划分

说明：以下模块划分用于表达目标模块边界，不代表当前仓库已全部存在；真实实现请以 `1.4 当前实现状态与卡点` 和实际目录为准。

当前仓库实际存在的核心入口：

- `agents/failure-triage-agent/src/agent.py`
- `agents/failure-triage-agent/src/index.py`
- `agents/failure-triage-agent/src/schema.py`
- `agents/failure-triage-agent/src/tools/`
- `agents/failure-triage-agent/src/utils/`

| 模块 | 文件路径 | 职责 |
|------|---------|------|
| `agent.py` | `agents/failure-triage-agent/src/agent.py` | Agent 主入口 |
| `failure_analyzer.py` | `agents/failure-triage-agent/src/failure_analyzer.py` | 失败分析 |
| `severity_assessor.py` | `agents/failure-triage-agent/src/severity_assessor.py` | 严重性评估 |
| `ownership_resolver.py` | `agents/failure-triage-agent/src/ownership_resolver.py` | 责任归属解析 |
| `priority_assigner.py` | `agents/failure-triage-agent/src/priority_assigner.py` | 优先级分配 |
| `escalation_detector.py` | `agents/failure-triage-agent/src/escalation_detector.py` | 升级检测 |
| `ticket_creator.py` | `agents/failure-triage-agent/src/ticket_creator.py` | 票据创建 |
| `adapters/` | `agents/failure-triage-agent/src/adapters/` | 票据系统适配器 |

---

## 3. 输入输出契约

### 3.1 输入 Schema

```python
# agents/failure-triage-agent/src/schema.py

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime

class Severity(str, Enum):
    CRITICAL = "critical"  # P0 - 阻塞发布
    MAJOR = "major"        # P1 - 重要功能
    MINOR = "minor"        # P2 - 一般问题
    TRIVIAL = "trivial"    # P3 - 轻微问题

class QueuePriority(str, Enum):
    URGENT = "urgent"      # 立即处理
    HIGH = "high"          # 今天处理
    NORMAL = "normal"      # 本周处理
    LOW = "low"            # 有空处理

class TicketAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    REOPEN = "reopen"
    CLOSE = "close"
    NO_ACTION = "no_action"

class TeamInfo(BaseModel):
    """团队信息"""
    team_id: str
    team_name: str
    members: List[str]
    on_call: Optional[str] = None
    slack_channel: Optional[str] = None

class FailureContext(BaseModel):
    """失败上下文"""
    failure_analysis_id: str
    failure_category: str
    likely_cause: str
    test_case_id: str
    test_title: str
    first_seen: datetime
    occurrence_count: int
    affected_users: int = 0
    is_blocking_release: bool = False

class TeamStructure(BaseModel):
    """团队结构"""
    teams: List[TeamInfo]
    component_ownership: Dict[str, str]  # component -> team_id
    module_ownership: Dict[str, str]     # module -> team_id

class TicketSystemConfig(BaseModel):
    """票据系统配置"""
    system_type: str = "jira"  # jira/github/custom
    project_key: str = "TEST"
    default_assignee: Optional[str] = None
    custom_fields: Dict[str, Any] = {}

class FailureTriageInput(BaseModel):
    """Agent 输入"""
    request_id: str
    failure_context: FailureContext
    team_structure: TeamStructure
    ownership_rules: Optional[Dict] = None
    severity_criteria: Optional[Dict] = None
    ticket_system_config: Optional[TicketSystemConfig] = None
    
    class Config:
        schema_extra = {
            "example": {
                "request_id": "triage-001",
                "failure_context": {
                    "failure_category": "locator_not_found",
                    "test_title": "用户登录测试",
                    "occurrence_count": 1
                },
                "team_structure": {
                    "teams": [
                        {"team_id": "team-frontend", "team_name": "前端团队"}
                    ]
                }
            }
        }

class TriageDecision(BaseModel):
    """分类决策"""
    severity: Severity
    owner_team: str
    owner_team_name: str
    assigned_to: Optional[str] = None
    queue_priority: QueuePriority
    ticket_action: TicketAction
    ticket_id: Optional[str] = None
    escalation_required: bool = False
    escalation_reason: Optional[str] = None
    triage_confidence: float
    routing_rationale: str
    sla_hours: int

class FailureTriageOutput(BaseModel):
    """Agent 输出"""
    request_id: str
    triage_decision: TriageDecision
    ticket_info: Optional[Dict] = None
    notifications: List[Dict] = []
    warnings: List[str] = []
    processing_time_ms: int
    agent_version: str
    timestamp: datetime
    
    class Config:
        schema_extra = {
            "example": {
                "request_id": "triage-001",
                "triage_decision": {
                    "severity": "major",
                    "owner_team": "team-frontend",
                    "queue_priority": "high",
                    "ticket_action": "create"
                }
            }
        }
```

---

## 4. 核心功能实现

说明：本章代码块主要用于表达目标实现方式和模块边界，不代表这些模块文件已在当前仓库全部落地；当前真实实现仍以 `src/agent.py`、`src/schema.py`、`src/tools/` 和 `src/utils/` 为主。

### 4.1 严重性评估器

```python
# agents/failure-triage-agent/src/severity_assessor.py

from typing import Dict, List, Any

class SeverityAssessor:
    """严重性评估器"""
    
    DEFAULT_CRITERIA = {
        'critical': {
            'conditions': [
                {'field': 'is_blocking_release', 'operator': 'eq', 'value': True},
                {'field': 'occurrence_count', 'operator': 'gt', 'value': 10},
                {'field': 'affected_users', 'operator': 'gt', 'value': 1000}
            ],
            'logic': 'any'  # any/all
        },
        'major': {
            'conditions': [
                {'field': 'occurrence_count', 'operator': 'gt', 'value': 5},
                {'field': 'affected_users', 'operator': 'gt', 'value': 100},
                {'field': 'failure_category', 'operator': 'in', 
                 'value': ['assertion_failed', 'application_error']}
            ],
            'logic': 'any'
        },
        'minor': {
            'conditions': [
                {'field': 'occurrence_count', 'operator': 'gt', 'value': 1},
                {'field': 'failure_category', 'operator': 'in',
                 'value': ['locator_not_found', 'timeout']}
            ],
            'logic': 'any'
        }
    }
    
    def assess(self, failure_context: Dict, 
               custom_criteria: Dict = None) -> Dict[str, Any]:
        """评估失败严重程度"""
        criteria = {**self.DEFAULT_CRITERIA, **(custom_criteria or {})}
        
        # 从高到低检查
        for severity in ['critical', 'major', 'minor']:
            if self._matches_severity(failure_context, criteria[severity]):
                return {
                    'severity': severity,
                    'confidence': self._calculate_confidence(failure_context, severity),
                    'matching_conditions': self._get_matching_conditions(
                        failure_context, criteria[severity]
                    )
                }
        
        # 默认 trivial
        return {
            'severity': 'trivial',
            'confidence': 0.8,
            'matching_conditions': []
        }
    
    def _matches_severity(self, context: Dict, criteria: Dict) -> bool:
        """检查是否匹配严重程度"""
        conditions = criteria.get('conditions', [])
        logic = criteria.get('logic', 'any')
        
        if not conditions:
            return False
        
        results = [self._evaluate_condition(context, cond) for cond in conditions]
        
        if logic == 'all':
            return all(results)
        else:  # any
            return any(results)
    
    def _evaluate_condition(self, context: Dict, condition: Dict) -> bool:
        """评估单个条件"""
        field = condition.get('field')
        operator = condition.get('operator')
        expected = condition.get('value')
        
        actual = context.get(field)
        
        if operator == 'eq':
            return actual == expected
        elif operator == 'ne':
            return actual != expected
        elif operator == 'gt':
            return actual > expected
        elif operator == 'gte':
            return actual >= expected
        elif operator == 'lt':
            return actual < expected
        elif operator == 'lte':
            return actual <= expected
        elif operator == 'in':
            return actual in expected
        elif operator == 'contains':
            return expected in str(actual)
        
        return False
    
    def _calculate_confidence(self, context: Dict, severity: str) -> float:
        """计算置信度"""
        confidence = 0.5
        
        # 发生次数越多置信度越高
        occurrence = context.get('occurrence_count', 1)
        if occurrence > 10:
            confidence += 0.3
        elif occurrence > 5:
            confidence += 0.2
        elif occurrence > 1:
            confidence += 0.1
        
        # 阻塞发布置信度高
        if context.get('is_blocking_release'):
            confidence += 0.2
        
        return min(1.0, confidence)
    
    def _get_matching_conditions(self, context: Dict, criteria: Dict) -> List[str]:
        """获取匹配的条件说明"""
        matching = []
        for cond in criteria.get('conditions', []):
            if self._evaluate_condition(context, cond):
                matching.append(f"{cond['field']} {cond['operator']} {cond['value']}")
        return matching
```

### 4.2 责任归属解析器

```python
# agents/failure-triage-agent/src/ownership_resolver.py

from typing import Dict, List, Any

class OwnershipResolver:
    """责任归属解析器"""
    
    def resolve(self, failure_context: Dict, team_structure: Dict,
                ownership_rules: Dict = None) -> Dict[str, Any]:
        """解析责任归属"""
        rules = ownership_rules or self._get_default_rules()
        
        # 1. 基于组件匹配
        team_id = self._match_by_component(failure_context, team_structure, rules)
        if team_id:
            return self._build_result(team_id, team_structure, 'component')
        
        # 2. 基于模块匹配
        team_id = self._match_by_module(failure_context, team_structure, rules)
        if team_id:
            return self._build_result(team_id, team_structure, 'module')
        
        # 3. 基于失败类型匹配
        team_id = self._match_by_failure_type(failure_context, team_structure, rules)
        if team_id:
            return self._build_result(team_id, team_structure, 'failure_type')
        
        # 4. 默认团队
        default_team = self._get_default_team(team_structure)
        return self._build_result(default_team, team_structure, 'default')
    
    def _get_default_rules(self) -> Dict:
        """获取默认规则"""
        return {
            'component_mapping': {
                'auth': 'team-backend',
                'user': 'team-backend',
                'payment': 'team-payment',
                'order': 'team-order',
                'frontend': 'team-frontend',
                'ui': 'team-frontend'
            },
            'module_mapping': {
                'api': 'team-backend',
                'web': 'team-frontend',
                'mobile': 'team-mobile'
            },
            'failure_type_mapping': {
                'locator_not_found': 'team-frontend',
                'assertion_failed': 'team-qa',
                'api_error': 'team-backend',
                'network_error': 'team-infra'
            }
        }
    
    def _match_by_component(self, context: Dict, team_structure: Dict,
                            rules: Dict) -> str:
        """基于组件匹配"""
        test_title = context.get('test_title', '').lower()
        
        for component, team_id in rules.get('component_mapping', {}).items():
            if component in test_title:
                return team_id
        
        return None
    
    def _match_by_module(self, context: Dict, team_structure: Dict,
                         rules: Dict) -> str:
        """基于模块匹配"""
        # 从测试文件路径提取模块
        test_file = context.get('test_file', '')
        
        for module, team_id in rules.get('module_mapping', {}).items():
            if module in test_file.lower():
                return team_id
        
        return None
    
    def _match_by_failure_type(self, context: Dict, team_structure: Dict,
                               rules: Dict) -> str:
        """基于失败类型匹配"""
        failure_category = context.get('failure_category', '')
        
        return rules.get('failure_type_mapping', {}).get(failure_category)
    
    def _get_default_team(self, team_structure: Dict) -> str:
        """获取默认团队"""
        teams = team_structure.get('teams', [])
        if teams:
            return teams[0]['team_id']
        return 'unassigned'
    
    def _build_result(self, team_id: str, team_structure: Dict,
                      match_type: str) -> Dict:
        """构建结果"""
        team_info = self._find_team(team_id, team_structure)
        
        return {
            'team_id': team_id,
            'team_name': team_info.get('team_name', 'Unknown'),
            'match_type': match_type,
            'confidence': self._calculate_confidence(match_type),
            'on_call': team_info.get('on_call'),
            'slack_channel': team_info.get('slack_channel')
        }
    
    def _find_team(self, team_id: str, team_structure: Dict) -> Dict:
        """查找团队信息"""
        for team in team_structure.get('teams', []):
            if team['team_id'] == team_id:
                return team
        return {}
    
    def _calculate_confidence(self, match_type: str) -> float:
        """计算置信度"""
        confidence_map = {
            'component': 0.9,
            'module': 0.8,
            'failure_type': 0.7,
            'default': 0.5
        }
        return confidence_map.get(match_type, 0.5)
```

### 4.3 优先级分配器

```python
# agents/failure-triage-agent/src/priority_assigner.py

from typing import Dict, List, Any

class PriorityAssigner:
    """优先级分配器"""
    
    def assign(self, severity: str, context: Dict,
               team_info: Dict) -> Dict[str, Any]:
        """分配队列优先级"""
        # 基础优先级由严重程度决定
        base_priority = self._severity_to_priority(severity)
        
        # 调整因素
        adjustments = self._calculate_adjustments(context, team_info)
        
        # 最终优先级
        final_priority = self._adjust_priority(base_priority, adjustments)
        
        return {
            'queue_priority': final_priority,
            'base_priority': base_priority,
            'adjustments': adjustments,
            'sla_hours': self._get_sla_hours(final_priority),
            'rationale': self._generate_rationale(final_priority, adjustments)
        }
    
    def _severity_to_priority(self, severity: str) -> str:
        """严重程度转优先级"""
        mapping = {
            'critical': 'urgent',
            'major': 'high',
            'minor': 'normal',
            'trivial': 'low'
        }
        return mapping.get(severity, 'normal')
    
    def _calculate_adjustments(self, context: Dict, team_info: Dict) -> List[Dict]:
        """计算优先级调整"""
        adjustments = []
        
        # 调整 1: 发生次数
        occurrence = context.get('occurrence_count', 1)
        if occurrence > 10:
            adjustments.append({
                'factor': 'high_occurrence',
                'effect': 'increase',
                'magnitude': 2,
                'reason': f'发生{occurrence}次'
            })
        
        # 调整 2: 影响用户数
        affected = context.get('affected_users', 0)
        if affected > 1000:
            adjustments.append({
                'factor': 'high_impact',
                'effect': 'increase',
                'magnitude': 2,
                'reason': f'影响{affected}用户'
            })
        
        # 调整 3: 是否在值班
        if team_info.get('on_call'):
            adjustments.append({
                'factor': 'on_call_available',
                'effect': 'maintain',
                'magnitude': 0,
                'reason': '有值班人员'
            })
        
        return adjustments
    
    def _adjust_priority(self, base: str, adjustments: List[Dict]) -> str:
        """调整优先级"""
        priority_order = ['low', 'normal', 'high', 'urgent']
        base_index = priority_order.index(base)
        
        total_adjustment = sum(
            adj['magnitude'] if adj['effect'] == 'increase' else -adj['magnitude']
            for adj in adjustments
        )
        
        final_index = min(len(priority_order) - 1, max(0, base_index + total_adjustment))
        return priority_order[final_index]
    
    def _get_sla_hours(self, priority: str) -> int:
        """获取 SLA 小时数"""
        sla_map = {
            'urgent': 4,
            'high': 24,
            'normal': 72,
            'low': 168
        }
        return sla_map.get(priority, 72)
    
    def _generate_rationale(self, priority: str, adjustments: List[Dict]) -> str:
        """生成优先级说明"""
        reasons = [f'基础优先级：{priority}']
        for adj in adjustments:
            if adj['magnitude'] > 0:
                reasons.append(f"{adj['reason']}，优先级提升")
        return '; '.join(reasons)
```

### 4.4 升级检测器

```python
# agents/failure-triage-agent/src/escalation_detector.py

from typing import Dict, List, Any

class EscalationDetector:
    """升级检测器"""
    
    def detect(self, severity: str, context: Dict,
               team_info: Dict, historical_data: Dict) -> Dict[str, Any]:
        """检测是否需要升级"""
        escalation_required = False
        reasons = []
        
        # 检查 1: Critical 级别自动升级
        if severity == 'critical':
            escalation_required = True
            reasons.append('Critical 级别问题')
        
        # 检查 2: 重复失败
        occurrence = context.get('occurrence_count', 1)
        if occurrence > 5:
            escalation_required = True
            reasons.append(f'重复失败{occurrence}次')
        
        # 检查 3: 超时未处理
        first_seen = context.get('first_seen')
        if first_seen and self._is_overdue(first_seen, severity):
            escalation_required = True
            reasons.append('处理超时')
        
        # 检查 4: 影响关键功能
        if context.get('is_blocking_release'):
            escalation_required = True
            reasons.append('阻塞发布')
        
        # 检查 5: 团队无响应
        if self._team_no_response(team_info, historical_data):
            escalation_required = True
            reasons.append('团队无响应')
        
        return {
            'escalation_required': escalation_required,
            'reasons': reasons,
            'escalation_level': self._determine_escalation_level(reasons),
            'suggested_escalation_target': self._get_escalation_target(team_info)
        }
    
    def _is_overdue(self, first_seen: Any, severity: str) -> bool:
        """检查是否超时"""
        # 简化实现
        return False
    
    def _team_no_response(self, team_info: Dict, historical_data: Dict) -> bool:
        """检查团队是否无响应"""
        # 简化实现
        return False
    
    def _determine_escalation_level(self, reasons: List[str]) -> str:
        """确定升级级别"""
        if len(reasons) >= 3:
            return 'high'
        elif len(reasons) >= 1:
            return 'medium'
        return 'none'
    
    def _get_escalation_target(self, team_info: Dict) -> str:
        """获取升级目标"""
        # 简化实现
        return 'engineering_manager'
```

### 4.5 票据创建器

```python
# agents/failure-triage-agent/src/ticket_creator.py

from typing import Dict, List, Any, Optional

class TicketCreator:
    """票据创建器"""
    
    def __init__(self, adapter: Any = None):
        self.adapter = adapter  # Jira/GitHub adapter
    
    def create_or_update(self, triage_input: Dict,
                         triage_decision: Dict) -> Dict[str, Any]:
        """创建或更新票据"""
        action = self._determine_action(triage_input, triage_decision)
        
        if action == 'no_action':
            return {'action': 'no_action', 'ticket_id': None}
        
        ticket_data = self._prepare_ticket_data(triage_input, triage_decision)
        
        if action == 'create':
            return self._create_ticket(ticket_data)
        elif action == 'update':
            return self._update_ticket(ticket_data)
        elif action == 'reopen':
            return self._reopen_ticket(ticket_data)
        
        return {'action': 'no_action', 'ticket_id': None}
    
    def _determine_action(self, triage_input: Dict,
                         triage_decision: Dict) -> str:
        """确定票据动作"""
        # 检查是否有现有票据
        existing_ticket = triage_input.get('existing_ticket_id')
        
        if not existing_ticket:
            return 'create'
        
        # 检查票据状态
        ticket_status = triage_input.get('ticket_status', 'open')
        
        if ticket_status == 'closed':
            return 'reopen'
        elif ticket_status == 'open':
            return 'update'
        
        return 'create'
    
    def _prepare_ticket_data(self, triage_input: Dict,
                            triage_decision: Dict) -> Dict:
        """准备票据数据"""
        context = triage_input.get('failure_context', {})
        
        return {
            'title': f"[{triage_decision['severity'].upper()}] {context.get('test_title', 'Unknown Failure')}",
            'description': self._generate_description(context, triage_decision),
            'severity': triage_decision['severity'],
            'priority': triage_decision['queue_priority'],
            'assignee': triage_decision.get('assigned_to'),
            'labels': self._generate_labels(context, triage_decision),
            'components': self._extract_components(context)
        }
    
    def _generate_description(self, context: Dict, decision: Dict) -> str:
        """生成票据描述"""
        return f"""
## 失败信息

- **测试用例**: {context.get('test_title', 'N/A')}
- **失败类别**: {context.get('failure_category', 'N/A')}
- **可能原因**: {context.get('likely_cause', 'N/A')}
- **发生次数**: {context.get('occurrence_count', 1)}
- **首次发现**: {context.get('first_seen', 'N/A')}

## 分类信息

- **严重程度**: {decision['severity']}
- **责任团队**: {decision['owner_team_name']}
- **队列优先级**: {decision['queue_priority']}
- **SLA**: {decision.get('sla_hours', 'N/A')} 小时

## 路由依据

{decision.get('routing_rationale', 'N/A')}
"""
    
    def _generate_labels(self, context: Dict, decision: Dict) -> List[str]:
        """生成标签"""
        labels = [
            'automated',
            'test-failure',
            context.get('failure_category', 'unknown')
        ]
        
        if context.get('is_blocking_release'):
            labels.append('blocking-release')
        
        if context.get('occurrence_count', 1) > 5:
            labels.append('recurring')
        
        return labels
    
    def _extract_components(self, context: Dict) -> List[str]:
        """提取组件"""
        # 从测试标题提取
        title = context.get('test_title', '').lower()
        components = []
        
        if 'login' in title or 'auth' in title:
            components.append('authentication')
        if 'payment' in title:
            components.append('payment')
        if 'order' in title:
            components.append('order')
        
        return components
    
    def _create_ticket(self, ticket_data: Dict) -> Dict:
        """创建票据"""
        if self.adapter:
            return self.adapter.create_ticket(ticket_data)
        
        # 模拟创建
        return {
            'action': 'create',
            'ticket_id': f'TICKET-{1000}',
            'ticket_url': f'https://jira.example.com/browse/TICKET-1000',
            'status': 'created'
        }
    
    def _update_ticket(self, ticket_data: Dict) -> Dict:
        """更新票据"""
        if self.adapter:
            return self.adapter.update_ticket(ticket_data)
        
        return {
            'action': 'update',
            'ticket_id': ticket_data.get('existing_id'),
            'status': 'updated'
        }
    
    def _reopen_ticket(self, ticket_data: Dict) -> Dict:
        """重新打开票据"""
        if self.adapter:
            return self.adapter.reopen_ticket(ticket_data)
        
        return {
            'action': 'reopen',
            'ticket_id': ticket_data.get('existing_id'),
            'status': 'reopened'
        }
```

---

## 5. Agent 主实现

```python
# agents/failure-triage-agent/src/agent.py

import time
from datetime import datetime
from typing import Dict, Any

from .schemas import (
    FailureTriageInput,
    FailureTriageOutput,
    TriageDecision,
    Severity,
    QueuePriority,
    TicketAction
)
from .failure_analyzer import FailureAnalyzer
from .severity_assessor import SeverityAssessor
from .ownership_resolver import OwnershipResolver
from .priority_assigner import PriorityAssigner
from .escalation_detector import EscalationDetector
from .ticket_creator import TicketCreator

class FailureTriageAgent:
    """Failure Triage Agent 主类"""
    
    VERSION = "0.1.0"
    
    def __init__(self, ticket_adapter: Any = None):
        self.failure_analyzer = FailureAnalyzer()
        self.severity_assessor = SeverityAssessor()
        self.ownership_resolver = OwnershipResolver()
        self.priority_assigner = PriorityAssigner()
        self.escalation_detector = EscalationDetector()
        self.ticket_creator = TicketCreator(ticket_adapter)
    
    async def triage(self, input_data: FailureTriageInput) -> FailureTriageOutput:
        """分类失败"""
        start_time = time.time()
        
        # Stage 1: 失败分析
        failure_analysis = self.failure_analyzer.analyze(
            input_data.failure_context.model_dump()
        )
        
        # Stage 2: 严重性评估
        severity_result = self.severity_assessor.assess(
            input_data.failure_context.model_dump(),
            input_data.severity_criteria
        )
        
        # Stage 3: 责任归属解析
        ownership_result = self.ownership_resolver.resolve(
            input_data.failure_context.model_dump(),
            input_data.team_structure.model_dump(),
            input_data.ownership_rules
        )
        
        # Stage 4: 优先级分配
        priority_result = self.priority_assigner.assign(
            severity_result['severity'],
            input_data.failure_context.model_dump(),
            ownership_result
        )
        
        # Stage 5: 升级检测
        escalation_result = self.escalation_detector.detect(
            severity_result['severity'],
            input_data.failure_context.model_dump(),
            ownership_result,
            {}
        )
        
        # Stage 6: 票据创建
        triage_decision_dict = {
            'severity': severity_result['severity'],
            'owner_team': ownership_result['team_id'],
            'owner_team_name': ownership_result['team_name'],
            'assigned_to': ownership_result.get('on_call'),
            'queue_priority': priority_result['queue_priority'],
            'sla_hours': priority_result['sla_hours'],
            'routing_rationale': ownership_result.get('match_type', 'unknown')
        }
        
        ticket_result = self.ticket_creator.create_or_update(
            input_data.model_dump(),
            triage_decision_dict
        )
        
        # 组装决策
        triage_decision = TriageDecision(
            severity=Severity(severity_result['severity']),
            owner_team=ownership_result['team_id'],
            owner_team_name=ownership_result['team_name'],
            assigned_to=ownership_result.get('on_call'),
            queue_priority=QueuePriority(priority_result['queue_priority']),
            ticket_action=TicketAction(ticket_result.get('action', 'no_action')),
            ticket_id=ticket_result.get('ticket_id'),
            escalation_required=escalation_result['escalation_required'],
            escalation_reason=', '.join(escalation_result['reasons']) if escalation_result['reasons'] else None,
            triage_confidence=severity_result.get('confidence', 0.5),
            routing_rationale=ownership_result.get('match_type', 'unknown'),
            sla_hours=priority_result['sla_hours']
        )
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        return FailureTriageOutput(
            request_id=input_data.request_id,
            triage_decision=triage_decision,
            ticket_info=ticket_result if ticket_result.get('ticket_id') else None,
            notifications=self._generate_notifications(triage_decision, escalation_result),
            warnings=self._generate_warnings(triage_decision),
            processing_time_ms=processing_time_ms,
            agent_version=self.VERSION,
            timestamp=datetime.now()
        )
    
    def _generate_notifications(self, decision: TriageDecision,
                               escalation: Dict) -> list:
        """生成通知"""
        notifications = []
        
        # 通知责任团队
        notifications.append({
            'type': 'team_notification',
            'target': decision.owner_team,
            'message': f'新失败分配：{decision.severity.value} - {decision.ticket_id}'
        })
        
        # 升级通知
        if decision.escalation_required:
            notifications.append({
                'type': 'escalation_notification',
                'target': escalation.get('suggested_escalation_target'),
                'message': f'升级通知：{decision.escalation_reason}'
            })
        
        return notifications
    
    def _generate_warnings(self, decision: TriageDecision) -> list:
        """生成警告"""
        warnings = []
        
        if decision.triage_confidence < 0.6:
            warnings.append('分类置信度较低，建议人工复核')
        
        if decision.escalation_required:
            warnings.append(f'需要升级：{decision.escalation_reason}')
        
        if decision.owner_team == 'unassigned':
            warnings.append('未匹配到责任团队')
        
        return warnings
```

---

## 6. 测试策略

说明：以下测试文件名和代码片段是建议测试蓝图，不代表当前仓库已经存在同名 `tests/` 文件；当前 triage 能力成熟度仍要结合上游 failure-analysis 输出质量一起判断。

### 6.1 单元测试

```python
# agents/failure-triage-agent/tests/test_severity_assessor.py

import pytest
from src.severity_assessor import SeverityAssessor

class TestSeverityAssessor:
    def test_assess_critical(self):
        assessor = SeverityAssessor()
        context = {
            'is_blocking_release': True,
            'occurrence_count': 1,
            'affected_users': 0
        }
        
        result = assessor.assess(context)
        
        assert result['severity'] == 'critical'
        assert result['confidence'] > 0.5
    
    def test_assess_minor(self):
        assessor = SeverityAssessor()
        context = {
            'is_blocking_release': False,
            'occurrence_count': 2,
            'failure_category': 'locator_not_found'
        }
        
        result = assessor.assess(context)
        
        assert result['severity'] == 'minor'
```

### 6.2 Golden Test Set

```python
# agents/failure-triage-agent/tests/golden_tests.py

import pytest
from src.agent import FailureTriageAgent
from src.schemas import (
    FailureTriageInput, FailureContext, TeamStructure, TeamInfo
)

GOLDEN_TEST_CASES = [
    {
        'name': 'Critical 失败分类',
        'input': FailureTriageInput(
            request_id='golden-ft-001',
            failure_context=FailureContext(
                failure_analysis_id='fa-001',
                failure_category='assertion_failed',
                test_case_id='tc-001',
                test_title='支付流程测试',
                first_seen=datetime.now(),
                occurrence_count=1,
                is_blocking_release=True
            ),
            team_structure=TeamStructure(
                teams=[
                    TeamInfo(
                        team_id='team-payment',
                        team_name='支付团队',
                        members=['user1', 'user2']
                    )
                ]
            )
        ),
        'expected': {
            'severity': 'critical',
            'escalation_required': True,
            'ticket_action': 'create'
        }
    }
]

@pytest.mark.parametrize('test_case', GOLDEN_TEST_CASES)
@pytest.mark.asyncio
async def test_golden_cases(test_case):
    agent = FailureTriageAgent()
    output = await agent.triage(test_case['input'])
    
    assert output.triage_decision.severity.value == test_case['expected']['severity']
    assert output.triage_decision.escalation_required == test_case['expected']['escalation_required']
    assert output.triage_decision.ticket_action.value == test_case['expected']['ticket_action']
```

---

## 7. 实施计划

### Phase 1: 基础框架（Week 1）

| 任务 | 预计 | 状态 |
|------|------|------|
| 项目结构搭建 | 1 天 | ⏳ |
| 输入输出 Schema 定义 | 1 天 | ⏳ |
| 严重性评估器实现 | 2 天 | ⏳ |
| 责任归属解析器实现 | 2 天 | ⏳ |

### Phase 2: 核心能力（Week 2）

| 任务 | 预计 | 状态 |
|------|------|------|
| 优先级分配器实现 | 1 天 | ⏳ |
| 升级检测器实现 | 1 天 | ⏳ |
| 票据创建器实现 | 2 天 | ⏳ |
| Agent 主逻辑 | 2 天 | ⏳ |
| 集成测试 | 2 天 | ⏳ |

### Phase 3: 企业级能力（Week 3）

| 任务 | 预计 | 状态 |
|------|------|------|
| Jira/GitHub 适配器 | 2 天 | ⏳ |
| Golden Test Set 建立 | 1 天 | ⏳ |
| 监控指标接入 | 1 天 | ⏳ |
| 文档完善 | 1 天 | ⏳ |
| 验收测试 | 1 天 | ⏳ |

---

## 8. 验收标准

### 功能验收

- [ ] 严重程度判定准确率 > 90%
- [ ] 路由准确率 > 85%
- [ ] 优先级合理性 > 85%
- [ ] 升级识别准确率 > 90%
- [ ] 票据准确率 > 95%

### 质量验收

- [ ] 单元测试覆盖率 > 85%
- [ ] Golden Test Set 通过率 > 85%
- [ ] P95 延迟 < 3s
- [ ] 错误路由率 < 5%

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
