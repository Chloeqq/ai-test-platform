# Risk Evaluation Agent 详细设计

> **状态**: ⏳ L2 → L4 提升中
> **优先级**: P2
> **目标成熟度**: L4（企业级）
> **预计完成**: 2026-05-09（3 周）
> **当前准确率**: ~75%
> **目标准确率**: > 85%

---

## 1. Agent 概述

### 1.1 职责定义

Risk Evaluation Agent 负责评估版本/变更的风险等级，综合测试结果、变更范围、历史数据等因素，输出可解释的风险评分和发布建议。

**核心职责**:
- 风险量化评分（0-100）
- 风险因素识别和权重分析
- 趋势预测（基于历史数据）
- 发布建议（pass/fail/waived）
- 缓解建议生成
- 阈值配置支持

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **可解释性** | 每个风险分数都有明确依据 |
| **保守评估** | 宁可高估风险，不可低估 |
| **可配置** | 支持自定义风险阈值 |
| **趋势感知** | 考虑历史趋势和模式 |
| **决策支持** | 输出明确的发布建议 |

### 1.3 在平台中的位置

```
Test Results → [Risk Evaluation] → Release Decision
     ↓              ↓                    ↓
  测试结果        风险评分            发布/阻断/人工审批
     ↓
  变更范围
  历史数据
```

### 1.4 当前实现状态与卡点

当前仓库里的 `agents/risk-evaluation-agent/src/agent.py` 已经是可运行实现，因此这份文档不应被理解为“从零设计一个还不存在的风险系统”。

当前实际能力：

- 基于 `priority / execution_status / failure_analysis / retry_policy / case_complexity / triage_severity` 做规则化评分
- 输出 `risk_score / risk_level / gate_decision / recommendation / factors / metadata`
- 已能支持 `allow / manual_review / block` 这类门禁建议
- 已经是 URL-first 治理链和 review/gate 回显的一部分

当前卡点：

1. 它更接近“可解释的规则评分器”，还不是成熟的趋势预测模型。
2. 历史数据、失败聚类、长期质量趋势的利用还比较浅。
3. 当前很多风险结论仍然强依赖上游 failure-analysis、failure-triage 和 execution 结果质量。

下一步优先级建议：

1. 先继续强化因素可解释性，而不是急着做黑盒预测。
2. 把 `execution_gate`、失败来源分类、覆盖缺口和历史趋势一起纳入稳定输入。
3. 把“风险评分”和“发布决策”继续明确分层，避免把 AI/规则建议误当最终裁决。

这意味着本文更准确的定位是：

**“已部分落地的 Risk Evaluation Agent 的企业级增强设计稿”**，而不是“当前已完整实现的风险治理说明”。 

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                   Risk Evaluation Agent                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Change     │  │   Test       │  │   Historical │          │
│  │   Analyzer   │→ │   Result     │→ │   Trend      │          │
│  │              │  │   Analyzer   │  │   Analyzer   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         ↑                ↑                   ↓                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Threshold  │  │   Risk       │  │   Release    │          │
│  │   Manager    │← │   Scorer     │← │   Advisor    │          │
│  │              │  │              │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         ↓                                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Risk Factor Calculators                      │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐  │  │
│  │  │  Change    │  │   Quality  │  │      Business      │  │  │
│  │  │  Scope     │  │   Metrics  │  │      Impact        │  │  │
│  │  └────────────┘  └────────────┘  └────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────┐
                    │  Risk Report +  │
                    │  Release Advice │
                    └─────────────────┘
```

### 2.2 模块划分

说明：以下模块划分用于表达目标模块边界，不代表当前仓库已全部存在；真实实现请以 `1.4 当前实现状态与卡点` 和实际目录为准。

当前仓库实际存在的核心入口：

- `agents/risk-evaluation-agent/src/agent.py`
- `agents/risk-evaluation-agent/src/index.py`
- `agents/risk-evaluation-agent/src/schema.py`
- `agents/risk-evaluation-agent/src/tools/`
- `agents/risk-evaluation-agent/src/utils/score-calculator.py`

| 模块 | 文件路径 | 职责 |
|------|---------|------|
| `agent.py` | `agents/risk-evaluation-agent/src/agent.py` | Agent 主入口 |
| `change_analyzer.py` | `agents/risk-evaluation-agent/src/change_analyzer.py` | 变更分析 |
| `test_result_analyzer.py` | `agents/risk-evaluation-agent/src/test_result_analyzer.py` | 测试结果分析 |
| `historical_trend_analyzer.py` | `agents/risk-evaluation-agent/src/historical_trend_analyzer.py` | 历史趋势分析 |
| `risk_scorer.py` | `agents/risk-evaluation-agent/src/risk_scorer.py` | 风险评分 |
| `threshold_manager.py` | `agents/risk-evaluation-agent/src/threshold_manager.py` | 阈值管理 |
| `release_advisor.py` | `agents/risk-evaluation-agent/src/release_advisor.py` | 发布建议 |
| `calculators/` | `agents/risk-evaluation-agent/src/calculators/` | 风险因子计算器 |

---

## 3. 输入输出契约

### 3.1 输入 Schema

```python
# agents/risk-evaluation-agent/src/schema.py

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime

