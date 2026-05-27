# Requirement Parser Agent 详细设计

> **状态**: 🔄 L2 → L4 提升中
> **优先级**: P1
> **目标成熟度**: L4（企业级）
> **预计完成**: 2026-04-18（4 周）
> **当前准确率**: ~75%
> **目标准确率**: > 85%

---

## 1. Agent 概述

### 1.1 职责定义

Requirement Parser Agent 负责解析多源需求输入，提取结构化的测试意图和业务实体，为后续测试设计提供高质量输入。

**核心职责**:
- 解析 PRD 文档、Swagger/OpenAPI、Git Diff、缺陷单、线上日志
- 识别业务实体、操作、规则、约束
- 检测需求歧义、矛盾、缺失
- 输出结构化需求规格和测试意图
- 判定需求优先级和可测试性

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **多源兼容** | 统一处理 5 种输入源，输出一致 schema |
| **歧义显性化** | 不隐藏不确定性，明确标注歧义点 |
| **可追溯** | 每个提取的实体可追溯到原文位置 |
| **置信度透明** | 输出置信度并校准，低置信度触发人工审核 |
| **质量门禁** | 不可测试的需求自动阻断 |

### 1.3 在平台中的位置

```
输入源层 → [Requirement Parser] → 测试资产中心 → Test Design Agent
     ↓
  多源输入
  (PRD/Swagger/Git Diff/Bug/Logs)
```

### 1.4 当前实现状态与卡点

当前仓库里的 `agents/requirement-parser-agent/src/agent.py` 已经是可运行实现，并且不是单纯的 prompt 拼接器，而是已经具备：

- 多源输入归一化
- `user_story / prd_url / openapi_url / git_diff_path` 的实际接入
- 规则优先的实体、规则、意图提取
- LLM overlay 作为增量补充
- `confidence / warnings / requires_review` 输出
- 解析评估日志落盘

这意味着它的现实定位是“规则优先的需求解析器”，不是“纯 AI 需求理解器”。

当前卡点主要有三类：

1. 仍然缺少真正统一的 `page_surface` 作为正式输入源。
2. 复杂页面语义和需求歧义的判定仍然存在误差。
3. 置信度校准还没有形成长期的统计闭环。

下一步优先级建议：

1. 把 `page_surface` 作为一等输入接入。
2. 将解析输出与页面分析、测试点计划的依赖关系显式化。
3. 用历史人工修正数据做置信度校准与回放验证。

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                   Requirement Parser Agent                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Input      │  │   Source     │  │   Entity     │          │
│  │   Normalizer │→ │   Parser     │→ │   Extractor  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         ↑                ↑                   ↓                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Quality    │  │  Ambiguity   │  │   Output     │          │
│  │    Gate      │← │   Detector   │← │  Assembler   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Source-Specific Parsers                      │  │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │  │
│  │  │  PRD   │ │Swagger │ │Git Diff│ │  Bug   │ │  Logs  │ │  │
│  │  │Parser  │ │Parser  │ │Parser  │ │Parser  │ │Parser  │ │  │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────┐
                    │  Requirement    │
                    │  Specification  │
                    │  (Structured)   │
                    └─────────────────┘
```

### 2.2 模块划分

说明：以下模块划分用于表达目标模块边界，不代表当前仓库已全部存在；真实实现请以 `1.4 当前实现状态与卡点` 和实际目录为准。

当前仓库实际存在的核心入口：

- `agents/requirement-parser-agent/src/agent.py`
- `agents/requirement-parser-agent/src/index.py`
- `agents/requirement-parser-agent/src/schema.py`
- `agents/requirement-parser-agent/src/tools/`
- `agents/requirement-parser-agent/src/policies/`
- `agents/requirement-parser-agent/src/utils/`

| 模块 | 文件路径 | 职责 |
|------|---------|------|
| `agent.py` | `agents/requirement-parser-agent/src/agent.py` | Agent 主入口，编排调用 |
| `input_normalizer.py` | `agents/requirement-parser-agent/src/input_normalizer.py` | 输入标准化 |
| `parsers/` | `agents/requirement-parser-agent/src/parsers/` | 各源解析器 |
| `entity_extractor.py` | `agents/requirement-parser-agent/src/entity_extractor.py` | 实体识别提取 |
| `ambiguity_detector.py` | `agents/requirement-parser-agent/src/ambiguity_detector.py` | 歧义检测 |
| `quality_gate.py` | `agents/requirement-parser-agent/src/quality_gate.py` | 质量门禁 |
| `confidence_calibrator.py` | `agents/requirement-parser-agent/src/confidence_calibrator.py` | 置信度校准 |

---

## 3. 输入输出契约

### 3.1 输入 Schema

```python
# agents/requirement-parser-agent/src/schema.py

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Union
from enum import Enum
from datetime import datetime

class InputSourceType(str, Enum):
    PRD = "prd"
    SWAGGER = "swagger"
    GIT_DIFF = "git_diff"
    BUG_REPORT = "bug_report"
    LOGS = "logs"

