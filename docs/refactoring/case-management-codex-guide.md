# 测试用例管理层重构 - Codex 工作指导文档

> 文档版本：v1.0  
> 目标：指导 AI 编程助手完成测试用例管理层的体系化重构  
> 项目位置：`/Users/bettyhuang/PycharmProjects/ai-test-platform`

---

## 📋 一、任务概述

### 1.1 当前问题

测试用例管理层存在以下混乱：

| 问题 | 现状 | 影响 |
|------|------|------|
| 数据模型分散 | Web UI Service 一套、Shared Backend 一套、YAML 文件一套 | 同一用例多处存储，易不一致 |
| ID 规范不统一 | `tc-product-001` vs `atp-web-prod-core-fn-ai-0001` | 跨系统引用困难 |
| 生命周期管理弱 | 只有 status 字段，缺少状态机 | 无法追踪用例演进过程 |
| 分类体系混乱 | tags/markers/module 混用 | 筛选和统计不准确 |
| 版本控制浅层 | 只存 script_code 快照 | 无法追溯变更原因和影响 |
| 与执行层脱节 | execution 记录简单 | 无法关联 trace/证据 |

### 1.2 目标

构建**统一的测试用例管理中心**，实现：

1. ✅ 统一数据模型 (Single Source of Truth)
2. ✅ 标准用例 ID 规范
3. ✅ 完整的版本控制
4. ✅ 清晰的生命周期状态机
5. ✅ 多维度分类体系
6. ✅ 与执行层/缺陷系统深度集成

---

## 🚫 二、禁止事项 (重要约束)

**在开始编码前，必须遵守以下约束：**

1. **不要修改现有数据库表结构**，除非明确标注为"需要迁移"
2. **不要删除现有 API 接口**，新接口使用 `/api/v1/` 前缀
3. **不要改动 `runners/web-playwright-python/` 目录**，这是执行层，本次只重构管理层
4. **不要使用 `DROP TABLE` 或 `ALTER TABLE`**，所有数据库变更用 Alembic 迁移
5. **不要硬编码配置**，所有配置项放入 `.env.example`
6. **不要跳过测试**，每个新 Service 必须有对应的 `tests/` 单元测试
7. **不要直接复制现有代码**，理解后按新规范重写
8. **不要一次性提交所有更改**，按 Phase 分批次提交 PR

---

## 📐 三、编码规范

### 3.1 项目结构约定

```
apps/shared_backend/
├── models/
│   ├── test_case.py          # 新增：统一用例模型
│   ├── case_version.py       # 新增：版本快照模型
│   └── case_taxonomy.py      # 新增：分类体系模型
├── schemas/
│   ├── test_case.py          # 新增：Pydantic Schema
│   └── case_filter.py        # 新增：查询过滤 Schema
├── services/
│   ├── case_management_service.py  # 新增：用例管理服务
│   └── case_version_service.py     # 新增：版本控制服务
└── utils/
    ├── case_ids.py           # 已有：ID 生成工具 (需完善)
    └── case_rules.py         # 已有：规则校验 (需完善)

apps/web-ui-service/
├── app/
│   ├── routers/
│   │   ├── case_management.py      # 新增：统一 API 入口
│   │   └── test_cases.py           # 已有：保留兼容
│   ├── services/
│   │   └── test_case_service.py    # 已有：逐步迁移
│   └── models/
│       └── test_case.py            # 已有：保留兼容
```

### 3.2 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 用例 ID | `{project}-{client}-{page}-{module}-{type}-{source}-{sequence}` | `atp-web-prod-core-fn-ai-0001` |
| 版本 ID | `{case_id}:v{version_no}` | `atp-web-prod-core-fn-ai-0001:v3` |
| Python 类 | PascalCase | `TestCaseManagementService` |
| Python 函数 | snake_case | `create_test_case` |
| API 路径 | kebab-case | `/api/v1/case-management` |
| 数据库表 | snake_case 复数 | `test_cases`, `case_versions` |

### 3.3 类型注解

**必须使用类型注解**，示例：