class RiskLevel(str, Enum):
    LOW = "low"          # 0-25
    MEDIUM = "medium"    # 26-50
    HIGH = "high"        # 51-75
    CRITICAL = "critical" # 76-100

class ReleaseDecision(str, Enum):
    PASS = "pass"           # 允许发布
    FAIL = "fail"           # 阻断发布
    WAIVED = "waived"       # 风险放行（需审批）
    NEEDS_REVIEW = "needs_review"  # 需要人工评审

class ChangeScope(BaseModel):
    """变更范围"""
    changed_files: List[str] = []
    added_lines: int = 0
    deleted_lines: int = 0
    modified_lines: int = 0
    affected_modules: List[str] = []
    affected_services: List[str] = []
    is_hotfix: bool = False
    has_database_change: bool = False
    has_api_change: bool = False
    has_ui_change: bool = False

class TestMetrics(BaseModel):
    """测试指标"""
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    pass_rate: float = 0.0
    p0_tests: int = 0
    p0_passed: int = 0
    p0_failed: int = 0
    flaky_tests: int = 0
    new_tests: int = 0
    new_tests_failed: int = 0
    regression_tests: int = 0
    regression_failed: int = 0

class HistoricalData(BaseModel):
    """历史数据"""
    last_7_days_fail_rate: float = 0.0
    last_30_days_fail_rate: float = 0.0
    trend: str = "stable"  # improving/stable/degrading
    consecutive_successful_releases: int = 0
    recent_incidents: int = 0
    average_fix_time_hours: float = 0.0

class BusinessContext(BaseModel):
    """业务上下文"""
    release_type: str = "regular"  # regular/hotfix/major
    business_impact: str = "normal"  # low/normal/high/critical
    user_visibility: str = "partial"  # none/partial/full
    rollback_complexity: str = "easy"  # easy/medium/hard
    compliance_required: bool = False

class RiskThresholds(BaseModel):
    """风险阈值配置"""
    max_risk_score: float = 60.0
    auto_pass_below: float = 30.0
    p0_pass_rate_required: float = 1.0
    overall_pass_rate_required: float = 0.95
    max_flaky_ratio: float = 0.05

class RiskEvaluationInput(BaseModel):
    """Agent 输入"""
    request_id: str
    change_scope: ChangeScope
    test_metrics: TestMetrics
    historical_data: Optional[HistoricalData] = None
    business_context: Optional[BusinessContext] = None
    thresholds: Optional[RiskThresholds] = None
    custom_factors: Optional[List[Dict]] = None
    
    class Config:
        schema_extra = {
            "example": {
                "request_id": "risk-eval-001",
                "change_scope": {
                    "changed_files": ["src/auth.py", "src/user.py"],
                    "affected_modules": ["auth", "user"]
                },
                "test_metrics": {
                    "total_tests": 100,
                    "passed_tests": 98,
                    "pass_rate": 0.98
                }
            }
        }

class RiskFactor(BaseModel):
    """风险因素"""
    factor_id: str
    name: str
    category: str  # change/quality/history/business
    weight: float  # 权重 0-1
    score: float   # 得分 0-100
    contribution: float  # 对总分的贡献
    evidence: List[str]  # 支撑证据
    trend: Optional[str] = None  # 趋势

class RiskEvaluationReport(BaseModel):
    """风险评估报告"""
    report_id: str
    risk_score: float  # 0-100
    risk_level: RiskLevel
    risk_factors: List[RiskFactor]
    contributing_evidence: Dict[str, Any]
    trend_analysis: Dict[str, Any]
    release_recommendation: ReleaseDecision
    mitigation_suggestions: List[str]
    requires_approval: bool
    approval_reason: Optional[str] = None
    metadata: Dict[str, Any]

class RiskEvaluationOutput(BaseModel):
    """Agent 输出"""
    request_id: str
    risk_report: RiskEvaluationReport
    evaluation_details: Dict[str, Any] = {
        "processing_stages": [],
        "factors_evaluated": 0
    }
    warnings: List[str] = []
    processing_time_ms: int
    agent_version: str
    model_used: str
    timestamp: datetime
    
    class Config:
        schema_extra = {
            "example": {
                "request_id": "risk-eval-001",
                "risk_report": {
                    "risk_score": 45.0,
                    "risk_level": "medium",
                    "release_recommendation": "pass"
                },
                "processing_time_ms": 2345
            }
        }
