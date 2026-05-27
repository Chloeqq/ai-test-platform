# 失败聚类与风险分析设计方案

**状态**: 设计稿（已补当前状态说明）  
**版本**: 1.0  
**创建时间**: 2026-04-02

## 文档状态说明（2026-04-02 更新）

这份文档描述的是“第二版平台级失败分析能力”的理想设计，不再等同于项目当前的起点。

当前状态总结：

- failure clusters：`已完成第一版`
- flaky analysis：`已完成第一版`
- governance risk / manager summary：`已完成第一版`
- `FailureClusteringService / FlakyDetectionService / RiskScoringService` 作为本文同名独立类：`未按原样实现`
- “缺少跨 case 聚类”这一旧判断：`不再成立`

当前更准确的说法是：

> 失败聚类、Flaky、治理风险第一版已经落地并进入 dashboard / governance 消费；本文更适合作为“第二版算法增强设计”，而不是从 0 到 1 的实施文档。

---

## 一、背景与目标

### 当前问题

```
单次失败 → AI 分析 → 单 case 报告
    ↓
    缺少跨 case 洞察
    缺少批量趋势分析
    缺少根因聚类
```

**痛点**:
1. 每个失败单独分析，无法发现系统性问题
2. 无法区分环境问题 vs 应用 bug vs 测试脚本问题
3. 无法识别 flaky 测试
4. 回归报告缺少风险排序和决策建议

### 目标能力

```
批量失败 → 聚类分析 → 根因分组 → 风险排序 → 决策建议
    ↓
    识别系统性问题
    区分失败来源
    发现 flaky 测试
    支持发布决策
```

---

## 二、数据模型设计

> 当前状态说明
>
> 本节中的 `FailureRecord / FailureCluster / FlakyTestRecord / RiskScore` 是完整目标模型。
> 当前项目里已经有 failure cluster、flaky、治理风险的实际消费能力，但还没有按本文定义收口为这组独立 schema。

### 2.1 失败记录模型