```python
# ✅ 正确
from typing import Optional, List
from pydantic import BaseModel, Field

class TestCaseCreatePayload(BaseModel):
    title: str = Field(..., max_length=100)
    page_code: str = Field(..., min_length=3, max_length=8)
    tags: Optional[List[str]] = Field(default_factory=list)

# ❌ 错误 - 缺少类型注解
def create_case(payload):
    ...
```

### 3.4 错误处理

**统一使用 FastAPI HTTPException**：

```python
from fastapi import HTTPException, status

def get_case_or_404(db: Session, case_id: str) -> TestCase:
    case = db.execute(select(TestCase).where(TestCase.case_id == case_id)).scalar_one_or_none()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CASE_NOT_FOUND", "message": f"用例 {case_id} 不存在"}
        )
    return case
```

### 3.5 日志规范

**使用 structlog 结构化日志**：

```python
import structlog

logger = structlog.get_logger(__name__)

def create_test_case(self, payload: TestCaseCreatePayload) -> TestCase:
    logger.info(
        "case_created",
        case_id=payload.case_id,
        title=payload.title,
        created_by=payload.created_by,
    )
    ...
```

---

## 🗄️ 四、数据模型定义

### 4.1 核心用例模型 (新增)

**文件**: `apps/shared_backend/models/test_case.py`

```python
from enum import Enum
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, Integer, JSON, DateTime, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class CaseStatus(str, Enum):
    """用例状态机 - 严格遵循"""
    DRAFT = "draft"              # 草稿
    IN_REVIEW = "in_review"      # 评审中
    APPROVED = "approved"        # 已批准
    AUTOMATED = "automated"      # 已自动化
    ACTIVE = "active"            # 运行中
    DEPRECATED = "deprecated"    # 已废弃
    ARCHIVED = "archived"        # 已归档


class CaseType(str, Enum):
    """用例类型"""
    SMOKE = "sm"
    FUNCTIONAL = "fn"
    REGRESSION = "rg"
    EXCEPTION = "ex"
    INTEGRATION = "int"
    E2E = "e2e"


class CaseSource(str, Enum):
    """用例来源"""
    AI_GENERATED = "ai"
    MANUAL = "mn"
    CODE_COVERAGE = "cv"
    IMPORTED = "imp"
    FEEDBACK = "fb"


class ClientType(str, Enum):
    """客户端类型"""
    WEB = "web"
    APP = "app"
    API = "api"
    ADMIN = "admin"
    H5 = "h5"


class TestCase(Base):
    """测试用例核心表"""
    __tablename__ = "test_cases_v2"  # 新表，避免与旧表冲突
    
    # ========== 主键 ==========
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    
    # ========== 核心标识 (不变或少变) ==========
    project: Mapped[str] = mapped_column(String(20), default="atp", nullable=False)
    client: Mapped[str] = mapped_column(String(10), default="web", nullable=False)
    page_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    module_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    case_type: Mapped[str] = mapped_column(String(10), default="fn", nullable=False)
    source: Mapped[str] = mapped_column(String(10), default="ai", nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # ========== 语义信息 ==========
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    preconditions: Mapped[List[str]] = mapped_column(JSON, default=list)
    expected_result: Mapped[str] = mapped_column(Text, nullable=False)
    
    # ========== 分类标签 ==========
    tags: Mapped[List[str]] = mapped_column(JSON, default=list)
    business_flows: Mapped[List[str]] = mapped_column(JSON, default=list)
    priority: Mapped[str] = mapped_column(String(10), default="P2")
    
    # ========== 脚本信息 ==========
    runner_type: Mapped[str] = mapped_column(String(20), default="playwright")
    script_path: Mapped[str] = mapped_column(String(500), default="")
    script_code: Mapped[str] = mapped_column(Text, default="")
    data_config: Mapped[dict] = mapped_column(JSON, default=dict)
    markers: Mapped[List[str]] = mapped_column(JSON, default=list)
    
    # ========== 状态信息 ==========
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    ai_status: Mapped[str] = mapped_column(String(40), default="generated")
    run_status: Mapped[str] = mapped_column(String(40), default="unknown")
    last_execution_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_execution_id: Mapped[Optional[str]] = mapped_column(String(64))
    flaky_score: Mapped[float] = mapped_column(default=0.0)
    failure_count: Mapped[int] = mapped_column(default=0)
    success_count: Mapped[int] = mapped_column(default=0)
    
    # ========== 审计字段 ==========
    created_by: Mapped[str] = mapped_column(String(60), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(60))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_changed_by: Mapped[str] = mapped_column(String(60), default="system")
    last_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    # ========== 关联关系 ==========
    versions: Mapped[List["TestCaseVersion"]] = relationship(
        "TestCaseVersion",
        back_populates="case",
        cascade="all, delete-orphan",
    )
    executions: Mapped[List["TestCaseExecution"]] = relationship(
        "TestCaseExecution",
        back_populates="case",
        cascade="all, delete-orphan",
    )
    defects: Mapped[List["TestCaseDefect"]] = relationship(
        "TestCaseDefect",
        back_populates="case",
        cascade="all, delete-orphan",
    )
    
    # ========== 索引 ==========
    __table_args__ = (
        Index("idx_case_status", "status"),
        Index("idx_case_priority", "priority"),
        Index("idx_case_client", "client"),
        Index("idx_case_created_at", "created_at"),
    )
```

