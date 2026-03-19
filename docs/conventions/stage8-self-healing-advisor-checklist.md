# Stage 8 Self-Healing Advisor Checklist

本文档用于固化阶段8的完成状态，明确当前已经实现的能力边界。

阶段目标：

1. 新增 `self-healing-advisor-agent`
2. 基于 AI 分析生成结构化修复建议 `suggestion.json`
3. 接入 pytest 失败流程
4. 在 Allure 展示修复建议
5. 增加安全校验
6. 不允许自动修改 YAML 文件

---

## 1. 新增 `self-healing-advisor-agent`

当前状态：已完成

已存在目录：

- [agents/self-healing-advisor-agent](/Users/bettyhuang/PycharmProjects/ai-test-platform/agents/self-healing-advisor-agent)

当前实现包括：

- 只读建议脚本：
  - [prompt.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/agents/self-healing-advisor-agent/prompt.py)
  - [suggest.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/agents/self-healing-advisor-agent/suggest.py)
- 现有 `src/` 版 agent：
  - [agent.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/agents/self-healing-advisor-agent/src/agent.py)

---

## 2. 基于 AI 分析生成结构化修复建议 `suggestion.json`

当前状态：已完成

Runner 在 pytest 失败后会生成：

- `artifacts/<case>/suggestion.json`

相关实现：

- [conftest.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/conftest.py)

当前输入来源：

- `failure_reason`
- `failure_analysis`
- 当前页面名
- 现有 `page-object` target 列表

---

## 3. 接入 pytest 失败流程

当前状态：已完成

当前失败产物链路：

- `failed.png`
- `page.html`
- `meta.txt`
- `analysis.txt`
- `suggestion.json`

当前执行顺序：

1. pytest 失败
2. 保存截图和 HTML
3. 保存 `meta.txt`
4. 调用 `failure-analysis-agent`
5. 生成 `analysis.txt`
6. 调用 `self-healing-advisor`
7. 生成 `suggestion.json`

对应实现：

- [conftest.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/conftest.py)

---

## 4. 在 Allure 展示修复建议

当前状态：已完成

当前 Allure 中已附加：

- `self-healing-suggestion`
  - 文件附件，来自 `suggestion.json`
- `self-healing-advice`
  - 文本附件，来自 `suggestion.json` 内容

对应实现：

- [conftest.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/conftest.py)

---

## 5. 安全校验

当前状态：已完成

当前已实现的安全规则：

- `target` 只能来自 `available_targets`
- 如果 `target` 不存在，自动清空
- `fix_candidates` 只能来自 `available_targets`
- 如果 `confidence < 0.5`
  - 输出被压成 `no_change`
  - 不输出实际建议

对应实现：

- [suggest.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/agents/self-healing-advisor-agent/suggest.py)

对应测试：

- [test_suggest.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/agents/self-healing-advisor-agent/test_suggest.py)

---

## 6. 不允许自动修改 YAML 文件

当前状态：已完成

当前边界：

- 不自动修改 YAML
- 不自动修改 page-object
- 不自动回写测试资产
- 只输出建议

明确约束位置：

- [prompt.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/agents/self-healing-advisor-agent/prompt.py)
- [suggest.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/agents/self-healing-advisor-agent/suggest.py)

当前 runner / orchestrator 侧只做：

- 落 `suggestion.json`
- 报告返回建议路径与预览
- 控制台展示建议内容

---

## 当前结论

阶段8当前状态：`已完成`

当前系统已经具备：

- Self-Healing Advisor 模块
- pytest 失败后自动生成 `suggestion.json`
- Allure 展示修复建议
- 安全校验
- 严格的只读建议边界

但当前仍然明确不做：

- 自动修改 YAML
- 自动修改 page-object
- 自动应用修复建议
