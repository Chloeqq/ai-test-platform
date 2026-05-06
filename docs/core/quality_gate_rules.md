# 质量门禁规范

这份文档定义平台何时允许进入生成/执行，何时必须阻断。

## 1. 目标

- 防止低质量需求直接进入生成链路
- 防止歧义、缺失字段和覆盖不足被静默放行
- 让 block 的原因可解释、可追踪

## 2. 当前门禁维度

- `test_intents` 数量
- `parse_confidence`
- 高歧义数量
- 覆盖缺口比例
- `design_input`
- `page`

## 3. 阻断条件

- `test_intents` 为空或低于阈值
- `parse_confidence` 低于阈值
- 存在高歧义且策略要求阻断
- `coverage_gap_ratio` 超阈值
- `design_input` 为空
- `page` 为空

## 4. 输出建议

- `decision`: `allow` / `block`
- `blockers`: 具体阻断项
- `metrics`: 相关数值
- `explanation`: 人类可读解释

## 5. 与 Dify 的关系

- Dify 节点 1 不应绕开门禁
- 如果检索结果不足，应输出 `block`
- 不允许靠 LLM 自己“补齐缺失信息”来冒充通过

