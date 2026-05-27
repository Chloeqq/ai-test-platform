# 企业级 AI Agent 技术规范

**版本**: 1.0  
**日期**: 2026-03-20  
**适用范围**: AI 自动化测试平台所有 Agent 模块

---

## 1. 总则

### 1.1 设计原则

```
┌─────────────────────────────────────────────────────────────┐
│                    企业级 Agent 核心原则                     │
├─────────────────────────────────────────────────────────────┤
│  1. 可信优先：所有输出必须带置信度评分                       │
│  2. 可追溯：所有生成物必须可追溯到输入源                     │
│  3. 可解释：所有决策必须有依据展示                           │
│  4. 可干预：所有环节必须支持人工确认和修正                   │
│  5. 可学习：所有人工修正必须反馈给 AI 改进                    │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 AI/人工边界

| 环节 | AI 负责 | 人工负责 | 确认方式 |
|------|--------|----------|----------|
| 页面分析 | 元素识别、定位器生成 | 低置信度元素确认 | 勾选确认 |
| 测试点生成 | 场景列举、优先级建议 | 范围确认、优先级调整 | 勾选 + 拖拽 |
| Page Object | 定位器生成、元素分组 | 高风险元素确认 | 告警确认 |
| 用例生成 | 步骤填充、断言生成 | 抽样检查 (20%) | 滚动浏览 |
| 测试执行 | 全自动 | 触发执行 | 点击按钮 |
| 报告生成 | 全自动 | 无 | 无 |
| 失败分析 | 归因建议、自愈建议 | 确认修复方案 | 选择确认 |
| 风险评估 | 风险评分、建议 | 发布决策 | 点击确认 |

**目标**: AI 完成 85% 工作，人工花 5-7 分钟确认关键节点。

---

## 2. 通用 Agent 要求

### 2.1 输出结构规范

所有 Agent 的输出必须遵循以下结构：

```python
class AIGeneratedOutput(BaseModel):
    """AI 生成输出通用结构"""
    
    # 核心内容
    content: Any                    # 生成的具体内容
    
    # 置信度相关（必需）
    confidence: float               # 置信度 0.0-1.0
    confidence_factors: dict        # 置信度计算依据
    confidence_threshold: float     # 置信度阈值（默认 0.6）
    
    # 质量标记（必需）
    quality_level: str              # HIGH/MEDIUM/LOW
    requires_review: bool           # 是否需要人工确认
    review_reason: str              # 需要确认的原因
    
    # 告警和异常（必需）
    warnings: List[WarningItem]     # 告警列表
    errors: List[ErrorItem]         # 错误列表
    low_confidence_items: list      # 低置信度项目详情
    
    # 追溯信息（必需）
    input_sources: List[str]        # 输入源追溯
    generation_timestamp: str       # 生成时间戳
    agent_version: str              # Agent 版本
    model_info: str                 # 使用的 AI 模型信息
    
    # 执行建议（可选）
    suggestions: List[str]          # 后续操作建议
    next_steps: List[str]           # 推荐下一步
```

### 2.2 置信度评分规范

```python
class ConfidenceScorer:
    """置信度评分器基类"""
    
    # 置信度等级定义
    CONFIDENCE_LEVELS = {
        "HIGH": (0.85, 1.0),      # 可直接执行，无需确认
        "MEDIUM": (0.60, 0.85),   # 需要人工确认
        "LOW": (0.00, 0.60),      # 需要人工干预
    }
    
    def calculate_confidence(self, factors: dict) -> float:
        """
        计算置信度
        
        Args:
            factors: 置信度影响因子字典
            
        Returns:
            置信度分数 0.0-1.0
        """
        # 必须实现加权计算逻辑
        # 权重总和必须为 1.0
        pass
    
    def get_quality_level(self, confidence: float) -> str:
        """根据置信度获取质量等级"""
        for level, (min_score, max_score) in self.CONFIDENCE_LEVELS.items():
            if min_score <= confidence <= max_score:
                return level
        return "LOW"
    
    def requires_review(self, confidence: float) -> bool:
        """判断是否需要人工确认"""
        return confidence < self.CONFIDENCE_LEVELS["HIGH"][0]
```

### 2.3 告警规范

```python
class WarningItem(BaseModel):
    """告警项结构"""
    
    code: str                     # 告警代码（唯一标识）
    message: str                  # 告警信息（用户可见）
    severity: str                 # 严重程度：info/warning/error/blocker
    category: str                 # 告警类别
    confidence: float             # 告警置信度
    evidence: List[str]           # 告警依据
    suggestion: str               # 处理建议
    auto_fixable: bool            # 是否可自动修复
    requires_action: bool         # 是否需要人工处理
```

**告警代码规范**:
```
{AGENT}_{CATEGORY}_{ISSUE}_{SEVERITY}

