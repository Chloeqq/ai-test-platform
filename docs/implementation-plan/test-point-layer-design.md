# 测试点中间层设计方案

**状态**: 设计稿（已补当前状态说明）  
**版本**: 1.0  
**创建时间**: 2026-04-02

## 文档状态说明（2026-04-02 更新）

这份文档的方向仍然成立，但它描述的是“理想化独立测试点层”，不再等同于项目当前现实状态。

当前状态总结：

- `TestPointPlanV1`：`已完成`
- 测试点确认与治理消费面：`已完成基础版`
- 独立 `TestPointGenerationService / CaseGenerationService`：`部分完成`
- `CoverageMatrix`：`未完成`
- “缺少测试点中间层”这一旧判断：`不再成立`

当前更准确的说法是：

> 测试点中间层已经存在，并且完成了第一版闭环；后续值得继续推进的是 `CoverageMatrix`、更独立的资产中心，以及更细粒度的 traceability/coverage 消费面。

---

## 一、背景与目标

### 当前问题

```
需求文本 ──────────────────→ YAML 用例
         ↑                    ↑
         │                    │
    缺少结构化              缺少可解释性
    缺少覆盖矩阵            缺少优先级
```

**痛点**:
1. 需求到 YAML 跳跃过大，无法追溯"为什么生成这些用例"
2. 无法评估测试覆盖度
3. 无法基于风险/优先级筛选回归范围
4. 无法做测试点级别的复用和沉淀

### 目标架构

```
输入源 (需求/PRD/OpenAPI/Git Diff)
         ↓
    ┌─────────────────┐
    │  测试点生成器   │
    └─────────────────┘
         ↓
    ┌─────────────────┐
    │  测试点资产中心  │ ←── 覆盖矩阵 / 优先级 / 风险评分
    └─────────────────┘
         ↓
    ┌─────────────────┐
    │  用例生成器     │ ←── 消费测试点，生成 YAML
    └─────────────────┘
         ↓
      YAML 用例
```

---

## 二、数据模型设计

### 2.1 核心模型

