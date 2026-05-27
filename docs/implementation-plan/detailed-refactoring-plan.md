# AI Test Platform 深度模块分析与改进方案

**生成时间**: 2026-04-02  
**分析范围**: 核心模块代码结构、架构债务、具体重构方案

## 文档状态说明（2026-04-02 更新）

这份文档仍然可以作为重构方向参考，但其中部分“当前状态”和“推荐实施路径”已经落后于当前代码。

请按下面的标签理解本文：

- `已完成`：目标已经达成，只是实现方式可能与本文设计不同
- `部分完成`：方向已经落地，但仍有剩余增强项
- `未完成`：当前仍未实现
- `不再建议按原方案继续`：核心目标已达成，不建议为了贴合旧文档而重做

当前真实基线：

- [orchestrator_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py)：`1585` 行
- [legacy_workbench.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/routers/legacy_workbench.py)：`2186` 行
- 全仓测试：`195 passed`

---

## 一、核心模块深度分析

### 1.1 Orchestrator Service (`orchestrator_service.py`)

#### 当前状态
```
文件位置: apps/ai-orchestrator/src/orchestrator_service.py
代码行数: 1,585 行（已更新为当前实际值）
类数量: 3 (OrchestratorError, OrchestrationResult, OrchestratorService)
方法数量: 40+
```

**当前判断**: `已完成`，且 `不再建议按原方案继续`

补充说明：

- 当前主文件已经通过 support/facade 模式完成大幅拆分
- 已落地的 support 包括：
  - `multisource_support.py`
  - `execution_report_support.py`
  - `analytics_query_support.py`
  - `failure_healing_support.py`
  - `requirement_testpoint_support.py`
  - `requirement_parse_support.py`
  - `agent_execution_support.py`
  - `orchestration_flow_support.py`
- 因此，不再建议为了贴合本文结构而重新硬拆成 `config.py / quality_gate_service.py / requirement_service.py / generation_service.py / execution_service.py / evidence_service.py / report_service.py`

#### 职责分析
| 职责域 | 方法示例 | 行数估算 |
|--------|----------|----------|
| 需求解析 | `_parse_requirement_spec`, `_enforce_requirement_quality_gate` | ~400 行 |
| 测试生成 | `_generate_case`, `_generate_script_bundle` | ~300 行 |
| 执行编排 | `_run_case`, `_build_execution_plan` | ~250 行 |
| 证据管理 | `_build_evidence_manifest`, `_snapshot_evidence_files` | ~350 行 |
| 报告生成 | `_build_and_save_report` | ~200 行 |
| 质量门禁 | `_enforce_requirement_quality_gate` | ~180 行 |
| 多源输入 | `_build_fallback_multisource_context` | ~220 行 |
| 工具调用 | Agent 运行时模块加载 | ~300 行 |
| 辅助方法 | 各种 `_build_*`, `_env_*` | ~500 行 |
| 配置与初始化 | `__init__`, 配置项 | ~200 行 |
| 错误处理 | 各类异常处理逻辑 | ~200 行 |
| 遥测记录 | `_record_requirement_parse_telemetry` | ~100 行 |

#### 问题诊断

```
❌ 单一职责原则违反
   - 一个类承担了编排、执行、报告、证据、门禁等 10+ 个职责
   - 方法间耦合度高，难以独立测试

❌ 可测试性差
   - 大量文件系统操作硬编码在类内部
   - 依赖 importlib 动态加载，mock 困难

❌ 配置爆炸
   - 12+ 个环境变量配置项集中在 __init__
   - 缺少配置验证层

❌ 错误处理不统一
   - 混合使用 Exception、OrchestratorError、OrchestratorValidationError
   - 缺少全局错误处理策略
```

#### 重构方案