示例:
- PAGE_ANALYSIS_ELEMENT_LOW_CONFIDENCE_WARNING
- TEST_DESIGN_COVERAGE_GAP_ERROR
- SCRIPT_GENERATION_SYNTAX_ERROR_BLOCKER
```

### 2.4 追溯规范

```python
class TraceabilityInfo(BaseModel):
    """追溯信息结构"""
    
    # 输入追溯
    input_sources: List[InputSource]
    
    # 处理过程
    processing_steps: List[ProcessingStep]
    
    # 输出关联
    output_dependencies: List[OutputDependency]
    
    # 决策依据
    decision_rationale: List[DecisionRationale]


class InputSource(BaseModel):
    """输入源追溯"""
    source_type: str              # 类型：url/file/api/manual
    source_id: str                # 源标识
    source_content_hash: str      # 内容哈希（用于变更检测）
    confidence: float             # 输入源置信度
    timestamp: str                # 输入时间


class ProcessingStep(BaseModel):
    """处理步骤追溯"""
    step_name: str                # 步骤名称
    step_type: str                # 类型：ai_rule/hybrid/manual
    ai_model: str                 # 使用的 AI 模型
    parameters: dict              # 处理参数
    duration_ms: int              # 耗时
    confidence: float             # 步骤置信度


class DecisionRationale(BaseModel):
    """决策依据追溯"""
    decision: str                 # 做出的决策
    basis: str                    # 决策依据
    confidence: float             # 决策置信度
    alternatives: List[str]       # 考虑过的其他选项
    reason_for_rejection: str     # 拒绝其他选项的原因
```

---

## 3. 各 Agent 专项要求

### 3.1 Page Analysis Agent

**职责**: 页面分析、元素识别、表面信息抽取

**输入契约**:
```python
class PageAnalysisInput(BaseModel):
    url: str                      # 目标 URL（必需）
    login_required: bool          # 是否需要登录
    credentials: Optional[dict]   # 登录凭证（可选）
    wait_timeout: int             # 等待超时（秒）
    sampling_count: int           # 采样次数（默认 3）
    security_check: bool          # 安全检查（默认 True）
```

**输出契约**:
```python
class PageSurfaceV1(BaseModel):
    """页面表面信息 V1"""
    
    # 基础信息
    url: str
    page_title: str
    load_time_ms: int
    stability_score: float        # 页面稳定性评分
    
    # 元素列表
    elements: List[PageElement]
    
    # 结构识别
    page_type: str                # list/form/detail/approval/query
    page_type_confidence: float
    structure_zones: dict         # 查询区/结果区/表单区等
    
    # 置信度（必需）
    confidence: float
    confidence_factors: dict
    
    # 告警（必需）
    warnings: List[WarningItem]
    
    # 追溯（必需）
    traceability: TraceabilityInfo
```

**核心能力要求**:

| 能力 | 要求 | 验收标准 |
|------|------|----------|
| DOM 抽取 | 完整抽取所有可交互元素 | 元素识别率>95% |
| 定位器生成 | 为每个元素生成稳定定位器 | 定位器有效率>90% |
| 页面类型识别 | 识别列表/表单/详情/审批页 | 识别准确率>85% |
| 稳定性检测 | 多次采样检测元素稳定性 | 稳定性评分准确率>80% |
| iframe 处理 | 支持 iframe 内元素抽取 | iframe 元素识别率>80% |
| 弹窗检测 | 检测并记录弹窗信息 | 弹窗检测率>90% |
| 安全检查 | SSRF 防护、域名白名单 | 100% 拦截非法 URL |

**置信度计算因子**:
```python
confidence_factors = {
    "dom_completeness": 0.25,      # DOM 完整度
    "locator_uniqueness": 0.25,    # 定位器唯一性
    "sampling_consistency": 0.20,  # 采样一致性
    "page_type_clarity": 0.15,     # 页面类型清晰度
    "stability_score": 0.15,       # 稳定性评分
}
```

**告警规则**:
```python
WARNING_RULES = [
    {
        "condition": "element.confidence < 0.5",
        "code": "PAGE_ANALYSIS_ELEMENT_LOW_CONFIDENCE",
        "severity": "warning",
        "message": "元素置信度低，可能需要人工确认"
    },
    {
        "condition": "page_type_confidence < 0.6",
        "code": "PAGE_ANALYSIS_PAGE_TYPE_UNCERTAIN",
        "severity": "warning",
        "message": "页面类型识别置信度低"
    },
    {
        "condition": "stability_score < 0.7",
        "code": "PAGE_ANALYSIS_PAGE_UNSTABLE",
        "severity": "error",
        "message": "页面不稳定，可能存在动态加载"
    },
    {
        "condition": "sampling_consistency < 0.8",
        "code": "PAGE_ANALYSIS_SAMPLING_INCONSISTENT",
        "severity": "warning",
        "message": "多次采样结果不一致"
    }
]
```

---

### 3.2 Page Object Agent

**职责**: 页面对象生成、定位器管理、元素分组

**输入契约**:
```python
class PageObjectInput(BaseModel):
    page_surface: PageSurfaceV1     # 页面表面信息（必需）
    semantic_model: Optional[dict]  # 语义模型（可选）
    existing_page_object: Optional[dict]  # 现有页面对象（可选）
    merge_strategy: str             # 合并策略：overwrite/merge/prefer_existing