```python
# apps/shared_backend/schemas/failure_record.py

from enum import Enum
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class FailureSource(Enum):
    """失败来源"""
    APPLICATION_BUG = "application_bug"     # 应用缺陷
    TEST_SCRIPT_BUG = "test_script_bug"     # 测试脚本缺陷
    ENVIRONMENT_ISSUE = "environment_issue" # 环境问题
    DATA_ISSUE = "data_issue"               # 测试数据问题
    NETWORK_ISSUE = "network_issue"         # 网络问题
    TIMEOUT = "timeout"                     # 超时
    FLAKY = "flaky"                         # 不稳定测试
    UNKNOWN = "unknown"                     # 未知


class FailureCategory(Enum):
    """失败类别"""
    ELEMENT_NOT_FOUND = "element_not_found"
    ELEMENT_NOT_INTERACTABLE = "element_not_interactable"
    ASSERTION_FAILED = "assertion_failed"
    NAVIGATION_FAILED = "navigation_failed"
    NETWORK_ERROR = "network_error"
    TIMEOUT_EXCEEDED = "timeout_exceeded"
    JAVASCRIPT_ERROR = "javascript_error"
    AUTHENTICATION_FAILED = "authentication_failed"
    DATA_VALIDATION_FAILED = "data_validation_failed"
    OTHER = "other"


class FailureSeverity(Enum):
    """失败严重程度"""
    BLOCKER = "blocker"     # 阻塞发布
    CRITICAL = "critical"   # 严重问题
    MAJOR = "major"         # 主要问题
    MINOR = "minor"         # 次要问题
    TRIVIAL = "trivial"     # 轻微问题


class FailureRecord(BaseModel):
    """失败记录"""
    
    # 标识
    id: str = Field(..., description="失败记录唯一标识")
    execution_id: str = Field(..., description="执行记录 ID")
    case_id: str = Field(..., description="用例 ID")
    step_id: Optional[str] = Field(None, description="失败步骤 ID")
    
    # 失败信息
    error_message: str = Field(..., description="错误消息")
    error_stack: Optional[str] = Field(None, description="错误堆栈")
    error_type: str = Field(..., description="错误类型")
    
    # 分类
    source: FailureSource = Field(default=FailureSource.UNKNOWN)
    category: FailureCategory = Field(default=FailureCategory.OTHER)
    severity: FailureSeverity = Field(default=FailureSeverity.MAJOR)
    
    # 上下文
    page: str = Field(..., description="失败页面")
    url: str = Field(..., description="失败时 URL")
    browser: str = Field(default="chromium", description="浏览器")
    environment: str = Field(default="unknown", description="环境")
    
    # 证据
    screenshot_path: Optional[str] = None
    video_path: Optional[str] = None
    trace_path: Optional[str] = None
    html_path: Optional[str] = None
    console_logs: list[str] = Field(default_factory=list)
    network_logs: list[dict] = Field(default_factory=list)
    
    # AI 分析结果
    ai_analysis: Optional[dict[str, Any]] = None
    ai_confidence: float = Field(default=0.0, ge=0, le=1)
    ai_recommendation: Optional[str] = None
    
    # 时间戳
    failed_at: datetime = Field(default_factory=datetime.utcnow)
    analyzed_at: Optional[datetime] = None
    
    # 元数据
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True


class FailureCluster(BaseModel):
    """失败聚类"""
    
    # 标识
    id: str = Field(..., description="聚类唯一标识")
    name: str = Field(..., description="聚类名称")
    
    # 聚类特征
    cluster_key: str = Field(..., description="聚类键 (用于分组)")
    common_pattern: str = Field(..., description="共同模式")
    
    # 成员
    failure_ids: list[str] = Field(default_factory=list, description="成员失败 ID 列表")
    case_ids: list[str] = Field(default_factory=list, description="涉及用例 ID 列表")
    
    # 统计
    count: int = Field(default=0, description="失败数量")
    first_occurrence: datetime = Field(default_factory=datetime.utcnow)
    last_occurrence: datetime = Field(default_factory=datetime.utcnow)
    
    # 根因分析
    root_cause: Optional[str] = None
    root_cause_confidence: float = Field(default=0.0)
    
    # 影响评估
    affected_modules: list[str] = Field(default_factory=list)
    affected_pages: list[str] = Field(default_factory=list)
    severity: FailureSeverity = Field(default=FailureSeverity.MAJOR)
    
    # 处理状态
    status: str = Field(default="new", description="处理状态")  # new, investigating, resolved, ignored
    assigned_to: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class FlakyTestRecord(BaseModel):
    """Flaky 测试记录"""
    
    case_id: str = Field(..., description="用例 ID")
    case_name: str = Field(..., description="用例名称")
    
    # 统计
    total_runs: int = Field(..., description="总运行次数")
    passed_runs: int = Field(..., description="通过次数")
    failed_runs: int = Field(..., description="失败次数")
    
    # Flaky 指标
    flaky_rate: float = Field(..., ge=0, le=1, description="Flaky 率")
    consecutive_failures: int = Field(default=0, description="连续失败次数")
    last_failure_at: Optional[datetime] = None
    
    # 失败模式
    failure_patterns: list[str] = Field(default_factory=list)
    common_error_messages: list[str] = Field(default_factory=list)
    
    # 可能原因
    suspected_causes: list[str] = Field(default_factory=list)
    
    # 处理建议
    recommendations: list[str] = Field(default_factory=list)
    
    # 时间戳
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def compute_flaky_rate(self):
        """计算 Flaky 率"""
        if self.total_runs == 0:
            self.flaky_rate = 0.0
        else:
            # Flaky 率 = 失败率 * (1 - 连续失败倾向)
            failure_rate = self.failed_runs / self.total_runs
            streak_penalty = min(1.0, self.consecutive_failures / 5)
            self.flaky_rate = failure_rate * (1 - streak_penalty * 0.5)
```

### 2.2 风险评分模型