```

---

## 4. 核心功能实现

说明：本章代码块主要用于表达目标实现方式和模块边界，不代表这些模块文件已在当前仓库全部落地；当前真实实现仍以 `src/agent.py`、`src/schema.py`、`src/tools/` 和 `src/utils/score-calculator.py` 为主。

### 4.1 变更分析器

```python
# agents/risk-evaluation-agent/src/change_analyzer.py

from typing import Dict, List, Any

class ChangeAnalyzer:
    """变更分析器"""
    
    def analyze(self, change_scope: Dict) -> Dict[str, Any]:
        """分析变更范围，提取风险因素"""
        return {
            'size_score': self._calculate_size_score(change_scope),
            'complexity_score': self._calculate_complexity_score(change_scope),
            'type_score': self._calculate_type_score(change_scope),
            'affected_areas': self._identify_affected_areas(change_scope),
            'risk_indicators': self._identify_risk_indicators(change_scope)
        }
    
    def _calculate_size_score(self, scope: Dict) -> float:
        """计算变更规模分数"""
        total_changes = (
            scope.get('added_lines', 0) +
            scope.get('deleted_lines', 0) +
            scope.get('modified_lines', 0)
        )
        
        # 规模越大风险越高
        if total_changes == 0:
            return 0
        elif total_changes < 50:
            return 20
        elif total_changes < 200:
            return 40
        elif total_changes < 500:
            return 60
        elif total_changes < 1000:
            return 80
        else:
            return 100
    
    def _calculate_complexity_score(self, scope: Dict) -> float:
        """计算变更复杂度分数"""
        score = 0
        
        # 文件数量
        file_count = len(scope.get('changed_files', []))
        score += min(file_count * 5, 30)
        
        # 模块数量
        module_count = len(scope.get('affected_modules', []))
        score += min(module_count * 10, 30)
        
        # 服务数量
        service_count = len(scope.get('affected_services', []))
        score += min(service_count * 15, 40)
        
        return min(100, score)
    
    def _calculate_type_score(self, scope: Dict) -> float:
        """计算变更类型风险分数"""
        score = 0
        
        # 数据库变更高风险
        if scope.get('has_database_change'):
            score += 40
        
        # API 变更中风险
        if scope.get('has_api_change'):
            score += 25
        
        # UI 变更低风险
        if scope.get('has_ui_change'):
            score += 15
        
        # Hotfix 额外风险
        if scope.get('is_hotfix'):
            score += 20
        
        return min(100, score)
    
    def _identify_affected_areas(self, scope: Dict) -> List[str]:
        """识别受影响区域"""
        areas = []
        
        if scope.get('has_database_change'):
            areas.append('database')
        if scope.get('has_api_change'):
            areas.append('api')
        if scope.get('has_ui_change'):
            areas.append('ui')
        
        areas.extend(scope.get('affected_modules', []))
        areas.extend(scope.get('affected_services', []))
        
        return list(set(areas))
    
    def _identify_risk_indicators(self, scope: Dict) -> List[Dict]:
        """识别风险指标"""
        indicators = []
        
        if scope.get('is_hotfix'):
            indicators.append({
                'type': 'hotfix',
                'severity': 'high',
                'description': '这是一个热修复，可能存在 rushed 风险'
            })
        
        if scope.get('has_database_change'):
            indicators.append({
                'type': 'database_change',
                'severity': 'high',
                'description': '包含数据库变更，需要回滚方案'
            })
        
        file_count = len(scope.get('changed_files', []))
        if file_count > 50:
            indicators.append({
                'type': 'large_change',
                'severity': 'medium',
                'description': f'变更文件数量大 ({file_count}个)'
            })
        
        return indicators
```

### 4.2 测试结果分析器

```python
# agents/risk-evaluation-agent/src/test_result_analyzer.py

from typing import Dict, List, Any

