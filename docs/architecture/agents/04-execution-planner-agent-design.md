# Execution Planner Agent 详细设计

> **状态**: ⏳ L2 → L4 提升中
> **优先级**: P1
> **目标成熟度**: L4（企业级）
> **预计完成**: 2026-05-09（4 周）
> **当前准确率**: ~75%
> **目标准确率**: > 85%

---

## 1. Agent 概述

### 1.1 职责定义

Execution Planner Agent 负责规划测试执行策略，包括任务调度、资源分配、并发控制、重试策略等，确保测试高效、稳定执行。

**核心职责**:
- 创建统一任务模型
- 智能调度（优先级、依赖感知）
- 资源优化分配
- 并发控制
- 重试策略（区分 flaky）
- 执行风险评估

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **任务标准化** | 统一任务模型，支持 Web/API/Mobile |
| **依赖感知** | 调度时考虑任务依赖关系 |
| **资源优化** | 最大化资源利用率，避免浪费 |
| **智能重试** | 区分临时失败和永久失败 |
| **风险可控** | 识别执行风险，提前预警 |

### 1.3 在平台中的位置

```
Test Design → [Execution Planner] → Runner
     ↓              ↓                   ↓
  测试点计划      执行计划        执行结果
                     ↓
               任务队列
```

### 1.4 当前实现状态与卡点

当前仓库里的 `agents/execution-planner-agent/src/agent.py` 已经能产出基础执行计划，但它仍然偏“单次运行规划器”，而不是完整的全局调度中心。

当前实际能力：

- 生成运行模式和 stage 切分
- 根据 `priority / steps / execution_requested` 计算基础计划
- 输出 `parallelism / retry_policy / scheduling_hints`

当前卡点：

1. 还没有真正的跨任务队列调度能力。
2. 资源分配更多是启发式，不是资源池级别的强约束。
3. flaky 识别和动态重排还比较轻。

下一步优先级建议：

1. 先把任务模型、队列模型、环境模型统一。
2. 再接入更完整的资源约束和依赖感知调度。
3. 最后再扩展执行期动态调整和重试策略。

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                   Execution Planner Agent                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Test       │  │   Task       │  │  Dependency  │          │
│  │   Analyzer   │→ │   Builder    │→ │   Resolver   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         ↑                ↑                   ↓                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Risk       │  │   Schedule   │  │   Resource   │          │
│  │   Assessor   │← │   Optimizer  │← │   Allocator  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         ↓                                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Execution Strategies                         │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐  │  │
│  │  │  Priority  │  │   Retry    │  │    Concurrency     │  │  │
│  │  │  Queue     │  │  Strategy  │  │     Controller     │  │  │
│  │  └────────────┘  └────────────┘  └────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────┐
                    │  Execution      │
                    │  Plan +         │
                    │  Schedule       │
                    └─────────────────┘
```

### 2.2 模块划分

说明：以下模块划分用于表达目标模块边界，不代表当前仓库已全部存在；真实实现请以 `1.4 当前实现状态与卡点` 和实际目录为准。

当前仓库实际存在的核心入口：

- `agents/execution-planner-agent/src/agent.py`
- `agents/execution-planner-agent/src/index.py`
- `agents/execution-planner-agent/src/schema.py`
- `agents/execution-planner-agent/src/tools/index.py`
- `agents/execution-planner-agent/src/utils/`

| 模块 | 文件路径 | 职责 |
|------|---------|------|
| `agent.py` | `agents/execution-planner-agent/src/agent.py` | Agent 主入口 |
| `test_analyzer.py` | `agents/execution-planner-agent/src/test_analyzer.py` | 测试任务分析 |
| `task_builder.py` | `agents/execution-planner-agent/src/task_builder.py` | 任务构建 |
| `dependency_resolver.py` | `agents/execution-planner-agent/src/dependency_resolver.py` | 依赖解析 |
| `resource_allocator.py` | `agents/execution-planner-agent/src/resource_allocator.py` | 资源分配 |
| `schedule_optimizer.py` | `agents/execution-planner-agent/src/schedule_optimizer.py` | 调度优化 |
| `risk_assessor.py` | `agents/execution-planner-agent/src/risk_assessor.py` | 风险评估 |
| `strategies/` | `agents/execution-planner-agent/src/strategies/` | 执行策略 |

---

## 3. 输入输出契约

### 3.1 输入 Schema

```python
# agents/execution-planner-agent/src/schema.py

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime

class TaskPriority(str, Enum):
    CRITICAL = "critical"  # P0
    HIGH = "high"          # P1
    NORMAL = "normal"      # P2
    LOW = "low"            # P3

class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"

