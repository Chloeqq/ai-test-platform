# Data Generation Agent 详细设计

> **状态**: 🚧 待实现（当前为空壳）
> **优先级**: P0
> **目标成熟度**: L4（企业级）
> **预计完成**: 2026-04-18（4 周）

---

## 1. Agent 概述

### 1.1 职责定义

Data Generation Agent 负责为测试场景生成高质量、可复用、合规的测试数据，包括：

- 边界值数据生成
- 关联业务数据生成
- 敏感数据脱敏
- 测试数据清理
- 数据质量验证

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **安全优先** | 数据泄露零容忍，脱敏完整率 100% |
| **可追溯** | 每条数据可追溯到生成原因和使用场景 |
| **可清理** | 测试完成后自动清理污染数据 |
| **可复用** | 数据模板化，支持跨用例复用 |
| **可验证** | 生成数据必须通过业务规则验证 |

### 1.3 当前实现状态

当前仓库里的 `agents/data-generation-agent/src/agent.py`、`src/schema.py`、`src/evaluator.py` 仍然是空文件，因此这里应视为“绿色空壳 + 目标设计”，而不是“已落地能力”。

这意味着本设计的第一目标不是先接入 LLM，而是先把下面四件事做扎实：

- 模板库
- 关系编排
- 校验器
- 清理与追溯注册器

### 1.4 重设计边界

数据生成能力更适合做成“确定性服务 + 可选 AI 建议”，而不是 prompt-only 的智能生成器。

建议边界如下：

- 默认由模板和规则生成数据，保证可重复、可回放、可清理。
- 关联数据必须由关系图或显式依赖驱动，不能靠模型自由发挥。
- 敏感字段必须先脱敏策略校验，再允许写入测试环境。
- AI 如果参与，只能用于模板推荐、边界值建议、异常场景补充。
- 任何生成结果都要经过 validator，未通过校验的数据不得进入执行链路。

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Data Generation Agent                     │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Input     │  │  Generator  │  │   Output    │         │
│  │  Processor  │→ │  Engine     │→ │  Validator  │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│         ↑                ↑                   ↓               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Data      │  │   Template  │  │   Cleanup   │         │
│  │  Templates  │  │    Library  │  │  Manager    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────┐
                    │  Data Registry  │
                    │  (SQLite/Redis) │
                    └─────────────────┘
```

### 2.2 模块划分

说明：以下模块划分用于表达目标模块边界，不代表当前仓库已全部存在；当前仓库只有少量占位入口文件，真实现状请以 `1.4 重设计边界` 前的说明和实际目录为准。

当前仓库实际存在的核心入口：

- `agents/data-generation-agent/src/agent.py`
- `agents/data-generation-agent/src/index.py`
- `agents/data-generation-agent/src/schema.py`
- `agents/data-generation-agent/src/prompt.py`
- `agents/data-generation-agent/src/evaluator.py`

| 模块 | 文件路径 | 职责 |
|------|---------|------|
| `agent.py` | `agents/data-generation-agent/src/agent.py` | Agent 主入口，编排调用 |
| `input_processor.py` | `agents/data-generation-agent/src/input_processor.py` | 输入解析和验证 |
| `generator_engine.py` | `agents/data-generation-agent/src/generator_engine.py` | 数据生成核心引擎 |
| `validators/` | `agents/data-generation-agent/src/validators/` | 数据验证器 |
| `templates/` | `agents/data-generation-agent/src/templates/` | 数据模板库 |
| `cleanup_manager.py` | `agents/data-generation-agent/src/cleanup_manager.py` | 数据清理管理 |
| `registry.py` | `agents/data-generation-agent/src/registry.py` | 数据注册和追溯 |

---

## 3. 输入输出契约

### 3.1 输入 Schema

```python
# agents/data-generation-agent/src/schema.py

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime

class DataType(str, Enum):
    USER = "user"
    PRODUCT = "product"
    ORDER = "order"
    PAYMENT = "payment"
    CUSTOM = "custom"