```python
# apps/shared_backend/schemas/test_point.py

from enum import Enum
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class TestPointType(Enum):
    """测试点类型"""
    FUNCTIONAL = "functional"           # 功能验证
    EDGE_CASE = "edge_case"            # 边界条件
    ERROR_HANDLING = "error_handling"   # 异常处理
    PERFORMANCE = "performance"         # 性能
    SECURITY = "security"               # 安全
    COMPATIBILITY = "compatibility"     # 兼容性
    ACCESSIBILITY = "accessibility"     # 可访问性


class TestPointPriority(Enum):
    """测试点优先级"""
    P0 = "p0"  # 阻塞性，必须测试
    P1 = "p1"  # 核心功能，高优先级
    P2 = "p2"  # 一般功能，中优先级
    P3 = "p3"  # 边缘功能，低优先级


class TestPointRisk(Enum):
    """测试点风险等级"""
    LOW = "low"       # 稳定功能，低变更频率
    MEDIUM = "medium" # 一般功能，中等变更
    HIGH = "high"     # 核心功能，高频变更
    CRITICAL = "critical"  # 资金/安全相关


class TestPointStatus(Enum):
    """测试点状态"""
    DRAFT = "draft"           # 草稿
    REVIEWED = "reviewed"     # 已评审
    ACTIVE = "active"         # 激活 (有关联用例)
    DEPRECATED = "deprecated" # 废弃
    COVERED = "covered"       # 已覆盖


class TestPointSource(Enum):
    """测试点来源"""
    REQUIREMENT = "requirement"
    OPENAPI = "openapi"
    GIT_DIFF = "git_diff"
    DEFECT = "defect"
    MANUAL = "manual"
    AI_GENERATED = "ai_generated"


class TestPoint(BaseModel):
    """测试点"""
    
    # 标识
    id: str = Field(..., description="测试点唯一标识")
    title: str = Field(..., description="测试点标题")
    description: str = Field(..., description="测试点详细描述")
    
    # 分类
    type: TestPointType = Field(..., description="测试点类型")
    priority: TestPointPriority = Field(..., description="优先级")
    risk: TestPointRisk = Field(..., description="风险等级")
    
    # 状态
    status: TestPointStatus = Field(default=TestPointStatus.DRAFT)
    
    # 来源
    source: TestPointSource = Field(..., description="来源")
    source_id: Optional[str] = Field(None, description="来源 ID (如需求 ID)")
    source_text: Optional[str] = Field(None, description="来源原文片段")
    
    # 业务上下文
    page: str = Field(..., description="关联页面")
    module: Optional[str] = Field(None, description="关联模块")
    feature: Optional[str] = Field(None, description="关联功能")
    
    # 前置条件
    prerequisites: list[str] = Field(default_factory=list, description="前置条件列表")
    
    # 测试数据要求
    data_requirements: list[dict[str, Any]] = Field(default_factory=list)
    
    # 期望结果
    expected_results: list[str] = Field(default_factory=list, description="期望结果列表")
    
    # 覆盖信息
    covered_by_cases: list[str] = Field(default_factory=list, description="覆盖的用例 ID 列表")
    coverage_confidence: float = Field(default=0.0, ge=0, le=1, description="覆盖置信度")
    
    # 评审信息
    reviewer_id: Optional[str] = Field(None, description="评审人")
    reviewed_at: Optional[datetime] = Field(None, description="评审时间")
    review_comments: Optional[str] = Field(None, description="评审意见")
    
    # 元数据
    tags: list[str] = Field(default_factory=list, description="标签")
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True


class TestPointPlan(BaseModel):
    """测试点计划"""
    
    id: str
    name: str
    description: str
    
    # 关联的需求/任务
    requirement_id: Optional[str] = None
    requirement_text: Optional[str] = None
    
    # 测试点列表
    test_points: list[TestPoint] = Field(default_factory=list)
    
    # 统计信息
    statistics: dict[str, Any] = Field(default_factory=dict)
    
    # 生成信息
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    generated_by: str = "ai"  # "ai" or user_id
    
    def compute_statistics(self) -> dict[str, Any]:
        """计算统计信息"""
        total = len(self.test_points)
        by_type = {}
        by_priority = {}
        by_risk = {}
        by_status = {}
        covered = 0
        
        for tp in self.test_points:
            # 按类型统计
            tp_type = tp.type
            by_type[tp_type] = by_type.get(tp_type, 0) + 1
            
            # 按优先级统计
            tp_priority = tp.priority
            by_priority[tp_priority] = by_priority.get(tp_priority, 0) + 1
            
            # 按风险统计
            tp_risk = tp.risk
            by_risk[tp_risk] = by_risk.get(tp_risk, 0) + 1
            
            # 按状态统计
            tp_status = tp.status
            by_status[tp_status] = by_status.get(tp_status, 0) + 1
            
            # 覆盖统计
            if tp.covered_by_cases:
                covered += 1
        
        self.statistics = {
            "total": total,
            "by_type": by_type,
            "by_priority": by_priority,
            "by_risk": by_risk,
            "by_status": by_status,
            "coverage_rate": covered / total if total > 0 else 0.0,
        }
        return self.statistics
```

### 2.2 覆盖矩阵模型

**当前判断**: `未完成`

补充说明：

- 当前已有 selection / coverage / traceability 摘要，但还没有本文定义的独立 `CoverageMatrix` 模型与稳定消费面
- 这是这份设计稿里目前最值得继续推进的部分之一