**目标架构**:
```
apps/ai-orchestrator/src/
├── core/
│   ├── orchestrator.py          # 主编排器 (协调各服务)
│   ├── config.py                # 配置管理
│   └── errors.py                # 统一错误处理
├── services/
│   ├── requirement_service.py   # 需求解析服务
│   ├── generation_service.py    # 测试生成服务
│   ├── execution_service.py     # 执行编排服务
│   ├── evidence_service.py      # 证据管理服务
│   ├── report_service.py        # 报告生成服务
│   └── quality_gate_service.py  # 质量门禁服务
├── adapters/
│   ├── agent_adapter.py         # Agent 调用适配器
│   └── runner_adapter.py        # Runner 调用适配器
├── schemas/
│   └── ...                      # 数据模型 (复用 shared_backend)
└── utils/
    └── ...                      # 工具函数
```

**具体实施步骤**:

```python
# Step 1: 提取配置管理 (apps/ai-orchestrator/src/core/config.py)

from dataclasses import dataclass
from typing import Optional
import os

@dataclass(frozen=True)
class OrchestratorConfig:
    """不可变配置对象"""
    
    # 质量门禁配置
    requirement_quality_gate_enabled: bool = True
    requirement_min_parse_confidence: float = 0.6
    requirement_min_test_intents: int = 1
    requirement_block_high_ambiguity: bool = True
    requirement_max_coverage_gap_ratio: float = 0.5
    
    # 执行配置
    execution_record_compat_builder_enabled: bool = True
    test_point_steps_authoritative: bool = True
    
    # 路径配置
    repo_root: Path
    runner_root: Path
    generated_cases_root: Path
    report_root: Path
    
    @classmethod
    def from_env(cls, repo_root: Optional[Path] = None) -> 'OrchestratorConfig':
        """从环境变量构建配置"""
        return cls(
            repo_root=repo_root or Path(__file__).parents[3],
            requirement_quality_gate_enabled=os.getenv('REQUIREMENT_QUALITY_GATE_ENABLED', 'true').lower() == 'true',
            requirement_min_parse_confidence=float(os.getenv('REQUIREMENT_MIN_PARSE_CONFIDENCE', '0.6')),
            # ... 其他配置
        )
    
    def validate(self) -> list[str]:
        """验证配置有效性"""
        errors = []
        if not (0 <= self.requirement_min_parse_confidence <= 1):
            errors.append("requirement_min_parse_confidence must be between 0 and 1")
        if self.requirement_min_test_intents < 1:
            errors.append("requirement_min_test_intents must be >= 1")
        return errors
```

```python
# Step 2: 提取质量门禁服务 (apps/ai-orchestrator/src/services/quality_gate_service.py)

from dataclasses import dataclass
from typing import Protocol
from enum import Enum

class GateSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass(frozen=True)
class GateViolation:
    """门禁违规记录"""
    code: str
    category: str
    severity: GateSeverity
    message: str
    metric_key: str
    current_value: Any
    threshold: Any

class QualityGateResult:
    def __init__(self):
        self.violations: list[GateViolation] = []
        self.blocked = False
    
    def add_violation(self, violation: GateViolation):
        self.violations.append(violation)
        if violation.severity in {GateSeverity.CRITICAL, GateSeverity.HIGH}:
            self.blocked = True
    
    def to_dict(self) -> dict:
        return {
            "blocked": self.blocked,
            "violation_count": len(self.violations),
            "violations": [asdict(v) for v in self.violations],
        }

class RequirementQualityGateService:
    """需求质量门禁服务"""
    
    BLOCKER_CATALOG = {
        "insufficient_test_intents": {
            "category": "coverage",
            "severity": GateSeverity.HIGH,
            "code": "REQQG_INTENTS_LOW",
        },
        # ... 其他 catalog
    }
    
    def __init__(self, config: OrchestratorConfig):
        self.config = config
    
    def check(self, requirement_spec: dict) -> QualityGateResult:
        result = QualityGateResult()
        
        if not self.config.requirement_quality_gate_enabled:
            return result
        
        # 检查测试意图数量
        intent_count = len(requirement_spec.get("test_intents", []))
        if intent_count < self.config.requirement_min_test_intents:
            result.add_violation(GateViolation(
                code="REQQG_INTENTS_LOW",
                category="coverage",
                severity=GateSeverity.HIGH,
                message=f"测试意图数量 ({intent_count}) 低于最低要求 ({self.config.requirement_min_test_intents})",
                metric_key="intent_count",
                current_value=intent_count,
                threshold=self.config.requirement_min_test_intents,
            ))
        
        # 检查解析置信度
        parse_confidence = requirement_spec.get("parse_confidence", 0)
        if parse_confidence < self.config.requirement_min_parse_confidence:
            result.add_violation(GateViolation(
                code="REQQG_CONFIDENCE_LOW",
                category="quality",
                severity=GateSeverity.HIGH,
                message=f"解析置信度 ({parse_confidence:.2f}) 低于最低要求 ({self.config.requirement_min_parse_confidence})",
                metric_key="parse_confidence",
                current_value=parse_confidence,
                threshold=self.config.requirement_min_parse_confidence,
            ))
        
        return result
```