class ResourceType(str, Enum):
    BROWSER = "browser"
    API = "api"
    MOBILE = "mobile"
    DATABASE = "database"
    CUSTOM = "custom"

class RetryStrategy(str, Enum):
    NONE = "none"
    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    LINEAR = "linear"

class TestTask(BaseModel):
    """测试任务"""
    task_id: str
    test_point_id: str
    test_case_id: Optional[str] = None
    title: str
    priority: TaskPriority
    estimated_duration_seconds: int = 60
    dependencies: List[str] = []  # 依赖的任务 ID
    resource_requirements: Dict[str, Any] = {
        "type": ResourceType.BROWSER,
        "browser": "chromium",
        "headless": True
    }
    retry_config: Dict[str, Any] = {
        "strategy": RetryStrategy.EXPONENTIAL,
        "max_retries": 2,
        "delay_seconds": 5
    }
    environment: str = "test"  # test/staging/prod
    tags: List[str] = []
    metadata: Dict[str, Any] = {}
    status: TaskStatus = TaskStatus.PENDING
    assigned_worker: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict] = None

class Environment(BaseModel):
    """执行环境"""
    env_id: str
    name: str
    type: str
    status: str  # available/busy/unavailable
    resources: Dict[str, int]  # 资源容量
    current_load: float  # 0-1
    health_score: float  # 0-100

class ExecutionConstraints(BaseModel):
    """执行约束"""
    max_concurrent_tasks: int = 10
    max_parallel_per_environment: int = 5
    time_budget_minutes: int = 60
    required_environments: List[str] = []
    excluded_tags: List[str] = []
    must_include_tests: List[str] = []

class ExecutionPlannerInput(BaseModel):
    """Agent 输入"""
    request_id: str
    test_tasks: List[TestTask]
    environments: List[Environment]
    constraints: Optional[ExecutionConstraints] = None
    historical_data: Optional[Dict] = {
        "flaky_tests": [],
        "average_duration": {},
        "failure_patterns": []
    }
    
    class Config:
        schema_extra = {
            "example": {
                "request_id": "exec-plan-001",
                "test_tasks": [
                    {
                        "task_id": "task-001",
                        "test_point_id": "tp-001",
                        "title": "用户登录测试",
                        "priority": "critical",
                        "estimated_duration_seconds": 30
                    }
                ],
                "environments": [
                    {
                        "env_id": "env-001",
                        "name": "Chrome-Local",
                        "type": "browser",
                        "status": "available"
                    }
                ]
            }
        }

class ScheduledTask(BaseModel):
    """已调度的任务"""
    task: TestTask
    scheduled_time: datetime
    assigned_environment: str
    estimated_start_time: datetime
    estimated_end_time: datetime
    queue_position: int

class ExecutionPlan(BaseModel):
    """执行计划"""
    plan_id: str
    title: str
    total_tasks: int
    scheduled_tasks: List[ScheduledTask]
    unscheduled_tasks: List[TestTask]  # 无法调度的任务
    timeline: List[Dict]  # 时间线
    resource_allocation: Dict[str, Any]
    risk_assessment: Dict[str, Any]
    statistics: Dict[str, Any]
    plan_confidence: float
    requires_review: bool
    metadata: Dict[str, Any]

class ExecutionPlannerOutput(BaseModel):
    """Agent 输出"""
    request_id: str
    execution_plan: ExecutionPlan
    planning_details: Dict[str, Any] = {
        "processing_stages": [],
        "optimization_iterations": 0
    }
    warnings: List[str] = []
    processing_time_ms: int
    agent_version: str
    model_used: str
    timestamp: datetime
    
    class Config:
        schema_extra = {
            "example": {
                "request_id": "exec-plan-001",
                "execution_plan": {
                    "plan_id": "plan-001",
                    "total_tasks": 10,
                    "scheduled_tasks": [...],
                    "plan_confidence": 0.85
                },
                "processing_time_ms": 2345
            }
        }
```

---

## 4. 核心功能实现

说明：本章代码块主要用于表达目标实现方式和模块边界，不代表这些模块文件已在当前仓库落地；当前真实实现仍以 `src/agent.py`、`src/schema.py` 和轻量工具/策略逻辑为主。

### 4.1 测试任务分析器

```python
# agents/execution-planner-agent/src/test_analyzer.py

from typing import List, Dict, Any

