# Failure Analysis Agent 详细设计

> **状态**: ⏳ L2 → L4 提升中
> **优先级**: P1
> **目标成熟度**: L4（企业级）
> **预计完成**: 2026-05-09（4 周）
> **当前准确率**: ~75%
> **目标准确率**: > 85%

---

## 1. Agent 概述

### 1.1 职责定义

Failure Analysis Agent 负责分析测试失败根因，综合多源证据（截图、日志、Network、Trace）进行智能归因，区分应用 bug 和测试脚本问题。

**核心职责**:
- 失败分类（locator/assertion/auth/network/timeout 等）
- 根因定位
- 多源证据综合分析
- 应用 bug vs 测试脚本 bug 区分
- 相似失败案例检索
- 可解释的分析报告

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **证据驱动** | 基于多源证据分析，不凭空推断 |
| **可解释性** | 每个结论都有证据支撑 |
| **保守归因** | 置信度低时标记人工复核 |
| **相似检索** | 利用历史失败案例辅助分析 |
| **应用/测试区分** | 明确区分应用 bug 和脚本问题 |

### 1.3 在平台中的位置

```
Execution → [Failure Analysis] → Triage / Self-Healing
    ↓              ↓                    ↓
  执行结果      失败分析报告      责任分配/修复建议
    ↓
  多源证据
```

### 1.4 当前实现状态与卡点

当前仓库里失败分析的主实现入口不是 `src/agent.py`，而是 [`agents/failure-analysis-agent/analyze.py`](../../../agents/failure-analysis-agent/analyze.py)。这点需要在文档里明确，否则容易让读者误以为目录结构比现实更完整。

当前实际能力：

- 规则优先 + 模型兜底的双路径分析
- 根据 stdout / stderr / URL / HTML / 证据文件做分类
- 输出 `failure_category / likely_cause / confidence / risk_level / recommended_action`

当前卡点：

1. 证据不足时仍可能把应用 bug 和脚本 bug 混在一起。
2. 目前更像“强分类器 + 解释器”，还不是成熟的根因分析系统。
3. 高质量历史失败案例积累不足，会影响相似案例检索和归因准确性。

下一步优先级建议：

1. 把失败分类和证据结构标准化。
2. 让应用 bug / 测试 bug / 环境 bug 的边界更明确。
3. 把人工复核结果回流成归因校准数据。

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                   Failure Analysis Agent                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Evidence   │  │   Failure    │  │   Root       │          │
│  │   Collector  │→ │   Classifier │→ │   Cause      │          │
│  │              │  │              │  │   Analyzer   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         ↑                ↑                   ↓                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Similar    │  │  Application │  │   Report     │          │
│  │   Case       │← │   vs Test    │← │   Generator  │          │
│  │   Retriever  │  │   Bug        │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         ↓                                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Evidence Analyzers                           │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐  │  │
│  │  │ Screenshot │  │    Log     │  │     Network        │  │  │
│  │  │ Analyzer   │  │  Analyzer  │  │     Analyzer       │  │  │
│  │  └────────────┘  └────────────┘  └────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────┐
                    │  Failure        │
                    │  Analysis       │
                    │  Report         │
                    └─────────────────┘
```

### 2.2 模块划分

说明：以下模块划分用于表达目标模块边界，不代表当前仓库已全部存在；当前仓库真实实现仍以根目录脚本为主，请以 `1.4 当前实现状态与卡点` 和实际目录为准。

当前仓库实际存在的核心入口：

- `agents/failure-analysis-agent/analyze.py`
- `agents/failure-analysis-agent/prompt.py`
- `agents/failure-analysis-agent/test_analyze.py`

| 模块 | 文件路径 | 职责 |
|------|---------|------|
| `analyze.py` | `agents/failure-analysis-agent/analyze.py` | 当前主入口，规则+模型双路径分析 |
| `evidence_collector.py` | `agents/failure-analysis-agent/src/evidence_collector.py` | 证据收集 |
| `failure_classifier.py` | `agents/failure-analysis-agent/src/failure_classifier.py` | 失败分类 |
| `root_cause_analyzer.py` | `agents/failure-analysis-agent/src/root_cause_analyzer.py` | 根因分析 |
| `analyzers/` | `agents/failure-analysis-agent/src/analyzers/` | 证据分析器 |
| `similar_case_retriever.py` | `agents/failure-analysis-agent/src/similar_case_retriever.py` | 相似案例检索 |
| `bug_type_classifier.py` | `agents/failure-analysis-agent/src/bug_type_classifier.py` | 应用/测试 bug 区分 |
| `report_generator.py` | `agents/failure-analysis-agent/src/report_generator.py` | 报告生成 |

---

## 3. 输入输出契约

### 3.1 输入 Schema

```python
# 目标 schema 示例（建议后续拆分到 agents/failure-analysis-agent/src/schema.py）

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime

class FailureCategory(str, Enum):
    LOCATOR_NOT_FOUND = "locator_not_found"
    ASSERTION_FAILED = "assertion_failed"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    AUTH_ERROR = "auth_error"
    APPLICATION_ERROR = "application_error"
    TEST_DATA_ERROR = "test_data_error"
    ENVIRONMENT_ERROR = "environment_error"
    UNKNOWN = "unknown"

class EvidenceType(str, Enum):
    SCREENSHOT = "screenshot"
    VIDEO = "video"
    TRACE = "trace"
    CONSOLE_LOG = "console_log"
    NETWORK_LOG = "network_log"
    PAGE_HTML = "page_html"
    TEST_LOG = "test_log"

class Evidence(BaseModel):
    """证据"""
    evidence_id: str
    type: EvidenceType
    path: Optional[str] = None
    content: Optional[str] = None  # 日志等文本内容
    metadata: Dict[str, Any] = {}
    captured_at: datetime

class FailedTestCase(BaseModel):
    """失败用例信息"""
    test_case_id: str
    test_point_id: str
    title: str
    file_path: str
    line_number: int
    error_message: str
    error_stack: str
    duration_ms: int
    retry_count: int
    environment: str

class FailureAnalysisInput(BaseModel):
    """Agent 输入"""
    request_id: str
    test_case: FailedTestCase
    evidence: List[Evidence]
    historical_failures: Optional[List[Dict]] = None  # 历史相似失败
    environment_info: Optional[Dict] = {
        "browser": "chromium",
        "browser_version": "latest",
        "os": "linux",
        "runner_version": "1.0"
    }
    
    class Config:
        schema_extra = {
            "example": {
                "request_id": "failure-analysis-001",
                "test_case": {
                    "test_case_id": "tc-001",
                    "title": "用户登录测试",
                    "error_message": "TimeoutError: Timeout 30s exceeded"
                },
                "evidence": [
                    {
                        "evidence_id": "ev-001",
                        "type": "screenshot",
                        "path": "/screenshots/failure-001.png"
                    }
                ]
            }
        }

class AnalysisConfidence(BaseModel):
    """分析置信度"""
    overall: float  # 0-1
    category_confidence: float
    cause_confidence: float
    evidence_quality: str  # high/medium/low

class FailureAnalysisReport(BaseModel):
    """失败分析报告"""
    report_id: str
    failure_category: FailureCategory
    likely_cause: str
    confidence: AnalysisConfidence
    evidence_summary: Dict[str, Any]
    error_analysis: Dict[str, Any]
    alternative_hypotheses: List[Dict]
    application_bug_probability: float  # 0-1
    test_bug_probability: float  # 0-1
    suggested_actions: List[str]
    similar_cases: List[Dict]
    requires_manual_review: bool
    metadata: Dict[str, Any]

class FailureAnalysisOutput(BaseModel):
    """Agent 输出"""
    request_id: str
    analysis_report: FailureAnalysisReport
    analysis_details: Dict[str, Any] = {
        "processing_stages": [],
        "evidence_analyzed": 0,
        "similar_cases_found": 0
    }
    warnings: List[str] = []
    processing_time_ms: int
    agent_version: str
    model_used: str
    timestamp: datetime
    
    class Config:
        schema_extra = {
            "example": {
                "request_id": "failure-analysis-001",
                "analysis_report": {
                    "failure_category": "timeout",
                    "likely_cause": "页面加载超时，可能是网络慢或元素不存在",
                    "confidence": {"overall": 0.75},
                    "application_bug_probability": 0.3,
                    "test_bug_probability": 0.7
                },
                "processing_time_ms": 3456
            }
        }
```

---

## 4. 核心功能实现

说明：本章代码块主要用于表达目标拆分后的实现方式；当前仓库真实实现仍集中在根目录 `analyze.py`，下面的 `src/...` 示例应理解为后续重构蓝图，而不是现状文件。

### 4.1 证据收集器

```python
# agents/failure-analysis-agent/src/evidence_collector.py

from typing import List, Dict, Any
import os
from pathlib import Path