```

**输出契约**:
```python
class PageObjectDraftV1(BaseModel):
    """页面对象草稿 V1"""
    
    # 基础信息
    page_name: str
    page_url: str
    
    # 元素定义
    elements: Dict[str, PageObjectElement]
    
    # 元素分组
    element_groups: Dict[str, List[str]]  # 查询区/表单区/结果区等
    
    # 定位器映射
    locator_map: Dict[str, LocatorInfo]
    
    # 置信度（必需）
    confidence: float
    confidence_factors: dict
    
    # 风险标记（必需）
    high_risk_elements: List[str]
    requires_review_elements: List[str]
    
    # 告警（必需）
    warnings: List[WarningItem]
    
    # 追溯（必需）
    traceability: TraceabilityInfo
```

**核心能力要求**:

| 能力 | 要求 | 验收标准 |
|------|------|----------|
| 定位器生成 | 为每个元素生成最佳定位器 | 定位器有效率>90% |
| 定位器验证 | 实时验证定位器有效性 | 验证准确率>95% |
| 备用定位器 | 为低置信度元素生成备用定位器 | 覆盖率>80% |
| 元素分组 | 按功能区域分组元素 | 分组准确率>85% |
| 风险标记 | 标记高风险元素 | 风险识别率>90% |
| 合并策略 | 与现有页面对象智能合并 | 合并冲突率<5% |

**置信度计算因子**:
```python
confidence_factors = {
    "locator_verified": 0.35,      # 定位器已验证
    "locator_stability": 0.25,     # 定位器稳定性
    "element_interactable": 0.20,  # 元素可交互
    "grouping_accuracy": 0.10,     # 分组准确性
    "merge_conflict_free": 0.10,   # 无合并冲突
}
```

**定位器优先级规则**:
```python
LOCATOR_PRIORITY = [
    "data-testid",                  # 最优：测试专用标识
    "data-test",                    # 次优：测试标识
    "role",                         # 推荐：ARIA role
    "placeholder",                  # 推荐：占位符
    "aria-label",                   # 推荐：ARIA 标签
    "css",                          # 一般：CSS 选择器
    "xpath",                        # 一般：XPath
    "text",                         # 较差：文本匹配
    "dynamic_id",                   # 最差：动态 ID
]
```

---

### 3.3 Requirement Parser Agent

**职责**: 需求解析、页面语义推断、测试意图提取

**输入契约**:
```python
class RequirementParserInput(BaseModel):
    requirement_text: Optional[str]  # 需求文本（可选）
    page_surface: Optional[PageSurfaceV1]  # 页面表面（可选）
    openapi_spec: Optional[dict]    # OpenAPI 规范（可选）
    prd_text: Optional[str]         # PRD 文本（可选）
    git_diff: Optional[str]         # 代码变更（可选）
    defect_ticket: Optional[str]    # 缺陷单（可选）
    input_sources: Optional[List[dict]]  # 多源输入（可选）
    
    # 至少需要一个输入源
    @validator
    def at_least_one_source(cls, v):
        sources = [v.get('requirement_text'), v.get('page_surface'), ...]
        if not any(sources):
            raise ValueError("至少需要一个输入源")
        return v
```

**输出契约**:
```python
class RequirementSpecV1(BaseModel):
    """需求规格 V1"""
    
    # 基础信息
    page: str                       # 页面标识
    priority: str                   # 优先级 P0/P1/P2
    business_goals: List[str]       # 业务目标
    
    # 测试意图
    test_intents: List[TestIntent]  # 测试意图列表
    
    # 业务规则
    business_rules: List[BusinessRule]
    
    # 歧义和不确定性
    ambiguities: List[Ambiguity]
    
    # 置信度（必需）
    confidence: float
    confidence_factors: dict
    
    # 质量门禁（必需）
    quality_gate: QualityGateResult
    
    # 告警（必需）
    warnings: List[WarningItem]
    
    # 追溯（必需）
    traceability: TraceabilityInfo