class TestAnalyzer:
    """测试任务分析器"""
    
    def analyze(self, tasks: List[Dict], historical_data: Dict) -> List[Dict]:
        """分析测试任务，提取调度所需信息"""
        analyzed = []
        
        for task in tasks:
            analyzed.append({
                'task_id': task['task_id'],
                'priority_score': self._calculate_priority_score(task),
                'estimated_duration': self._estimate_duration(task, historical_data),
                'is_flaky': self._check_flaky(task, historical_data),
                'resource_needs': task.get('resource_requirements', {}),
                'dependency_count': len(task.get('dependencies', [])),
                'is_blocking': self._is_blocking_task(task),
                'complexity_score': self._calculate_complexity(task)
            })
        
        return analyzed
    
    def _calculate_priority_score(self, task: Dict) -> float:
        """计算优先级分数"""
        priority_map = {
            'critical': 100,
            'high': 75,
            'normal': 50,
            'low': 25
        }
        return priority_map.get(task.get('priority', 'normal'), 50)
    
    def _estimate_duration(self, task: Dict, historical_data: Dict) -> int:
        """估算执行时长"""
        task_id = task['task_id']
        
        # 使用历史数据
        avg_duration = historical_data.get('average_duration', {}).get(task_id)
        if avg_duration:
            return int(avg_duration * 1.2)  # 增加 20% 缓冲
        
        # 使用估算值
        return task.get('estimated_duration_seconds', 60)
    
    def _check_flaky(self, task: Dict, historical_data: Dict) -> bool:
        """检查是否是 flaky 测试"""
        flaky_tests = historical_data.get('flaky_tests', [])
        return task['task_id'] in flaky_tests or task.get('test_point_id') in flaky_tests
    
    def _is_blocking_task(self, task: Dict) -> bool:
        """判断是否是阻塞性任务"""
        # P0 且有其他任务依赖它
        return task.get('priority') == 'critical'
    
    def _calculate_complexity(self, task: Dict) -> float:
        """计算任务复杂度"""
        complexity = 1.0
        
        # 依赖越多越复杂
        dependency_count = len(task.get('dependencies', []))
        complexity += dependency_count * 0.1
        
        # 资源需求多的复杂
        resource_count = len(task.get('resource_requirements', {}))
        complexity += resource_count * 0.05
        
        return min(5.0, complexity)
```

### 4.2 任务构建器

```python
# agents/execution-planner-agent/src/task_builder.py

from typing import List, Dict, Any
from datetime import datetime
from .schemas import TestTask, TaskPriority, TaskStatus, RetryStrategy, ResourceType

class TaskBuilder:
    """任务构建器"""
    
    def build_from_test_points(self, test_points: List[Dict]) -> List[TestTask]:
        """从测试点构建任务"""
        tasks = []
        
        for i, tp in enumerate(test_points):
            task = TestTask(
                task_id=f"task-{datetime.now().strftime('%Y%m%d%H%M%S')}-{i:03d}",
                test_point_id=tp.get('test_point_id', f'tp-{i}'),
                title=tp.get('title', 'Untitled Test'),
                priority=self._map_priority(tp.get('priority', 'P1')),
                estimated_duration_seconds=self._estimate_from_test_point(tp),
                dependencies=[],
                resource_requirements={
                    'type': self._infer_resource_type(tp),
                    'browser': 'chromium',
                    'headless': True
                },
                retry_config={
                    'strategy': RetryStrategy.EXPONENTIAL,
                    'max_retries': 2,
                    'delay_seconds': 5
                },
                environment='test',
                tags=tp.get('tags', []),
                status=TaskStatus.PENDING
            )
            tasks.append(task)
        
        return tasks
    
    def _map_priority(self, priority: str) -> TaskPriority:
        """映射优先级"""
        mapping = {
            'P0': TaskPriority.CRITICAL,
            'P1': TaskPriority.HIGH,
            'P2': TaskPriority.NORMAL,
            'P3': TaskPriority.LOW
        }
        return mapping.get(priority, TaskPriority.NORMAL)
    
    def _estimate_from_test_point(self, tp: Dict) -> int:
        """从测试点估算执行时长"""
        step_count = len(tp.get('test_steps', []))
        # 每步约 5 秒
        return max(30, step_count * 5)
    
    def _infer_resource_type(self, tp: Dict) -> ResourceType:
        """推断资源类型"""
        tags = tp.get('tags', [])
        
        if 'api' in tags or '接口' in tp.get('title', ''):
            return ResourceType.API
        elif 'mobile' in tags or 'app' in tp.get('title', ''):
            return ResourceType.MOBILE
        else:
            return ResourceType.BROWSER
```

### 4.3 依赖解析器

```python
# agents/execution-planner-agent/src/dependency_resolver.py

from typing import List, Dict, Set
from collections import defaultdict