```python
class RiskScore(BaseModel):
    """风险评分"""
    
    # 综合评分 (0-100)
    overall_score: float = Field(..., ge=0, le=100)
    
    # 维度评分
    failure_rate_score: float = Field(..., ge=0, le=100)  # 失败率维度
    severity_score: float = Field(..., ge=0, le=100)      # 严重程度维度
    trend_score: float = Field(..., ge=0, le=100)         # 趋势维度
    coverage_score: float = Field(..., ge=0, le=100)      # 覆盖度维度
    flaky_score: float = Field(..., ge=0, le=100)         # 稳定性维度
    
    # 风险等级
    risk_level: str = Field(..., description="风险等级")  # low, medium, high, critical
    
    # 风险因素
    risk_factors: list[dict[str, Any]] = Field(default_factory=list)
    
    # 建议
    recommendations: list[str] = Field(default_factory=list)
    
    # 时间戳
    computed_at: datetime = Field(default_factory=datetime.utcnow)
    
    @classmethod
    def compute_level(cls, score: float) -> str:
        """根据评分计算风险等级"""
        if score >= 80:
            return "critical"
        elif score >= 60:
            return "high"
        elif score >= 40:
            return "medium"
        else:
            return "low"


class ReleaseReadiness(BaseModel):
    """发布就绪评估"""
    
    # 评估结果
    ready: bool = Field(..., description="是否就绪")
    confidence: float = Field(..., ge=0, le=1, description="置信度")
    
    # 风险评分
    risk_score: RiskScore
    
    # 门禁检查结果
    gate_checks: list[dict[str, Any]] = Field(default_factory=list)
    
    # 阻塞问题
    blockers: list[str] = Field(default_factory=list)
    
    # 警告
    warnings: list[str] = Field(default_factory=list)
    
    # 建议
    recommendation: str = Field(..., description="发布建议")
    
    # 时间戳
    assessed_at: datetime = Field(default_factory=datetime.utcnow)
```

---

## 三、服务层设计

### 3.1 失败聚类服务