```

**核心能力要求**:

| 能力 | 要求 | 验收标准 |
|------|------|----------|
| 多源输入支持 | 支持 requirement/page_surface/OpenAPI 等 | 支持≥6 种输入源 |
| 页面类型推断 | 从 page_surface 推断页面类型 | 推断准确率>85% |
| 业务动作提取 | 提取查询/新增/编辑/删除等动作 | 提取准确率>80% |
| 测试意图生成 | 生成访问性/查询/提交等意图 | 意图完整率>85% |
| 歧义检测 | 检测需求中的歧义点 | 歧义检出率>90% |
| 质量门禁 | 输出质量门禁结果 | 门禁决策准确率>85% |

**置信度计算因子**:
```python
confidence_factors = {
    "input_source_quality": 0.25,  # 输入源质量
    "inference_clarity": 0.25,     # 推断清晰度
    "ambiguity_level": 0.20,       # 歧义程度（反向）
    "completeness": 0.15,          # 完整性
    "historical_accuracy": 0.15,   # 历史准确率
}
```

**质量门禁规则**:
```python
QUALITY_GATE_RULES = [
    {
        "condition": "confidence < 0.5",
        "decision": "block",
        "reason": "需求解析置信度过低"
    },
    {
        "condition": "len(test_intents) == 0",
        "decision": "block",
        "reason": "未生成任何测试意图"
    },
    {
        "condition": "len(ambiguities) > 3",
        "decision": "manual_review",
        "reason": "歧义点过多，需要人工澄清"
    },
    {
        "condition": "confidence < 0.7",
        "decision": "allow_with_warning",
        "reason": "置信度中等，建议人工复核"
    }
]
```

---

### 3.4 Test Design Agent

**职责**: 测试点设计、场景生成、优先级划分

**输入契约**:
```python
class TestDesignInput(BaseModel):
    requirement_spec: RequirementSpecV1  # 需求规格（必需）
    semantic_model: PageSemanticModelV1  # 语义模型（必需）
    page_object: PageObjectDraftV1       # 页面对象（必需）
    test_templates: Optional[List[dict]] # 测试模板（可选）
```

**输出契约**:
```python
class TestPointPlanV1(BaseModel):
    """测试点计划 V1"""
    
    # 测试点列表
    test_points: List[TestPoint]
    
    # 覆盖分析
    coverage_analysis: CoverageAnalysis
    
    # 优先级分布
    priority_distribution: dict     # P0/P1/P2 数量
    
    # 依赖关系
    dependencies: List[TestPointDependency]
    
    # 置信度（必需）
    confidence: float
    confidence_factors: dict
    
    # 覆盖缺口（必需）
    coverage_gap: float
    coverage_gap_details: List[str]
    
    # 告警（必需）
    warnings: List[WarningItem]
    
    # 追溯（必需）
    traceability: TraceabilityInfo
```

**核心能力要求**:

| 能力 | 要求 | 验收标准 |
|------|------|----------|
| 页面类型模板 | 按页面类型选择测试模板 | 模板匹配率>90% |
| 测试点 - 元素关联 | 测试点关联到具体页面元素 | 关联率 100% |
| 置信度继承 | 从依赖元素继承置信度 | 继承逻辑正确率 100% |
| 覆盖分析 | 分析测试点覆盖情况 | 覆盖率计算准确率>90% |
| 依赖关系 | 识别测试点间依赖 | 依赖识别准确率>85% |
| 优先级划分 | 合理划分 P0/P1/P2 | 优先级合理率>85% |

**置信度计算因子**:
```python
confidence_factors = {
    "element_coverage": 0.30,      # 元素覆盖率
    "scenario_completeness": 0.25, # 场景完整度
    "dependency_element_confidence": 0.25,  # 依赖元素置信度
    "template_match_quality": 0.10,  # 模板匹配质量
    "historical_pass_rate": 0.10,    # 历史通过率
}
```

**测试点置信度继承规则**:
```python
def calculate_test_point_confidence(test_point, dependent_elements):
    """测试点置信度从依赖元素继承"""
    
    # 基础置信度
    base_confidence = test_point.intrinsic_confidence
    
    # 依赖元素置信度（取最小值）
    element_confidence = min([
        elem.confidence for elem in dependent_elements
    ])
    
    # 继承规则：测试点置信度不超过依赖元素置信度
    final_confidence = min(base_confidence, element_confidence)
    
    # 低置信度标记
    if final_confidence < 0.6:
        test_point.suggestion = "SKIP"
        test_point.skip_reason = "依赖元素置信度低"
    
    return final_confidence
```

---

### 3.5 Script Generation Agent

**职责**: 测试代码生成、语法验证、可执行性检查

**输入契约**:
```python
class ScriptGenerationInput(BaseModel):
    case_bundle: GeneratedCaseBundleV1  # 用例包（必需）
    framework: str = "playwright"        # 框架
    language: str = "python"             # 语言
    code_style: Optional[dict]           # 代码风格配置
```

**输出契约**:
```python
class GeneratedScript(BaseModel):
    """生成的脚本 V1"""
    
    # 脚本内容
    script_code: str
    
    # 脚本元信息
    filename: str
    entrypoint: str
    framework: str
    language: str
    
    # 步骤信息
    steps: List[ScriptStep]
    
    # 验证结果（必需）
    syntax_valid: bool
    syntax_errors: List[str]
    executability_check: ExecutabilityResult
    
    # 置信度（必需）
    confidence: float
    confidence_factors: dict
    
    # 告警（必需）
    warnings: List[WarningItem]
    
    # 追溯（必需）
    traceability: TraceabilityInfo