class PRDInput(BaseModel):
    """PRD 文档输入"""
    type: InputSourceType = InputSourceType.PRD
    content: str  # Markdown/文本内容
    metadata: Dict[str, Any] = {
        "version": "",
        "author": "",
        "created_at": "",
        "sections": []
    }
    attachments: Optional[List[str]] = None  # 附件路径（原型图等）

class SwaggerInput(BaseModel):
    """Swagger/OpenAPI 输入"""
    type: InputSourceType = InputSourceType.SWAGGER
    spec: Dict[str, Any]  # OpenAPI spec 对象
    spec_url: Optional[str] = None
    endpoints_filter: Optional[List[str]] = None  # 指定端点

class GitDiffInput(BaseModel):
    """Git Diff 输入"""
    type: InputSourceType = InputSourceType.GIT_DIFF
    diff_content: str  # git diff 输出
    base_branch: str
    target_branch: str
    commit_hash: Optional[str] = None
    changed_files: List[str] = []

class BugReportInput(BaseModel):
    """缺陷单输入"""
    type: InputSourceType = InputSourceType.BUG_REPORT
    title: str
    description: str
    steps_to_reproduce: List[str]
    expected_result: str
    actual_result: str
    severity: str  # critical/major/minor
    component: str
    metadata: Dict[str, Any] = {
        "reporter": "",
        "assigned_to": "",
        "created_at": "",
        "status": ""
    }

class LogsInput(BaseModel):
    """线上日志输入"""
    type: InputSourceType = InputSourceType.LOGS
    log_entries: List[Dict[str, Any]]
    time_range: Dict[str, str]  # start/end
    error_patterns: Optional[List[str]] = None
    user_sessions: Optional[List[str]] = None

class RequirementParserInput(BaseModel):
    """Agent 统一输入"""
    request_id: str
    source: Union[PRDInput, SwaggerInput, GitDiffInput, BugReportInput, LogsInput]
    context: Optional[Dict[str, Any]] = {
        "project": "",
        "module": "",
        "related_requirements": []
    }
    extraction_config: Optional[Dict[str, Any]] = {
        "extract_entities": True,
        "extract_rules": True,
        "extract_constraints": True,
        "detect_ambiguities": True,
        "min_confidence": 0.6
    }
    
    class Config:
        schema_extra = {
            "example": {
                "request_id": "req-parse-20260321-001",
                "source": {
                    "type": "prd",
                    "content": "# 用户登录功能\n\n用户可以...",
                    "metadata": {"version": "1.0", "author": "PM"}
                },
                "context": {"project": "ecommerce", "module": "auth"}
            }
        }
```

### 3.2 输出 Schema

```python
class BusinessEntity(BaseModel):
    """业务实体"""
    entity_id: str
    name: str
    type: str  # user/order/product/payment/etc
    attributes: List[Dict[str, Any]]
    relationships: List[str] = []  # 关联的其他实体 ID
    source_location: Optional[str] = None  # 原文位置
    confidence: float

class BusinessRule(BaseModel):
    """业务规则"""
    rule_id: str
    description: str
    type: str  # validation/calculation/state_transition
    conditions: List[str]
    actions: List[str]
    priority: str = "normal"  # critical/high/normal/low
    source_location: Optional[str] = None
    confidence: float

class TestIntent(BaseModel):
    """测试意图"""
    intent_id: str
    description: str
    type: str  # functional/performance/security/compatibility
    priority: str  # P0/P1/P2
    related_entities: List[str]
    related_rules: List[str]
    acceptance_criteria: List[str]
    source_location: Optional[str] = None
    confidence: float

class Ambiguity(BaseModel):
    """歧义点"""
    ambiguity_id: str
    description: str
    type: str  # vague/contradictory/incomplete/multiple_interpretations
    location: str
    impact: str  # high/medium/low
    suggestions: List[str]  # 澄清建议
    confidence: float

class QualityGateResult(BaseModel):
    """质量门禁结果"""
    passed: bool
    score: float  # 0-100
    blockers: List[str] = []  # 阻塞问题
    warnings: List[str] = []
    recommendations: List[str] = []

class RequirementSpecification(BaseModel):
    """结构化需求规格"""
    spec_id: str
    title: str
    version: str
    summary: str
    business_goal: str
    entities: List[BusinessEntity]
    rules: List[BusinessRule]
    test_intents: List[TestIntent]
    ambiguities: List[Ambiguity]
    quality_gate: QualityGateResult
    parse_confidence: float
    requires_review: bool
    source_type: str
    metadata: Dict[str, Any]

class RequirementParserOutput(BaseModel):
    """Agent 输出"""
    request_id: str
    requirement_spec: RequirementSpecification
    parsing_details: Dict[str, Any] = {
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
                "request_id": "req-parse-20260321-001",
                "requirement_spec": {
                    "spec_id": "spec-001",
                    "title": "用户登录功能",
                    "entities": [...],
                    "test_intents": [...],
                    "parse_confidence": 0.85
                },
                "processing_time_ms": 3456
            }
        }
```

---

## 4. 核心功能实现

说明：本章代码块主要用于表达目标实现方式和模块边界，不代表这些模块文件已在当前仓库落地；当前真实可运行实现仍以 `src/agent.py`、`src/schema.py`、`src/tools/`、`src/utils/` 为主。

### 4.1 输入标准化器

```python
# agents/requirement-parser-agent/src/input_normalizer.py