```python
# apps/web-ui-service/app/services/failure_clustering_service.py

from typing import Optional
from collections import defaultdict
import hashlib

class FailureClusteringService:
    """失败聚类服务"""
    
    def __init__(
        self,
        failure_repository: FailureRepository,
        cluster_repository: ClusterRepository,
        ai_analysis_service: AIAnalysisService,
    ):
        self.failure_repo = failure_repository
        self.cluster_repo = cluster_repository
        self.ai_service = ai_analysis_service
    
    def compute_cluster_key(self, failure: FailureRecord) -> str:
        """计算聚类键"""
        # 多维度聚类策略
        components = [
            failure.category,           # 按类别
            self._normalize_error(failure.error_message),  # 标准化错误消息
            failure.page,               # 按页面
            self._extract_module(failure.url),  # 按模块
        ]
        key_str = "|".join(components)
        return hashlib.md5(key_str.encode()).hexdigest()[:12]
    
    def _normalize_error(self, error_message: str) -> str:
        """标准化错误消息 (移除动态内容)"""
        import re
        # 移除时间戳
        normalized = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', '<TIMESTAMP>', error_message)
        # 移除 UUID
        normalized = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '<UUID>', normalized, flags=re.I)
        # 移除数字 ID
        normalized = re.sub(r'\b\d{5,}\b', '<ID>', normalized)
        # 移除动态元素选择器
        normalized = re.sub(r'\[data-id="[^\"]+"\]', '[data-id="<ID>"]', normalized)
        return normalized[:200]  # 限制长度
    
    def _extract_module(self, url: str) -> str:
        """从 URL 提取模块"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')
        return path_parts[0] if path_parts else "unknown"
    
    async def cluster_failures(
        self,
        execution_ids: list[str],
        min_cluster_size: int = 2,
    ) -> list[FailureCluster]:
        """对失败进行聚类"""
        
        # 1. 获取失败记录
        failures = await self.failure_repo.get_by_executions(execution_ids)
        
        # 2. 分组
        groups: dict[str, list[FailureRecord]] = defaultdict(list)
        for failure in failures:
            key = self.compute_cluster_key(failure)
            groups[key].append(failure)
        
        # 3. 创建聚类
        clusters = []
        for cluster_key, group in groups.items():
            if len(group) < min_cluster_size:
                continue  # 跳过小聚类
            
            # 分析共同模式
            common_pattern = self._find_common_pattern(group)
            
            # 创建聚类
            cluster = FailureCluster(
                id=f"CLUSTER-{cluster_key}",
                name=f"{group[0].category.value} - {common_pattern[:50]}",
                cluster_key=cluster_key,
                common_pattern=common_pattern,
                failure_ids=[f.id for f in group],
                case_ids=list(set(f.case_id for f in group)),
                count=len(group),
                first_occurrence=min(f.failed_at for f in group),
                last_occurrence=max(f.failed_at for f in group),
                affected_pages=list(set(f.page for f in group)),
                affected_modules=list(set(self._extract_module(f.url) for f in group)),
            )
            
            # 根因分析 (AI)
            if len(group) >= 3:  # 足够多样本才调用 AI
                analysis = await self.ai_service.analyze_cluster(group)
                cluster.root_cause = analysis.get("root_cause")
                cluster.root_cause_confidence = analysis.get("confidence", 0.0)
            
            clusters.append(cluster)
        
        # 4. 按影响排序
        clusters.sort(key=lambda c: c.count, reverse=True)
        
        return clusters
    
    def _find_common_pattern(self, failures: list[FailureRecord]) -> str:
        """找出共同模式"""
        if not failures:
            return ""
        
        # 找出共同的错误关键词
        error_words = []
        for failure in failures:
            words = set(failure.error_message.lower().split())
            error_words.append(words)
        
        # 找交集
        if len(error_words) > 0:
            common = error_words[0]
            for words in error_words[1:]:
                common = common.intersection(words)
            
            # 过滤停用词
            stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'at', 'to', 'for', 'on', 'in'}
            common = common - stopwords
            
            if common:
                return ' '.join(sorted(common)[:10])
        
        # 回退到第一个错误消息
        return failures[0].error_message[:100]
```

### 3.2 Flaky 检测服务