class TestResultAnalyzer:
    """测试结果分析器"""
    
    def analyze(self, test_metrics: Dict) -> Dict[str, Any]:
        """分析测试结果，提取风险因素"""
        return {
            'pass_rate_score': self._calculate_pass_rate_score(test_metrics),
            'p0_score': self._calculate_p0_score(test_metrics),
            'flaky_score': self._calculate_flaky_score(test_metrics),
            'new_test_score': self._calculate_new_test_score(test_metrics),
            'regression_score': self._calculate_regression_score(test_metrics),
            'risk_indicators': self._identify_risk_indicators(test_metrics)
        }
    
    def _calculate_pass_rate_score(self, metrics: Dict) -> float:
        """计算通过率风险分数"""
        pass_rate = metrics.get('pass_rate', 1.0)
        
        # 通过率越低风险越高
        if pass_rate >= 0.99:
            return 0
        elif pass_rate >= 0.95:
            return 20
        elif pass_rate >= 0.90:
            return 40
        elif pass_rate >= 0.80:
            return 60
        elif pass_rate >= 0.70:
            return 80
        else:
            return 100
    
    def _calculate_p0_score(self, metrics: Dict) -> float:
        """计算 P0 测试风险分数"""
        p0_total = metrics.get('p0_tests', 0)
        p0_failed = metrics.get('p0_failed', 0)
        
        if p0_total == 0:
            return 0
        
        p0_pass_rate = (p0_total - p0_failed) / p0_total
        
        # P0 必须 100% 通过
        if p0_pass_rate == 1.0:
            return 0
        elif p0_pass_rate >= 0.9:
            return 50
        else:
            return 100
    
    def _calculate_flaky_score(self, metrics: Dict) -> float:
        """计算 Flaky 测试风险分数"""
        total = metrics.get('total_tests', 1)
        flaky = metrics.get('flaky_tests', 0)
        
        flaky_ratio = flaky / total if total > 0 else 0
        
        if flaky_ratio == 0:
            return 0
        elif flaky_ratio < 0.02:
            return 20
        elif flaky_ratio < 0.05:
            return 40
        elif flaky_ratio < 0.10:
            return 60
        else:
            return 100
    
    def _calculate_new_test_score(self, metrics: Dict) -> float:
        """计算新测试风险分数"""
        new_tests = metrics.get('new_tests', 0)
        new_failed = metrics.get('new_tests_failed', 0)
        
        if new_tests == 0:
            return 0
        
        new_pass_rate = (new_tests - new_failed) / new_tests
        
        if new_pass_rate >= 0.95:
            return 10
        elif new_pass_rate >= 0.80:
            return 40
        else:
            return 80
    
    def _calculate_regression_score(self, metrics: Dict) -> float:
        """计算回归测试风险分数"""
        regression = metrics.get('regression_tests', 0)
        regression_failed = metrics.get('regression_failed', 0)
        
        if regression == 0:
            return 0
        
        regression_pass_rate = (regression - regression_failed) / regression
        
        if regression_pass_rate >= 0.99:
            return 0
        elif regression_pass_rate >= 0.95:
            return 30
        elif regression_pass_rate >= 0.90:
            return 60
        else:
            return 100
    
    def _identify_risk_indicators(self, metrics: Dict) -> List[Dict]:
        """识别风险指标"""
        indicators = []
        
        # P0 失败
        if metrics.get('p0_failed', 0) > 0:
            indicators.append({
                'type': 'p0_failure',
                'severity': 'critical',
                'description': f'{metrics["p0_failed"]}个 P0 测试失败'
            })
        
        # 通过率过低
        if metrics.get('pass_rate', 1.0) < 0.95:
            indicators.append({
                'type': 'low_pass_rate',
                'severity': 'high',
                'description': f'通过率 {metrics["pass_rate"]:.1%} 低于 95%'
            })
        
        # Flaky 过多
        flaky_ratio = metrics.get('flaky_tests', 0) / max(metrics.get('total_tests', 1), 1)
        if flaky_ratio > 0.05:
            indicators.append({
                'type': 'high_flaky_ratio',
                'severity': 'medium',
                'description': f'Flaky 测试比例 {flaky_ratio:.1%} 过高'
            })
        
        return indicators
```

### 4.3 历史趋势分析器

```python
# agents/risk-evaluation-agent/src/historical_trend_analyzer.py

from typing import Dict, List, Any

class HistoricalTrendAnalyzer:
    """历史趋势分析器"""
    
    def analyze(self, historical_data: Dict) -> Dict[str, Any]:
        """分析历史趋势，提取风险因素"""
        return {
            'trend_score': self._calculate_trend_score(historical_data),
            'stability_score': self._calculate_stability_score(historical_data),
            'incident_score': self._calculate_incident_score(historical_data),
            'risk_indicators': self._identify_risk_indicators(historical_data)
        }
    
    def _calculate_trend_score(self, data: Dict) -> float:
        """计算趋势分数"""
        trend = data.get('trend', 'stable')
        
        if trend == 'improving':
            return 0
        elif trend == 'stable':
            return 20
        elif trend == 'degrading':
            return 60
        else:
            return 40
    
    def _calculate_stability_score(self, data: Dict) -> float:
        """计算稳定性分数"""
        # 近期失败率
        recent_fail_rate = data.get('last_7_days_fail_rate', 0)
        historical_fail_rate = data.get('last_30_days_fail_rate', 0)
        
        # 近期比历史高则风险高
        if recent_fail_rate > historical_fail_rate * 1.5:
            return 80
        elif recent_fail_rate > historical_fail_rate:
            return 40
        else:
            return 20
    
    def _calculate_incident_score(self, data: Dict) -> float:
        """计算事故分数"""
        incidents = data.get('recent_incidents', 0)
        consecutive_success = data.get('consecutive_successful_releases', 0)
        
        score = 0
        
        # 事故越多风险越高
        score += incidents * 20
        
        # 连续成功越多风险越低
        score -= consecutive_success * 5
        
        return max(0, min(100, score))
    
    def _identify_risk_indicators(self, data: Dict) -> List[Dict]:
        """识别风险指标"""
        indicators = []
        
        # 趋势恶化
        if data.get('trend') == 'degrading':
            indicators.append({
                'type': 'degrading_trend',
                'severity': 'high',
                'description': '质量趋势正在恶化'
            })
        
        # 近期失败率高
        if data.get('last_7_days_fail_rate', 0) > 0.1:
            indicators.append({
                'type': 'high_recent_fail_rate',
                'severity': 'high',
                'description': '近 7 天失败率超过 10%'
            })
        
        # 近期事故
        if data.get('recent_incidents', 0) > 0:
            indicators.append({
                'type': 'recent_incidents',
                'severity': 'medium',
                'description': f'近期有{data["recent_incidents"]}起事故'
            })
        
        return indicators