### 4.2 版本快照模型 (新增)

**文件**: `apps/shared_backend/models/case_version.py`

```python
from datetime import datetime
from typing import List
from sqlalchemy import String, Text, Integer, JSON, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class TestCaseVersion(Base):
    """测试用例版本快照"""
    __tablename__ = "case_versions"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    version_id: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("test_cases_v2.case_id", ondelete="CASCADE"), index=True, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    
    # 快照内容 (完整用例副本)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # 变更元数据
    changed_by: Mapped[str] = mapped_column(String(60), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    change_type: Mapped[str] = mapped_column(String(40), nullable=False)  # created/updated/reviewed/rollback
    change_summary: Mapped[str] = mapped_column(Text, default="")
    diff_summary: Mapped[dict] = mapped_column(JSON, default=dict)  # {added: 5, removed: 2, modified: 3}
    
    # 关联执行
    execution_ids: Mapped[List[str]] = mapped_column(JSON, default=list)
    
    # 关联关系
    case: Mapped["TestCase"] = relationship("TestCase", back_populates="versions")
```

### 4.3 执行记录模型 (新增)

**文件**: `apps/shared_backend/models/case_execution.py`

```python
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class TestCaseExecution(Base):
    """测试用例执行记录"""
    __tablename__ = "case_executions"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("test_cases_v2.case_id", ondelete="CASCADE"), index=True, nullable=False)
    run_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # 执行批次 ID
    
    status: Mapped[str] = mapped_column(String(40), nullable=False)  # passed/failed/skipped
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    
    # 执行上下文
    runner_type: Mapped[str] = mapped_column(String(40))
    environment: Mapped[str] = mapped_column(String(40), default="staging")
    browser: Mapped[str] = mapped_column(String(40))
    
    # 证据索引
    evidence_manifest_path: Mapped[str] = mapped_column(Text, default="")
    report_url: Mapped[str] = mapped_column(Text, default="")
    
    # 时间戳
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # 关联关系
    case: Mapped["TestCase"] = relationship("TestCase", back_populates="executions")
```

---

## 🔧 五、服务层实现规范

### 5.1 用例管理服务 (核心)

**文件**: `apps/shared_backend/services/case_management_service.py`

**必须实现的方法**:

```python
class TestCaseManagementService:
    """测试用例管理服务 - 统一入口"""
    
    def __init__(self, db: Session):
        self.db = db
        self.logger = structlog.get_logger(__name__)
    
    # ========== 用例 CRUD ==========
    
    def create_case(self, payload: TestCaseCreatePayload) -> TestCase:
        """
        创建用例
        
        步骤:
        1. 生成标准 case_id
        2. 验证字段合规性 (调用 validate_case_payload)
        3. 创建核心记录
        4. 创建初始版本快照 (version_no=1)
        5. 写入数据库
        """
        pass
    
    def update_case(self, case_id: str, payload: TestCaseUpdatePayload) -> TestCase:
        """
        更新用例
        
        步骤:
        1. 获取用例 (不存在则 404)
        2. 检测变更内容
        3. 更新用例字段
        4. 创建新版本快照 (version_no+1)
        5. 写入数据库
        """
        pass
    
    def get_case(self, case_id: str) -> TestCase:
        """获取单个用例"""
        pass
    
    def delete_case(self, case_id: str, soft_delete: bool = True) -> None:
        """
        删除用例
        
        参数:
        - soft_delete: True=标记为 archived, False=物理删除
        """
        pass
    
    # ========== 用例查询 ==========
    
    def list_cases(self, filters: CaseFilterPayload) -> PaginatedResult[TestCase]:
        """
        查询用例列表
        
        支持过滤:
        - 关键字搜索 (title/case_id)
        - page_code / module_code
        - case_type / source / status
        - tags (包含匹配)
        - 时间范围
        """
        pass
    
    def search_cases(self, query: str, filters: CaseFilterPayload) -> List[TestCase]:
        """全文搜索用例"""
        pass
    
    # ========== 用例评审 ==========
    
    def submit_for_review(self, case_id: str, submitter: str) -> None:
        """提交评审 (status -> in_review)"""
        pass
    
    def review_case(
        self,
        case_id: str,
        reviewer: str,
        approved: bool,
        comment: str = "",
    ) -> None:
        """
        评审用例
        
        - approved=True: status -> approved, 记录 reviewer/reviewed_at
        - approved=False: status -> draft, 记录评审意见
        """
        pass
    
    # ========== 用例版本 ==========
    
    def get_case_versions(self, case_id: str) -> List[TestCaseVersion]:
        """获取用例所有版本"""
        pass
    
    def get_version_diff(
        self,
        case_id: str,
        from_version: int,
        to_version: int,
    ) -> CaseVersionDiff:
        """对比两个版本的差异"""
        pass
    
    def rollback_to_version(self, case_id: str, target_version: int, operator: str) -> TestCase:
        """回滚到指定版本"""
        pass
    
    # ========== 用例执行关联 ==========
    
    def record_execution(
        self,
        case_id: str,
        execution_payload: ExecutionRecordPayload,
    ) -> TestCaseExecution:
        """记录执行结果"""
        pass
    
    def get_case_executions(self, case_id: str, limit: int = 10) -> List[TestCaseExecution]:
        """获取用例执行历史"""
        pass
    
    # ========== 用例统计 ==========
    
    def get_case_statistics(self, filters: CaseFilterPayload) -> CaseStatistics:
        """
        获取用例统计
        
        返回:
        - total: 总数
        - by_status: 按状态分组
        - by_type: 按类型分组
        - by_source: 按来源分组
        - automation_rate: 自动化率
        - pass_rate: 通过率
        """
        pass
```

### 5.2 用例 ID 生成服务

**文件**: `apps/shared_backend/utils/case_ids.py` (已有，需完善)

**必须实现的函数**:

```python
def build_case_id(
    *,
    project: str = "atp",
    client: str = "web",
    page_code: str,
    module_code: str,
    case_type: str = "fn",
    source: str = "ai",
    sequence: int,
) -> str:
    """
    构建标准用例 ID
    
    格式：{project}-{client}-{page}-{module}-{type}-{source}-{sequence}
    示例：atp-web-prod-core-fn-ai-0001
    """
    pass


def normalize_case_id(value: str, fallback: str = DEFAULT_CASE_ID) -> str:
    """标准化用例 ID (容错处理)"""
    pass


def match_case_id(value: str) -> Optional[re.Match]:
    """验证用例 ID 格式"""
    pass


def next_case_sequence(
    *,
    existing_case_ids: List[str],
    page_code: str,
    module_code: str,
    case_type: str = "fn",
    source: str = "ai",
) -> int:
    """计算下一个序列号"""
    pass
```

---

## 🌐 六、API 接口规范