class SensitivityLevel(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"

class BoundaryValueConfig(BaseModel):
    include_min: bool = True
    include_max: bool = True
    include_null: bool = True
    include_empty_string: bool = True
    include_special_chars: bool = True
    custom_boundaries: List[Any] = []

class DataRequirement(BaseModel):
    """单个数据需求"""
    data_type: DataType
    quantity: int = Field(ge=1, le=10000)
    fields: Dict[str, Any]  # 字段定义
    constraints: Dict[str, Any] = {}  # 约束条件
    boundary_config: Optional[BoundaryValueConfig] = None
    relationships: List[str] = []  # 关联的其他数据需求 ID
    sensitivity: SensitivityLevel = SensitivityLevel.INTERNAL

class DataGenerationInput(BaseModel):
    """Agent 输入"""
    request_id: str
    requirements: List[DataRequirement]
    templates: Optional[List[Dict]] = None  # 使用的模板
    existing_data: Optional[Dict[str, List]] = None  # 现有数据（增量生成）
    environment: str = "test"  # test/staging
    cleanup_policy: str = "auto"  # auto/manual/none
    validation_rules: Optional[List[Dict]] = None  # 自定义验证规则
    metadata: Dict[str, Any] = {}  # 元数据（项目、版本等）
    
    class Config:
        schema_extra = {
            "example": {
                "request_id": "req-20260321-001",
                "requirements": [
                    {
                        "data_type": "user",
                        "quantity": 10,
                        "fields": {
                            "username": {"type": "string", "pattern": "^[a-z]{5,10}$"},
                            "email": {"type": "string", "format": "email"},
                            "age": {"type": "integer", "min": 18, "max": 100}
                        },
                        "boundary_config": {
                            "include_min": True,
                            "include_max": True,
                            "include_null": False
                        }
                    }
                ],
                "environment": "test",
                "cleanup_policy": "auto"
            }
        }
```

### 3.2 输出 Schema

```python
class DataField(BaseModel):
    """单个数据字段"""
    name: str
    value: Any
    data_type: str
    sensitivity: SensitivityLevel
    is_masked: bool = False

class GeneratedDataRecord(BaseModel):
    """单条生成数据"""
    record_id: str
    data_type: str
    fields: List[DataField]
    relationships: Dict[str, str] = {}  # 关联记录 ID
    metadata: Dict[str, Any] = {}

class ValidationResult(BaseModel):
    """验证结果"""
    passed: bool
    errors: List[str] = []
    warnings: List[str] = []

class DataGenerationOutput(BaseModel):
    """Agent 输出"""
    request_id: str
    generated_data: Dict[str, List[GeneratedDataRecord]]  # 按类型分组
    validation_results: Dict[str, ValidationResult]  # 按类型分组
    coverage_analysis: Dict[str, Any]  # 覆盖分析
    sensitivity_report: Dict[str, int]  # 各敏感度级别数量
    cleanup_instructions: List[Dict]  # 清理指令
    generation_confidence: float = Field(ge=0, le=1)
    warnings: List[str] = []
    requires_manual_review: bool = False
    processing_time_ms: int
    token_usage: Dict[str, int] = {}
    agent_version: str
    timestamp: datetime
    
    class Config:
        schema_extra = {
            "example": {
                "request_id": "req-20260321-001",
                "generated_data": {
                    "user": [
                        {
                            "record_id": "usr-001",
                            "data_type": "user",
                            "fields": [
                                {"name": "username", "value": "testuser1", "data_type": "string", "sensitivity": "internal"},
                                {"name": "email", "value": "test1@example.com", "data_type": "string", "sensitivity": "internal"},
                                {"name": "age", "value": 25, "data_type": "integer", "sensitivity": "public"}
                            ]
                        }
                    ]
                },
                "validation_results": {
                    "user": {"passed": True, "errors": [], "warnings": []}
                },
                "generation_confidence": 0.95,
                "processing_time_ms": 2345
            }
        }
```

---

## 4. 核心功能实现

说明：本章代码块全部属于目标实现蓝图。当前仓库里的 data-generation-agent 仍是空壳入口，因此下面的生成器、脱敏器、清理器和校验器都不能视为已实现能力。

### 4.1 边界值生成器

```python
# agents/data-generation-agent/src/generators/boundary_generator.py

from typing import Any, Dict, List
import random
import string
from datetime import datetime, timedelta

class BoundaryGenerator:
    """边界值生成器"""
    
    @staticmethod
    def generate_integer_boundary(min_val: int, max_val: int, config: Dict) -> List[int]:
        """生成整数边界值"""
        values = []
        
        if config.get('include_min'):
            values.append(min_val)
        if config.get('include_max'):
            values.append(max_val)
        if config.get('include_null'):
            values.append(None)
        
        # 边界附近值
        if max_val - min_val >= 4:
            values.extend([
                min_val + 1,
                max_val - 1,
                0 if min_val <= 0 <= max_val else None
            ])
        
        # 自定义边界
        values.extend(config.get('custom_boundaries', []))
        
        return [v for v in values if v is not None]
    
    @staticmethod
    def generate_string_boundary(pattern: str, config: Dict) -> List[str]:
        """生成字符串边界值"""
        values = []
        
        if config.get('include_empty_string'):
            values.append("")
        if config.get('include_null'):
            values.append(None)
        if config.get('include_special_chars'):
            values.extend(["<script>", "'; DROP TABLE users;--", "🎉"])
        
        # 长度边界
        if 'min_length' in pattern or 'max_length' in pattern:
            min_len = pattern.get('min_length', 1)
            max_len = pattern.get('max_length', 100)
            values.extend([
                'a' * min_len,
                'a' * max_len,
                'a' * (min_len - 1) if min_len > 1 else None,
                'a' * (max_len + 1)
            ])
        
        return [v for v in values if v is not None]
    
    @staticmethod
    def generate_date_boundary(min_date: datetime, max_date: datetime, config: Dict) -> List[datetime]:
        """生成日期边界值"""
        values = []
        
        if config.get('include_min'):
            values.append(min_date)
        if config.get('include_max'):
            values.append(max_date)
        if config.get('include_null'):
            values.append(None)
        
        # 特殊日期
        values.extend([
            datetime.now(),
            datetime(1970, 1, 1),  # Unix epoch
            datetime(2099, 12, 31)  # 远未来
        ])
        
        return [v for v in values if v is not None]
```

### 4.2 关联数据生成器

```python
# agents/data-generation-agent/src/generators/relationship_generator.py

from typing import Dict, List, Any
from uuid import uuid4

class RelationshipGenerator:
    """关联数据生成器"""
    
    def __init__(self):
        self.generated_records: Dict[str, Dict[str, Any]] = {}
    
    def generate_user_order_chain(self, user_count: int, orders_per_user: int) -> Dict:
        """生成用户 - 订单关联数据"""
        result = {
            'users': [],
            'orders': []
        }
        
        # 先生成用户
        for i in range(user_count):
            user_id = f"usr-{uuid4().hex[:8]}"
            user = {
                'record_id': user_id,
                'data_type': 'user',
                'fields': [
                    {'name': 'user_id', 'value': user_id, 'data_type': 'string', 'sensitivity': 'internal'},
                    {'name': 'username', 'value': f'user_{i}', 'data_type': 'string', 'sensitivity': 'internal'},
                    {'name': 'email', 'value': f'user_{i}@test.com', 'data_type': 'string', 'sensitivity': 'internal'}
                ]
            }
            result['users'].append(user)
            self.generated_records[user_id] = user
        
        # 生成订单（关联用户）
        for user in result['users']:
            user_id = user['fields'][0]['value']
            for j in range(orders_per_user):
                order_id = f"ord-{uuid4().hex[:8]}"
                order = {
                    'record_id': order_id,
                    'data_type': 'order',
                    'fields': [
                        {'name': 'order_id', 'value': order_id, 'data_type': 'string', 'sensitivity': 'internal'},
                        {'name': 'user_id', 'value': user_id, 'data_type': 'string', 'sensitivity': 'internal', 'references': user_id},
                        {'name': 'amount', 'value': round(random.uniform(10, 1000), 2), 'data_type': 'number', 'sensitivity': 'confidential'},
                        {'name': 'status', 'value': random.choice(['pending', 'paid', 'shipped', 'delivered']), 'data_type': 'string', 'sensitivity': 'internal'}
                    ],
                    'relationships': {
                        'user': user_id
                    }
                }
                result['orders'].append(order)
                self.generated_records[order_id] = order
        
        return result
```

### 4.3 数据脱敏器

```python
# agents/data-generation-agent/src/masker.py

import re
from typing import Any, Dict, List

class DataMasker:
    """数据脱敏器"""
    
    SENSITIVE_PATTERNS = {
        'phone': r'^1[3-9]\d{9}$',
        'email': r'^[\w\.-]+@[\w\.-]+\.\w+$',
        'id_card': r'^\d{17}[\dXx]$',
        'bank_card': r'^\d{16,19}$',
        'password': re.compile(r'password|passwd|pwd|secret', re.IGNORECASE)
    }
    
    @staticmethod
    def mask_phone(phone: str) -> str:
        """手机号脱敏"""
        if len(phone) == 11:
            return phone[:3] + '****' + phone[-4:]
        return phone
    
    @staticmethod
    def mask_email(email: str) -> str:
        """邮箱脱敏"""
        if '@' in email:
            parts = email.split('@')
            return parts[0][:2] + '***@' + parts[1]
        return email
    
    @staticmethod
    def mask_id_card(id_card: str) -> str:
        """身份证脱敏"""
        if len(id_card) >= 10:
            return id_card[:6] + '****' + id_card[-4:]
        return id_card
    
    @staticmethod
    def mask_by_field_name(field_name: str, value: Any) -> Any:
        """根据字段名脱敏"""
        name_lower = field_name.lower()
        
        if any(kw in name_lower for kw in ['password', 'passwd', 'pwd', 'secret']):
            return '***'
        if 'phone' in name_lower and isinstance(value, str):
            return DataMasker.mask_phone(value)
        if 'email' in name_lower and isinstance(value, str):
            return DataMasker.mask_email(value)
        if 'id_card' in name_lower or 'identity' in name_lower and isinstance(value, str):
            return DataMasker.mask_id_card(value)
        
        return value
    
    @staticmethod
    def detect_and_mask(field_name: str, value: Any, sensitivity: str) -> tuple:
        """检测并脱敏，返回 (脱敏后值，是否脱敏)"""
        if sensitivity in ['confidential', 'restricted']:
            masked = DataMasker.mask_by_field_name(field_name, value)
            return masked, masked != value
        
        # 根据值模式检测
        if isinstance(value, str):
            for pattern_name, pattern in DataMasker.SENSITIVE_PATTERNS.items():
                if isinstance(pattern, re.Pattern):
                    if pattern.search(value):
                        return '***', True
                elif re.match(pattern, value):
                    masked = getattr(DataMasker, f'mask_{pattern_name}', lambda x: x)(value)
                    return masked, True
        
        return value, False
```

### 4.4 数据清理管理器

```python
# agents/data-generation-agent/src/cleanup_manager.py

import json
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path

class CleanupManager:
    """数据清理管理器"""
    
    def __init__(self, registry_path: str = ".data_generation/registry"):
        self.registry_path = Path(registry_path)
        self.registry_path.mkdir(parents=True, exist_ok=True)
    
    def register_cleanup(self, request_id: str, cleanup_instructions: List[Dict]):
        """注册清理指令"""
        registry_file = self.registry_path / f"{request_id}.json"
        registry_data = {
            'request_id': request_id,
            'created_at': datetime.now().isoformat(),
            'cleanup_instructions': cleanup_instructions,
            'status': 'pending',  # pending/completed/failed
            'cleaned_at': None
        }
        
        with open(registry_file, 'w') as f:
            json.dump(registry_data, f, indent=2)
    
    def execute_cleanup(self, request_id: str, executor: callable) -> Dict:
        """执行清理"""
        registry_file = self.registry_path / f"{request_id}.json"
        
        if not registry_file.exists():
            return {'success': False, 'error': 'Registry not found'}
        
        with open(registry_file, 'r') as f:
            registry_data = json.load(f)
        
        results = []
        for instruction in registry_data['cleanup_instructions']:
            try:
                executor(instruction)
                results.append({'instruction': instruction, 'status': 'success'})
            except Exception as e:
                results.append({'instruction': instruction, 'status': 'failed', 'error': str(e)})
        
        # 更新状态
        registry_data['status'] = 'completed' if all(r['status'] == 'success' for r in results) else 'failed'
        registry_data['cleaned_at'] = datetime.now().isoformat()
        registry_data['results'] = results
        
        with open(registry_file, 'w') as f:
            json.dump(registry_data, f, indent=2)
        
        return {'success': True, 'results': results}
    
    def list_pending_cleanups(self) -> List[Dict]:
        """列出待清理项"""
        pending = []
        for file in self.registry_path.glob("*.json"):
            with open(file, 'r') as f:
                data = json.load(f)
                if data['status'] == 'pending':
                    pending.append(data)
        return pending
```

---

## 5. 验证器实现

说明：这一章同样属于目标设计，不代表当前仓库已经存在对应 `validators/` 目录或可运行校验器。

```python
# agents/data-generation-agent/src/validators/__init__.py

from typing import Any, Dict, List
from datetime import datetime

class DataValidator:
    """数据验证器"""
    
    @staticmethod
    def validate_type(value: Any, expected_type: str) -> bool:
        """类型验证"""
        type_map = {
            'string': str,
            'integer': int,
            'number': (int, float),
            'boolean': bool,
            'array': list,
            'object': dict,
            'datetime': datetime
        }
        
        expected = type_map.get(expected_type)
        if not expected:
            return True  # 未知类型，跳过验证
        
        return isinstance(value, expected)
    
    @staticmethod
    def validate_pattern(value: str, pattern: str) -> bool:
        """正则模式验证"""
        import re
        try:
            return bool(re.match(pattern, value))
        except:
            return True  # 无效正则，跳过验证
    
    @staticmethod
    def validate_range(value: Any, min_val: Any = None, max_val: Any = None) -> bool:
        """范围验证"""
        if min_val is not None and value < min_val:
            return False
        if max_val is not None and value > max_val:
            return False
        return True
    
    @staticmethod
    def validate_email(value: str) -> bool:
        """邮箱格式验证"""
        import re
        pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        return bool(re.match(pattern, value))
    
    @staticmethod
    def validate_required(fields: Dict[str, Any], required_fields: List[str]) -> List[str]:
        """必填字段验证，返回缺失字段列表"""
        missing = []
        for field in required_fields:
            if field not in fields or fields[field] is None:
                missing.append(field)
        return missing
```

---

## 6. Agent 主实现

```python
# agents/data-generation-agent/src/agent.py

import time
from datetime import datetime
from typing import Dict, List, Any
from uuid import uuid4

from .schemas import DataGenerationInput, DataGenerationOutput, ValidationResult
from .generator_engine import GeneratorEngine
from .validators import DataValidator
from .masker import DataMasker
from .cleanup_manager import CleanupManager

class DataGenerationAgent:
    """Data Generation Agent 主类"""
    
    VERSION = "0.1.0"
    
    def __init__(self):
        self.generator = GeneratorEngine()
        self.validator = DataValidator()
        self.masker = DataMasker()
        self.cleanup_manager = CleanupManager()
        self.token_usage = {'prompt': 0, 'completion': 0}
    
    async def generate(self, input_data: DataGenerationInput) -> DataGenerationOutput:
        """生成测试数据"""
        start_time = time.time()
        
        generated_data = {}
        validation_results = {}
        cleanup_instructions = []
        sensitivity_report = {'public': 0, 'internal': 0, 'confidential': 0, 'restricted': 0}
        warnings = []
        requires_review = False
        
        for requirement in input_data.requirements:
            # 1. 生成数据
            records = self.generator.generate(
                data_type=requirement.data_type,
                quantity=requirement.quantity,
                fields=requirement.fields,
                constraints=requirement.constraints,
                boundary_config=requirement.boundary_config,
                relationships=requirement.relationships
            )
            
            # 2. 脱敏处理
            for record in records:
                for field in record['fields']:
                    masked_value, was_masked = DataMasker.detect_and_mask(
                        field['name'],
                        field['value'],
                        field.get('sensitivity', 'internal')
                    )
                    field['value'] = masked_value
                    field['is_masked'] = was_masked
                    
                    # 统计敏感度
                    sensitivity_report[field.get('sensitivity', 'internal')] += 1
            
            # 3. 验证数据
            errors = []
            field_warnings = []
            
            for record in records:
                for field in record['fields']:
                    field_def = requirement.fields.get(field['name'], {})
                    
                    # 类型验证
                    if 'type' in field_def:
                        if not self.validator.validate_type(field['value'], field_def['type']):
                            errors.append(f"Field {field['name']} type mismatch")
                    
                    # 模式验证
                    if 'pattern' in field_def:
                        if not self.validator.validate_pattern(str(field['value']), field_def['pattern']):
                            errors.append(f"Field {field['name']} pattern mismatch")
                    
                    # 范围验证
                    if 'min' in field_def or 'max' in field_def:
                        if not self.validator.validate_range(
                            field['value'],
                            field_def.get('min'),
                            field_def.get('max')
                        ):
                            errors.append(f"Field {field['name']} out of range")
            
            validation_results[requirement.data_type] = ValidationResult(
                passed=len(errors) == 0,
                errors=errors,
                warnings=field_warnings
            )
            
            if errors:
                requires_review = True
                warnings.append(f"{requirement.data_type}: {len(errors)} validation errors")
            
            generated_data[requirement.data_type] = records
            
            # 4. 注册清理指令
            if input_data.cleanup_policy == 'auto':
                cleanup_instructions.append({
                    'type': 'delete',
                    'data_type': requirement.data_type,
                    'record_ids': [r['record_id'] for r in records],
                    'environment': input_data.environment
                })
        
        # 5. 注册清理
        if cleanup_instructions:
            self.cleanup_manager.register_cleanup(input_data.request_id, cleanup_instructions)
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        return DataGenerationOutput(
            request_id=input_data.request_id,
            generated_data=generated_data,
            validation_results=validation_results,
            coverage_analysis=self._analyze_coverage(generated_data, input_data.requirements),
            sensitivity_report=sensitivity_report,
            cleanup_instructions=cleanup_instructions,
            generation_confidence=self._calculate_confidence(validation_results),
            warnings=warnings,
            requires_manual_review=requires_review,
            processing_time_ms=processing_time_ms,
            token_usage=self.token_usage,
            agent_version=self.VERSION,
            timestamp=datetime.now()
        )
    
    def _analyze_coverage(self, data: Dict, requirements: List) -> Dict:
        """分析数据覆盖度"""
        return {
            'boundary_coverage': 0.85,  # TODO: 实际计算
            'scenario_coverage': 0.90,
            'data_type_coverage': len(data) / len(requirements) if requirements else 0
        }
    
    def _calculate_confidence(self, validation_results: Dict) -> float:
        """计算生成置信度"""
        if not validation_results:
            return 0.0
        
        passed = sum(1 for r in validation_results.values() if r.passed)
        return passed / len(validation_results)
```

---

## 7. 测试策略

说明：以下测试代码是目标测试蓝图，不代表当前仓库已经存在这些 `tests/` 文件；在 data-generation-agent 尚未真正实现前，这些测试也不应被视作当前覆盖率证据。

### 7.1 单元测试

```python
# agents/data-generation-agent/tests/test_generator.py

import pytest
from src.generator_engine import GeneratorEngine
from src.masker import DataMasker
from src.validators import DataValidator

class TestBoundaryGenerator:
    def test_integer_boundary(self):
        values = BoundaryGenerator.generate_integer_boundary(
            min_val=1,
            max_val=100,
            config={'include_min': True, 'include_max': True, 'include_null': False}
        )
        assert 1 in values
        assert 100 in values
        assert None not in values
    
    def test_string_boundary(self):
        values = BoundaryGenerator.generate_string_boundary(
            pattern={'min_length': 5, 'max_length': 10},
            config={'include_empty_string': True, 'include_special_chars': True}
        )
        assert "" in values
        assert "aaaaa" in values

class TestDataMasker:
    def test_phone_masking(self):
        assert DataMasker.mask_phone("13812345678") == "138****5678"
    
    def test_email_masking(self):
        assert DataMasker.mask_email("test@example.com") == "te***@example.com"
    
    def test_password_masking(self):
        masked, changed = DataMasker.detect_and_mask("password", "secret123", "internal")
        assert masked == "***"
        assert changed == True

class TestDataValidator:
    def test_type_validation(self):
        assert DataValidator.validate_type(123, "integer") == True
        assert DataValidator.validate_type("abc", "integer") == False
    
    def test_email_validation(self):
        assert DataValidator.validate_email("test@example.com") == True
        assert DataValidator.validate_email("invalid") == False
```

### 7.2 集成测试

```python
# agents/data-generation-agent/tests/test_agent_integration.py

import pytest
from src.agent import DataGenerationAgent
from src.schemas import DataGenerationInput, DataRequirement, BoundaryValueConfig

@pytest.mark.asyncio
async def test_full_generation_flow():
    agent = DataGenerationAgent()
    
    input_data = DataGenerationInput(
        request_id="test-001",
        requirements=[
            DataRequirement(
                data_type="user",
                quantity=5,
                fields={
                    "username": {"type": "string", "pattern": "^[a-z]{5,10}$"},
                    "email": {"type": "string", "format": "email"},
                    "age": {"type": "integer", "min": 18, "max": 100}
                },
                boundary_config=BoundaryValueConfig(
                    include_min=True,
                    include_max=True,
                    include_null=False
                )
            )
        ],
        environment="test",
        cleanup_policy="auto"
    )
    
    output = await agent.generate(input_data)
    
    assert output.request_id == "test-001"
    assert "user" in output.generated_data
    assert len(output.generated_data["user"]) == 5
    assert output.validation_results["user"].passed == True
    assert output.generation_confidence > 0.8
```

---

## 8. 实施计划

### Phase 1: 基础框架（Week 1-2）

| 任务 | 负责人 | 预计 | 状态 |
|------|--------|------|------|
| 项目结构搭建 | | 2 天 | ⏳ |
| 输入输出 Schema 定义 | | 2 天 | ⏳ |
| 边界值生成器实现 | | 3 天 | ⏳ |
| 基础验证器实现 | | 2 天 | ⏳ |
| 单元测试框架 | | 1 天 | ⏳ |

### Phase 2: 核心能力（Week 3-4）

| 任务 | 负责人 | 预计 | 状态 |
|------|--------|------|------|
| 关联数据生成器 | | 3 天 | ⏳ |
| 数据脱敏器 | | 2 天 | ⏳ |
| 清理管理器 | | 2 天 | ⏳ |
| Agent 主逻辑 | | 3 天 | ⏳ |
| 集成测试 | | 2 天 | ⏳ |

### Phase 3: 企业级能力（Week 5-6）

| 任务 | 负责人 | 预计 | 状态 |
|------|--------|------|------|
| 数据模板库建设 | | 3 天 | ⏳ |
| 监控指标接入 | | 2 天 | ⏳ |
| Golden Test Set | | 2 天 | ⏳ |
| 文档完善 | | 2 天 | ⏳ |
| 验收测试 | | 1 天 | ⏳ |

---

## 9. 验收标准

### 功能验收

- [ ] 支持 5 种以上数据类型（user/product/order/payment/custom）
- [ ] 边界值覆盖率 100%
- [ ] 关联数据生成正确率 > 95%
- [ ] 数据脱敏完整率 100%
- [ ] 数据验证通过率 > 98%
- [ ] 清理完整率 100%

### 质量验收

- [ ] 单元测试覆盖率 > 85%
- [ ] 集成测试通过率 100%
- [ ] P95 延迟 < 5s
- [ ] 生成置信度校准 > 0.85
- [ ] 数据泄露率 0%

### 运维验收

- [ ] 结构化日志输出
- [ ] Prometheus 指标接入
- [ ] 告警规则配置
- [ ] 灰度发布流程验证
- [ ] 回滚方案验证

---

*文档版本：1.0*
*创建日期：2026-03-21*
*最后更新：2026-03-21*
*维护团队：AI Test Platform Core Team*