class DependencyResolver:
    """依赖解析器"""
    
    def resolve(self, tasks: List[Dict]) -> Dict[str, Any]:
        """解析任务依赖关系"""
        # 构建依赖图
        graph = defaultdict(list)
        reverse_graph = defaultdict(list)
        
        for task in tasks:
            task_id = task['task_id']
            for dep in task.get('dependencies', []):
                graph[dep].append(task_id)
                reverse_graph[task_id].append(dep)
        
        return {
            'graph': dict(graph),
            'reverse_graph': dict(reverse_graph),
            'roots': self._find_roots(tasks, reverse_graph),
            'leaves': self._find_leaves(tasks, graph),
            'has_cycle': self._detect_cycle(tasks, graph),
            'execution_order': self._topological_sort(tasks, reverse_graph)
        }
    
    def _find_roots(self, tasks: List[Dict], reverse_graph: Dict) -> List[str]:
        """找到根节点（无依赖的任务）"""
        all_ids = {t['task_id'] for t in tasks}
        has_deps = set(reverse_graph.keys())
        return list(all_ids - has_deps)
    
    def _find_leaves(self, tasks: List[Dict], graph: Dict) -> List[str]:
        """找到叶节点（不被依赖的任务）"""
        all_ids = {t['task_id'] for t in tasks}
        is_depended = set(graph.keys())
        return list(all_ids - is_depended)
    
    def _detect_cycle(self, tasks: List[Dict], graph: Dict) -> bool:
        """检测是否有循环依赖"""
        visited = set()
        rec_stack = set()
        
        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        for task in tasks:
            if task['task_id'] not in visited:
                if dfs(task['task_id']):
                    return True
        
        return False
    
    def _topological_sort(self, tasks: List[Dict], reverse_graph: Dict) -> List[str]:
        """拓扑排序，返回执行顺序"""
        in_degree = defaultdict(int)
        all_ids = [t['task_id'] for t in tasks]
        
        for task_id in all_ids:
            in_degree[task_id] = len(reverse_graph.get(task_id, []))
        
        queue = [tid for tid in all_ids if in_degree[tid] == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            for neighbor in [t for t in all_ids if node in reverse_graph.get(t, [])]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        return result
```

### 4.4 资源分配器

```python
# agents/execution-planner-agent/src/resource_allocator.py

from typing import List, Dict, Any

class ResourceAllocator:
    """资源分配器"""
    
    def allocate(self, tasks: List[Dict], environments: List[Dict], 
                 constraints: Dict) -> Dict[str, Any]:
        """分配资源给任务"""
        allocations = {}
        env_load = {env['env_id']: 0 for env in environments}
        env_capacity = {env['env_id']: self._get_capacity(env) for env in environments}
        
        # 按优先级排序任务
        sorted_tasks = sorted(tasks, key=lambda t: self._priority_score(t), reverse=True)
        
        for task in sorted_tasks:
            # 找到最合适的环境
            best_env = self._find_best_environment(
                task, environments, env_load, env_capacity, constraints
            )
            
            if best_env:
                allocations[task['task_id']] = {
                    'environment': best_env['env_id'],
                    'resources': self._allocate_resources(task, best_env),
                    'estimated_wait_time': self._estimate_wait_time(best_env, env_load)
                }
                env_load[best_env['env_id']] += 1
        
        return {
            'allocations': allocations,
            'unallocated': [t['task_id'] for t in tasks if t['task_id'] not in allocations],
            'utilization': self._calculate_utilization(environments, env_load)
        }
    
    def _priority_score(self, task: Dict) -> float:
        """计算优先级分数"""
        priority_map = {'critical': 100, 'high': 75, 'normal': 50, 'low': 25}
        return priority_map.get(task.get('priority', 'normal'), 50)
    
    def _get_capacity(self, env: Dict) -> int:
        """获取环境容量"""
        return env.get('resources', {}).get('concurrent_tasks', 5)
    
    def _find_best_environment(self, task: Dict, environments: List[Dict],
                               env_load: Dict, env_capacity: Dict,
                               constraints: Dict) -> Dict:
        """找到最合适的环境"""
        candidates = []
        
        for env in environments:
            # 检查环境状态
            if env.get('status') != 'available':
                continue
            
            # 检查负载
            if env_load[env['env_id']] >= env_capacity[env['env_id']]:
                continue
            
            # 检查环境类型匹配
            required_type = task.get('resource_requirements', {}).get('type')
            if required_type and env.get('type') != required_type:
                continue
            
            # 计算分数
            score = self._score_environment(env, task)
            candidates.append((score, env))
        
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]
        
        return None
    
    def _score_environment(self, env: Dict, task: Dict) -> float:
        """对环境评分"""
        score = 50.0
        
        # 健康度
        score += env.get('health_score', 50) * 0.3
        
        # 当前负载（负载越低越好）
        score += (1 - env.get('current_load', 0.5)) * 20
        
        # 类型匹配
        required_type = task.get('resource_requirements', {}).get('type')
        if env.get('type') == required_type:
            score += 30
        
        return score
    
    def _allocate_resources(self, task: Dict, env: Dict) -> Dict:
        """分配具体资源"""
        return {
            'browser': task.get('resource_requirements', {}).get('browser', 'chromium'),
            'headless': task.get('resource_requirements', {}).get('headless', True),
            'viewport': {'width': 1920, 'height': 1080}
        }
    
    def _estimate_wait_time(self, env: Dict, env_load: Dict) -> int:
        """估算等待时间"""
        # 简化估算：每个任务 30 秒
        return env_load[env['env_id']] * 30
    
    def _calculate_utilization(self, environments: List[Dict], env_load: Dict) -> Dict:
        """计算资源利用率"""
        total_capacity = sum(self._get_capacity(env) for env in environments)
        total_used = sum(env_load.values())
        
        return {
            'overall': total_used / total_capacity if total_capacity > 0 else 0,
            'per_environment': {
                env['env_id']: env_load[env['env_id']] / self._get_capacity(env)
                for env in environments
            }
        }