```python
# Step 3: 重构主编排器 (apps/ai-orchestrator/src/core/orchestrator.py)

from typing import Optional, Protocol
from .config import OrchestratorConfig
from ..services.requirement_service import RequirementService
from ..services.generation_service import GenerationService
from ..services.execution_service import ExecutionService
from ..services.evidence_service import EvidenceService
from ..services.report_service import ReportService
from ..services.quality_gate_service import RequirementQualityGateService

class Orchestrator:
    """主编排器 - 仅负责协调各服务"""
    
    def __init__(
        self,
        config: OrchestratorConfig,
        requirement_service: RequirementService,
        generation_service: GenerationService,
        execution_service: ExecutionService,
        evidence_service: EvidenceService,
        report_service: ReportService,
        quality_gate_service: RequirementQualityGateService,
    ):
        self.config = config
        self.requirement_service = requirement_service
        self.generation_service = generation_service
        self.execution_service = execution_service
        self.evidence_service = evidence_service
        self.report_service = report_service
        self.quality_gate_service = quality_gate_service
    
    def orchestrate(
        self,
        requirement: str,
        page: str = "",
        execute: bool = False,
        source: str = "manual",
        **kwargs,
    ) -> OrchestrationResult:
        # 1. 需求解析
        requirement_spec = self.requirement_service.parse(requirement, page, source, **kwargs)
        
        # 2. 质量门禁检查
        gate_result = self.quality_gate_service.check(requirement_spec)
        if gate_result.blocked:
            raise QualityGateBlockedError(gate_result)
        
        # 3. 测试生成
        case = self.generation_service.generate_case(requirement_spec)
        script = self.generation_service.generate_script(case)
        test_points = self.generation_service.build_test_points(case, requirement_spec)
        
        # 4. 执行 (可选)
        execution_record = None
        evidence_manifest = None
        if execute:
            execution_record = self.execution_service.execute(case)
            evidence_manifest = self.evidence_service.collect(execution_record)
        
        # 5. 报告生成 (如果执行失败)
        report = None
        if execute and execution_record.status == "failed":
            report = self.report_service.generate(execution_record, evidence_manifest)
        
        return OrchestrationResult(
            requirement_spec=requirement_spec,
            case=case,
            generated_script=script,
            test_points=test_points,
            execution_record=execution_record,
            evidence_manifest=evidence_manifest,
            report=report,
            gate_result=gate_result,
        )
```

**预期收益**:
- 单文件行数: 3367 → ~400 (orchestrator.py)
- 可测试性: 每个服务可独立 mock 测试
- 可维护性: 职责清晰，新人上手成本降低 60%
- 可扩展性: 新增功能只需添加新服务，不影响现有代码

---

### 1.2 Legacy Workbench (`legacy_workbench.py`)

#### 当前状态
```
文件位置: apps/web-ui-service/app/routers/legacy_workbench.py
代码行数: 2,186 行
路由数量: 15+
```

**当前判断**: `部分完成`

补充说明：