### 6.1 路由设计

**文件**: `apps/web-ui-service/app/routers/case_management.py`

```python
from fastapi import APIRouter, Depends, Query, Path

router = APIRouter(prefix="/api/v1/cases", tags=["测试用例管理"])

# ========== 基础 CRUD ==========

@router.post("", response_model=TestCaseDetailResponse)
def create_case(
    payload: TestCaseCreatePayload,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """创建测试用例"""
    pass

@router.get("", response_model=PaginatedCasesResponse)
def list_cases(
    q: str = Query(default="", description="搜索关键字"),
    page_code: str = Query(default="", description="页面代码"),
    module_code: str = Query(default="", description="模块代码"),
    case_type: str = Query(default="", description="用例类型"),
    source: str = Query(default="", description="用例来源"),
    status: str = Query(default="", description="状态"),
    tag: str = Query(default="", description="标签"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=50, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
):
    """查询测试用例列表"""
    pass

@router.get("/{case_id}", response_model=TestCaseDetailResponse)
def get_case_detail(
    case_id: str = Path(..., description="用例 ID"),
    db: Session = Depends(get_db),
):
    """获取用例详情 (含版本/执行/缺陷)"""
    pass

@router.put("/{case_id}", response_model=TestCaseDetailResponse)
def update_case(
    case_id: str,
    payload: TestCaseUpdatePayload,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """更新测试用例"""
    pass

@router.delete("/{case_id}")
def delete_case(
    case_id: str,
    soft_delete: bool = Query(default=True, description="软删除"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """删除测试用例"""
    pass

# ========== 用例评审 ==========

@router.post("/{case_id}/review/submit")
def submit_for_review(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """提交用例评审"""
    pass

@router.post("/{case_id}/review/decision")
def review_case(
    case_id: str,
    payload: ReviewDecisionPayload,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """评审用例 (批准/拒绝)"""
    pass

# ========== 用例版本 ==========

@router.get("/{case_id}/versions")
def get_case_versions(
    case_id: str,
    db: Session = Depends(get_db),
):
    """获取用例所有版本"""
    pass

@router.get("/{case_id}/versions/{from_version}/compare/{to_version}")
def compare_versions(
    case_id: str,
    from_version: int,
    to_version: int,
    db: Session = Depends(get_db),
):
    """对比版本差异"""
    pass

@router.post("/{case_id}/versions/{target_version}/rollback")
def rollback_version(
    case_id: str,
    target_version: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """回滚到指定版本"""
    pass

# ========== 用例执行 ==========

@router.get("/{case_id}/executions")
def get_case_executions(
    case_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """获取用例执行历史"""
    pass

@router.post("/{case_id}/executions")
def record_execution(
    case_id: str,
    payload: ExecutionRecordPayload,
    db: Session = Depends(get_db),
):
    """记录执行结果"""
    pass

# ========== 用例统计 ==========

@router.get("/statistics/overview")
def get_case_statistics(
    product_line: str = Query(default=""),
    module_code: str = Query(default=""),
    db: Session = Depends(get_db),
):
    """获取用例统计概览"""
    pass
```

### 6.2 响应格式规范

**统一响应结构**:

```python
# 成功响应
{
    "code": "SUCCESS",
    "data": { ... },
    "message": "操作成功",
    "timestamp": "2026-04-05T12:00:00Z"
}

# 错误响应
{
    "code": "CASE_NOT_FOUND",
    "data": null,
    "message": "用例 atp-web-prod-core-fn-ai-0001 不存在",
    "timestamp": "2026-04-05T12:00:00Z"
}
```

**分页响应**:

```python
{
    "code": "SUCCESS",
    "data": {
        "items": [...],
        "pagination": {
            "page": 1,
            "page_size": 50,
            "total_items": 120,
            "total_pages": 3,
            "has_prev": false,
            "has_next": true,
            "prev_page": null,
            "next_page": 2
        }
    }
}
```

---

## 🧪 七、测试要求

### 7.1 单元测试覆盖

**每个 Service 方法必须有测试**:

```python
# apps/shared_backend/tests/test_case_management_service.py

class TestCaseManagementServiceTest:
    """用例管理服务测试"""
    
    def test_create_case_success(self, db_session):
        """测试成功创建用例"""
        service = TestCaseManagementService(db_session)
        payload = TestCaseCreatePayload(
            title="测试用例",
            page_code="prod",
            module_code="core",
            ...
        )
        case = service.create_case(payload)
        
        assert case.case_id.startswith("atp-web-prod-core-")
        assert case.status == "draft"
        assert case.version_no == 1
    
    def test_create_case_duplicate_id(self, db_session):
        """测试重复 ID 报错"""
        pass
    
    def test_update_case_creates_version(self, db_session):
        """测试更新用例创建新版本"""
        pass
    
    def test_review_case_approval(self, db_session):
        """测试评审通过"""
        pass
    
    def test_review_case_rejection(self, db_session):
        """测试评审拒绝"""
        pass
    
    def test_rollback_to_version(self, db_session):
        """测试版本回滚"""
        pass
```

### 7.2 集成测试

```python
# apps/web-ui-service/tests/integration/test_case_api.py

class TestCaseManagementAPITest:
    """用例管理 API 集成测试"""
    
    def test_create_case_api(self, client, auth_token):
        """测试创建用例 API"""
        response = client.post(
            "/api/v1/cases",
            json={...},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "SUCCESS"
    
    def test_list_cases_filter(self, client, auth_token):
        """测试筛选查询"""
        pass
    
    def test_version_diff_api(self, client, auth_token):
        """测试版本对比 API"""
        pass
```

### 7.3 测试覆盖率要求

| 模块 | 覆盖率要求 |
|------|------------|
| Service 层 | ≥ 90% |
| API 路由 | ≥ 85% |
| 工具函数 | ≥ 95% |
| 模型层 | ≥ 80% |

---

## 📦 八、数据库迁移

### 8.1 Alembic 迁移脚本

**文件**: `apps/web-ui-service/migrations/versions/0001_add_case_management_tables.py`

```python
"""add case management tables

Revision ID: 0001
Revises: previous_revision
Create Date: 2026-04-05

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '0001'
down_revision = 'previous_revision'


def upgrade():
    # 创建 test_cases_v2 表
    op.create_table(
        'test_cases_v2',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.String(64), nullable=False),
        sa.Column('project', sa.String(20), nullable=False),
        sa.Column('client', sa.String(10), nullable=False),
        sa.Column('page_code', sa.String(20), nullable=False),
        sa.Column('module_code', sa.String(20), nullable=False),
        sa.Column('case_type', sa.String(10), nullable=False),
        sa.Column('source', sa.String(10), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('preconditions', sa.JSON(), nullable=True),
        sa.Column('expected_result', sa.Text(), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('business_flows', sa.JSON(), nullable=True),
        sa.Column('priority', sa.String(10), nullable=True),
        sa.Column('runner_type', sa.String(20), nullable=True),
        sa.Column('script_path', sa.String(500), nullable=True),
        sa.Column('script_code', sa.Text(), nullable=True),
        sa.Column('data_config', sa.JSON(), nullable=True),
        sa.Column('markers', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('ai_status', sa.String(40), nullable=True),
        sa.Column('run_status', sa.String(40), nullable=True),
        sa.Column('last_execution_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_execution_id', sa.String(64), nullable=True),
        sa.Column('flaky_score', sa.Float(), nullable=True),
        sa.Column('failure_count', sa.Integer(), nullable=True),
        sa.Column('success_count', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.String(60), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('reviewed_by', sa.String(60), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_changed_by', sa.String(60), nullable=True),
        sa.Column('last_changed_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('case_id'),
    )
    op.create_index('idx_case_status', 'test_cases_v2', ['status'])
    op.create_index('idx_case_priority', 'test_cases_v2', ['priority'])
    op.create_index('idx_case_page_code', 'test_cases_v2', ['page_code'])
    op.create_index('idx_case_module_code', 'test_cases_v2', ['module_code'])
    
    # 创建 case_versions 表
    op.create_table(
        'case_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('version_id', sa.String(80), nullable=False),
        sa.Column('case_id', sa.String(64), nullable=False),
        sa.Column('version_no', sa.Integer(), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.Column('changed_by', sa.String(60), nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('change_type', sa.String(40), nullable=False),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('diff_summary', sa.JSON(), nullable=True),
        sa.Column('execution_ids', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['test_cases_v2.case_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('version_id'),
    )
    op.create_index('idx_version_case_id', 'case_versions', ['case_id'])
    op.create_index('idx_version_no', 'case_versions', ['version_no'])
    
    # 创建 case_executions 表
    op.create_table(
        'case_executions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('execution_id', sa.String(64), nullable=False),
        sa.Column('case_id', sa.String(64), nullable=False),
        sa.Column('run_id', sa.String(64), nullable=False),
        sa.Column('status', sa.String(40), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('runner_type', sa.String(40), nullable=True),
        sa.Column('environment', sa.String(40), nullable=True),
        sa.Column('browser', sa.String(40), nullable=True),
        sa.Column('evidence_manifest_path', sa.Text(), nullable=True),
        sa.Column('report_url', sa.Text(), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['case_id'], ['test_cases_v2.case_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('execution_id'),
    )
    op.create_index('idx_execution_case_id', 'case_executions', ['case_id'])
    op.create_index('idx_execution_run_id', 'case_executions', ['run_id'])


def downgrade():
    op.drop_table('case_executions')
    op.drop_table('case_versions')
    op.drop_table('test_cases_v2')
```