```

**核心能力要求**:

| 能力 | 要求 | 验收标准 |
|------|------|----------|
| 代码生成 | 生成符合框架规范的代码 | 代码生成率 100% |
| 语法验证 | 验证生成代码语法正确性 | 语法错误检出率 100% |
| 元素引用验证 | 验证引用的元素存在且有效 | 引用验证率 100% |
| 可执行性预检 | 预检代码可执行性 | 预检准确率>90% |
| 代码追溯 | 代码步骤追溯回测试点 | 追溯完整率 100% |

**置信度计算因子**:
```python
confidence_factors = {
    "syntax_valid": 0.35,          # 语法正确
    "element_references_valid": 0.25,  # 元素引用有效
    "executability_score": 0.20,   # 可执行性评分
    "code_quality": 0.10,          # 代码质量
    "traceability_complete": 0.10, # 追溯完整
}
```

**语法验证规则**:
```python
def validate_syntax(script_code: str) -> SyntaxValidationResult:
    """语法验证"""
    
    errors = []
    warnings = []
    
    # 1. Python 语法检查
    try:
        ast.parse(script_code)
    except SyntaxError as e:
        errors.append(f"Python 语法错误：{e}")
    
    # 2. 导入检查
    required_imports = ["pytest", "playwright"]
    for imp in required_imports:
        if f"import {imp}" not in script_code:
            warnings.append(f"缺少导入：{imp}")
    
    # 3. 函数定义检查
    if "def test_" not in script_code:
        errors.append("缺少测试函数定义")
    
    # 4. 断言检查
    if "assert" not in script_code:
        warnings.append("缺少断言")
    
    return SyntaxValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )
```

---

### 3.6 Execution Planner Agent

**职责**: 执行规划、门禁检查、策略制定

**输入契约**:
```python
class ExecutionPlannerInput(BaseModel):
    case_bundle: GeneratedCaseBundleV1  # 用例包（必需）
    execution_mode: str = "yaml"         # 执行模式：yaml/script
    environment: dict                    # 执行环境配置
    parallel: bool = False               # 是否并行
```

**输出契约**:
```python
class ExecutionPlanV1(BaseModel):
    """执行计划 V1"""
    
    # 执行配置
    execution_mode: str
    test_cases: List[TestCasePlan]
    parallel_config: ParallelConfig
    
    # 门禁结果（必需）
    gate_decision: str              # allow/allow_with_warning/block
    gate_check_result: GateCheckResult
    
    # 策略配置
    retry_strategy: RetryStrategy
    timeout_config: TimeoutConfig
    
    # 置信度（必需）
    confidence: float
    confidence_factors: dict
    
    # 告警（必需）
    warnings: List[WarningItem]
    
    # 追溯（必需）
    traceability: TraceabilityInfo
```

**核心能力要求**:

| 能力 | 要求 | 验收标准 |
|------|------|----------|
| 执行门禁 | 检查用例执行前置条件 | 门禁准确率>95% |
| 风险用例标记 | 标记高风险用例 | 风险识别率>90% |
| 重试策略 | 制定合理的重试策略 | 重试有效率>80% |
| 超时配置 | 配置合理的超时时间 | 超时合理率>85% |
| 并发控制 | 控制并发执行 | 并发安全率 100% |

**执行门禁规则**:
```python
class GateChecker:
    """执行门禁检查器"""
    
    def check(self, case_bundle) -> GateCheckResult:
        blockers = []
        warnings = []
        
        # 检查 1: 页面分析置信度
        if case_bundle.page_surface.confidence < 0.5:
            blockers.append("页面分析置信度<50%")
        
        # 检查 2: 关键元素缺失
        critical = case_bundle.semantic_model.critical_elements
        missing = [e for e in critical if e.confidence < 0.4]
        if missing:
            blockers.append(f"关键元素置信度低：{missing}")
        
        # 检查 3: 测试点覆盖不足
        if case_bundle.test_point_plan.coverage_gap > 0.3:
            warnings.append("测试点覆盖缺口>30%")
        
        # 检查 4: 脚本语法错误
        if case_bundle.script.syntax_errors:
            blockers.append(f"脚本语法错误")
        
        # 检查 5: 低置信度用例
        low_conf_cases = [
            c for c in case_bundle.test_cases
            if c.confidence < 0.5
        ]
        if low_conf_cases:
            warnings.append(f"{len(low_conf_cases)}个用例置信度低")
        
        # 决策
        if blockers:
            return GateCheckResult(
                decision="block",
                reasons=blockers,
                warnings=warnings
            )
        elif warnings:
            return GateCheckResult(
                decision="allow_with_warning",
                warnings=warnings
            )
        else:
            return GateCheckResult(decision="allow")
```

---

### 3.7 Risk Evaluation Agent

**职责**: 风险评估、风险报告、发布建议

**输入契约**:
```python
class RiskEvaluationInput(BaseModel):
    execution_result: ExecutionRecordV1  # 执行结果（必需）
    page_analysis: PageSurfaceV1         # 页面分析（必需）
    test_point_plan: TestPointPlanV1     # 测试点计划（必需）
    historical_data: Optional[dict]      # 历史数据（可选）