```

### 4.5 调度优化器

```python
# agents/execution-planner-agent/src/schedule_optimizer.py

from typing import List, Dict, Any
from datetime import datetime, timedelta

class ScheduleOptimizer:
    """调度优化器"""
    
    def optimize(self, tasks: List[Dict], allocations: Dict, 
                 dependencies: Dict, constraints: Dict) -> List[Dict]:
        """优化执行调度"""
        scheduled = []
        current_time = datetime.now()
        
        # 按依赖顺序和优先级调度
        execution_order = dependencies.get('execution_order', [])
        
        for task_id in execution_order:
            task = next((t for t in tasks if t['task_id'] == task_id), None)
            if not task:
                continue
            
            allocation = allocations.get('allocations', {}).get(task_id)
            if not allocation:
                continue
            
            # 计算最早开始时间（考虑依赖）
            earliest_start = self._calculate_earliest_start(
                task, scheduled, dependencies
            )
            
            # 创建调度
            scheduled_task = {
                'task': task,
                'scheduled_time': current_time,
                'assigned_environment': allocation['environment'],
                'estimated_start_time': max(current_time, earliest_start),
                'estimated_end_time': max(current_time, earliest_start) + \
                                     timedelta(seconds=task.get('estimated_duration_seconds', 60)),
                'queue_position': len(scheduled)
            }
            
            scheduled.append(scheduled_task)
            current_time += timedelta(seconds=5)  # 任务间隔
        
        return scheduled
    
    def _calculate_earliest_start(self, task: Dict, scheduled: List[Dict],
                                  dependencies: Dict) -> datetime:
        """计算最早开始时间"""
        task_deps = task.get('dependencies', [])
        if not task_deps:
            return datetime.now()
        
        # 找到所有依赖任务的结束时间
        max_end_time = datetime.now()
        for dep_id in task_deps:
            dep_scheduled = next((s for s in scheduled if s['task']['task_id'] == dep_id), None)
            if dep_scheduled:
                dep_end = dep_scheduled['estimated_end_time']
                if dep_end > max_end_time:
                    max_end_time = dep_end
        
        return max_end_time
```

### 4.6 风险评估器

```python
# agents/execution-planner-agent/src/risk_assessor.py

from typing import List, Dict, Any