```python
# apps/web-ui-service/app/services/flaky_detection_service.py

class FlakyDetectionService:
    """Flaky 测试检测服务"""
    
    FLAKY_THRESHOLD = 0.1  # 失败率 > 10% 视为 flaky
    MIN_RUNS = 5  # 最少运行次数
    
    def __init__(self, execution_repository: ExecutionRepository):
        self.exec_repo = execution_repository
    
    async def detect_flaky_tests(
        self,
        days: int = 30,
        min_runs: int = None,
    ) -> list[FlakyTestRecord]:
        """检测 flaky 测试"""
        
        min_runs = min_runs or self.MIN_RUNS
        
        # 获取历史执行记录
        executions = await self.exec_repo.get_recent(days)
        
        # 按用例分组
        case_runs: dict[str, list[dict]] = defaultdict(list)
        for exec in executions:
            for case_result in exec.case_results:
                case_runs[case_result["case_id"]].append({
                    "execution_id": exec.id,
                    "status": case_result["status"],
                    "error": case_result.get("error"),
                    "timestamp": exec.started_at,
                })
        
        # 分析 flaky
        flaky_tests = []
        for case_id, runs in case_runs.items():
            if len(runs) < min_runs:
                continue
            
            passed = sum(1 for r in runs if r["status"] == "passed")
            failed = sum(1 for r in runs if r["status"] == "failed")
            
            failure_rate = failed / len(runs)
            if failure_rate > self.FLAKY_THRESHOLD:
                record = FlakyTestRecord(
                    case_id=case_id,
                    case_name=runs[0].get("case_name", "Unknown"),
                    total_runs=len(runs),
                    passed_runs=passed,
                    failed_runs=failed,
                    flaky_rate=failure_rate,
                )
                record.compute_flaky_rate()
                
                # 分析失败模式
                record.failure_patterns = self._analyze_failure_patterns(runs)
                record.common_error_messages = self._extract_common_errors(runs)
                record.suspected_causes = self._infer_causes(record)
                record.recommendations = self._generate_recommendations(record)
                
                flaky_tests.append(record)
        
        # 按 flaky 率排序
        flaky_tests.sort(key=lambda x: x.flaky_rate, reverse=True)
        
        return flaky_tests
    
    def _analyze_failure_patterns(self, runs: list[dict]) -> list[str]:
        """分析失败模式"""
        patterns = []
        error_messages = [r.get("error", "") for r in runs if r["status"] == "failed"]
        
        if any("timeout" in msg.lower() for msg in error_messages):
            patterns.append("timeout_related")
        if any("element not found" in msg.lower() for msg in error_messages):
            patterns.append("element_locating")
        if any("assertion" in msg.lower() for msg in error_messages):
            patterns.append("assertion_failure")
        if any("network" in msg.lower() for msg in error_messages):
            patterns.append("network_issue")
        
        return patterns
    
    def _infer_causes(self, record: FlakyTestRecord) -> list[str]:
        """推断可能原因"""
        causes = []
        
        if "timeout_related" in record.failure_patterns:
            causes.append("页面加载时间不稳定")
        if "element_locating" in record.failure_patterns:
            causes.append("元素定位器不稳定 (可能依赖动态内容)")
        if "assertion_failure" in record.failure_patterns:
            causes.append("断言条件过于严格或依赖时序")
        if "network_issue" in record.failure_patterns:
            causes.append("网络请求不稳定")
        
        if record.flaky_rate > 0.3:
            causes.append("测试本身可能存在竞态条件")
        
        return causes
    
    def _generate_recommendations(self, record: FlakyTestRecord) -> list[str]:
        """生成修复建议"""
        recommendations = []
        
        if "element_locating" in record.failure_patterns:
            recommendations.append("使用更稳定的元素定位器 (如 data-testid)")
            recommendations.append("增加元素等待条件")
        
        if "timeout_related" in record.failure_patterns:
            recommendations.append("增加超时时间或使用智能等待")
        
        if "assertion_failure" in record.failure_patterns:
            recommendations.append("检查断言是否依赖不稳定的状态")
            recommendations.append("考虑使用更宽松的断言条件")
        
        if record.flaky_rate > 0.5:
            recommendations.append("考虑暂时禁用该测试直至修复")
        
        return recommendations
```

### 3.3 风险评分服务