```python
class CoverageMatrix(BaseModel):
    """测试覆盖矩阵"""
    
    # 矩阵维度
    rows: list[str] = Field(..., description="行标签 (如功能模块)")
    columns: list[str] = Field(..., description="列标签 (如测试类型)")
    
    # 矩阵数据: row_index -> col_index -> test_point_ids
    data: dict[int, dict[int, list[str]]] = Field(default_factory=dict)
    
    # 覆盖率统计
    coverage_rate: float = Field(default=0.0)
    
    def get_cell(self, row_idx: int, col_idx: int) -> list[str]:
        """获取单元格中的测试点 ID"""
        return self.data.get(row_idx, {}).get(col_idx, [])
    
    def set_cell(self, row_idx: int, col_idx: int, test_point_ids: list[str]):
        """设置单元格"""
        if row_idx not in self.data:
            self.data[row_idx] = {}
        self.data[row_idx][col_idx] = test_point_ids
        self._update_coverage()
    
    def _update_coverage(self):
        """更新覆盖率"""
        total_cells = len(self.rows) * len(self.columns)
        filled_cells = sum(
            1 for row in self.data.values() 
            for col_ids in row.values() 
            if col_ids
        )
        self.coverage_rate = filled_cells / total_cells if total_cells > 0 else 0.0
```

---

## 三、服务层设计

### 3.1 测试点生成服务

**当前判断**: `部分完成`

补充说明：

- 相关能力已经存在，但并不是按本文里的单独 `TestPointGenerationService` 类名落地
- 当前主要由以下能力承接：
  - [requirement_testpoint_support.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/services/requirement_testpoint_support.py)
  - [workbench_generation_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_generation_service.py)
- 因此，不建议为了贴合本文命名而再新建同名服务

```python
# apps/web-ui-service/app/services/test_point_service.py

from typing import Optional
from agents.test_design_agent.src.agent import TestDesignAgent

class TestPointGenerationService:
    """测试点生成服务"""
    
    def __init__(
        self,
        test_design_agent: TestDesignAgent,
        test_point_repository: TestPointRepository,
    ):
        self.agent = test_design_agent
        self.repo = test_point_repository
    
    async def generate_from_requirement(
        self,
        requirement_text: str,
        page: str,
        source: str = "requirement",
        source_id: Optional[str] = None,
    ) -> TestPointPlan:
        """从需求生成测试点计划"""
        
        # 1. 调用 AI Agent 生成测试点
        raw_test_points = await self.agent.generate_test_points(
            requirement=requirement_text,
            page=page,
            constraints={
                "include_types": ["functional", "edge_case", "error_handling"],
                "min_priority": "p2",
            },
        )
        
        # 2. 转换为标准模型
        test_points = []
        for raw in raw_test_points:
            tp = TestPoint(
                id=self._generate_id(),
                title=raw["title"],
                description=raw["description"],
                type=TestPointType(raw["type"]),
                priority=TestPointPriority(raw["priority"]),
                risk=TestPointRisk(raw.get("risk", "medium")),
                source=TestPointSource(source),
                source_id=source_id,
                source_text=requirement_text[:500],
                page=page,
                expected_results=raw.get("expected_results", []),
                prerequisites=raw.get("prerequisites", []),
            )
            test_points.append(tp)
        
        # 3. 创建计划
        plan = TestPointPlan(
            id=self._generate_plan_id(),
            name=f"测试点计划 - {page} - {datetime.now().strftime('%Y%m%d')}",
            description=f"基于需求生成的测试点计划",
            requirement_text=requirement_text,
            test_points=test_points,
            generated_by="ai",
        )
        plan.compute_statistics()
        
        # 4. 持久化
        await self.repo.save_plan(plan)
        for tp in test_points:
            await self.repo.save_test_point(tp)
        
        return plan
    
    async def generate_from_openapi(
        self,
        openapi_spec: dict,
        endpoints: list[str],
    ) -> TestPointPlan:
        """从 OpenAPI 规范生成测试点"""
        # TODO: 实现 OpenAPI 解析
        pass
    
    async def generate_from_git_diff(
        self,
        diff: str,
        changed_files: list[str],
    ) -> TestPointPlan:
        """从 Git Diff 生成测试点"""
        # TODO: 实现变更影响分析
        pass
    
    def _generate_id(self) -> str:
        """生成测试点 ID"""
        return f"TP-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    
    def _generate_plan_id(self) -> str:
        """生成计划 ID"""
        return f"TPP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
```