class RiskAssessor:
    """风险评估器"""
    
    def assess(self, tasks: List[Dict], schedule: List[Dict], 
               historical_data: Dict) -> Dict[str, Any]:
        """评估执行风险"""
        return {
            'overall_risk_score': self._calculate_overall_risk(tasks, schedule),
            'risk_factors': self._identify_risk_factors(tasks, schedule, historical_data),
            'flaky_risk': self._assess_flaky_risk(tasks, historical_data),
            'timeout_risk': self._assess_timeout_risk(schedule),
            'resource_risk': self._assess_resource_risk(schedule),
            'mitigation_suggestions': self._generate_mitigations(tasks, schedule)
        }
    
    def _calculate_overall_risk(self, tasks: List[Dict], schedule: List[Dict]) -> float:
        """计算整体风险分数"""
        risk = 0.0
        
        # Flaky 测试比例
        flaky_count = sum(1 for t in tasks if t.get('is_flaky', False))
        if tasks:
            risk += (flaky_count / len(tasks)) * 30
        
        # 高优先级任务失败风险
        critical_count = sum(1 for t in tasks if t.get('priority') == 'critical')
        if tasks:
            risk += (critical_count / len(tasks)) * 20
        
        # 调度密度风险
        if schedule:
            avg_gap = self._calculate_avg_gap(schedule)
            if avg_gap < 10:  # 间隔太短
                risk += 20
        
        return min(100, risk)
    
    def _identify_risk_factors(self, tasks: List[Dict], schedule: List[Dict],
                               historical_data: Dict) -> List[Dict]:
        """识别风险因素"""
        factors = []
        
        # Flaky 测试
        flaky_tasks = [t for t in tasks if t.get('is_flaky', False)]
        if flaky_tasks:
            factors.append({
                'type': 'flaky_tests',
                'severity': 'medium',
                'count': len(flaky_tasks),
                'description': f'{len(flaky_tasks)}个测试标记为 flaky',
                'affected_tests': [t['task_id'] for t in flaky_tasks]
            })
        
        # 长耗时测试
        long_tasks = [t for t in tasks if t.get('estimated_duration_seconds', 0) > 300]
        if long_tasks:
            factors.append({
                'type': 'long_running_tests',
                'severity': 'low',
                'count': len(long_tasks),
                'description': f'{len(long_tasks)}个测试预计超过 5 分钟'
            })
        
        return factors
    
    def _assess_flaky_risk(self, tasks: List[Dict], historical_data: Dict) -> Dict:
        """评估 Flaky 风险"""
        flaky_count = sum(1 for t in tasks if t.get('is_flaky', False))
        
        return {
            'flaky_count': flaky_count,
            'flaky_ratio': flaky_count / len(tasks) if tasks else 0,
            'retry_recommended': flaky_count > 0,
            'suggested_retries': 2 if flaky_count > 0 else 0
        }
    
    def _assess_timeout_risk(self, schedule: List[Dict]) -> Dict:
        """评估超时风险"""
        if not schedule:
            return {'timeout_risk': 'low', 'at_risk_count': 0}
        
        total_duration = sum(
            (s['estimated_end_time'] - s['estimated_start_time']).total_seconds()
            for s in schedule
        )
        
        risk = 'low'
        if total_duration > 3600:
            risk = 'high'
        elif total_duration > 1800:
            risk = 'medium'
        
        return {
            'timeout_risk': risk,
            'total_duration_seconds': total_duration,
            'at_risk_count': 1 if risk == 'high' else 0
        }
    
    def _assess_resource_risk(self, schedule: List[Dict]) -> Dict:
        """评估资源风险"""
        env_usage = {}
        for s in schedule:
            env = s['assigned_environment']
            env_usage[env] = env_usage.get(env, 0) + 1
        
        overloaded = [env for env, count in env_usage.items() if count > 10]
        
        return {
            'resource_risk': 'high' if overloaded else 'low',
            'overloaded_environments': overloaded
        }
    
    def _calculate_avg_gap(self, schedule: List[Dict]) -> float:
        """计算平均间隔"""
        if len(schedule) < 2:
            return float('inf')
        
        gaps = []
        for i in range(1, len(schedule)):
            gap = (schedule[i]['scheduled_time'] - schedule[i-1]['scheduled_time']).total_seconds()
            gaps.append(gap)
        
        return sum(gaps) / len(gaps)
    
    def _generate_mitigations(self, tasks: List[Dict], schedule: List[Dict]) -> List[str]:
        """生成缓解建议"""
        suggestions = []
        
        flaky_count = sum(1 for t in tasks if t.get('is_flaky', False))
        if flaky_count > 0:
            suggestions.append(f'为{flaky_count}个 flaky 测试启用自动重试')
        
        critical_count = sum(1 for t in tasks if t.get('priority') == 'critical')
        if critical_count > 5:
            suggestions.append('优先执行 P0 测试，考虑分批执行')
        
        if len(schedule) > 50:
            suggestions.append('测试数量较多，考虑并行执行或分片')
        
        return suggestions
```

---

## 5. Agent 主实现

```python
# agents/execution-planner-agent/src/agent.py

import time
from datetime import datetime
from typing import Dict, Any

from .schemas import (
    ExecutionPlannerInput,
    ExecutionPlannerOutput,
    ExecutionPlan
)
from .test_analyzer import TestAnalyzer
from .task_builder import TaskBuilder
from .dependency_resolver import DependencyResolver
from .resource_allocator import ResourceAllocator
from .schedule_optimizer import ScheduleOptimizer
from .risk_assessor import RiskAssessor