---

## 🔄 九、数据迁移策略

### 9.1 旧数据迁移

**文件**: `scripts/migrate_old_cases.py`

```python
#!/usr/bin/env python3
"""
将旧 test_cases 表数据迁移到 test_cases_v2

使用方法:
    python scripts/migrate_old_cases.py --dry-run
    python scripts/migrate_old_cases.py --execute
"""

import argparse
from sqlalchemy import create_engine, Session, select
from apps.shared_backend.models.test_case import TestCase as TestCaseV2
from apps.web-ui-service.app.models.test_case import TestCase as TestCaseV1


def migrate_case(old_case: TestCaseV1) -> dict:
    """转换旧用例到新格式"""
    # 生成标准 case_id
    case_id = build_case_id(
        page_code=old_case.module[:3].lower(),
        module_code="core",
        case_type="fn",
        source="mn",
        sequence=old_case.id,
    )
    
    return {
        "case_id": case_id,
        "project": "atp",
        "client": "web",
        "page_code": old_case.module[:3].lower(),
        "module_code": "core",
        "case_type": "fn",
        "source": "mn",
        "sequence": old_case.id,
        "title": old_case.name,
        "description": "",
        "expected_result": "",
        "status": "automated" if old_case.script_code else "draft",
        "script_code": old_case.script_code,
        "created_by": old_case.creator,
        "created_at": old_case.created_at,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只预览不执行")
    parser.add_argument("--batch-size", type=int, default=100, help="每批迁移数量")
    args = parser.parse_args()
    
    engine = create_engine("sqlite:///dev.db")
    
    with Session(engine) as session:
        old_cases = session.execute(select(TestCaseV1)).scalars().all()
        
        print(f"找到 {len(old_cases)} 条旧用例")
        
        for i, old_case in enumerate(old_cases):
            new_data = migrate_case(old_case)
            
            if args.dry_run:
                print(f"[DRY RUN] Would migrate: {old_case.id} -> {new_data['case_id']}")
            else:
                new_case = TestCaseV2(**new_data)
                session.add(new_case)
                
                if (i + 1) % args.batch_size == 0:
                    session.commit()
                    print(f"Migrated {i + 1} cases...")
        
        if not args.dry_run:
            session.commit()
            print("Migration completed!")


if __name__ == "__main__":
    main()
```

---

## ✅ 十、验收标准

### 10.1 功能验收