```

**输出契约**:
```python
class RiskReportV1(BaseModel):
    """风险报告 V1"""
    
    # 风险评估
    overall_risk_level: str         # LOW/MEDIUM/HIGH/CRITICAL
    risk_score: float               # 风险分数 0-100
    
    # 风险维度
    risk_dimensions: Dict[str, RiskDimension]
    
    # 发布建议
    release_recommendation: str     # recommend/caution/block
    recommendation_reason: str
    
    # 置信度（必需）
    confidence: float
    confidence_factors: dict
    
    # 证据（必需）
    evidence: List[RiskEvidence]
    
    # 告警（必需）
    warnings: List[WarningItem]
    
    # 追溯（必需）
    traceability: TraceabilityInfo
```

**核心能力要求**:

| 能力 | 要求 | 验收标准 |
|------|------|----------|
| 多维度评估 | 从多个维度评估风险 | 维度完整率 100% |
| 风险量化 | 量化风险分数 | 分数合理率>85% |
| 证据收集 | 收集风险评估证据 | 证据完整率>90% |
| 发布建议 | 给出明确的发布建议 | 建议合理率>85% |
| 置信度评分 | 评估自身风险置信度 | 置信度准确率>80% |

**风险维度定义**:
```python
RISK_DIMENSIONS = {
    "page_analysis": {
        "weight": 0.20,
        "factors": ["confidence", "stability", "completeness"]
    },
    "test_coverage": {
        "weight": 0.25,
        "factors": ["coverage_ratio", "critical_coverage", "gap_severity"]
    },
    "failure_severity": {
        "weight": 0.30,
        "factors": ["failure_count", "failure_type", "impact_scope"]
    },
    "historical_stability": {
        "weight": 0.15,
        "factors": ["historical_pass_rate", "flaky_rate", "trend"]
    },
    "change_risk": {
        "weight": 0.10,
        "factors": ["code_change_scope", "affected_areas", "complexity"]
    }
}
```

---

### 3.8 Failure Analysis Agent

**职责**: 失败分析、归因分类、根因定位

**输入契约**:
```python
class FailureAnalysisInput(BaseModel):
    failure_evidence: FailureEvidenceV1  # 失败证据（必需）
    test_case: TestCaseV1                # 测试用例（必需）
    page_object: PageObjectDraftV1       # 页面对象（必需）
    execution_logs: str                  # 执行日志（必需）
```

**输出契约**:
```python
class FailureAnalysisV1(BaseModel):
    """失败分析 V1"""
    
    # 失败分类
    failure_source: str             # page_object/page_analysis/case_design/app_bug
    failure_category: str           # locator/timeout/assertion/data/permission
    
    # 归因分析
    root_cause: str
    contributing_factors: List[str]
    
    # 多假设
    hypotheses: List[FailureHypothesis]  # 按置信度排序
    
    # 置信度（必需）
    confidence: float
    confidence_factors: dict
    
    # 告警（必需）
    warnings: List[WarningItem]
    
    # 追溯（必需）
    traceability: TraceabilityInfo
```

**核心能力要求**:

| 能力 | 要求 | 验收标准 |
|------|------|----------|
| 失败来源分类 | 区分生成侧/应用侧失败 | 分类准确率>85% |
| 归因分析 | 分析失败根因 | 归因准确率>80% |
| 多假设输出 | 输出多个可能原因 | 假设完整率>90% |
| 置信度评分 | 评估归因置信度 | 置信度准确率>80% |

**失败来源分类规则**:
```python
FAILURE_SOURCE_RULES = [
    {
        "pattern": "TimeoutError|ElementNotVisible",
        "source": "page_object",
        "confidence_boost": 0.2
    },
    {
        "pattern": "AssertionError.*expected.*got",
        "source": "app_bug",
        "confidence_boost": 0.3
    },
    {
        "pattern": "KeyError|AttributeError",
        "source": "case_design",
        "confidence_boost": 0.4
    },
    {
        "pattern": "Locator.*not found",
        "source": "page_analysis",
        "confidence_boost": 0.3
    }
]
```

---

### 3.9 Self-Healing Agent

**职责**: 自愈建议、修复方案、范围限制

**输入契约**:
```python
class SelfHealingInput(BaseModel):
    failure_analysis: FailureAnalysisV1  # 失败分析（必需）
    page_object: PageObjectDraftV1       # 页面对象（必需）
    test_case: TestCaseV1                # 测试用例（必需）
    max_attempts: int = 3                # 最大尝试次数
```

**输出契约**:
```python
class SelfHealingSuggestionV1(BaseModel):
    """自愈建议 V1"""
    
    # 修复建议
    suggested_fixes: List[HealingFix]
    
    # 范围限制
    allowed_fixes: List[str]          # 允许的修复类型
    forbidden_fixes: List[str]        # 禁止的修复类型
    
    # 置信度（必需）
    confidence: float
    confidence_factors: dict
    
    # 审批要求（必需）
    requires_approval: bool
    approval_reason: str
    
    # 告警（必需）
    warnings: List[WarningItem]
    
    # 追溯（必需）
    traceability: TraceabilityInfo