```python
# apps/web-ui-service/app/services/risk_scoring_service.py

class RiskScoringService:

**当前判断**

- `FailureClusteringService`：`部分完成`
- `FlakyDetectionService`：`部分完成`
- `RiskScoringService`：`未完成`

补充说明：

- 当前 failure cluster / flaky / governance risk 相关能力，主要已经落在：
  - [workbench_governance_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_governance_service.py)
  - [dashboard.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/routers/dashboard.py)
- 因此，不建议为了贴合本文命名而强行新建同名 service
- 更值得继续做的是：
  - 增强 cluster 排序和解释性
  - 增强 flaky 与 multisource/change impact 的关联
  - 把风险评分升级成更明确、可拆解的多维模型
    """风险评分服务"""
    
    # 权重配置
    WEIGHTS = {
        "failure_rate": 0.30,
        "severity": 0.25,
        "trend": 0.20,
        "coverage": 0.15,
        "flaky": 0.10,
    }
    
    def __init__(
        self,
        failure_repository: FailureRepository,
        execution_repository: ExecutionRepository,
        test_point_repository: TestPointRepository,
    ):
        self.failure_repo = failure_repository
        self.exec_repo = execution_repository
        self.tp_repo = test_point_repository
    
    async def compute_risk_score(
        self,
        project: str,
        days: int = 7,
    ) -> RiskScore:
        """计算项目风险评分"""
        
        # 1. 获取数据
        failures = await self.failure_repo.get_by_project(project, days)
        executions = await self.exec_repo.get_by_project(project, days)
        test_points = await self.tp_repo.list_by_project(project)
        
        # 2. 计算各维度评分
        failure_rate_score = self._compute_failure_rate_score(failures, executions)
        severity_score = self._compute_severity_score(failures)
        trend_score = self._compute_trend_score(executions, days)
        coverage_score = self._compute_coverage_score(test_points)
        flaky_score = self._compute_flaky_score(executions)
        
        # 3. 加权计算
        overall = (
            failure_rate_score * self.WEIGHTS["failure_rate"] +
            severity_score * self.WEIGHTS["severity"] +
            trend_score * self.WEIGHTS["trend"] +
            coverage_score * self.WEIGHTS["coverage"] +
            flaky_score * self.WEIGHTS["flaky"]
        )
        
        # 4. 识别风险因素
        risk_factors = self._identify_risk_factors(
            failures, executions, test_points
        )
        
        # 5. 生成建议
        recommendations = self._generate_recommendations(
            risk_factors, overall
        )
        
        return RiskScore(
            overall_score=round(overall, 2),
            failure_rate_score=round(failure_rate_score, 2),
            severity_score=round(severity_score, 2),
            trend_score=round(trend_score, 2),
            coverage_score=round(coverage_score, 2),
            flaky_score=round(flaky_score, 2),
            risk_level=RiskScore.compute_level(overall),
            risk_factors=risk_factors,
            recommendations=recommendations,
        )
    
    def _compute_failure_rate_score(self, failures, executions) -> float:
        """计算失败率评分 (0-100, 越高越危险)"""
        if not executions:
            return 0.0
        
        total_cases = sum(len(e.case_results) for e in executions)
        if total_cases == 0:
            return 0.0
        
        failure_rate = len(failures) / total_cases
        # 失败率 0% → 0 分，50%+ → 100 分
        return min(100, failure_rate * 200)
    
    def _compute_severity_score(self, failures) -> float:
        """计算严重程度评分"""
        if not failures:
            return 0.0
        
        severity_weights = {
            "blocker": 1.0,
            "critical": 0.8,
            "major": 0.5,
            "minor": 0.2,
            "trivial": 0.1,
        }
        
        weighted_sum = sum(
            severity_weights.get(f.severity, 0.5) for f in failures
        )
        avg_severity = weighted_sum / len(failures)
        
        # 考虑 blocker 数量
        blocker_count = sum(1 for f in failures if f.severity == "blocker")
        blocker_bonus = min(30, blocker_count * 10)
        
        return min(100, avg_severity * 70 + blocker_bonus)
    
    def _compute_trend_score(self, executions, days) -> float:
        """计算趋势评分 (恶化→高分)"""
        if len(executions) < 2:
            return 50.0  # 中性
        
        # 按时间排序
        sorted_execs = sorted(executions, key=lambda e: e.started_at)
        
        # 比较最近和最早
        recent_failure_rate = self._calc_failure_rate(sorted_execs[-3:])
        early_failure_rate = self._calc_failure_rate(sorted_execs[:3])
        
        diff = recent_failure_rate - early_failure_rate
        
        # 恶化→高分，改善→低分
        return max(0, min(100, 50 + diff * 100))
    
    def _calc_failure_rate(self, executions) -> float:
        """计算执行集的失败率"""
        total = sum(len(e.case_results) for e in executions)
        if total == 0:
            return 0.0
        failed = sum(
            sum(1 for r in e.case_results if r["status"] == "failed")
            for e in executions
        )
        return failed / total
    
    def _compute_coverage_score(self, test_points) -> float:
        """计算覆盖度评分 (覆盖越低→分越高)"""
        if not test_points:
            return 100.0
        
        covered = sum(1 for tp in test_points if tp.covered_by_cases)
        coverage_rate = covered / len(test_points)
        
        # 覆盖率 100% → 0 分，0% → 100 分
        return (1 - coverage_rate) * 100
    
    def _compute_flaky_score(self, executions) -> float:
        """计算稳定性评分"""
        # TODO: 实现 flaky 分析
        return 20.0  # 默认低风险
    
    def _identify_risk_factors(self, failures, executions, test_points) -> list[dict]:
        """识别风险因素"""
        factors = []
        
        # 高失败率
        if executions:
            failure_rate = len(failures) / sum(len(e.case_results) for e in executions)
            if failure_rate > 0.2:
                factors.append({
                    "type": "high_failure_rate",
                    "severity": "high",
                    "description": f"失败率 {failure_rate:.1%} 超过阈值 (20%)",
                })
        
        # Blocker 问题
        blockers = [f for f in failures if f.severity == "blocker"]
        if blockers:
            factors.append({
                "type": "blocker_issues",
                "severity": "critical",
                "description": f"发现 {len(blockers)} 个阻塞性问题",
            })
        
        # 低覆盖
        if test_points:
            coverage = sum(1 for tp in test_points if tp.covered_by_cases) / len(test_points)
            if coverage < 0.5:
                factors.append({
                    "type": "low_coverage",
                    "severity": "medium",
                    "description": f"测试覆盖率 {coverage:.1%} 低于阈值 (50%)",
                })
        
        return factors
    
    def _generate_recommendations(self, risk_factors, overall_score) -> list[str]:
        """生成建议"""
        recommendations = []
        
        for factor in risk_factors:
            if factor["type"] == "high_failure_rate":
                recommendations.append("优先修复高频失败用例")
                recommendations.append("分析失败聚类，识别系统性问题")
            elif factor["type"] == "blocker_issues":
                recommendations.append("立即处理阻塞性问题，可能影响发布")
            elif factor["type"] == "low_coverage":
                recommendations.append("补充测试用例，提高覆盖率")
        
        if overall_score >= 60:
            recommendations.append("建议推迟发布，待风险降低后再评估")
        elif overall_score >= 40:
            recommendations.append("可以发布，但需密切监控线上质量")
        else:
            recommendations.append("质量状况良好，可以发布")
        
        return recommendations
```

