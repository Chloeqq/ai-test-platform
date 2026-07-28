# EvieAi Code Quality Gate

状态：Active

## 1. 目标

该门禁将 `AGENTS.md` 和 `coding-standards.md` 的代码要求转换为可重复执行的本地与 CI 检查，并实行：

```text
zero new violations
```

历史违规逐项登记，不会因为总量存在而阻塞；新增违规必须失败。历史违规被修复后，必须同步收缩基线，禁止重新引入。

门禁执行失败与代码违规使用不同退出语义：

- 发现新增或未收口违规：退出码 `1`；
- Git、baseline、Ruff、format、Mypy 或解析过程异常：退出码 `2`。

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

`--staged` 会通过 `git checkout-index` 建立临时只读快照。Ruff、format、
Mypy 和 AST 均检查 index blob，不读取对应工作树内容，也不修改工作树或
Git index。

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

Changed-files 使用 Git NUL 分隔记录，显式处理新增、修改、删除、重命名、
复制、空格和 Unicode 路径。

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

常规 CI 从 PR merge-base 读取受信 baseline，不信任 PR 当前版本的
baseline。同一 PR 对 baseline 的新增、删除、替换、统计或元数据修改均会
fail-closed，并输出新增豁免、删除豁免或序列化变化。

首次引入 baseline 时，merge-base 中尚不存在该文件。该 bootstrap 只在以下
条件全部满足时通过：

- `source_commit` 等于实际 merge-base；
- 门禁从 merge-base 建立独立快照；
- 在快照上重新执行 Ruff、format、Mypy 和 AST；
- 重新扫描结果与提交的 baseline 完全一致。

以下命令只用于生成本地候选 baseline：

```bash
PYTHON_BIN=.venv/bin/python \
  .venv/bin/python scripts/ci/evie_ai_quality_gate.py \
  --base-ref origin/dev \
  --write-baseline
```

基线写入器会拒绝任何新增违规；正常 PR 门禁仍会拒绝候选 baseline 的任何
变化。后续确需收缩历史基线时，必须使用单独批准的 baseline 治理流程，不得
与业务变更混合。

不得通过手工编辑 baseline、全局 `noqa`、宽泛 ignore、排除新文件或降低
规则强度绕过门禁。

## 6. 工具失败边界

工具进程缺失、无法启动、异常退出、返回空诊断、输出格式畸形或诊断无法
完整解析时，门禁必须失败。退出码 `1` 只有在成功解析出至少一条违规时才被
视为“发现违规”，不得解释为工具成功。

## 7. GitHub Required Check

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
