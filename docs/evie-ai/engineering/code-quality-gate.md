# EvieAi Code Quality Gate

状态：Active

## 1. 目标

该门禁将 `AGENTS.md` 和 `coding-standards.md` 的代码要求转换为可重复执行的本地与 CI 检查，并实行：

```text
zero new violations
```

历史违规逐项登记，不会因为总量存在而阻塞；新增违规必须失败。历史违规被修复后，必须同步收缩基线，禁止重新引入。

## 2. 统一命令

本地完整检查：

```bash
make evie-ai-quality-gate
```

指定比较基线：

```bash
BASE_REF=origin/dev make evie-ai-quality-gate
```

Pre-commit 使用暂存区模式：

```bash
scripts/qa/run-evie-ai-quality-gate.sh --staged
```

## 3. 门禁范围

门禁包含：

- Changed-files Ruff；
- Ruff format；
- EvieAi 生产模块 Mypy；
- Service 禁止直接调用 `datetime.now()` 或 `utcnow()`；
- 函数长度、McCabe 复杂度、参数数量和嵌套层级；
- 状态和角色 magic string；
- 错误码 magic string；
- 核心签名和值对象中的 `Any`；
- EvieAi 分层和冻结链路依赖；
- 现有 EvieAi 架构测试；
- `git diff --check`；
- 逐项 zero-new baseline 比较。

失败输出统一为：

```text
path:line: RULE: message | fix: repair direction
```

## 4. 阈值

| 规则 | 阈值 |
|---|---:|
| 一般函数长度 | 40 行 |
| McCabe 复杂度 | 10 |
| 独立业务参数 | 5 |
| 控制流嵌套 | 3 层 |

阈值定义在 `scripts/ci/evie_ai_quality/ast_rules.py`，基线同时记录阈值快照。

## 5. 基线治理

权威基线：

```text
scripts/ci/evie_ai_quality_baseline.json
```

只有在历史违规减少时才允许更新：

```bash
PYTHON_BIN=.venv/bin/python \
  .venv/bin/python scripts/ci/evie_ai_quality_gate.py \
  --base-ref origin/dev \
  --write-baseline
```

基线写入器会拒绝任何新增违规。不得通过全局 `noqa`、宽泛 ignore、排除新文件或降低规则强度更新基线。

## 6. GitHub Required Check

独立 workflow 产生以下 check：

```text
evie-ai-code-quality
```

仓库管理员需要在 `dev` 的 Branch Protection 或 Ruleset 中：

1. 启用 Require status checks to pass；
2. 添加 `evie-ai-code-quality`；
3. 禁止在该 check 失败时合并；
4. 不将 CI-B01、CI-B02 作为该独立门禁的豁免。

GitHub 仓库设置不由代码 PR 自动修改。