| 功能 | 验收标准 | 验证方法 |
|------|----------|----------|
| 创建用例 | 生成标准 case_id，创建版本快照 | API 测试 + 数据库验证 |
| 更新用例 | 自动创建新版本，记录变更人 | 对比版本历史 |
| 查询用例 | 支持多维度筛选，分页正确 | API 测试 |
| 评审流程 | 状态机正确流转 | 状态转换测试 |
| 版本对比 | 准确显示差异 | UI 手动验证 |
| 版本回滚 | 恢复历史版本内容 | 回滚后验证内容 |
| 执行记录 | 正确关联用例 | 查询执行历史 |
| 统计报表 | 数据准确 | 对比数据库统计 |

### 10.2 代码质量验收

| 指标 | 要求 | 验证工具 |
|------|------|----------|
| 类型注解 | 100% | mypy |
| 单元测试覆盖率 | ≥ 90% | pytest-cov |
| 代码规范 | 无 ruff 警告 | ruff |
| 文档完整性 | 所有公共方法有 docstring | 人工审查 |
| 日志规范 | 关键操作有日志 | 日志审查 |

### 10.3 性能验收

| 场景 | 要求 | 验证方法 |
|------|------|----------|
| 创建用例 | < 200ms | 压测 |
| 查询列表 (1000 条) | < 500ms | 压测 |
| 版本对比 | < 300ms | 压测 |
| 并发创建 (10 并发) | 无死锁 | 压测 |

---

## 📅 十一、实施计划

### Phase 1: 数据模型 (2 天)

- [ ] 创建 `test_cases_v2` 表模型
- [ ] 创建 `case_versions` 表模型
- [ ] 创建 `case_executions` 表模型
- [ ] 编写 Alembic 迁移脚本
- [ ] 运行迁移验证

### Phase 2: 服务层 (3 天)

- [ ] 实现 `TestCaseManagementService`
- [ ] 实现 `TestCaseVersionService`
- [ ] 完善 `case_ids.py` 工具函数
- [ ] 完善 `case_rules.py` 校验规则
- [ ] 编写单元测试 (≥90% 覆盖)

### Phase 3: API 层 (2 天)

- [ ] 实现 `/api/v1/cases` 路由
- [ ] 实现评审相关 API
- [ ] 实现版本管理 API
- [ ] 实现统计 API
- [ ] 编写集成测试

### Phase 4: 数据迁移 (1 天)

- [ ] 编写迁移脚本
- [ ] 执行干跑验证
- [ ] 执行正式迁移
- [ ] 数据一致性校验

### Phase 5: 文档与优化 (1 天)

- [ ] 更新 API 文档
- [ ] 编写使用指南
- [ ] 性能优化
- [ ] 代码审查

---

## 📚 十二、参考文档

- [项目架构文档](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/architecture/current-architecture-and-flows.md)
- [Shared Backend 代码](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/)
- [现有用例服务](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/test_case_service.py)
- [用例 ID 规范](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/case_ids.py)
- [用例规则校验](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/case_rules.py)

---

## 🆘 十三、遇到问题时

### 常见问题处理

1. **不确定字段含义** → 查看 `case_rules.py` 中的校验逻辑
2. **不确定状态机流转** → 参考本文档 4.1 节的 `CaseStatus` 枚举
3. **不确定 API 响应格式** → 参考本文档 6.2 节
4. **数据库迁移失败** → 检查 Alembic 版本号，确保 `down_revision` 正确
5. **测试失败** → 先运行 `pytest -xvs` 查看详细错误

### 求助方式

如果遇到问题无法解决：

1. 先查看项目现有代码的类似实现
2. 查阅本文档相关章节
3. 保留错误日志和堆栈信息
4. 向用户报告问题时附上：
   - 问题描述
   - 已尝试的解决方案
   - 错误日志
   - 相关代码片段

---

**最后提醒**: 

- ✅ **分阶段提交**: 每个 Phase 完成后提交一个 PR，不要一次性提交所有代码
- ✅ **及时沟通**: 遇到不确定的设计决策，先询问再实现
- ✅ **保持兼容**: 新 API 使用 `/api/v1/` 前缀，旧 API 保留至少 30 天

---

*文档结束*