class EvidenceCollector:
    """证据收集器"""
    
    def collect(self, test_case: Dict, evidence_dir: str) -> List[Dict]:
        """收集测试失败相关证据"""
        evidence = []
        test_id = test_case.get('test_case_id', 'unknown')
        
        # 1. 截图证据
        screenshot_path = self._find_evidence(evidence_dir, test_id, '*.png')
        if screenshot_path:
            evidence.append({
                'evidence_id': f'ev-screenshot-{len(evidence)}',
                'type': 'screenshot',
                'path': str(screenshot_path),
                'metadata': self._get_file_metadata(screenshot_path)
            })
        
        # 2. 视频证据
        video_path = self._find_evidence(evidence_dir, test_id, '*.webm')
        if video_path:
            evidence.append({
                'evidence_id': f'ev-video-{len(evidence)}',
                'type': 'video',
                'path': str(video_path),
                'metadata': self._get_file_metadata(video_path)
            })
        
        # 3. Trace 证据
        trace_path = self._find_evidence(evidence_dir, test_id, 'trace.zip')
        if trace_path:
            evidence.append({
                'evidence_id': f'ev-trace-{len(evidence)}',
                'type': 'trace',
                'path': str(trace_path),
                'metadata': self._get_file_metadata(trace_path)
            })
        
        # 4. 日志证据
        log_path = self._find_evidence(evidence_dir, test_id, '*.log')
        if log_path:
            evidence.append({
                'evidence_id': f'ev-log-{len(evidence)}',
                'type': 'test_log',
                'path': str(log_path),
                'content': self._read_file(log_path),
                'metadata': self._get_file_metadata(log_path)
            })
        
        # 5. Network 证据
        network_path = self._find_evidence(evidence_dir, test_id, 'network.json')
        if network_path:
            evidence.append({
                'evidence_id': f'ev-network-{len(evidence)}',
                'type': 'network_log',
                'path': str(network_path),
                'content': self._read_file(network_path),
                'metadata': self._get_file_metadata(network_path)
            })
        
        return evidence
    
    def _find_evidence(self, evidence_dir: str, test_id: str, 
                       pattern: str) -> Path:
        """查找证据文件"""
        dir_path = Path(evidence_dir)
        
        # 按测试 ID 查找
        for file in dir_path.glob(f"*{test_id}*{pattern}"):
            return file
        
        # 按最新文件查找
        files = list(dir_path.glob(f"**/{pattern}"))
        if files:
            return max(files, key=lambda f: f.stat().st_mtime)
        
        return None
    
    def _get_file_metadata(self, file_path: Path) -> Dict:
        """获取文件元数据"""
        try:
            stat = file_path.stat()
            return {
                'size_bytes': stat.st_size,
                'modified_at': stat.st_mtime,
                'exists': True
            }
        except:
            return {'exists': False}
    
    def _read_file(self, file_path: Path) -> str:
        """读取文件内容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()[:10000]  # 限制大小
        except:
            return ""
```

### 4.2 失败分类器

```python
# agents/failure-analysis-agent/src/failure_classifier.py

from typing import Dict, List, Any
import re

class FailureClassifier:
    """失败分类器"""
    
    CATEGORY_PATTERNS = {
        'locator_not_found': [
            r'Element.*not found',
            r'locator.*not found',
            r'NoSuchElement',
            r'TimeoutError.*wait.*selector',
            r'Element.*not visible',
            r'Element.*not interactable'
        ],
        'assertion_failed': [
            r'AssertionError',
            r'assert.*failed',
            r'expected.*but got',
            r'Expected:.*Actual:',
            r'to_be_visible.*failed',
            r'to_contain_text.*failed'
        ],
        'timeout': [
            r'TimeoutError',
            r'Timeout.*exceeded',
            r'Timeout.*wait',
            r'Navigation timeout',
            r'Response timeout'
        ],
        'network_error': [
            r'NetworkError',
            r'ERR_.*',
            r'Connection.*refused',
            r'Connection.*reset',
            r'503.*Service Unavailable',
            r'502.*Bad Gateway',
            r'500.*Internal Server Error'
        ],
        'auth_error': [
            r'Authentication.*failed',
            r'Unauthorized',
            r'401.*Unauthorized',
            r'403.*Forbidden',
            r'Token.*expired',
            r'Session.*expired'
        ],
        'application_error': [
            r'JavaScript.*error',
            r'Uncaught.*Exception',
            r'Application.*error',
            r'Internal.*error'
        ],
        'test_data_error': [
            r'Data.*not found',
            r'Invalid.*data',
            r'Test.*data.*missing',
            r'Fixture.*not found'
        ],
        'environment_error': [
            r'Environment.*not configured',
            r'Service.*unavailable',
            r'Database.*connection.*failed',
            r'Browser.*crashed'
        ]
    }
    
    def classify(self, error_message: str, error_stack: str,
                 evidence: List[Dict]) -> Dict[str, Any]:
        """分类失败类型"""
        combined_text = f"{error_message}\n{error_stack}"
        
        # 1. 基于错误消息匹配
        category_scores = {}
        for category, patterns in self.CATEGORY_PATTERNS.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    score += 1
            if score > 0:
                category_scores[category] = score
        
        # 2. 基于证据调整
        category_scores = self._adjust_with_evidence(category_scores, evidence)
        
        # 3. 确定最终分类
        if category_scores:
            best_category = max(category_scores, key=category_scores.get)
            confidence = min(1.0, category_scores[best_category] * 0.3)
        else:
            best_category = 'unknown'
            confidence = 0.3
        
        return {
            'category': best_category,
            'confidence': confidence,
            'all_scores': category_scores,
            'matched_patterns': self._get_matched_patterns(combined_text)
        }
    
    def _adjust_with_evidence(self, category_scores: Dict, 
                              evidence: List[Dict]) -> Dict:
        """用证据调整分类分数"""
        for ev in evidence:
            ev_type = ev.get('type', '')
            
            # 截图分析（简化）
            if ev_type == 'screenshot':
                # TODO: 实际应该分析截图内容
                pass
            
            # Network 日志分析
            if ev_type == 'network_log':
                content = ev.get('content', '')
                if '500' in content or '503' in content:
                    category_scores['application_error'] = \
                        category_scores.get('application_error', 0) + 2
                if 'ERR_' in content:
                    category_scores['network_error'] = \
                        category_scores.get('network_error', 0) + 2
        
        return category_scores
    
    def _get_matched_patterns(self, text: str) -> List[str]:
        """获取匹配的模式"""
        matched = []
        for category, patterns in self.CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    matched.append(f"{category}: {pattern}")
        return matched[:5]  # 限制数量
```

### 4.3 根因分析器

```python
# agents/failure-analysis-agent/src/root_cause_analyzer.py

from typing import Dict, List, Any

class RootCauseAnalyzer:
    """根因分析器"""
    
    CAUSE_TEMPLATES = {
        'locator_not_found': [
            {
                'cause': '元素定位器已变更',
                'indicators': ['DOM 结构变化', 'CSS 选择器失效'],
                'probability': 0.6
            },
            {
                'cause': '页面未完全加载',
                'indicators': ['网络慢', '资源加载超时'],
                'probability': 0.3
            },
            {
                'cause': '元素在 iframe 中',
                'indicators': ['跨 frame 访问'],
                'probability': 0.1
            }
        ],
        'assertion_failed': [
            {
                'cause': '业务逻辑变更',
                'indicators': ['文本内容变化', '预期值过时'],
                'probability': 0.5
            },
            {
                'cause': '测试数据问题',
                'indicators': ['数据不匹配', '数据缺失'],
                'probability': 0.3
            },
            {
                'cause': '断言过于严格',
                'indicators': ['格式细微差异'],
                'probability': 0.2
            }
        ],
        'timeout': [
            {
                'cause': '网络速度慢',
                'indicators': ['资源加载慢', 'API 响应慢'],
                'probability': 0.4
            },
            {
                'cause': '元素加载条件未满足',
                'indicators': ['异步加载未完成'],
                'probability': 0.4
            },
            {
                'cause': '超时时间设置过短',
                'indicators': ['其他测试正常'],
                'probability': 0.2
            }
        ],
        'network_error': [
            {
                'cause': '后端服务异常',
                'indicators': ['5xx 错误', '服务不可用'],
                'probability': 0.7
            },
            {
                'cause': '网络配置问题',
                'indicators': ['连接拒绝', 'DNS 解析失败'],
                'probability': 0.2
            },
            {
                'cause': '测试环境问题',
                'indicators': ['环境不稳定'],
                'probability': 0.1
            }
        ]
    }
    
    def analyze(self, category: str, evidence: List[Dict],
                error_message: str) -> Dict[str, Any]:
        """分析根因"""
        templates = self.CAUSE_TEMPLATES.get(category, [])
        
        if not templates:
            return {
                'likely_cause': '未知根因',
                'confidence': 0.3,
                'alternative_causes': [],
                'supporting_evidence': []
            }
        
        # 选择最可能的根因
        best_cause = max(templates, key=lambda x: x['probability'])
        
        # 用证据验证
        verified_causes = self._verify_with_evidence(templates, evidence)
        
        if verified_causes:
            best_cause = verified_causes[0]
        
        return {
            'likely_cause': best_cause['cause'],
            'confidence': best_cause['probability'],
            'indicators': best_cause['indicators'],
            'alternative_causes': [
                {
                    'cause': c['cause'],
                    'probability': c['probability']
                }
                for c in templates if c != best_cause
            ][:3],
            'supporting_evidence': self._find_supporting_evidence(
                best_cause['indicators'], evidence
            )
        }
    
    def _verify_with_evidence(self, causes: List[Dict], 
                              evidence: List[Dict]) -> List[Dict]:
        """用证据验证根因"""
        verified = []
        
        for cause in causes:
            score = cause['probability']
            indicators = cause.get('indicators', [])
            
            # 检查证据是否支持
            for ev in evidence:
                content = ev.get('content', '')
                
                for indicator in indicators:
                    if indicator.lower() in content.lower():
                        score += 0.1
            
            cause['verified_probability'] = min(1.0, score)
            verified.append(cause)
        
        # 按验证后的概率排序
        verified.sort(key=lambda x: x.get('verified_probability', 0), reverse=True)
        return verified
    
    def _find_supporting_evidence(self, indicators: List[str],
                                  evidence: List[Dict]) -> List[Dict]:
        """找到支撑证据"""
        supporting = []
        
        for ev in evidence:
            content = ev.get('content', '')
            for indicator in indicators:
                if indicator.lower() in content.lower():
                    supporting.append({
                        'evidence_id': ev['evidence_id'],
                        'type': ev['type'],
                        'indicator': indicator
                    })
                    break
        
        return supporting
```

### 4.4 应用/测试 Bug 区分器

```python
# agents/failure-analysis-agent/src/bug_type_classifier.py

from typing import Dict, List, Any

class BugTypeClassifier:
    """应用 Bug vs 测试 Bug 分类器"""
    
    def classify(self, failure_category: str, root_cause: Dict,
                 evidence: List[Dict], historical_data: Dict) -> Dict[str, Any]:
        """区分应用 bug 和测试脚本 bug"""
        
        # 特征提取
        features = self._extract_features(
            failure_category, root_cause, evidence, historical_data
        )
        
        # 评分
        application_score = self._score_application_bug(features)
        test_score = self._score_test_bug(features)
        
        # 归一化
        total = application_score + test_score
        if total > 0:
            app_prob = application_score / total
            test_prob = test_score / total
        else:
            app_prob = 0.5
            test_prob = 0.5
        
        return {
            'application_bug_probability': app_prob,
            'test_bug_probability': test_prob,
            'classification': 'application' if app_prob > test_prob else 'test',
            'confidence': max(app_prob, test_prob),
            'reasoning': self._generate_reasoning(features, app_prob, test_prob)
        }
    
    def _extract_features(self, failure_category: str, root_cause: Dict,
                         evidence: List[Dict], historical_data: Dict) -> Dict:
        """提取分类特征"""
        return {
            'category': failure_category,
            'root_cause': root_cause.get('likely_cause', ''),
            'is_recurring': self._is_recurring_failure(evidence, historical_data),
            'affects_multiple_tests': self._affects_multiple_tests(evidence),
            'has_network_error': self._has_network_error(evidence),
            'has_js_error': self._has_js_error(evidence),
            'is_locator_issue': failure_category == 'locator_not_found',
            'is_assertion_issue': failure_category == 'assertion_failed',
            'test_age_days': self._get_test_age(evidence, historical_data)
        }
    
    def _score_application_bug(self, features: Dict) -> float:
        """应用 bug 评分"""
        score = 0.0
        
        # 网络错误 → 可能是应用问题
        if features['has_network_error']:
            score += 0.3
        
        # JS 错误 → 应用问题
        if features['has_js_error']:
            score += 0.3
        
        # 影响多个测试 → 可能是应用问题
        if features['affects_multiple_tests']:
            score += 0.2
        
        #  recurring failure → 可能是应用问题
        if features['is_recurring']:
            score += 0.1
        
        # 特定类别
        if features['category'] in ['network_error', 'application_error', 'auth_error']:
            score += 0.2
        
        return min(1.0, score)
    
    def _score_test_bug(self, features: Dict) -> float:
        """测试 bug 评分"""
        score = 0.0
        
        # 定位器问题 → 测试问题
        if features['is_locator_issue']:
            score += 0.4
        
        # 断言问题 → 可能是测试问题
        if features['is_assertion_issue']:
            score += 0.2
        
        # 新测试 → 更可能是测试问题
        if features['test_age_days'] < 7:
            score += 0.2
        
        # 仅影响单个测试
        if not features['affects_multiple_tests']:
            score += 0.1
        
        return min(1.0, score)
    
    def _is_recurring_failure(self, evidence: List[Dict], 
                             historical_data: Dict) -> bool:
        """是否是重复失败"""
        # 检查历史数据
        return historical_data.get('consecutive_failures', 0) > 2
    
    def _affects_multiple_tests(self, evidence: List[Dict]) -> bool:
        """是否影响多个测试"""
        # 简化实现
        return False
    
    def _has_network_error(self, evidence: List[Dict]) -> bool:
        """是否有网络错误"""
        for ev in evidence:
            if ev['type'] == 'network_log':
                content = ev.get('content', '')
                if 'ERR_' in content or '500' in content:
                    return True
        return False
    
    def _has_js_error(self, evidence: List[Dict]) -> bool:
        """是否有 JS 错误"""
        for ev in evidence:
            if ev['type'] == 'console_log':
                content = ev.get('content', '')
                if 'Error' in content or 'Exception' in content:
                    return True
        return False
    
    def _get_test_age(self, evidence: List[Dict], 
                     historical_data: Dict) -> int:
        """获取测试年龄（天）"""
        return historical_data.get('test_age_days', 30)
    
    def _generate_reasoning(self, features: Dict, app_prob: float, 
                           test_prob: float) -> List[str]:
        """生成推理说明"""
        reasoning = []
        
        if features['has_network_error']:
            reasoning.append('检测到网络错误，可能是应用问题')
        if features['is_locator_issue']:
            reasoning.append('定位器失败，可能是测试脚本问题')
        if features['is_recurring']:
            reasoning.append('重复失败，需要进一步调查')
        if features['test_age_days'] < 7:
            reasoning.append('新测试，可能存在脚本问题')
        
        reasoning.append(f'应用 bug 概率：{app_prob:.1%}')
        reasoning.append(f'测试 bug 概率：{test_prob:.1%}')
        
        return reasoning
```

### 4.5 相似案例检索器

```python
# agents/failure-analysis-agent/src/similar_case_retriever.py

from typing import List, Dict, Any
import hashlib

class SimilarCaseRetriever:
    """相似失败案例检索器"""
    
    def __init__(self, historical_db: List[Dict] = None):
        self.historical_db = historical_db or []
    
    def retrieve(self, current_failure: Dict, 
                 max_results: int = 5) -> List[Dict]:
        """检索相似失败案例"""
        if not self.historical_db:
            return []
        
        # 计算当前失败的指纹
        current_fp = self._calculate_fingerprint(current_failure)
        
        # 计算相似度
        scored_cases = []
        for historical in self.historical_db:
            similarity = self._calculate_similarity(current_failure, historical)
            if similarity > 0.5:  # 阈值
                scored_cases.append({
                    'case': historical,
                    'similarity': similarity
                })
        
        # 排序并返回
        scored_cases.sort(key=lambda x: x['similarity'], reverse=True)
        return [c['case'] for c in scored_cases[:max_results]]
    
    def _calculate_fingerprint(self, failure: Dict) -> str:
        """计算失败指纹"""
        content = f"{failure.get('category', '')}:{failure.get('error_message', '')}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _calculate_similarity(self, case1: Dict, case2: Dict) -> float:
        """计算两个失败的相似度"""
        similarity = 0.0
        
        # 类别相同
        if case1.get('category') == case2.get('category'):
            similarity += 0.4
        
        # 错误消息相似
        msg1 = case1.get('error_message', '')
        msg2 = case2.get('error_message', '')
        if msg1 and msg2:
            msg_similarity = self._string_similarity(msg1, msg2)
            similarity += msg_similarity * 0.4
        
        # 根因相似
        cause1 = case1.get('root_cause', '')
        cause2 = case2.get('root_cause', '')
        if cause1 and cause2 and cause1 == cause2:
            similarity += 0.2
        
        return min(1.0, similarity)
    
    def _string_similarity(self, s1: str, s2: str) -> float:
        """计算字符串相似度（简化 Jaccard）"""
        set1 = set(s1.lower().split())
        set2 = set(s2.lower().split())
        
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
```

---

## 5. Agent 主实现

```python
# agents/failure-analysis-agent/analyze.py

import time
from datetime import datetime
from typing import Dict, Any

from .schemas import (
    FailureAnalysisInput,
    FailureAnalysisOutput,
    FailureAnalysisReport,
    AnalysisConfidence
)
from .evidence_collector import EvidenceCollector
from .failure_classifier import FailureClassifier
from .root_cause_analyzer import RootCauseAnalyzer
from .bug_type_classifier import BugTypeClassifier
from .similar_case_retriever import SimilarCaseRetriever
from .report_generator import ReportGenerator

class FailureAnalysisAgent:
    """Failure Analysis Agent 主类"""
    
    VERSION = "0.1.0"
    MODEL_USED = "qwen-3.5-plus"
    
    def __init__(self, historical_db: list = None):
        self.evidence_collector = EvidenceCollector()
        self.classifier = FailureClassifier()
        self.root_cause_analyzer = RootCauseAnalyzer()
        self.bug_classifier = BugTypeClassifier()
        self.similar_retriever = SimilarCaseRetriever(historical_db)
        self.report_generator = ReportGenerator()
    
    async def analyze(self, input_data: FailureAnalysisInput) -> FailureAnalysisOutput:
        """分析失败"""
        start_time = time.time()
        processing_stages = []
        
        # Stage 1: 失败分类
        classification = self.classifier.classify(
            input_data.test_case.error_message,
            input_data.test_case.error_stack,
            [e.model_dump() for e in input_data.evidence]
        )
        processing_stages.append({
            'stage': 'failure_classification',
            'status': 'completed',
            'category': classification['category'],
            'confidence': classification['confidence']
        })
        
        # Stage 2: 根因分析
        root_cause = self.root_cause_analyzer.analyze(
            classification['category'],
            classification,
            [e.model_dump() for e in input_data.evidence],
            input_data.test_case.error_message
        )
        processing_stages.append({
            'stage': 'root_cause_analysis',
            'status': 'completed',
            'likely_cause': root_cause['likely_cause']
        })
        
        # Stage 3: 应用/测试 bug 区分
        bug_type = self.bug_classifier.classify(
            classification['category'],
            root_cause,
            [e.model_dump() for e in input_data.evidence],
            input_data.historical_failures or {}
        )
        processing_stages.append({
            'stage': 'bug_type_classification',
            'status': 'completed',
            'application_probability': bug_type['application_bug_probability']
        })
        
        # Stage 4: 相似案例检索
        similar_cases = self.similar_retriever.retrieve(
            {
                'category': classification['category'],
                'error_message': input_data.test_case.error_message,
                'root_cause': root_cause['likely_cause']
            }
        )
        processing_stages.append({
            'stage': 'similar_case_retrieval',
            'status': 'completed',
            'similar_count': len(similar_cases)
        })
        
        # Stage 5: 生成报告
        report = FailureAnalysisReport(
            report_id=f"report-{input_data.request_id}",
            failure_category=classification['category'],
            likely_cause=root_cause['likely_cause'],
            confidence=AnalysisConfidence(
                overall=classification['confidence'],
                category_confidence=classification['confidence'],
                cause_confidence=root_cause['confidence'],
                evidence_quality=self._assess_evidence_quality(input_data.evidence)
            ),
            evidence_summary=self._summarize_evidence(input_data.evidence),
            error_analysis={
                'message': input_data.test_case.error_message,
                'stack': input_data.test_case.error_stack[:500],
                'matched_patterns': classification.get('matched_patterns', [])
            },
            alternative_hypotheses=root_cause.get('alternative_causes', []),
            application_bug_probability=bug_type['application_bug_probability'],
            test_bug_probability=bug_type['test_bug_probability'],
            suggested_actions=self._generate_actions(
                classification['category'], root_cause, bug_type
            ),
            similar_cases=similar_cases,
            requires_manual_review=classification['confidence'] < 0.6,
            metadata={
                'test_case_id': input_data.test_case.test_case_id,
                'environment': input_data.test_case.environment
            }
        )
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        return FailureAnalysisOutput(
            request_id=input_data.request_id,
            analysis_report=report,
            analysis_details={
                'processing_stages': processing_stages,
                'evidence_analyzed': len(input_data.evidence),
                'similar_cases_found': len(similar_cases)
            },
            warnings=self._generate_warnings(classification, bug_type),
            processing_time_ms=processing_time_ms,
            agent_version=self.VERSION,
            model_used=self.MODEL_USED,
            timestamp=datetime.now()
        )
    
    def _assess_evidence_quality(self, evidence: list) -> str:
        """评估证据质量"""
        if len(evidence) >= 4:
            return 'high'
        elif len(evidence) >= 2:
            return 'medium'
        else:
            return 'low'
    
    def _summarize_evidence(self, evidence: list) -> Dict:
        """总结证据"""
        return {
            'total_count': len(evidence),
            'types': list(set(e.type for e in evidence)),
            'has_screenshot': any(e.type == 'screenshot' for e in evidence),
            'has_video': any(e.type == 'video' for e in evidence),
            'has_trace': any(e.type == 'trace' for e in evidence),
            'has_logs': any(e.type in ['console_log', 'network_log', 'test_log'] for e in evidence)
        }
    
    def _generate_actions(self, category: str, root_cause: Dict, 
                         bug_type: Dict) -> list:
        """生成建议行动"""
        actions = []
        
        if category == 'locator_not_found':
            actions.append('检查元素定位器是否已变更')
            actions.append('验证页面是否完全加载')
        elif category == 'timeout':
            actions.append('增加超时时间')
            actions.append('检查网络性能')
        elif category == 'assertion_failed':
            actions.append('验证断言预期值是否正确')
            actions.append('检查测试数据')
        
        if bug_type['application_bug_probability'] > 0.7:
            actions.append('提交应用 bug 报告')
        elif bug_type['test_bug_probability'] > 0.7:
            actions.append('修复测试脚本')
        
        return actions
    
    def _generate_warnings(self, classification: Dict, bug_type: Dict) -> list:
        """生成警告"""
        warnings = []
        
        if classification['confidence'] < 0.6:
            warnings.append('分析置信度较低，建议人工复核')
        
        if abs(bug_type['application_bug_probability'] - 0.5) < 0.2:
            warnings.append('应用/测试 bug 区分不明确')
        
        return warnings
```

---

## 6. 测试策略

说明：以下测试文件名和代码片段以目标测试形态给出，不代表当前仓库已经存在对应 `tests/` 目录；当前真实测试入口仍以 `agents/failure-analysis-agent/test_analyze.py` 为主。

### 6.1 单元测试

```python
# agents/failure-analysis-agent/tests/test_failure_classifier.py

import pytest
from src.failure_classifier import FailureClassifier

class TestFailureClassifier:
    def test_classify_locator_not_found(self):
        classifier = FailureClassifier()
        
        result = classifier.classify(
            error_message="Element button#submit not found",
            error_stack="TimeoutError: wait_for_selector failed",
            evidence=[]
        )
        
        assert result['category'] == 'locator_not_found'
        assert result['confidence'] > 0.3
    
    def test_classify_assertion_failed(self):
        classifier = FailureClassifier()
        
        result = classifier.classify(
            error_message="AssertionError: expected 'Hello' but got 'World'",
            error_stack="AssertionError at test.py:10",
            evidence=[]
        )
        
        assert result['category'] == 'assertion_failed'
```

### 6.2 Golden Test Set

```python
# agents/failure-analysis-agent/tests/golden_tests.py

import pytest
from src.agent import FailureAnalysisAgent
from src.schemas import FailureAnalysisInput, FailedTestCase, Evidence

GOLDEN_TEST_CASES = [
    {
        'name': '定位器失败分析',
        'input': FailureAnalysisInput(
            request_id='golden-fa-001',
            test_case=FailedTestCase(
                test_case_id='tc-001',
                test_point_id='tp-001',
                title='登录测试',
                file_path='tests/test_login.py',
                line_number=10,
                error_message='Element button#submit not found',
                error_stack='TimeoutError: wait_for_selector failed',
                duration_ms=30000,
                retry_count=0,
                environment='test'
            ),
            evidence=[
                Evidence(
                    evidence_id='ev-001',
                    type='screenshot',
                    path='/screenshots/failure.png'
                )
            ]
        ),
        'expected': {
            'category': 'locator_not_found',
            'min_confidence': 0.5,
            'has_suggestions': True
        }
    }
]

@pytest.mark.parametrize('test_case', GOLDEN_TEST_CASES)
@pytest.mark.asyncio
async def test_golden_cases(test_case):
    agent = FailureAnalysisAgent()
    output = await agent.analyze(test_case['input'])
    
    assert output.analysis_report.failure_category.value == test_case['expected']['category']
    assert output.analysis_report.confidence.overall >= test_case['expected']['min_confidence']
    assert len(output.analysis_report.suggested_actions) > 0 == test_case['expected']['has_suggestions']
```

---

## 7. 实施计划

### Phase 1: 基础框架（Week 1-2）

| 任务 | 预计 | 状态 |
|------|------|------|
| 项目结构搭建 | 2 天 | ⏳ |
| 输入输出 Schema 定义 | 2 天 | ⏳ |
| 证据收集器实现 | 2 天 | ⏳ |
| 失败分类器实现 | 2 天 | ⏳ |
| 单元测试框架 | 1 天 | ⏳ |

### Phase 2: 核心能力（Week 3-4）

| 任务 | 预计 | 状态 |
|------|------|------|
| 根因分析器实现 | 2 天 | ⏳ |
| Bug 类型分类器实现 | 2 天 | ⏳ |
| 相似案例检索器实现 | 2 天 | ⏳ |
| Agent 主逻辑 | 3 天 | ⏳ |
| 集成测试 | 2 天 | ⏳ |

### Phase 3: 企业级能力（Week 5-6）

| 任务 | 预计 | 状态 |
|------|------|------|
| 多源证据综合分析完善 | 2 天 | ⏳ |
| Golden Test Set 建立 | 2 天 | ⏳ |
| 监控指标接入 | 2 天 | ⏳ |
| 文档完善 | 2 天 | ⏳ |
| 验收测试 | 1 天 | ⏳ |

---

## 8. 验收标准

### 功能验收

- [ ] 失败分类准确率 > 85%
- [ ] 根因定位准确率 > 75%
- [ ] 应用/测试 bug 区分 > 80%
- [ ] 相似案例召回率 > 70%
- [ ] 可解释性 100%

### 质量验收

- [ ] 单元测试覆盖率 > 85%
- [ ] Golden Test Set 通过率 > 85%
- [ ] P95 延迟 < 8s
- [ ] 证据利用率 > 90%

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