### 3.2 测试点资产中心

```python
# apps/web-ui-service/app/services/test_point_repository.py

class TestPointRepository:
    """测试点仓储"""
    
    async def save_test_point(self, test_point: TestPoint):
        """保存测试点"""
        pass
    
    async def get_test_point(self, tp_id: str) -> Optional[TestPoint]:
        """获取测试点"""
        pass
    
    async def list_test_points(
        self,
        page: Optional[str] = None,
        type: Optional[TestPointType] = None,
        priority: Optional[TestPointPriority] = None,
        risk: Optional[TestPointRisk] = None,
        status: Optional[TestPointStatus] = None,
        tags: Optional[list[str]] = None,
    ) -> list[TestPoint]:
        """查询测试点"""
        pass
    
    async def save_plan(self, plan: TestPointPlan):
        """保存测试点计划"""
        pass
    
    async def get_plan(self, plan_id: str) -> Optional[TestPointPlan]:
        """获取测试点计划"""
        pass
    
    async def link_case_to_test_point(self, tp_id: str, case_id: str):
        """关联用例到测试点"""
        tp = await self.get_test_point(tp_id)
        if tp and case_id not in tp.covered_by_cases:
            tp.covered_by_cases.append(case_id)
            tp.coverage_confidence = self._compute_coverage_confidence(tp)
            tp.status = TestPointStatus.COVERED
            await self.save_test_point(tp)
    
    def _compute_coverage_confidence(self, tp: TestPoint) -> float:
        """计算覆盖置信度"""
        # 基于用例数量、用例类型等计算
        case_count = len(tp.covered_by_cases)
        if case_count == 0:
            return 0.0
        elif case_count == 1:
            return 0.7
        elif case_count >= 2:
            return min(0.95, 0.7 + 0.15 * case_count)
```

### 3.3 用例生成服务 (消费测试点)

**当前判断**: `部分完成`

补充说明：

- 从测试点生成用例的能力已经存在于现有 generation/orchestrator 主链中
- 但仍未形成本文所描述的独立 `CaseGenerationService`
- 后续如果继续推进，建议优先补齐 `CoverageMatrix` 与资产中心，再评估是否需要把用例生成链进一步独立命名

```python
# apps/web-ui-service/app/services/case_generation_service.py

class CaseGenerationService:
    """用例生成服务 (基于测试点)"""
    
    def __init__(
        self,
        test_point_repo: TestPointRepository,
        script_generation_agent: ScriptGenerationAgent,
    ):
        self.tp_repo = test_point_repo
        self.agent = script_generation_agent
    
    async def generate_case_from_test_point(
        self,
        test_point_id: str,
        framework: str = "playwright",
        language: str = "python",
    ) -> dict:
        """从单个测试点生成用例"""
        
        tp = await self.tp_repo.get_test_point(test_point_id)
        if not tp:
            raise ValueError(f"Test point {test_point_id} not found")
        
        # 构建生成上下文
        context = {
            "test_point": {
                "title": tp.title,
                "description": tp.description,
                "type": tp.type,
                "priority": tp.priority,
                "page": tp.page,
                "prerequisites": tp.prerequisites,
                "expected_results": tp.expected_results,
            },
            "constraints": {
                "framework": framework,
                "language": language,
                "style": "smoke",  # 复用现有 smoke 风格
            },
        }
        
        # 调用 Agent 生成
        case = await self.agent.generate(context)
        
        # 关联测试点
        case["test_point_id"] = tp.id
        case["test_point_title"] = tp.title
        
        return case
    
    async def generate_cases_from_plan(
        self,
        plan_id: str,
        priority_filter: Optional[list[TestPointPriority]] = None,
    ) -> list[dict]:
        """从测试点计划批量生成用例"""
        
        plan = await self.tp_repo.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")
        
        # 筛选测试点
        test_points = plan.test_points
        if priority_filter:
            test_points = [
                tp for tp in test_points 
                if tp.priority in priority_filter
            ]
        
        # 批量生成
        cases = []
        for tp in test_points:
            case = await self.generate_case_from_test_point(tp.id)
            cases.append(case)
        
        return cases
```