```

### 4.4 风险评分器

```python
# agents/risk-evaluation-agent/src/risk_scorer.py

from typing import Dict, List, Any

class RiskScorer:
    """风险评分器"""
    
    # 风险因子权重配置
    DEFAULT_WEIGHTS = {
        'change_size': 0.15,
        'change_complexity': 0.15,
        'change_type': 0.10,
        'test_pass_rate': 0.20,
        'p0_tests': 0.20,
        'flaky_tests': 0.10,
        'historical_trend': 0.05,
        'business_impact': 0.05
    }
    
    def calculate(self, change_analysis: Dict, test_analysis: Dict,
                  historical_analysis: Dict, business_context: Dict,
                  custom_weights: Dict = None) -> Dict[str, Any]:
        """计算风险评分"""
        weights = {**self.DEFAULT_WEIGHTS, **(custom_weights or {})}
        
        # 计算各因子分数
        factor_scores = self._calculate_factor_scores(
            change_analysis, test_analysis, historical_analysis, business_context
        )
        
        # 加权计算总分
        total_score = 0
        risk_factors = []
        
        for factor_name, weight in weights.items():
            score = factor_scores.get(factor_name, {}).get('score', 0)
            contribution = score * weight
            total_score += contribution
            
            risk_factors.append({
                'factor_id': factor_name,
                'name': self._get_factor_name(factor_name),
                'category': self._get_factor_category(factor_name),
                'weight': weight,
                'score': score,
                'contribution': contribution,
                'evidence': factor_scores.get(factor_name, {}).get('evidence', [])
            })
        
        return {
            'total_score': min(100, total_score),
            'risk_factors': risk_factors,
            'factor_scores': factor_scores,
            'breakdown': self._generate_breakdown(risk_factors)
        }
    
    def _calculate_factor_scores(self, change_analysis: Dict, test_analysis: Dict,
                                  historical_analysis: Dict, business_context: Dict) -> Dict:
        """计算各因子分数"""
        return {
            'change_size': {
                'score': change_analysis.get('size_score', 0),
                'evidence': [f"变更规模评分：{change_analysis.get('size_score', 0)}"]
            },
            'change_complexity': {
                'score': change_analysis.get('complexity_score', 0),
                'evidence': [f"变更复杂度评分：{change_analysis.get('complexity_score', 0)}"]
            },
            'change_type': {
                'score': change_analysis.get('type_score', 0),
                'evidence': change_analysis.get('risk_indicators', [])
            },
            'test_pass_rate': {
                'score': test_analysis.get('pass_rate_score', 0),
                'evidence': [f"通过率风险评分：{test_analysis.get('pass_rate_score', 0)}"]
            },
            'p0_tests': {
                'score': test_analysis.get('p0_score', 0),
                'evidence': [f"P0 测试风险评分：{test_analysis.get('p0_score', 0)}"]
            },
            'flaky_tests': {
                'score': test_analysis.get('flaky_score', 0),
                'evidence': [f"Flaky 测试风险评分：{test_analysis.get('flaky_score', 0)}"]
            },
            'historical_trend': {
                'score': historical_analysis.get('trend_score', 0),
                'evidence': historical_analysis.get('risk_indicators', [])
            },
            'business_impact': {
                'score': self._calculate_business_impact_score(business_context),
                'evidence': [f"业务影响：{business_context.get('business_impact', 'normal')}"]
            }
        }
    
    def _calculate_business_impact_score(self, context: Dict) -> float:
        """计算业务影响分数"""
        impact = context.get('business_impact', 'normal')
        
        impact_scores = {
            'low': 10,
            'normal': 30,
            'high': 60,
            'critical': 100
        }
        
        return impact_scores.get(impact, 30)
    
    def _get_factor_name(self, factor_id: str) -> str:
        """获取因子名称"""
        names = {
            'change_size': '变更规模',
            'change_complexity': '变更复杂度',
            'change_type': '变更类型',
            'test_pass_rate': '测试通过率',
            'p0_tests': 'P0 测试',
            'flaky_tests': 'Flaky 测试',
            'historical_trend': '历史趋势',
            'business_impact': '业务影响'
        }
        return names.get(factor_id, factor_id)
    
    def _get_factor_category(self, factor_id: str) -> str:
        """获取因子分类"""
        if factor_id.startswith('change_'):
            return 'change'
        elif factor_id.startswith('test_') or factor_id in ['p0_tests', 'flaky_tests']:
            return 'quality'
        elif factor_id == 'historical_trend':
            return 'history'
        else:
            return 'business'
    
    def _generate_breakdown(self, risk_factors: List[Dict]) -> Dict:
        """生成分解说明"""
        breakdown = {
            'change_risk': sum(f['contribution'] for f in risk_factors if f['category'] == 'change'),
            'quality_risk': sum(f['contribution'] for f in risk_factors if f['category'] == 'quality'),
            'history_risk': sum(f['contribution'] for f in risk_factors if f['category'] == 'history'),
            'business_risk': sum(f['contribution'] for f in risk_factors if f['category'] == 'business')
        }
        return breakdown