---

## 四、API 设计

```yaml
# 失败分析
GET    /api/v1/failures                      # 查询失败列表
GET    /api/v1/failures/{id}                 # 获取失败详情
POST   /api/v1/failures/analyze              # 批量分析失败
GET    /api/v1/failures/clusters             # 获取失败聚类

# Flaky 测试
GET    /api/v1/flaky-tests                   # 获取 flaky 测试列表
GET    /api/v1/flaky-tests/{caseId}          # 获取用例 flaky 详情

# 风险评分
GET    /api/v1/risk-score/{project}          # 获取项目风险评分
GET    /api/v1/release-readiness/{project}   # 获取发布就绪评估

# 统计
GET    /api/v1/statistics/failure-trend      # 失败趋势
GET    /api/v1/statistics/failure-by-category # 按类别统计
GET    /api/v1/statistics/coverage-matrix    # 覆盖矩阵
```

---

## 五、UI 设计

### 5.1 失败聚类视图

```
┌─────────────────────────────────────────────────────────────────┐
│  失败聚类分析                                    [刷新] [导出]   │
├─────────────────────────────────────────────────────────────────┤
│  执行批次：2026-04-02 12:00  |  总失败：45  |  聚类：8          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  🔴 [45%] Element Not Found - 商品列表页                         │
│     影响：12 个用例 | 页面：product-list, product-detail        │
│     根因：页面改版后 data-testid 变更 (置信度：85%)              │
│     建议：更新页面对象中的定位器                                  │
│     [查看详情] [创建 JIRA] [标记为已知]                          │
│                                                                 │
│  🟠 [22%] Timeout Exceeded - 支付流程                            │
│     影响：5 个用例 | 页面：checkout                             │
│     根因：第三方支付接口响应慢 (置信度：72%)                      │
│     建议：增加超时时间或使用 mock                                │
│     [查看详情] [创建 JIRA] [标记为已知]                          │
│                                                                 │
│  🟡 [15%] Assertion Failed - 价格计算                            │
│     影响：3 个用例 | 页面：cart                                 │
│     ...                                                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 发布就绪看板

```
┌─────────────────────────────────────────────────────────────────┐
│  发布就绪评估 - 项目：e-commerce                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  综合风险评分：42/100  [中等风险]                               │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  维度评分                                                 │  │
│  │  失败率  ████████░░  35/100                              │  │
│  │  严重度  ██████░░░░  28/100                              │  │
│  │  趋势    ████░░░░░░  20/100 (改善中)                      │  │
│  │  覆盖    ██████████  45/100                              │  │
│  │  稳定性  ██░░░░░░░░  12/100                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ⚠️  阻塞问题 (2)                                               │
│     • [BLOCKER] 支付流程失败率 35%                              │
│     • [BLOCKER] 订单创建接口超时                                 │
│                                                                 │
│  ⚡  建议                                                       │
│     ✓ 修复支付流程超时问题                                      │
│     ✓ 补充订单模块测试用例                                      │
│     ✓ 监控 flaky 测试：TC-CART-015                              │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  🟡 可以发布，但需密切监控线上质量                          │  │
│  │     置信度：78%                                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  [生成报告] [发送邮件] [创建门禁例外]                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 六、实施计划