---

## 四、API 设计

### 4.1 RESTful API

```yaml
# 测试点管理
POST   /api/v1/test-points              # 创建测试点
GET    /api/v1/test-points              # 查询测试点列表
GET    /api/v1/test-points/{id}         # 获取测试点详情
PUT    /api/v1/test-points/{id}         # 更新测试点
DELETE /api/v1/test-points/{id}         # 删除测试点

# 测试点计划
POST   /api/v1/test-point-plans              # 创建计划
GET    /api/v1/test-point-plans              # 查询计划列表
GET    /api/v1/test-point-plans/{id}         # 获取计划详情
POST   /api/v1/test-point-plans/{id}/generate-cases  # 从计划生成用例

# 覆盖矩阵
GET    /api/v1/coverage-matrix          # 获取覆盖矩阵
POST   /api/v1/coverage-matrix/compute  # 重新计算矩阵

# 统计
GET    /api/v1/test-points/statistics   # 获取统计信息
```

### 4.2 请求/响应示例

```http
POST /api/v1/test-point-plans
Content-Type: application/json

{
  "requirement_text": "用户可以在商品列表页搜索商品",
  "page": "product-list",
  "source": "requirement",
  "options": {
    "include_types": ["functional", "edge_case"],
    "min_priority": "p2"
  }
}

---

HTTP/1.1 201 Created
Content-Type: application/json

{
  "id": "TPP-20260402120000",
  "name": "测试点计划 - product-list - 20260402",
  "statistics": {
    "total": 8,
    "by_type": {
      "functional": 5,
      "edge_case": 3
    },
    "by_priority": {
      "p0": 2,
      "p1": 4,
      "p2": 2
    },
    "coverage_rate": 0.0
  },
  "test_points": [
    {
      "id": "TP-20260402120000-ABC123",
      "title": "验证搜索框可以输入关键字",
      "type": "functional",
      "priority": "p0",
      "risk": "medium",
      "status": "draft",
      ...
    },
    ...
  ]
}
```

---

## 五、UI 集成

### 5.1 测试点确认面板

```
┌─────────────────────────────────────────────────────────────┐
│  测试点计划: product-list - 20260402                         │
├─────────────────────────────────────────────────────────────┤
│  统计: 总计 8 个 | P0: 2 | P1: 4 | P2: 2 | 覆盖率：0%        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ☐ [P0] 验证搜索框可以输入关键字                             │
│     类型：functional  风险：medium                           │
│     期望：搜索框获得焦点，可以输入文本                        │
│     状态：☐ 已确认  ☐ 需修改  ☐ 不适用                       │
│                                                             │
│  ☐ [P0] 验证搜索结果正确显示                                 │
│     类型：functional  风险：high                             │
│     期望：显示与关键字匹配的商品列表                          │
│     状态：☐ 已确认  ☐ 需修改  ☐ 不适用                       │
│                                                             │
│  ☐ [P1] 验证空搜索结果显示提示                               │
│     类型：edge_case  风险：low                               │
│     ...                                                     │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  [全部确认] [批量生成用例] [导出]                            │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 覆盖矩阵视图

```
┌──────────────────────────────────────────────────────────────┐
│  测试覆盖矩阵                                                 │
├────────────┬──────────┬──────────┬──────────┬───────────────┤
│  功能模块  │ 功能测试  │ 边界测试  │ 异常测试  │ 覆盖率        │
├────────────┼──────────┼──────────┼──────────┼───────────────┤
│  商品搜索  │    ✅5   │    ✅3   │    ✅2   │   100%        │
│  商品筛选  │    ✅4   │    ✅2   │    ⚠️1   │    85%        │
│  商品详情  │    ✅6   │    ⚠️2   │    ✅3   │    90%        │
│  购物车    │    ✅3   │    ❌0   │    ❌0   │    30%        │
├────────────┼──────────┼──────────┼──────────┼───────────────┤
│  总计      │   18     │    7     │    6     │    78%        │
└────────────┴──────────┴──────────┴──────────┴───────────────┘