from typing import Dict, Any, Union
from .schemas import (
    RequirementParserInput,
    PRDInput, SwaggerInput, GitDiffInput,
    BugReportInput, LogsInput, InputSourceType
)

class InputNormalizer:
    """输入标准化器"""
    
    def normalize(self, input_data: RequirementParserInput) -> Dict[str, Any]:
        """将不同源输入转换为统一中间格式"""
        source = input_data.source
        
        if isinstance(source, PRDInput):
            return self._normalize_prd(source)
        elif isinstance(source, SwaggerInput):
            return self._normalize_swagger(source)
        elif isinstance(source, GitDiffInput):
            return self._normalize_git_diff(source)
        elif isinstance(source, BugReportInput):
            return self._normalize_bug_report(source)
        elif isinstance(source, LogsInput):
            return self._normalize_logs(source)
        
        raise ValueError(f"Unknown source type: {type(source)}")
    
    def _normalize_prd(self, source: PRDInput) -> Dict[str, Any]:
        """PRD 标准化"""
        return {
            "source_type": InputSourceType.PRD,
            "raw_content": source.content,
            "structured_content": self._parse_markdown_sections(source.content),
            "metadata": source.metadata,
            "attachments": source.attachments or []
        }
    
    def _normalize_swagger(self, source: SwaggerInput) -> Dict[str, Any]:
        """Swagger 标准化"""
        endpoints = []
        for path, methods in source.spec.get('paths', {}).items():
            if source.endpoints_filter and path not in source.endpoints_filter:
                continue
            for method, details in methods.items():
                endpoints.append({
                    "path": path,
                    "method": method.upper(),
                    "summary": details.get('summary', ''),
                    "description": details.get('description', ''),
                    "parameters": details.get('parameters', []),
                    "request_body": details.get('requestBody', {}),
                    "responses": details.get('responses', {})
                })
        
        return {
            "source_type": InputSourceType.SWAGGER,
            "endpoints": endpoints,
            "components": source.spec.get('components', {}),
            "metadata": {"spec_url": source.spec_url}
        }
    
    def _normalize_git_diff(self, source: GitDiffInput) -> Dict[str, Any]:
        """Git Diff 标准化"""
        changes = []
        current_file = None
        
        for line in source.diff_content.split('\n'):
            if line.startswith('diff --git'):
                current_file = line.split('/')[-1]
            elif line.startswith('+++') or line.startswith('---'):
                continue
            elif line.startswith('+') and not line.startswith('+++'):
                changes.append({
                    "file": current_file,
                    "type": "addition",
                    "content": line[1:]
                })
            elif line.startswith('-') and not line.startswith('---'):
                changes.append({
                    "file": current_file,
                    "type": "deletion",
                    "content": line[1:]
                })
        
        return {
            "source_type": InputSourceType.GIT_DIFF,
            "base_branch": source.base_branch,
            "target_branch": source.target_branch,
            "commit_hash": source.commit_hash,
            "changed_files": source.changed_files,
            "changes": changes
        }
    
    def _normalize_bug_report(self, source: BugReportInput) -> Dict[str, Any]:
        """缺陷单标准化"""
        return {
            "source_type": InputSourceType.BUG_REPORT,
            "title": source.title,
            "description": source.description,
            "steps_to_reproduce": source.steps_to_reproduce,
            "expected_result": source.expected_result,
            "actual_result": source.actual_result,
            "severity": source.severity,
            "component": source.component,
            "metadata": source.metadata
        }
    
    def _normalize_logs(self, source: LogsInput) -> Dict[str, Any]:
        """日志标准化"""
        error_logs = []
        user_paths = {}
        
        for entry in source.log_entries:
            if entry.get('level') in ['ERROR', 'CRITICAL']:
                error_logs.append(entry)
            
            session_id = entry.get('session_id')
            if session_id and source.user_sessions:
                if session_id not in user_paths:
                    user_paths[session_id] = []
                user_paths[session_id].append({
                    "timestamp": entry.get('timestamp'),
                    "action": entry.get('action'),
                    "path": entry.get('path')
                })
        
        return {
            "source_type": InputSourceType.LOGS,
            "time_range": source.time_range,
            "error_logs": error_logs,
            "error_patterns": source.error_patterns or [],
            "user_paths": user_paths
        }
    
    def _parse_markdown_sections(self, content: str) -> List[Dict[str, Any]]:
        """解析 Markdown 章节"""
        sections = []
        current_section = None
        current_content = []
        
        for line in content.split('\n'):
            if line.startswith('#'):
                if current_section:
                    sections.append({
                        "title": current_section,
                        "content": '\n'.join(current_content),
                        "level": current_section.count('#')
                    })
                current_section = line.lstrip('#').strip()
                current_content = []
            else:
                current_content.append(line)
        
        if current_section:
            sections.append({
                "title": current_section,
                "content": '\n'.join(current_content),
                "level": current_section.count('#')
            })
        
        return sections
```

### 4.2 实体提取器

```python
# agents/requirement-parser-agent/src/entity_extractor.py