class ExecutionPlannerAgent:
    """Execution Planner Agent 主类"""
    
    VERSION = "0.1.0"
    MODEL_USED = "qwen-3.5-plus"
    
    def __init__(self):
        self.analyzer = TestAnalyzer()
        self.builder = TaskBuilder()
        self.resolver = DependencyResolver()
        self.allocator = ResourceAllocator()
        self.optimizer = ScheduleOptimizer()
        self.assessor = RiskAssessor()
    
    async def plan(self, input_data: ExecutionPlannerInput) -> ExecutionPlannerOutput:
        """制定执行计划"""
        start_time = time.time()
        processing_stages = []
        
        # Stage 1: 测试任务分析
        analyzed = self.analyzer.analyze(
            [t.model_dump() for t in input_data.test_tasks],
            input_data.historical_data or {}
        )
        processing_stages.append({
            'stage': 'test_analysis',
            'status': 'completed',
            'task_count': len(analyzed)
        })
        
        # Stage 2: 依赖解析
        dependencies = self.resolver.resolve(
            [t.model_dump() for t in input_data.test_tasks]
        )
        processing_stages.append({
            'stage': 'dependency_resolution',
            'status': 'completed',
            'has_cycle': dependencies['has_cycle']
        })
        
        # Stage 3: 资源分配
        allocations = self.allocator.allocate(
            [t.model_dump() for t in input_data.test_tasks],
            [e.model_dump() for e in input_data.environments],
            input_data.constraints.model_dump() if input_data.constraints else {}
        )
        processing_stages.append({
            'stage': 'resource_allocation',
            'status': 'completed',
            'utilization': allocations['utilization']
        })
        
        # Stage 4: 调度优化
        schedule = self.optimizer.optimize(
            [t.model_dump() for t in input_data.test_tasks],
            allocations,
            dependencies,
            input_data.constraints.model_dump() if input_data.constraints else {}
        )
        processing_stages.append({
            'stage': 'schedule_optimization',
            'status': 'completed',
            'scheduled_count': len(schedule)
        })
        
        # Stage 5: 风险评估
        risk = self.assessor.assess(
            [t.model_dump() for t in input_data.test_tasks],
            schedule,
            input_data.historical_data or {}
        )
        processing_stages.append({
            'stage': 'risk_assessment',
            'status': 'completed',
            'risk_score': risk['overall_risk_score']
        })
        
        # Stage 6: 组装计划
        plan = ExecutionPlan(
            plan_id=f"plan-{input_data.request_id}",
            title=f"Execution Plan for {input_data.request_id}",
            total_tasks=len(input_data.test_tasks),
            scheduled_tasks=schedule,
            unscheduled_tasks=[
                t for t in input_data.test_tasks 
                if t.task_id not in allocations.get('allocations', {})
            ],
            timeline=self._build_timeline(schedule),
            resource_allocation=allocations,
            risk_assessment=risk,
            statistics=self._calculate_statistics(input_data.test_tasks, schedule),
            plan_confidence=self._calculate_confidence(risk),
            requires_review=risk['overall_risk_score'] > 50,
            metadata={
                'constraints': input_data.constraints.model_dump() if input_data.constraints else None
            }
        )
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        return ExecutionPlannerOutput(
            request_id=input_data.request_id,
            execution_plan=plan,
            planning_details={
                'processing_stages': processing_stages,
                'optimization_iterations': 1
            },
            warnings=self._generate_warnings(plan, risk),
            processing_time_ms=processing_time_ms,
            agent_version=self.VERSION,
            model_used=self.MODEL_USED,
            timestamp=datetime.now()
        )
    
    def _build_timeline(self, schedule: List[Dict]) -> List[Dict]:
        """构建时间线"""
        return [
            {
                'time': s['estimated_start_time'].isoformat(),
                'event': 'task_start',
                'task_id': s['task']['task_id']
            }
            for s in schedule[:10]  # 限制数量
        ]
    
    def _calculate_statistics(self, tasks: List, schedule: List[Dict]) -> Dict:
        """计算统计信息"""
        return {
            'total_tasks': len(tasks),
            'scheduled_tasks': len(schedule),
            'unscheduled_tasks': len(tasks) - len(schedule),
            'estimated_total_duration': sum(
                (s['estimated_end_time'] - s['estimated_start_time']).total_seconds()
                for s in schedule
            )
        }
    
    def _calculate_confidence(self, risk: Dict) -> float:
        """计算计划置信度"""
        risk_score = risk['overall_risk_score']
        return max(0.3, 1.0 - risk_score / 100)
    
    def _generate_warnings(self, plan: ExecutionPlan, risk: Dict) -> list:
        """生成警告"""
        warnings = []
        
        if plan.risk_assessment['overall_risk_score'] > 50:
            warnings.append(f'执行风险较高 ({plan.risk_assessment["overall_risk_score"]:.1f})')
        
        if plan.unscheduled_tasks:
            warnings.append(f'{len(plan.unscheduled_tasks)}个任务无法调度')
        
        if risk['flaky_risk']['flaky_count'] > 0:
            warnings.append(f'{risk["flaky_risk"]["flaky_count"]}个 flaky 测试')
        
        return warnings