图例：✅ 已覆盖  ⚠️ 部分覆盖  ❌ 未覆盖
```

---

## 六、实施计划

> 当前执行状态说明
>
> 本节原本是假设“测试点层尚未开始”。现在应按下面口径理解：
>
> - Phase 1：`部分完成`
> - Phase 2：`部分完成`
> - Phase 3：`部分完成`
> - Phase 4：`已完成基础版`
> - Phase 5：`部分完成`

### Phase 1: 基础建设 (1 周)
- [ ] 定义数据模型 (TestPoint, TestPointPlan)
- [ ] 创建数据库表
- [ ] 实现 Repository 层

### Phase 2: 生成服务 (1 周)
- [ ] 实现 TestPointGenerationService
- [ ] 集成 Test Design Agent
- [ ] 实现从需求生成测试点

### Phase 3: 消费服务 (1 周)
- [ ] 实现 CaseGenerationService
- [ ] 修改现有 YAML 生成器消费测试点
- [ ] 实现测试点→用例关联

### Phase 4: UI 集成 (1 周)
- [ ] 测试点确认面板
- [ ] 覆盖矩阵视图
- [ ] 统计图表

### Phase 5: 增强功能 (2 周)
- [ ] OpenAPI 测试点抽取
- [ ] Git Diff 变更影响分析
- [ ] 测试点复用推荐

当前状态补充：

- `定义数据模型 (TestPoint, TestPointPlan)`：`部分完成`
- `实现 TestPointGenerationService`：`部分完成`
- `实现 CaseGenerationService`：`部分完成`
- `测试点确认面板`：`已完成基础版`
- `OpenAPI 测试点抽取`：`已完成基础版`
- `Git Diff 变更影响分析`：`已完成基础版`
- `覆盖矩阵视图`：`未完成`
- `测试点复用推荐`：`未完成`

---

## 七、验收标准

> 当前状态说明
>
> 下列验收项中，基础闭环相关项已基本满足；`CoverageMatrix`、细粒度状态流转、优先级/风险筛选仍是后续重点。

- [ ] 可以从需求文本生成测试点计划
- [ ] 可以从测试点生成 YAML 用例
- [ ] 测试点状态可追踪 (draft → reviewed → covered)
- [ ] 覆盖矩阵可计算和展示
- [ ] 支持按优先级/风险筛选测试点
- [ ] 测试点可关联多个用例
- [ ] 有完整的 API 文档

---

## 八、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| AI 生成测试点质量不稳定 | 高 | 增加人工评审环节，设置置信度阈值 |
| 现有用例迁移成本高 | 中 | 渐进式迁移，新老并存 |
| 数据库性能问题 | 中 | 增加索引，分页查询 |
| 团队学习曲线 | 低 | 文档 + 培训 + 示例 |

---

## 九、当前建议下一步

基于当前代码状态，这份文档里最值得继续推进的项是：

1. 落地 `CoverageMatrix`
2. 强化 `traceability completeness`，区分 `covered / partial / gap / orphan`
3. 让测试点资产中心具备更稳定的独立筛选、统计和治理消费能力
4. 再评估是否有必要把 `TestPointGenerationService / CaseGenerationService` 继续显式独立命名

当前不建议优先做的项：

- 为了贴合本文命名而额外新建同名 service
- 在 `CoverageMatrix` 尚未完成前，先做大规模 UI 复杂化

更适合作为下一阶段入口的文档：

- [2026-04-02-platform-next-backlog.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/2026-04-02-platform-next-backlog.md)
- [2026-04-02-orchestrator-multisource-closure-backlog.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/2026-04-02-orchestrator-multisource-closure-backlog.md)

**文档维护**: 实施过程中持续更新  
**最后更新**: 2026-04-02