```

### 4.5 发布建议器

```python
# agents/risk-evaluation-agent/src/release_advisor.py

from typing import Dict, List, Any

class ReleaseAdvisor:
    """发布建议器"""
    
    def advise(self, risk_score: float, risk_factors: List[Dict],
               thresholds: Dict, business_context: Dict) -> Dict[str, Any]:
        """生成发布建议"""
        decision = self._make_decision(risk_score, thresholds)
        
        return {
            'decision': decision,
            'requires_approval': self._requires_approval(decision, risk_score, thresholds),
            'approval_reason': self._get_approval_reason(decision, risk_factors),
            'mitigation_suggestions': self._generate_mitigations(risk_factors),
            'confidence': self._calculate_confidence(risk_score, risk_factors)
        }
    
    def _make_decision(self, risk_score: float, thresholds: Dict) -> str:
        """做出发布决策"""
        max_risk = thresholds.get('max_risk_score', 60)
        auto_pass = thresholds.get('auto_pass_below', 30)
        
        if risk_score <= auto_pass:
            return 'pass'
        elif risk_score <= max_risk:
            return 'waived'
        else:
            return 'fail'
    
    def _requires_approval(self, decision: str, risk_score: float,
                          thresholds: Dict) -> bool:
        """判断是否需要审批"""
        if decision == 'fail':
            return True
        if decision == 'waived':
            return True
        return False
    
    def _get_approval_reason(self, decision: str, risk_factors: List[Dict]) -> str:
        """获取审批原因"""
        if decision == 'fail':
            return '风险评分超过阈值，需要人工评估是否放行'
        elif decision == 'waived':
            top_risks = sorted(risk_factors, key=lambda x: x['contribution'], reverse=True)[:3]
            reasons = [f"{f['name']}: {f['score']}分" for f in top_risks]
            return f'风险中等，主要风险：{", ".join(reasons)}'
        return ''
    
    def _generate_mitigations(self, risk_factors: List[Dict]) -> List[str]:
        """生成缓解建议"""
        suggestions = []
        
        # 按贡献排序
        sorted_factors = sorted(risk_factors, key=lambda x: x['contribution'], reverse=True)
        
        for factor in sorted_factors[:5]:  # 前 5 个风险因素
            suggestion = self._get_mitigation_for_factor(factor)
            if suggestion:
                suggestions.append(suggestion)
        
        return suggestions
    
    def _get_mitigation_for_factor(self, factor: Dict) -> str:
        """为特定因子生成缓解建议"""
        factor_id = factor['factor_id']
        score = factor['score']
        
        if score < 30:
            return None
        
        mitigations = {
            'change_size': '考虑将变更拆分为更小的发布单元',
            'change_complexity': '增加代码审查力度，确保变更质量',
            'change_type': '准备详细的回滚方案，特别是数据库变更',
            'test_pass_rate': '修复失败测试后再发布',
            'p0_tests': 'P0 测试必须 100% 通过才能发布',
            'flaky_tests': '调查并修复 flaky 测试',
            'historical_trend': '关注质量趋势，考虑延期发布',
            'business_impact': '选择低峰期发布，做好监控准备'
        }
        
        return mitigations.get(factor_id, f'关注{factor["name"]}风险')
    
    def _calculate_confidence(self, risk_score: float,
                             risk_factors: List[Dict]) -> float:
        """计算建议置信度"""
        # 风险因素越多，置信度越高
        factor_count = len([f for f in risk_factors if f['score'] > 0])
        
        base_confidence = 0.5
        factor_bonus = min(0.3, factor_count * 0.05)
        
        # 极端分数置信度高
        if risk_score < 20 or risk_score > 80:
            extreme_bonus = 0.2
        else:
            extreme_bonus = 0
        
        return min(1.0, base_confidence + factor_bonus + extreme_bonus)