- 路由拆分、service 分层、compat facade 收口这部分已经基本完成
- 当前 [legacy_workbench.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/routers/legacy_workbench.py) 主要承担 compat facade + infra bridge
- 继续机械式“拆空 legacy”已不再是高收益任务
- `ReviewStateMachine` 仍未实现

#### 问题分析

```
❌ 路由与业务逻辑混合
   - FastAPI router 直接调用服务层 + 数据访问层
   - 难以进行路由层单元测试

❌ 状态管理分散
   - review_state、execution_gate 直接操作数据库
   - 缺少统一的状态机定义

❌ 响应格式不统一
   - 部分返回 dict，部分返回 Pydantic 模型
   - 错误处理不一致
```

#### 重构方案

**目标架构**:
```
apps/web-ui-service/app/
├── routers/
│   ├── workbench.py             # 路由层 (仅处理 HTTP 协议)
│   ├── workbench_assets.py      # 资产管理
│   ├── workbench_gate.py        # 门禁管理
│   └── ...
├── services/
│   ├── workbench_service.py     # 工作台业务服务
│   ├── review_service.py        # 评审服务
│   ├── gate_service.py          # 门禁服务
│   └── ...
├── state/
│   ├── review_state.py          # 评审状态机
│   └── execution_gate.py        # 门禁状态机
└── schemas/
    └── workbench_schemas.py     # 请求/响应模型
```

**状态机设计示例**:

> 当前状态说明
>
> `ReviewStateMachine` 目前仍未实现。
> 这项可以保留为后续增强选项，但不再建议作为当前阶段的主任务，因为 review/gate 的 service 分层和 compat 收口已经基本完成。

```python
# apps/web-ui-service/app/state/review_state.py

from enum import Enum
from datetime import datetime
from pydantic import BaseModel

class ReviewStatus(Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"

class ReviewItemType(Enum):
    ELEMENT = "element"
    TEST_POINT = "test_point"
    RISK = "risk"

class ReviewState(BaseModel):
    """评审状态"""
    id: str
    session_id: str
    item_type: ReviewItemType
    item_id: str
    status: ReviewStatus
    reviewer_id: Optional[str] = None
    review_started_at: Optional[datetime] = None
    review_completed_at: Optional[datetime] = None
    decision: Optional[str] = None
    comments: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    def can_transition_to(self, new_status: ReviewStatus) -> bool:
        """状态转换验证"""
        transitions = {
            ReviewStatus.PENDING: {ReviewStatus.IN_REVIEW, ReviewStatus.EXPIRED},
            ReviewStatus.IN_REVIEW: {ReviewStatus.APPROVED, ReviewStatus.REJECTED},
            ReviewStatus.APPROVED: set(),  # 终态
            ReviewStatus.REJECTED: {ReviewStatus.PENDING},  # 可重新评审
            ReviewStatus.EXPIRED: {ReviewStatus.PENDING},
        }
        return new_status in transitions.get(self.status, set())
    
    def transition(self, new_status: ReviewStatus, reviewer_id: Optional[str] = None) -> 'ReviewState':
        """状态转换"""
        if not self.can_transition_to(new_status):
            raise InvalidStateTransitionError(
                f"Cannot transition from {self.status} to {new_status}"
            )
        
        now = datetime.utcnow()
        return ReviewState(
            **self.dict(),
            status=new_status,
            reviewer_id=reviewer_id,
            review_started_at=self.review_started_at or (now if new_status == ReviewStatus.IN_REVIEW else None),
            review_completed_at=now if new_status in {ReviewStatus.APPROVED, ReviewStatus.REJECTED} else None,
            updated_at=now,
        )

class ReviewStateMachine:
    """评审状态机管理"""
    
    def __init__(self, state_store: StateStore):
        self.state_store = state_store
    
    def get_state(self, session_id: str, item_type: ReviewItemType, item_id: str) -> ReviewState:
        state = self.state_store.get(session_id, item_type, item_id)
        if state is None:
            return self._create_initial_state(session_id, item_type, item_id)
        return state
    
    def approve(self, session_id: str, item_type: ReviewItemType, item_id: str, reviewer_id: str) -> ReviewState:
        state = self.get_state(session_id, item_type, item_id)
        new_state = state.transition(ReviewStatus.APPROVED, reviewer_id)
        self.state_store.save(new_state)
        return new_state
    
    def reject(self, session_id: str, item_type: ReviewItemType, item_id: str, reviewer_id: str, comments: str) -> ReviewState:
        state = self.get_state(session_id, item_type, item_id)
        new_state = state.transition(ReviewStatus.REJECTED, reviewer_id)
        new_state.comments = comments
        self.state_store.save(new_state)
        return new_state
```