from typing import List, Dict, Any
import re

class EntityExtractor:
    """业务实体提取器"""
    
    ENTITY_PATTERNS = {
        'user': r'(用户 | 客户 | 会员 | 买家 | 卖家 | 管理员)',
        'order': r'(订单 | 购物车 | 购物车项)',
        'product': r'(商品 | 产品 | 物品 |SKU)',
        'payment': r'(支付 | 付款 | 金额 | 价格 | 费用)',
        'inventory': r'(库存 | 仓库 | 备货)',
        'shipping': r'(物流 | 配送 | 运费 | 地址)',
        'notification': r'(通知 | 消息 | 短信 | 邮件 | 推送)',
        'authentication': r'(登录 | 注册 | 认证 | 权限 | 角色)'
    }
    
    def extract(self, normalized_content: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从标准化内容中提取实体"""
        entities = []
        entity_id_counter = 0
        
        # 根据源类型选择提取策略
        source_type = normalized_content.get('source_type')
        
        if source_type == 'prd':
            entities = self._extract_from_prd(normalized_content)
        elif source_type == 'swagger':
            entities = self._extract_from_swagger(normalized_content)
        elif source_type == 'git_diff':
            entities = self._extract_from_git_diff(normalized_content)
        elif source_type == 'bug_report':
            entities = self._extract_from_bug_report(normalized_content)
        elif source_type == 'logs':
            entities = self._extract_from_logs(normalized_content)
        
        # 为每个实体分配 ID 和置信度
        for entity in entities:
            entity['entity_id'] = f"ent-{entity_id_counter:03d}"
            entity['confidence'] = self._calculate_entity_confidence(entity)
            entity_id_counter += 1
        
        return entities
    
    def _extract_from_prd(self, content: Dict) -> List[Dict]:
        """从 PRD 提取实体"""
        entities = []
        text = content.get('raw_content', '')
        
        for entity_type, pattern in self.ENTITY_PATTERNS.items():
            matches = re.finditer(pattern, text)
            for match in matches:
                # 获取上下文
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end]
                
                entity = {
                    'name': match.group(),
                    'type': entity_type,
                    'attributes': self._extract_attributes(context),
                    'source_location': f"char_{match.start()}-{match.end()}",
                    'context': context
                }
                entities.append(entity)
        
        return self._deduplicate_entities(entities)
    
    def _extract_from_swagger(self, content: Dict) -> List[Dict]:
        """从 Swagger 提取实体"""
        entities = []
        components = content.get('components', {})
        schemas = components.get('schemas', {})
        
        for schema_name, schema_def in schemas.items():
            entity_type = self._infer_entity_type(schema_name)
            entity = {
                'name': schema_name,
                'type': entity_type,
                'attributes': self._extract_schema_attributes(schema_def),
                'source_location': f"schema/{schema_name}"
            }
            entities.append(entity)
        
        return entities
    
    def _extract_schema_attributes(self, schema_def: Dict) -> List[Dict]:
        """从 Schema 定义提取属性"""
        attributes = []
        properties = schema_def.get('properties', {})
        required = schema_def.get('required', [])
        
        for prop_name, prop_def in properties.items():
            attributes.append({
                'name': prop_name,
                'type': prop_def.get('type', 'string'),
                'required': prop_name in required,
                'description': prop_def.get('description', '')
            })
        
        return attributes
    
    def _infer_entity_type(self, schema_name: str) -> str:
        """从 Schema 名称推断实体类型"""
        name_lower = schema_name.lower()
        
        if 'user' in name_lower or 'customer' in name_lower:
            return 'user'
        elif 'order' in name_lower:
            return 'order'
        elif 'product' in name_lower or 'item' in name_lower:
            return 'product'
        elif 'payment' in name_lower or 'transaction' in name_lower:
            return 'payment'
        
        return 'custom'
    
    def _extract_attributes(self, context: str) -> List[Dict]:
        """从上下文提取属性"""
        # 简单实现，实际应该用 NLP 模型
        attributes = []
        
        # 检测常见属性模式
        patterns = [
            (r'(\w+) 为 (\w+)', 'property'),
            (r'(\w+) 必须', 'required'),
            (r'(\w+) 范围', 'range'),
        ]
        
        for pattern, attr_type in patterns:
            matches = re.findall(pattern, context)
            for match in matches:
                attributes.append({
                    'name': match[0],
                    'type': attr_type,
                    'source': pattern
                })
        
        return attributes
    
    def _deduplicate_entities(self, entities: List[Dict]) -> List[Dict]:
        """去重实体"""
        seen = set()
        unique = []
        
        for entity in entities:
            key = (entity['name'], entity['type'])
            if key not in seen:
                seen.add(key)
                unique.append(entity)
        
        return unique
    
    def _calculate_entity_confidence(self, entity: Dict) -> float:
        """计算实体置信度"""
        confidence = 0.5  # 基础置信度
        
        # 有属性则加分
        if entity.get('attributes'):
            confidence += 0.2
        
        # 有明确来源位置加分
        if entity.get('source_location'):
            confidence += 0.1
        
        # 常见实体类型加分
        if entity['type'] in ['user', 'order', 'product']:
            confidence += 0.1
        
        return min(confidence, 1.0)
```

### 4.3 歧义检测器

```python
# agents/requirement-parser-agent/src/ambiguity_detector.py

from typing import List, Dict, Any
import re

class AmbiguityDetector:
    """歧义检测器"""
    
    AMBIGUOUS_WORDS = [
        '可能', '也许', '大概', '约', '左右', '等', '等等',
        '适当', '合理', '及时', '快速', '高效',
        '用户友好', '易用', '美观', '流畅'
    ]
    
    CONTRADICTION_PATTERNS = [
        r'必须.*但不能',
        r'应该.*但不需要',
        r'所有.*但某些',
        r'总是.*但有时'
    ]
    
    def detect(self, entities: List[Dict], rules: List[Dict], content: Dict) -> List[Dict]:
        """检测歧义点"""
        ambiguities = []
        ambiguity_id_counter = 0
        
        # 检测模糊词汇
        vague = self._detect_vague_language(content)
        for v in vague:
            v['ambiguity_id'] = f"amb-{ambiguity_id_counter:03d}"
            v['confidence'] = 0.8
            ambiguities.append(v)
            ambiguity_id_counter += 1
        
        # 检测矛盾
        contradictions = self._detect_contradictions(rules)
        for c in contradictions:
            c['ambiguity_id'] = f"amb-{ambiguity_id_counter:03d}"
            c['confidence'] = 0.7
            ambiguities.append(c)
            ambiguity_id_counter += 1
        
        # 检测不完整
        incomplete = self._detect_incomplete_requirements(entities, rules)
        for i in incomplete:
            i['ambiguity_id'] = f"amb-{ambiguity_id_counter:03d}"
            i['confidence'] = 0.6
            ambiguities.append(i)
            ambiguity_id_counter += 1
        
        return ambiguities
    
    def _detect_vague_language(self, content: Dict) -> List[Dict]:
        """检测模糊语言"""
        ambiguities = []
        text = content.get('raw_content', '')
        
        for word in self.AMBIGUOUS_WORDS:
            if word in text:
                # 找到出现位置
                matches = list(re.finditer(re.escape(word), text))
                for match in matches:
                    start = max(0, match.start() - 30)
                    end = min(len(text), match.end() + 30)
                    context = text[start:end]
                    
                    ambiguities.append({
                        'description': f'使用模糊词汇："{word}"',
                        'type': 'vague',
                        'location': f"char_{match.start()}-{match.end()}",
                        'impact': 'medium',
                        'context': context,
                        'suggestions': [
                            f'将"{word}"替换为具体数值或明确标准',
                            '提供可量化的验收标准'
                        ]
                    })
        
        return ambiguities
    
    def _detect_contradictions(self, rules: List[Dict]) -> List[Dict]:
        """检测矛盾规则"""
        ambiguities = []
        
        for i, rule1 in enumerate(rules):
            for rule2 in rules[i+1:]:
                # 简单检测：查找矛盾模式
                for pattern in self.CONTRADICTION_PATTERNS:
                    text1 = rule1.get('description', '')
                    text2 = rule2.get('description', '')
                    
                    if re.search(pattern, text1 + text2):
                        ambiguities.append({
                            'description': '规则可能存在矛盾',
                            'type': 'contradictory',
                            'location': f"{rule1['rule_id']} vs {rule2['rule_id']}",
                            'impact': 'high',
                            'context': f"{text1[:50]}... | {text2[:50]}...",
                            'suggestions': [
                                '澄清两个规则的优先级',
                                '明确适用条件',
                                '合并或重构规则'
                            ]
                        })
        
        return ambiguities
    
    def _detect_incomplete_requirements(self, entities: List[Dict], rules: List[Dict]) -> List[Dict]:
        """检测不完整需求"""
        ambiguities = []
        
        # 检查实体是否有未定义的属性
        for entity in entities:
            attrs = entity.get('attributes', [])
            for attr in attrs:
                if attr.get('required') and not attr.get('type'):
                    ambiguities.append({
                        'description': f'实体 {entity["name"]} 的必填属性 {attr["name"]} 缺少类型定义',
                        'type': 'incomplete',
                        'location': f"entity/{entity['entity_id']}",
                        'impact': 'high',
                        'suggestions': [
                            f'定义 {attr["name"]} 的数据类型',
                            '提供默认值或约束条件'
                        ]
                    })
        
        return ambiguities
```

### 4.4 质量门禁

```python
# agents/requirement-parser-agent/src/quality_gate.py

from typing import Dict, List, Any
from .schemas import QualityGateResult

class QualityGate:
    """需求质量门禁"""
    
    def evaluate(self, spec: Dict) -> QualityGateResult:
        """评估需求质量"""
        blockers = []
        warnings = []
        recommendations = []
        
        # 检查 1: 必须有业务目标
        if not spec.get('business_goal'):
            blockers.append('缺少业务目标定义')
        
        # 检查 2: 必须有至少一个测试意图
        test_intents = spec.get('test_intents', [])
        if not test_intents:
            blockers.append('没有生成测试意图')
        
        # 检查 3: 高歧义阻断
        ambiguities = spec.get('ambiguities', [])
        high_impact_ambiguities = [a for a in ambiguities if a.get('impact') == 'high']
        if len(high_impact_ambiguities) > 3:
            blockers.append(f'高影响歧义点过多 ({len(high_impact_ambiguities)}个)')
        
        # 检查 4: 置信度过低
        parse_confidence = spec.get('parse_confidence', 0)
        if parse_confidence < 0.5:
            blockers.append(f'解析置信度过低 ({parse_confidence:.2f})')
        
        # 检查 5: 实体覆盖
        entities = spec.get('entities', [])
        if len(entities) == 0:
            warnings.append('未识别到业务实体')
        
        # 检查 6: 规则覆盖
        rules = spec.get('rules', [])
        if len(rules) == 0:
            warnings.append('未识别到业务规则')
        
        # 检查 7: P0 优先级比例
        p0_intents = [t for t in test_intents if t.get('priority') == 'P0']
        if len(p0_intents) > len(test_intents) * 0.5:
            recommendations.append('P0 测试意图比例过高，建议重新评估优先级')
        
        # 计算分数
        score = self._calculate_score(blockers, warnings, spec)
        
        return QualityGateResult(
            passed=len(blockers) == 0,
            score=score,
            blockers=blockers,
            warnings=warnings,
            recommendations=recommendations
        )
    
    def _calculate_score(self, blockers: List, warnings: List, spec: Dict) -> float:
        """计算质量分数"""
        score = 100.0
        
        # 每个 blocker 扣 20 分
        score -= len(blockers) * 20
        
        # 每个 warning 扣 5 分
        score -= len(warnings) * 5
        
        # 歧义点扣分
        ambiguities = spec.get('ambiguities', [])
        score -= len(ambiguities) * 2
        
        # 置信度奖励
        confidence = spec.get('parse_confidence', 0)
        score += confidence * 10
        
        return max(0, min(100, score))
```

### 4.5 置信度校准器

```python
# agents/requirement-parser-agent/src/confidence_calibrator.py

from typing import Dict, List, Any
import json
from pathlib import Path

class ConfidenceCalibrator:
    """置信度校准器"""
    
    def __init__(self, calibration_data_path: str = ".requirement_parser/calibration_data.json"):
        self.calibration_data_path = Path(calibration_data_path)
        self.calibration_data = self._load_calibration_data()
    
    def calibrate(self, raw_confidence: float, features: Dict[str, Any]) -> float:
        """校准置信度"""
        # 简单实现：基于历史数据调整
        # 实际应该用回归模型
        
        adjustment = 0.0
        
        # 特征 1: 输入长度
        input_length = features.get('input_length', 0)
        if input_length < 100:
            adjustment -= 0.1  # 输入太短，降低置信度
        elif input_length > 10000:
            adjustment -= 0.05  # 输入太长，也可能不准确
        
        # 特征 2: 实体数量
        entity_count = features.get('entity_count', 0)
        if entity_count == 0:
            adjustment -= 0.15  # 没有实体，置信度降低
        
        # 特征 3: 歧义数量
        ambiguity_count = features.get('ambiguity_count', 0)
        adjustment -= ambiguity_count * 0.02
        
        # 特征 4: 源类型
        source_type = features.get('source_type', '')
        if source_type == 'swagger':
            adjustment += 0.1  # Swagger 更结构化，置信度提高
        
        calibrated = raw_confidence + adjustment
        return max(0.0, min(1.0, calibrated))
    
    def record_feedback(self, request_id: str, predicted_confidence: float, actual_correct: bool):
        """记录反馈用于校准"""
        self.calibration_data.append({
            'request_id': request_id,
            'predicted_confidence': predicted_confidence,
            'actual_correct': actual_correct,
            'timestamp': str(datetime.now())
        })
        self._save_calibration_data()
    
    def _load_calibration_data(self) -> List[Dict]:
        """加载校准数据"""
        if self.calibration_data_path.exists():
            with open(self.calibration_data_path, 'r') as f:
                return json.load(f)
        return []
    
    def _save_calibration_data(self):
        """保存校准数据"""
        self.calibration_data_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.calibration_data_path, 'w') as f:
            json.dump(self.calibration_data, f, indent=2)
    
    def get_calibration_stats(self) -> Dict:
        """获取校准统计"""
        if not self.calibration_data:
            return {'count': 0, 'accuracy': 0, 'calibration_correlation': 0}
        
        correct = sum(1 for d in self.calibration_data if d['actual_correct'])
        count = len(self.calibration_data)
        
        return {
            'count': count,
            'accuracy': correct / count if count > 0 else 0,
            'last_updated': self.calibration_data[-1]['timestamp'] if self.calibration_data else None
        }
```

---

## 5. Agent 主实现

```python
# agents/requirement-parser-agent/src/agent.py

import time
from datetime import datetime
from typing import Dict, Any

from .schemas import (
    RequirementParserInput,
    RequirementParserOutput,
    RequirementSpecification
)
from .input_normalizer import InputNormalizer
from .entity_extractor import EntityExtractor
from .ambiguity_detector import AmbiguityDetector
from .quality_gate import QualityGate
from .confidence_calibrator import ConfidenceCalibrator

class RequirementParserAgent:
    """Requirement Parser Agent 主类"""
    
    VERSION = "0.1.0"
    MODEL_USED = "qwen-3.5-plus"
    
    def __init__(self):
        self.normalizer = InputNormalizer()
        self.entity_extractor = EntityExtractor()
        self.ambiguity_detector = AmbiguityDetector()
        self.quality_gate = QualityGate()
        self.confidence_calibrator = ConfidenceCalibrator()
        self.token_usage = {'prompt': 0, 'completion': 0}
    
    async def parse(self, input_data: RequirementParserInput) -> RequirementParserOutput:
        """解析需求"""
        start_time = time.time()
        processing_stages = []
        
        # Stage 1: 输入标准化
        normalized = self.normalizer.normalize(input_data)
        processing_stages.append({
            'stage': 'input_normalization',
            'status': 'completed',
            'duration_ms': int((time.time() - start_time) * 1000)
        })
        
        # Stage 2: 实体提取
        entities = self.entity_extractor.extract(normalized)
        processing_stages.append({
            'stage': 'entity_extraction',
            'status': 'completed',
            'entity_count': len(entities)
        })
        
        # Stage 3: 规则提取（简化实现）
        rules = self._extract_rules(normalized, entities)
        processing_stages.append({
            'stage': 'rule_extraction',
            'status': 'completed',
            'rule_count': len(rules)
        })
        
        # Stage 4: 测试意图生成
        test_intents = self._generate_test_intents(entities, rules, normalized)
        processing_stages.append({
            'stage': 'test_intent_generation',
            'status': 'completed',
            'intent_count': len(test_intents)
        })
        
        # Stage 5: 歧义检测
        ambiguities = self.ambiguity_detector.detect(entities, rules, normalized)
        processing_stages.append({
            'stage': 'ambiguity_detection',
            'status': 'completed',
            'ambiguity_count': len(ambiguities)
        })
        
        # Stage 6: 组装规格
        spec = RequirementSpecification(
            spec_id=f"spec-{input_data.request_id}",
            title=self._extract_title(normalized),
            version="1.0",
            summary=self._generate_summary(normalized),
            business_goal=self._extract_business_goal(normalized),
            entities=entities,
            rules=rules,
            test_intents=test_intents,
            ambiguities=ambiguities,
            quality_gate=None,  # 下一步计算
            parse_confidence=0.0,  # 下一步计算
            requires_review=False,  # 下一步计算
            source_type=normalized['source_type'],
            metadata=normalized.get('metadata', {})
        )
        
        # Stage 7: 质量门禁
        spec_dict = spec.model_dump()
        quality_result = self.quality_gate.evaluate(spec_dict)
        spec.quality_gate = quality_result
        
        # Stage 8: 置信度计算和校准
        raw_confidence = self._calculate_raw_confidence(entities, rules, test_intents, ambiguities)
        features = {
            'input_length': len(normalized.get('raw_content', '')),
            'entity_count': len(entities),
            'ambiguity_count': len(ambiguities),
            'source_type': normalized['source_type']
        }
        calibrated_confidence = self.confidence_calibrator.calibrate(raw_confidence, features)
        spec.parse_confidence = calibrated_confidence
        
        # Stage 9: 是否需要人工审核
        spec.requires_review = (
            not quality_result.passed or
            calibrated_confidence < 0.6 or
            len([a for a in ambiguities if a.get('impact') == 'high']) > 0
        )
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        return RequirementParserOutput(
            request_id=input_data.request_id,
            requirement_spec=spec,
            parsing_details={
                'input_tokens': self.token_usage['prompt'],
                'output_tokens': self.token_usage['completion'],
                'processing_stages': processing_stages
            },
            warnings=self._generate_warnings(spec),
            processing_time_ms=processing_time_ms,
            agent_version=self.VERSION,
            model_used=self.MODEL_USED,
            timestamp=datetime.now()
        )
    
    def _extract_rules(self, normalized: Dict, entities: List) -> List[Dict]:
        """提取业务规则（简化实现）"""
        # TODO: 实现完整的规则提取逻辑
        return []
    
    def _generate_test_intents(self, entities: List, rules: List, normalized: Dict) -> List[Dict]:
        """生成测试意图（简化实现）"""
        # TODO: 实现完整的测试意图生成逻辑
        return []
    
    def _extract_title(self, normalized: Dict) -> str:
        """提取标题"""
        return normalized.get('metadata', {}).get('title', 'Untitled Requirement')
    
    def _generate_summary(self, normalized: Dict) -> str:
        """生成摘要"""
        content = normalized.get('raw_content', '')
        return content[:200] + '...' if len(content) > 200 else content
    
    def _extract_business_goal(self, normalized: Dict) -> str:
        """提取业务目标"""
        # TODO: 实现业务目标提取
        return ""
    
    def _calculate_raw_confidence(self, entities: List, rules: List, 
                                   test_intents: List, ambiguities: List) -> float:
        """计算原始置信度"""
        confidence = 0.5
        
        # 实体数量奖励
        confidence += min(len(entities) * 0.05, 0.2)
        
        # 规则数量奖励
        confidence += min(len(rules) * 0.05, 0.1)
        
        # 歧义惩罚
        confidence -= len(ambiguities) * 0.05
        
        return max(0.0, min(1.0, confidence))
    
    def _generate_warnings(self, spec: RequirementSpecification) -> List[str]:
        """生成警告"""
        warnings = []
        
        if not spec.entities:
            warnings.append('未识别到业务实体')
        if not spec.rules:
            warnings.append('未识别到业务规则')
        if spec.parse_confidence < 0.7:
            warnings.append(f'解析置信度较低 ({spec.parse_confidence:.2f})')
        
        return warnings
```

---

## 6. 测试策略

说明：以下测试文件名和测试代码以“推荐测试资产”形式给出，不代表当前仓库已经具备同名 `tests/` 文件；当前真实测试覆盖请以各 Agent 目录下实际存在的 `tests/` 和集成测试为准。

### 6.1 单元测试

```python
# agents/requirement-parser-agent/tests/test_entity_extractor.py

import pytest
from src.entity_extractor import EntityExtractor

class TestEntityExtractor:
    def test_extract_from_prd(self):
        extractor = EntityExtractor()
        content = {
            'source_type': 'prd',
            'raw_content': '用户可以登录系统，查看订单状态'
        }
        
        entities = extractor.extract(content)
        
        assert len(entities) > 0
        assert any(e['type'] == 'user' for e in entities)
        assert any(e['type'] == 'order' for e in entities)
    
    def test_extract_from_swagger(self):
        extractor = EntityExtractor()
        content = {
            'source_type': 'swagger',
            'components': {
                'schemas': {
                    'User': {
                        'type': 'object',
                        'properties': {
                            'username': {'type': 'string'},
                            'email': {'type': 'string'}
                        },
                        'required': ['username']
                    }
                }
            }
        }
        
        entities = extractor.extract(content)
        
        assert len(entities) == 1
        assert entities[0]['name'] == 'User'
        assert len(entities[0]['attributes']) == 2
```

### 6.2 Golden Test Set

```python
# agents/requirement-parser-agent/tests/golden_tests.py

import pytest
from src.agent import RequirementParserAgent
from src.schemas import RequirementParserInput, PRDInput

GOLDEN_TEST_CASES = [
    {
        'name': '简单 PRD 解析',
        'input': RequirementParserInput(
            request_id='golden-001',
            source=PRDInput(
                content='# 用户登录\n\n用户可以输入用户名和密码登录系统'
            )
        ),
        'expected': {
            'min_entities': 1,
            'min_test_intents': 1,
            'min_confidence': 0.6
        }
    },
    # ... 更多测试用例
]

@pytest.mark.parametrize('test_case', GOLDEN_TEST_CASES)
@pytest.mark.asyncio
async def test_golden_cases(test_case):
    agent = RequirementParserAgent()
    output = await agent.parse(test_case['input'])
    
    assert len(output.requirement_spec.entities) >= test_case['expected']['min_entities']
    assert len(output.requirement_spec.test_intents) >= test_case['expected']['min_test_intents']
    assert output.requirement_spec.parse_confidence >= test_case['expected']['min_confidence']
```

---

## 7. 实施计划

### Phase 1: 基础框架（Week 1-2）

| 任务 | 预计 | 状态 |
|------|------|------|
| 项目结构搭建 | 2 天 | ⏳ |
| 输入输出 Schema 定义 | 2 天 | ⏳ |
| 输入标准化器实现 | 2 天 | ⏳ |
| 实体提取器实现 | 3 天 | ⏳ |
| 单元测试框架 | 1 天 | ⏳ |

### Phase 2: 核心能力（Week 3-4）

| 任务 | 预计 | 状态 |
|------|------|------|
| 歧义检测器实现 | 2 天 | ⏳ |
| 质量门禁实现 | 2 天 | ⏳ |
| 置信度校准器实现 | 2 天 | ⏳ |
| Agent 主逻辑 | 3 天 | ⏳ |
| 集成测试 | 2 天 | ⏳ |

### Phase 3: 企业级能力（Week 5-6）

| 任务 | 预计 | 状态 |
|------|------|------|
| 5 种输入源解析器完善 | 3 天 | ⏳ |
| Golden Test Set 建立 | 2 天 | ⏳ |
| 监控指标接入 | 2 天 | ⏳ |
| 文档完善 | 2 天 | ⏳ |
| 验收测试 | 1 天 | ⏳ |

---

## 8. 验收标准

### 功能验收

- [ ] 支持 5 种输入源（PRD/Swagger/Git Diff/Bug/Logs）
- [ ] 实体识别 F1 > 0.85
- [ ] 歧义检测召回率 > 80%
- [ ] 质量门禁有效阻断低质量需求
- [ ] 置信度校准相关性 > 0.75

### 质量验收

- [ ] 单元测试覆盖率 > 85%
- [ ] Golden Test Set 通过率 > 85%
- [ ] P95 延迟 < 8s
- [ ] 准确率 > 85%

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