```

---

## 5. Agent 主实现

```python
# agents/risk-evaluation-agent/src/agent.py

import time
from datetime import datetime
from typing import Dict, Any

from .schemas import (
    RiskEvaluationInput,
    RiskEvaluationOutput,
    RiskEvaluationReport,
    RiskLevel,
    ReleaseDecision
)
from .change_analyzer import ChangeAnalyzer
from .test_result_analyzer import TestResultAnalyzer
from .historical_trend_analyzer import HistoricalTrendAnalyzer
from .risk_scorer import RiskScorer
from .release_advisor import ReleaseAdvisor
from .threshold_manager import ThresholdManager

class RiskEvaluationAgent:
    """Risk Evaluation Agent 主类"""
    
    VERSION = "0.1.0"
    MODEL_USED = "qwen-3.5-plus"
    
    def __init__(self):
        self.change_analyzer = ChangeAnalyzer()
        self.test_analyzer = TestResultAnalyzer()
        self.historical_analyzer = HistoricalTrendAnalyzer()
        self.scorer = RiskScorer()
        self.advisor = ReleaseAdvisor()
        self.threshold_manager = ThresholdManager()
    
    async def evaluate(self, input_data: RiskEvaluationInput) -> RiskEvaluationOutput:
        """评估风险"""
        start_time = time.time()
        processing_stages = []
        
        # Stage 1: 变更分析
        change_analysis = self.change_analyzer.analyze(
            input_data.change_scope.model_dump()
        )
        processing_stages.append({
            'stage': 'change_analysis',
            'status': 'completed',
            'size_score': change_analysis['size_score']
        })
        
        # Stage 2: 测试结果分析
        test_analysis = self.test_analyzer.analyze(
            input_data.test_metrics.model_dump()
        )
        processing_stages.append({
            'stage': 'test_analysis',
            'status': 'completed',
            'pass_rate_score': test_analysis['pass_rate_score']
        })
        
        # Stage 3: 历史趋势分析
        historical_analysis = self.historical_analyzer.analyze(
            input_data.historical_data.model_dump() if input_data.historical_data else {}
        )
        processing_stages.append({
            'stage': 'historical_analysis',
            'status': 'completed',
            'trend_score': historical_analysis['trend_score']
        })
        
        # Stage 4: 风险评分
        thresholds = input_data.thresholds.model_dump() if input_data.thresholds else {}
        business_context = input_data.business_context.model_dump() if input_data.business_context else {}
        
        scoring_result = self.scorer.calculate(
            change_analysis,
            test_analysis,
            historical_analysis,
            business_context,
            thresholds.get('custom_weights')
        )
        processing_stages.append({
            'stage': 'risk_scoring',
            'status': 'completed',
            'total_score': scoring_result['total_score']
        })
        
        # Stage 5: 发布建议
        advice = self.advisor.advise(
            scoring_result['total_score'],
            scoring_result['risk_factors'],
            thresholds,
            business_context
        )
        processing_stages.append({
            'stage': 'release_advice',
            'status': 'completed',
            'decision': advice['decision']
        })
        
        # Stage 6: 组装报告
        risk_level = self._calculate_risk_level(scoring_result['total_score'])
        
        report = RiskEvaluationReport(
            report_id=f"report-{input_data.request_id}",
            risk_score=scoring_result['total_score'],
            risk_level=risk_level,
            risk_factors=scoring_result['risk_factors'],
            contributing_evidence=self._collect_evidence(scoring_result),
            trend_analysis=historical_analysis,
            release_recommendation=ReleaseDecision(advice['decision']),
            mitigation_suggestions=advice['mitigation_suggestions'],
            requires_approval=advice['requires_approval'],
            approval_reason=advice.get('approval_reason'),
            metadata={
                'change_scope': input_data.change_scope.model_dump(),
                'test_metrics': input_data.test_metrics.model_dump()
            }
        )
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        return RiskEvaluationOutput(
            request_id=input_data.request_id,
            risk_report=report,
            evaluation_details={
                'processing_stages': processing_stages,
                'factors_evaluated': len(scoring_result['risk_factors'])
            },
            warnings=self._generate_warnings(report, advice),
            processing_time_ms=processing_time_ms,
            agent_version=self.VERSION,
            model_used=self.MODEL_USED,
            timestamp=datetime.now()
        )
    
    def _calculate_risk_level(self, score: float) -> RiskLevel:
        """计算风险等级"""
        if score <= 25:
            return RiskLevel.LOW
        elif score <= 50:
            return RiskLevel.MEDIUM
        elif score <= 75:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL
    
    def _collect_evidence(self, scoring_result: Dict) -> Dict:
        """收集支撑证据"""
        evidence = {}
        for factor in scoring_result['risk_factors']:
            if factor['evidence']:
                evidence[factor['factor_id']] = factor['evidence']
        return evidence
    
    def _generate_warnings(self, report: RiskEvaluationReport,
                          advice: Dict) -> list:
        """生成警告"""
        warnings = []
        
        if report.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            warnings.append(f'风险等级为{report.risk_level.value}，建议谨慎发布')
        
        if advice['requires_approval']:
            warnings.append('需要人工审批')
        
        if report.risk_score > 70:
            warnings.append('风险评分较高，建议增加测试覆盖')
        
        return warnings
