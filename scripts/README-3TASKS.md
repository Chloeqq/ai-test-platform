# 🔧 三任务执行计划

**创建时间**: 2026-03-22  
**目标**: 简化项目、验证核心、降低维护负担  
**预计总时间**: 2-3 天

---

## 📋 任务总览

| 任务 | 目标 | 预计时间 | 优先级 |
|------|------|----------|--------|
| 1. 清理空文件 | 删除 258 个空文件，减少 60% 代码文件 | 30 分钟 | 🔴 P0 |
| 2. 拆分大文件 | 将 8,876 行文件拆分为可维护模块 | 8-14 小时 | 🟡 P1 |
| 3. 验证核心链路 | 跑通 URL→生成→执行→报告 | 2-3 小时 | 🔴 P0 |

---

## 任务一：清理空文件 (30 分钟)

### 目标
- 删除 258 个空 Python 文件
- 删除空目录
- 生成清理报告

### 执行步骤

```bash
# 1. 进入项目目录
cd /Users/bettyhuang/PycharmProjects/ai-test-platform

# 2. 预览要删除的文件（不实际删除）
./.venv/bin/python scripts/cleanup-empty-files.py

# 3. 确认无误后，执行删除
./.venv/bin/python scripts/cleanup-empty-files.py --force

# 4. 查看清理报告
ls -la reports/cleanup-report-*.txt
```

### 预期结果
- ✅ 删除约 258 个空文件
- ✅ 删除约 50-100 个空目录
- ✅ 生成清理报告
- ✅ 代码文件减少 60%

### 风险
- ⚠️ 可能误删有意保留的空文件（如 `__init__.py`）
- ✅ 脚本已排除 `.git`, `.venv`, `__pycache__` 等目录

### 回滚
- 无法回滚（已删除），但空文件不影响功能

---

## 任务二：拆分大文件 (8-14 小时)

### 目标
将 `legacy_workbench.py` (8,876 行) 拆分为可维护的模块结构

### 新目录结构

```
apps/web-ui-service/app/routers/legacy_workbench/
├── __init__.py              # 模块导出
├── router.py                # 主路由 (~500 行)
├── models.py                # Pydantic 模型 (~100 行)
├── utils/
│   ├── helpers.py           # 通用工具 (~400 行)
│   ├── review_helpers.py    # Review (~500 行)
│   ├── execution_gate.py    # Execution Gate (~600 行)
│   ├── runtime_manager.py   # 运行时 (~500 行)
│   └── quality_gate.py      # 质量门禁 (~400 行)
├── services/
│   ├── case_generator.py    # 用例生成 (~400 行)
│   ├── test_point_manager.py # 测试点 (~400 行)
│   ├── run_executor.py      # 运行执行 (~300 行)
│   └── report_service.py    # 报告 (~400 行)
└── handlers/
    ├── review_handler.py    # Review 处理 (~300 行)
    ├── execution_gate_handler.py # Gate 处理 (~300 行)
    └── run_handler.py       # 运行处理 (~300 行)
```

### 执行步骤

#### 第 1 步：创建框架 (30 分钟)

```bash
# 1. 运行拆分脚本（创建目录结构和占位文件）
./.venv/bin/python scripts/split-workbench.py

# 2. 查看生成的迁移指南
cat apps/web-ui-service/app/routers/legacy_workbench/MIGRATION_GUIDE.md
```

#### 第 2 步：迁移工具函数 (3-4 小时)

按功能分类迁移 `_` 开头的工具函数：

```bash
# 打开原文件和目标文件，对照迁移
# 建议顺序：
1. utils/helpers.py - 通用函数
2. utils/review_helpers.py - _review_* 函数
3. utils/execution_gate.py - _execution_gate_* 函数
4. utils/runtime_manager.py - _runtime_* 函数
5. utils/quality_gate.py - _quality_gate_* 函数
```

**迁移技巧**：
- 每次迁移 5-10 个函数
- 迁移后运行 `git diff` 确认
- 保持原文件不动，迁移完成后再删除

#### 第 3 步：迁移服务层 (2-3 小时)

```bash
# 迁移业务服务：
1. services/case_generator.py - 用例生成相关
2. services/test_point_manager.py - 测试点管理
3. services/run_executor.py - 运行执行
4. services/report_service.py - 报告生成
```

#### 第 4 步：迁移 Handler 层 (1-2 小时)

```bash
# 迁移路由处理：
1. handlers/review_handler.py
2. handlers/execution_gate_handler.py
3. handlers/run_handler.py
```

#### 第 5 步：更新 router.py (1 小时)

```bash
# 1. 更新 router.py 的导入
# 2. 将 @router 装饰的函数移到对应 handler
# 3. 确保导入路径正确
```

#### 第 6 步：测试验证 (2-3 小时)