```

**核心能力要求**:

| 能力 | 要求 | 验收标准 |
|------|------|----------|
| 修复范围限制 | 不修改业务逻辑 | 限制遵守率 100% |
| 修复建议生成 | 生成可行的修复方案 | 建议可行率>85% |
| 置信度评分 | 评估修复置信度 | 置信度准确率>80% |
| 审批判断 | 判断是否需要人工审批 | 审批判断准确率>90% |

**修复范围限制**:
```python
ALLOWED_FIXES = [
    "locator_update",           # 定位器更新
    "selector_alternative",     # 备用选择器
    "timeout_adjustment",       # 超时调整
    "wait_strategy_change",     # 等待策略变更
]

FORBIDDEN_FIXES = [
    "business_logic_change",    # 业务逻辑修改
    "assertion_removal",        # 断言删除
    "step_skip",                # 步骤跳过
    "test_case_modification",   # 测试用例修改
    "requirement_change",       # 需求变更
]
```

---

## 4. Agent 协作要求

### 4.1 数据传递规范

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent 数据流                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  PageAnalysisAgent                                          │
│       ↓ PageSurfaceV1 (带置信度)                            │
│  PageObjectAgent                                            │
│       ↓ PageObjectDraftV1 (带置信度)                        │
│  RequirementParserAgent                                     │
│       ↓ RequirementSpecV1 (带置信度)                        │
│  TestDesignAgent                                            │
│       ↓ TestPointPlanV1 (带置信度)                          │
│  ScriptGenerationAgent                                      │
│       ↓ GeneratedScript (带置信度)                          │
│  ExecutionPlannerAgent                                      │
│       ↓ ExecutionPlanV1 (带门禁结果)                        │
│  [执行]                                                     │
│       ↓ ExecutionRecordV1                                   │
│  FailureAnalysisAgent                                       │
│       ↓ FailureAnalysisV1 (带置信度)                        │
│  SelfHealingAgent                                           │
│       ↓ SelfHealingSuggestionV1 (带置信度)                  │
│  RiskEvaluationAgent                                        │
│       ↓ RiskReportV1 (带置信度)                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 置信度传递规则

```python
class ConfidencePropagation:
    """置信度传递规则"""
    
    @staticmethod
    def propagate(upstream_confidences: List[float], weights: List[float]) -> float:
        """
        置信度传递计算
        
        Args:
            upstream_confidences: 上游置信度列表
            weights: 对应权重（总和为 1.0）
            
        Returns:
            传递后的置信度
        """
        # 加权平均
        propagated = sum(c * w for c, w in zip(upstream_confidences, weights))
        
        # 置信度衰减（每经过一个 Agent 衰减 5%）
        decay_factor = 0.95
        propagated *= decay_factor
        
        return max(0.0, propagated)
    
    @staticmethod
    def inherit(parent_confidence: float, child_intrinsic: float) -> float:
        """
        置信度继承（子节点不超过父节点）
        
        Args:
            parent_confidence: 父节点置信度
            child_intrinsic: 子节点固有置信度
            
        Returns:
            继承后的置信度
        """
        return min(parent_confidence, child_intrinsic)
```

### 4.3 错误传递规则

```python
class ErrorPropagation:
    """错误传递规则"""
    
    @staticmethod
    def should_block_downstream(agent_output: AIGeneratedOutput) -> bool:
        """判断是否应该阻断下游"""
        
        # 规则 1: 置信度过低
        if agent_output.confidence < 0.4:
            return True
        
        # 规则 2: 有 blocker 级别告警
        if any(w.severity == "blocker" for w in agent_output.warnings):
            return True
        
        # 规则 3: 有未解决的错误
        if agent_output.errors:
            return True
        
        return False
```

---

## 5. 安全和合规要求

### 5.1 输入安全

```python
class InputSecurityChecker:
    """输入安全检查器"""
    
    def check_url(self, url: str) -> SecurityCheckResult:
        """URL 安全检查"""
        
        errors = []
        
        # 1. SSRF 防护
        if self._is_internal_url(url):
            errors.append("禁止访问内网 URL")
        
        # 2. 域名白名单
        if not self._is_whitelisted_domain(url):
            errors.append("域名不在白名单中")
        
        # 3. 协议检查
        if not url.startswith(("http://", "https://")):
            errors.append("只支持 HTTP/HTTPS 协议")
        
        # 4. 长度检查
        if len(url) > 2048:
            errors.append("URL 过长")
        
        return SecurityCheckResult(
            passed=len(errors) == 0,
            errors=errors
        )