---

### 1.3 Shared Contracts (`contracts.py`)

#### 当前状态
```
文件位置: apps/shared_backend/schemas/contracts.py
代码行数: 55,983 字节 (~1,500 行)
契约版本: 7 个 (PageSurfaceV1, TestPointPlanV1, etc.)
```

#### 优点
```
✅ 统一的契约层设计
✅ 版本化管理
✅ 兼容旧数据结构
✅ 详细的字段验证
```

#### 改进建议

```python
# 增加契约验证器

from typing import Protocol, TypeVar
from pydantic import BaseModel, ValidationError

T = TypeVar('T', bound=BaseModel)

class ContractValidator(Protocol[T]):
    def validate(self, data: dict) -> T: ...
    def validate_many(self, data_list: list[dict]) -> list[T]: ...

# 使用 Pydantic v2 进行强类型验证
from pydantic import ConfigDict

class PageSurfaceV1(BaseModel):
    model_config = ConfigDict(
        extra='forbid',  # 禁止多余字段
        frozen=True,     # 不可变
    )
    
    version: Literal["PageSurfaceV1"]
    page: str
    element_candidates: list[ElementCandidateV1]
    frame_surface: FrameSurfaceV1
    confidence_summary: ConfidenceSummaryV1
    
    @field_validator('element_candidates')
    @classmethod
    def validate_candidates(cls, v):
        if len(v) == 0:
            raise ValueError("element_candidates cannot be empty")
        return v
```

---

### 1.4 Self-Healing Agent

#### 当前状态
```
文件位置: agents/self-healing-advisor-agent/
核心文件:
  - suggest.py (9,575 字节)
  - patch_generator.py (11,577 字节)
  - self_healing_orchestrator.py (8,206 字节)
  - apply_patch.py (2,648 字节)
  - rollback.py (2,951 字节)
```

#### 架构评估

```
✅ 职责分离清晰 (建议/生成/应用/回滚)
✅ 有完整的 patch 预览机制
✅ 支持 rollback
✅ 有 confidence 阈值保护

⚠️ 缺少修复策略中心
⚠️ 缺少修复历史记录
⚠️ 缺少修复效果追踪
```

#### 增强方案

```python
# 新增修复策略中心

class HealingStrategy(Enum):
    LOCATOR_UPDATE = "locator_update"
    TIMEOUT_ADJUSTMENT = "timeout_adjustment"
    STEP_REORDER = "step_reorder"
    ASSERTION_RELAX = "assertion_relax"
    ELEMENT_WAIT = "element_wait"

class HealingPolicy(BaseModel):
    """自愈策略配置"""
    strategy: HealingStrategy
    auto_apply: bool = False  # 是否自动应用
    confidence_threshold: float = 0.85
    max_attempts: int = 3
    allowed_targets: list[str]  # 允许修复的 target 列表
    requires_approval: bool = True

class HealingHistory(BaseModel):
    """修复历史记录"""
    id: str
    case_id: str
    step_id: str
    strategy: HealingStrategy
    original_value: str
    new_value: str
    confidence: float
    applied_at: datetime
    applied_by: str  # "auto" or user_id
    rerun_result: Optional[str]  # "passed", "failed", "not_run"
    rolled_back: bool = False

class HealingStrategyCenter:
    """修复策略中心"""
    
    def __init__(self, policy_store: PolicyStore, history_store: HistoryStore):
        self.policy_store = policy_store
        self.history_store = history_store
    
    def get_policy(self, case_id: str, target: str) -> HealingPolicy:
        # 支持按 case/target 定制策略
        return self.policy_store.get(case_id, target)
    
    def record_healing(self, history: HealingHistory):
        self.history_store.save(history)
    
    def get_success_rate(self, strategy: HealingStrategy, days: int = 30) -> float:
        """获取策略成功率"""
        histories = self.history_store.get_by_strategy(strategy, days)
        if not histories:
            return 0.0
        successful = sum(1 for h in histories if h.rerun_result == "passed" and not h.rolled_back)
        return successful / len(histories)
```