```bash
# 1. 检查导入
cd apps/web-ui-service
../../.venv/bin/python -c "from app.routers.legacy_workbench.router import router; print('OK')"

# 2. 启动 Web UI
../../.venv/bin/python -m uvicorn app.main:app --app-dir apps/web-ui-service --port 8013

# 3. 手动测试主要功能
# 4. 运行现有测试
```

### 预期结果
- ✅ 8,876 行拆分为 12-15 个文件，每个 300-600 行
- ✅ 目录结构清晰，职责分离
- ✅ 所有测试仍然通过
- ✅ 可维护性大幅提升

### 风险
- ⚠️ 导入错误（循环导入）
- ⚠️ 功能遗漏
- ✅ 保留原文件，逐步迁移，可随时回滚

### 回滚
```bash
# 如果拆分失败，删除新目录，使用原文件
rm -rf apps/web-ui-service/app/routers/legacy_workbench/
git checkout apps/web-ui-service/app/routers/legacy_workbench.py
```

---

## 任务三：验证核心链路 (2-3 小时)

### 目标
跑通 `URL → 生成 → 执行 → 报告` 完整闭环

### 执行步骤

#### 第 1 步：运行验证脚本 (30 分钟)

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform

# 运行完整验证
./.venv/bin/python scripts/verify-core-chain.py

# 查看报告
cat reports/core-chain-verification-*.md
```

#### 第 2 步：修复问题 (1-2 小时)

根据验证报告修复问题：

| 问题 | 解决方案 |
|------|----------|
| Python 环境缺失 | `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt` |
| Web UI 导入失败 | 检查依赖，修复导入路径 |
| Runner 配置问题 | 检查 pytest.ini 和 conftest.py |
| Agent 缺失 | 确认核心 Agent 文件存在 |

#### 第 3 步：实际测试 (1 小时)

```bash
# 1. 启动 Web UI
cd apps/web-ui-service
../../.venv/bin/python -m uvicorn app.main:app --app-dir apps/web-ui-service --host 127.0.0.1 --port 8013

# 2. 访问 http://127.0.0.1:8013

# 3. 输入一个 URL（比如你的测试系统）

# 4. 生成测试用例

# 5. 执行测试

# 6. 查看报告
```

#### 第 4 步：运行 Smoke 测试 (30 分钟)

```bash
cd runners/web-playwright-python

# 收集测试
../../../.venv/bin/python -m pytest tests/test_yaml_smoke.py --collect-only -v

# 执行测试（需要真实环境）
../../../.venv/bin/python -m pytest tests/test_yaml_smoke.py -v --tb=short
```

### 预期结果
- ✅ Web UI 能正常启动
- ✅ 输入 URL 能生成测试用例
- ✅ 生成的用例能执行
- ✅ 执行结果有报告
- ✅ 失败能分析

### 风险
- ⚠️ 需要真实测试环境（有登录、有业务数据）
- ⚠️ Playwright 可能需要安装浏览器：`playwright install`

---

## 📅 建议执行顺序

### Day 1: 清理 + 验证 (3-4 小时)

```
上午 (1 小时):
  □ 任务一：清理空文件
  □ 查看清理报告

下午 (2-3 小时):
  □ 任务三：验证核心链路
  □ 修复发现的问题
  □ 确保 Web UI 能启动
```

### Day 2-3: 拆分大文件 (8-14 小时)

```
Day 2 上午 (3-4 小时):
  □ 运行拆分脚本，创建框架
  □ 迁移 utils 层工具函数

Day 2 下午 (3-4 小时):
  □ 迁移 services 层
  □ 迁移 handlers 层

Day 3 上午 (2-3 小时):
  □ 更新 router.py
  □ 测试验证
  □ 修复导入问题

Day 3 下午 (缓冲):
  □ 处理遗留问题
  □ 完善文档
  □ 删除原文件
```

---

## 🎯 成功标准

| 任务 | 成功标准 |
|------|----------|
| 清理 | 空文件删除，项目更清爽 |
| 拆分 | 大文件拆分为可维护模块 |
| 验证 | 核心链路能跑通 |

---

## 📞 需要帮助时

如果遇到问题：

1. **查看日志** - 每个脚本都生成详细报告
2. **检查 Git** - 所有改动都可以回滚
3. **逐步执行** - 不要一次性做所有事
4. **优先 P0** - 先做任务一和任务三，任务二可以缓一缓

---

## 🚀 快速开始

```bash
# 1. 进入项目
cd /Users/bettyhuang/PycharmProjects/ai-test-platform

# 2. 先做清理（30 分钟）
./.venv/bin/python scripts/cleanup-empty-files.py

# 3. 验证核心（2 小时）
./.venv/bin/python scripts/verify-core-chain.py

# 4. 如果都通过，再考虑拆分大文件
```

---

**Good Luck!** 🍀