```

### 5.2 输出审计

```python
class OutputAuditor:
    """输出审计器"""
    
    def audit(self, agent_output: AIGeneratedOutput) -> AuditResult:
        """审计 Agent 输出"""
        
        issues = []
        
        # 1. 置信度缺失检查
        if agent_output.confidence is None:
            issues.append("缺失置信度评分")
        
        # 2. 追溯信息检查
        if not agent_output.traceability:
            issues.append("缺失追溯信息")
        
        # 3. 告警完整性检查
        if agent_output.requires_review and not agent_output.review_reason:
            issues.append("需要确认但缺失原因")
        
        # 4. 敏感信息检查
        if self._contains_sensitive_info(agent_output.content):
            issues.append("包含敏感信息")
        
        return AuditResult(
            passed=len(issues) == 0,
            issues=issues
        )
```

### 5.3 日志和审计追踪

```python
class AgentLogger:
    """Agent 日志记录器"""
    
    def log_generation(self, agent_name: str, input_data: dict, output_data: dict):
        """记录生成日志"""
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent_name": agent_name,
            "input_hash": self._hash(input_data),
            "output_hash": self._hash(output_data),
            "confidence": output_data.get("confidence"),
            "quality_level": output_data.get("quality_level"),
            "requires_review": output_data.get("requires_review"),
            "warnings_count": len(output_data.get("warnings", [])),
            "errors_count": len(output_data.get("errors", [])),
            "model_info": output_data.get("model_info"),
            "duration_ms": output_data.get("processing_duration_ms"),
        }
        
        # 写入审计日志
        self._write_audit_log(log_entry)
```

---

## 6. 验收标准

### 6.1 通用验收标准

| 指标 | 要求 | 测量方法 |
|------|------|----------|
| 置信度评分完整性 | 100% 输出带置信度 | 代码审查 + 运行时检查 |
| 置信度准确率 | >80% 与人工评估一致 | 抽样对比 |
| 告警准确率 | >90% 告警有效 | 告警 - 问题对应率 |
| 追溯完整性 | 100% 输出可追溯 | 追溯链完整性检查 |
| 人工确认点覆盖率 | 100% 关键环节有确认 | 流程审查 |

### 6.2 各 Agent 验收标准

| Agent | 核心指标 | 目标值 |
|-------|----------|--------|
| Page Analysis | 元素识别率 | >95% |
| Page Analysis | 定位器有效率 | >90% |
| Page Object | 定位器验证准确率 | >95% |
| Requirement Parser | 页面类型推断准确率 | >85% |
| Test Design | 测试点 - 元素关联率 | 100% |
| Script Generation | 语法错误检出率 | 100% |
| Execution Planner | 门禁准确率 | >95% |
| Risk Evaluation | 风险评估合理率 | >85% |
| Failure Analysis | 失败分类准确率 | >85% |
| Self Healing | 修复范围限制遵守率 | 100% |

---

## 7. 持续改进

### 7.1 反馈收集

```python
class FeedbackCollector:
    """反馈收集器"""
    
    def collect_human_feedback(self, agent_name: str, feedback: dict):
        """收集人工反馈"""
        
        feedback_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent_name": agent_name,
            "feedback_type": feedback["type"],  # correction/approval/rejection
            "original_output": feedback["original"],
            "corrected_output": feedback.get("corrected"),
            "reason": feedback.get("reason"),
            "confidence_delta": feedback.get("confidence_delta"),
        }
        
        # 存储到反馈库
        self._store_feedback(feedback_entry)
        
        # 触发模型更新
        if feedback["type"] == "correction":
            self._trigger_model_update(agent_name, feedback_entry)
```

### 7.2 置信度校准

```python
class ConfidenceCalibrator:
    """置信度校准器"""
    
    def calibrate(self, agent_name: str, historical_data: List[dict]):
        """校准置信度评分"""
        
        # 分析历史数据
        actual_accuracy = self._calculate_actual_accuracy(historical_data)
        predicted_confidence = self._calculate_avg_confidence(historical_data)
        
        # 计算校准因子
        calibration_factor = actual_accuracy / predicted_confidence
        
        # 更新置信度计算参数
        self._update_confidence_params(agent_name, calibration_factor)
        
        # 记录校准结果
        self._log_calibration(agent_name, calibration_factor)
```

---

## 8. 附录

### 8.1 术语表

| 术语 | 定义 |
|------|------|
| 置信度 | AI 对自身输出正确性的评分 (0.0-1.0) |
| 质量等级 | 基于置信度的分级 (HIGH/MEDIUM/LOW) |
| 人工确认点 | 需要人工介入确认的关键节点 |
| 追溯 | 从输出追溯到输入和处理过程的能力 |
| 门禁 | 执行前的质量检查点 |
| 自愈 | AI 自动修复生成问题的能力 |

### 8.2 参考文档

- [URL 驱动一键全自动落地改造方案](./url_driven_auto_test_plan.md)
- [AI 幻觉防护设计](./ai_hallucination_prevention.md)
- [Agent 协作流程](./agent_collaboration_flow.md)

---

**文档维护**: AI 自动化测试平台架构组  
**最后更新**: 2026-03-20  
**下次审查**: 2026-04-20