> 当前执行状态说明
>
> 这一节现在应理解为“第二版增强计划”，而不是“尚未开始”。

### Phase 1: 数据层 (1 周)
- [ ] 定义 FailureRecord, FailureCluster 模型
- [ ] 创建数据库表
- [ ] 实现 Repository 层

### Phase 2: 聚类服务 (1 周)
- [ ] 实现 FailureClusteringService
- [ ] 实现聚类算法
- [ ] 集成 AI 根因分析

### Phase 3: Flaky 检测 (3 天)
- [ ] 实现 FlakyDetectionService
- [ ] 实现检测算法
- [ ] 生成修复建议

### Phase 4: 风险评分 (1 周)
- [ ] 实现 RiskScoringService
- [ ] 实现各维度评分算法
- [ ] 实现发布就绪评估

### Phase 5: UI 集成 (1 周)
- [ ] 失败聚类视图
- [ ] 风险评分看板
- [ ] 发布就绪报告

当前状态补充：

- `定义 FailureRecord, FailureCluster 模型`：`未完成`
- `实现 FailureClusteringService`：`部分完成`
- `实现 FlakyDetectionService`：`部分完成`
- `实现 RiskScoringService`：`未完成`
- `失败聚类视图`：`已完成第一版`
- `风险评分看板`：`已完成第一版治理视角`
- `发布就绪报告`：`未完成`

---

## 七、验收标准

> 当前状态说明
>
> 本节验收标准中，跨 case 聚类、Flaky 基础识别、治理消费面已经具备第一版；
> 真正还没完成的是更强算法深度、正式多维风险评分模型，以及发布就绪报告闭环。

- [ ] 可以对批量失败进行聚类分析
- [ ] 可以识别 Top 失败模式
- [ ] 可以检测 flaky 测试并给出建议
- [ ] 可以计算项目风险评分
- [ ] 可以生成发布就绪评估报告
- [ ] 有完整的 API 文档
- [ ] 有 UI 展示

---

## 八、当前建议下一步

基于当前代码状态，这份文档里最值得继续推进的项是：

1. 增强 cluster 排序与 explainability
2. 增强 flaky 与 multisource / change impact 的关联
3. 把风险评分升级成更明确、可拆解的多维模型
4. 补“发布就绪评估报告”闭环

当前不建议优先做的项：

- 为了贴合本文类名，先单独新建 `FailureClusteringService / FlakyDetectionService / RiskScoringService`
- 在算法第二版尚未明确前，先做大规模 UI 扩张

更适合作为下一阶段入口的文档：

- [2026-04-02-platform-next-backlog.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/2026-04-02-platform-next-backlog.md)

**文档维护**: 实施过程中持续更新  
**最后更新**: 2026-04-02