```

---

## 6. 测试策略

说明：以下测试代码是目标测试设计，不代表当前仓库已经存在同名 `tests/` 文件；当前执行规划能力的真实可用性请优先看调用链与集成测试结果。

### 6.1 单元测试

```python
# agents/execution-planner-agent/tests/test_dependency_resolver.py

import pytest
from src.dependency_resolver import DependencyResolver

class TestDependencyResolver:
    def test_resolve_simple_chain(self):
        resolver = DependencyResolver()
        tasks = [
            {'task_id': 'task-1', 'dependencies': []},
            {'task_id': 'task-2', 'dependencies': ['task-1']},
            {'task_id': 'task-3', 'dependencies': ['task-2']}
        ]
        
        result = resolver.resolve(tasks)
        
        assert not result['has_cycle']
        assert 'task-1' in result['roots']
        assert 'task-3' in result['leaves']
        assert result['execution_order'] == ['task-1', 'task-2', 'task-3']
    
    def test_detect_cycle(self):
        resolver = DependencyResolver()
        tasks = [
            {'task_id': 'task-1', 'dependencies': ['task-2']},
            {'task_id': 'task-2', 'dependencies': ['task-1']}
        ]
        
        result = resolver.resolve(tasks)
        
        assert result['has_cycle'] == True
```

### 6.2 Golden Test Set

```python
# agents/execution-planner-agent/tests/golden_tests.py

import pytest
from src.agent import ExecutionPlannerAgent
from src.schemas import ExecutionPlannerInput, TestTask, Environment

GOLDEN_TEST_CASES = [
    {
        'name': '简单执行计划',
        'input': ExecutionPlannerInput(
            request_id='golden-ep-001',
            test_tasks=[
                TestTask(
                    task_id='task-001',
                    test_point_id='tp-001',
                    title='登录测试',
                    priority='critical',
                    estimated_duration_seconds=30
                )
            ],
            environments=[
                Environment(
                    env_id='env-001',
                    name='Chrome-Local',
                    type='browser',
                    status='available',
                    resources={'concurrent_tasks': 5},
                    current_load=0.2,
                    health_score=95
                )
            ]
        ),
        'expected': {
            'all_tasks_scheduled': True,
            'no_cycle': True,
            'risk_score_below': 50
        }
    }
]

@pytest.mark.parametrize('test_case', GOLDEN_TEST_CASES)
@pytest.mark.asyncio
async def test_golden_cases(test_case):
    agent = ExecutionPlannerAgent()
    output = await agent.plan(test_case['input'])
    
    assert len(output.execution_plan.unscheduled_tasks) == 0 == test_case['expected']['all_tasks_scheduled']
    assert output.execution_plan.risk_assessment['overall_risk_score'] < test_case['expected']['risk_score_below']
```

---

## 7. 实施计划

### Phase 1: 基础框架（Week 1-2）

| 任务 | 预计 | 状态 |
|------|------|------|
| 项目结构搭建 | 2 天 | ⏳ |
| 输入输出 Schema 定义 | 2 天 | ⏳ |
| 任务分析器实现 | 2 天 | ⏳ |
| 依赖解析器实现 | 2 天 | ⏳ |
| 单元测试框架 | 1 天 | ⏳ |

### Phase 2: 核心能力（Week 3-4）

| 任务 | 预计 | 状态 |
|------|------|------|
| 资源分配器实现 | 2 天 | ⏳ |
| 调度优化器实现 | 2 天 | ⏳ |
| 风险评估器实现 | 2 天 | ⏳ |
| Agent 主逻辑 | 3 天 | ⏳ |
| 集成测试 | 2 天 | ⏳ |

### Phase 3: 企业级能力（Week 5-6）

| 任务 | 预计 | 状态 |
|------|------|------|
| 统一任务模型完善 | 2 天 | ⏳ |
| Golden Test Set 建立 | 2 天 | ⏳ |
| 监控指标接入 | 2 天 | ⏳ |
| 文档完善 | 2 天 | ⏳ |
| 验收测试 | 1 天 | ⏳ |

---

## 8. 验收标准

### 功能验收

- [ ] 统一任务模型可用
- [ ] 调度合理性 > 90%
- [ ] 资源利用率 > 75%
- [ ] 重试成功率 > 60%
- [ ] 依赖解析准确率 100%

### 质量验收

- [ ] 单元测试覆盖率 > 85%
- [ ] Golden Test Set 通过率 > 85%
- [ ] P95 延迟 < 3s
- [ ] 调度合理性 > 90%

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