---

## 二、优先级改进清单

> 以下清单已按当前状态重新标注，避免把“历史建议”误当成“尚未开始的任务”。

### P0 - 立即执行 (1-2 周)

| # | 任务 | 预计工时 | 风险 | 收益 |
|---|------|----------|------|------|
| 1 | 拆分 `orchestrator_service.py` 为服务层 | 5 天 | 中 | 可维护性 +60% |
| 2 | 实现 `ReviewStateMachine` | 3 天 | 低 | 状态管理规范化 |
| 3 | 统一响应格式 (Pydantic models) | 2 天 | 低 | API 一致性 |
| 4 | 增加配置验证层 | 1 天 | 低 | 配置错误早发现 |

当前状态：

- `#1` `已完成`
- `#2` `未完成`，但当前不是最高优先级
- `#3` `部分完成`，契约层已存在，但并未统一到全部 web-ui 响应
- `#4` `部分完成`，已存在边界护栏与部分配置整理，但未形成本文定义的独立配置验证层

### P1 - 短期 (2-4 周)

| # | 任务 | 预计工时 | 风险 | 收益 |
|---|------|----------|------|------|
| 5 | 实现测试点中间层完整闭环 | 5 天 | 中 | 生成质量 +40% |
| 6 | 增加修复策略中心 | 4 天 | 中 | 自愈成功率 +25% |
| 7 | 实现失败聚类分析 | 5 天 | 中 | 批量分析能力 |
| 8 | 增加契约验证器 (Pydantic v2) | 3 天 | 低 | 类型安全 |

当前状态：

- `#5` `部分完成`，`TestPointPlanV1` 与治理消费面已落地，但 CoverageMatrix 等仍未完成
- `#6` `部分完成`，已有 self-healing / gate / boundary，但未形成本文定义的独立“修复策略中心”
- `#7` `部分完成`，失败聚类、Flaky、治理风险第一版已落地，但算法深度仍可继续增强
- `#8` `未完成`

### P2 - 中期 (1-2 月)

| # | 任务 | 预计工时 | 风险 | 收益 |
|---|------|----------|------|------|
| 9 | 实现统一调度中心 | 10 天 | 高 | 并发执行能力 |
| 10 | API/Mobile Runner 对齐 | 7 天 | 中 | 多类型测试支持 |
| 11 | 报告治理视图 | 5 天 | 低 | 管理决策支持 |

---

## 三、具体实施指南

### 3.1 重构 orchestrator_service.py

**Week 1: 准备阶段**
```bash
# 1. 创建新目录结构
mkdir -p apps/ai-orchestrator/src/{core,services,adapters}

# 2. 添加 __init__.py
touch apps/ai-orchestrator/src/core/__init__.py
touch apps/ai-orchestrator/src/services/__init__.py
touch apps/ai-orchestrator/src/adapters/__init__.py

# 3. 运行现有测试建立基线
make test-orchestrator
```

**Week 2: 提取服务层**
```python
# 每天完成一个服务提取
# Day 1: config.py + errors.py
# Day 2: requirement_service.py
# Day 3: generation_service.py
# Day 4: execution_service.py
# Day 5: 集成测试 + 回归测试
```