```

---

## 6. 测试策略

说明：以下测试文件名和代码片段是推荐补齐的测试蓝图，不代表当前仓库已经存在同名 `tests/` 文件；阅读时请将其视为目标质量基线。

### 6.1 单元测试

```python
# agents/risk-evaluation-agent/tests/test_risk_scorer.py

import pytest
from src.risk_scorer import RiskScorer

class TestRiskScorer:
    def test_calculate_low_risk(self):
        scorer = RiskScorer()
        
        result = scorer.calculate(
            change_analysis={'size_score': 20, 'complexity_score': 20},
            test_analysis={'pass_rate_score': 0, 'p0_score': 0},
            historical_analysis={'trend_score': 0},
            business_context={'business_impact': 'low'}
        )
        
        assert result['total_score'] < 30
    
    def test_calculate_high_risk(self):
        scorer = RiskScorer()
        
        result = scorer.calculate(
            change_analysis={'size_score': 100, 'complexity_score': 80},
            test_analysis={'pass_rate_score': 80, 'p0_score': 100},
            historical_analysis={'trend_score': 60},
            business_context={'business_impact': 'critical'}
        )
        
        assert result['total_score'] > 70
```

### 6.2 Golden Test Set

```python
# agents/risk-evaluation-agent/tests/golden_tests.py

import pytest
from src.agent import RiskEvaluationAgent
from src.schemas import (
    RiskEvaluationInput, ChangeScope, TestMetrics,
    HistoricalData, BusinessContext
)

GOLDEN_TEST_CASES = [
    {
        'name': '低风险发布',
        'input': RiskEvaluationInput(
            request_id='golden-re-001',
            change_scope=ChangeScope(
                changed_files=['src/utils.py'],
                added_lines=10,
                affected_modules=['utils']
            ),
            test_metrics=TestMetrics(
                total_tests=100,
                passed_tests=100,
                pass_rate=1.0,
                p0_tests=10,
                p0_passed=10
            ),
            business_context=BusinessContext(
                release_type='regular',
                business_impact='low'
            )
        ),
        'expected': {
            'risk_level': 'low',
            'decision': 'pass',
            'risk_score_below': 30
        }
    }
]

@pytest.mark.parametrize('test_case', GOLDEN_TEST_CASES)
@pytest.mark.asyncio
async def test_golden_cases(test_case):
    agent = RiskEvaluationAgent()
    output = await agent.evaluate(test_case['input'])
    
    assert output.risk_report.risk_level.value == test_case['expected']['risk_level']
    assert output.risk_report.risk_score < test_case['expected']['risk_score_below']
```

---

## 7. 实施计划

### Phase 1: 基础框架（Week 1）

| 任务 | 预计 | 状态 |
|------|------|------|
| 项目结构搭建 | 1 天 | ⏳ |
| 输入输出 Schema 定义 | 1 天 | ⏳ |
| 变更分析器实现 | 2 天 | ⏳ |
| 测试结果分析器实现 | 2 天 | ⏳ |

### Phase 2: 核心能力（Week 2）

| 任务 | 预计 | 状态 |
|------|------|------|
| 历史趋势分析器实现 | 2 天 | ⏳ |
| 风险评分器实现 | 2 天 | ⏳ |
| 发布建议器实现 | 2 天 | ⏳ |
| Agent 主逻辑 | 2 天 | ⏳ |
| 集成测试 | 2 天 | ⏳ |

### Phase 3: 企业级能力（Week 3）

| 任务 | 预计 | 状态 |
|------|------|------|
| 阈值配置完善 | 1 天 | ⏳ |
| Golden Test Set 建立 | 2 天 | ⏳ |
| 监控指标接入 | 1 天 | ⏳ |
| 文档完善 | 1 天 | ⏳ |
| 验收测试 | 1 天 | ⏳ |

---

## 8. 验收标准

### 功能验收

- [ ] 风险因素可解释性 100%
- [ ] 趋势预测准确率 > 75%
- [ ] 缓解建议可操作性 > 80%
- [ ] 阈值配置覆盖率 100%

### 质量验收

- [ ] 单元测试覆盖率 > 85%
- [ ] Golden Test Set 通过率 > 85%
- [ ] P95 延迟 < 5s

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