**Week 3: 验证与清理**
```bash
# 1. 运行所有测试
make test

# 2. 性能对比 (确保无回归)
# 3. 删除旧代码
# 4. 更新文档
```

### 3.2 测试策略

```python
# tests/services/test_quality_gate_service.py

import pytest
from src.core.config import OrchestratorConfig
from src.services.quality_gate_service import RequirementQualityGateService

@pytest.fixture
def config():
    return OrchestratorConfig(
        repo_root=Path("/tmp/test"),
        requirement_quality_gate_enabled=True,
        requirement_min_parse_confidence=0.6,
        requirement_min_test_intents=1,
    )

@pytest.fixture
def service(config):
    return RequirementQualityGateService(config)

def test_check_passes_valid_requirement(service):
    requirement_spec = {
        "test_intents": ["intent1", "intent2"],
        "parse_confidence": 0.85,
        "high_ambiguity_count": 0,
    }
    result = service.check(requirement_spec)
    assert not result.blocked
    assert len(result.violations) == 0

def test_check_blocks_low_confidence(service):
    requirement_spec = {
        "test_intents": ["intent1"],
        "parse_confidence": 0.3,  # 低于阈值
        "high_ambiguity_count": 0,
    }
    result = service.check(requirement_spec)
    assert result.blocked
    assert any(v.code == "REQQG_CONFIDENCE_LOW" for v in result.violations)
```

---

## 四、风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 重构引入回归 bug | 高 | 中 | 完整测试覆盖 + 渐进式重构 |
| 团队学习曲线 | 中 | 高 | 代码审查 + 文档 + pair programming |
| 进度延期 | 中 | 中 | 分阶段交付 + 每日站会同步 |
| 配置迁移问题 | 低 | 高 | 向后兼容 + 迁移脚本 |

---

## 五、成功指标

### 代码质量指标
- [ ] 单文件最大行数: 3367 → <500
- [ ] 单元测试覆盖率: 当前 → +30%
- [ ] 圈复杂度: 平均 <10

### 开发效率指标
- [ ] 新功能开发时间: -40%
- [ ] Bug 修复时间: -30%
- [ ] 代码审查时间: -25%

### 运行质量指标
- [ ] 自愈成功率: 当前 → +25%
- [ ] 失败分析准确率: 当前 → +20%
- [ ] 平台可用性: 99.5% → 99.9%

---

## 六、附录

### A. 推荐工具
- **代码分析**: `pylint`, `mypy`, `radon`
- **测试**: `pytest`, `pytest-cov`, `pytest-mock`
- **重构**: `rope`, `pyright`
- **文档**: `mkdocs`, `pdoc`

### B. 参考架构
- Clean Architecture (Robert C. Martin)
- Domain-Driven Design
- Hexagonal Architecture

### C. 相关文档
- [current-architecture-and-flows.md](../architecture/current-architecture-and-flows.md)
- [platform-gap-analysis.md](./platform-gap-analysis.md)
- [next-phase-roadmap.md](./next-phase-roadmap.md)

---

## 七、当前建议下一步

基于当前代码状态，这份文档里后续最值得继续推进的项不是“继续按原图重拆”，而是：

1. 补齐 `CoverageMatrix / traceability completeness` 这类真正仍缺失的测试点能力
2. 继续增强 failure cluster / flaky / risk scoring 的第二版算法深度
3. 推进 strict manifest-first，逐步减少 compat builder 依赖
4. 建立统一调度中心（队列 / 并发 / 资源池）

不再建议继续推进的旧项：

- 为了贴合旧设计，把 `orchestrator` 再重拆成文档中的固定 7 个 service 文件名
- 继续机械式拆空 `legacy_workbench.py`
- 为了对齐文档结构而优先实现 `ReviewStateMachine`

更适合作为下一阶段总入口的文档：

- [2026-04-02-platform-next-backlog.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/2026-04-02-platform-next-backlog.md)

**文档维护**: 每次重构完成后更新此文档  
**最后更新**: 2026-04-02
