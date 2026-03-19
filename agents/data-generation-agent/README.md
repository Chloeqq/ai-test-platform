# Data Generation Agent

当前状态：`最小可运行（deterministic minimal）`

这不是企业级终态实现，而是把原先的空壳入口补成了一个可运行的、规则优先的数据生成最小版本。

当前能力：

- 确定性字段生成
- 基础边界值生成
- 内置模板库
- 关联记录引用
- 输出前校验
  - 长度/数值范围
  - 邮箱格式
  - 枚举值合法性
  - 正则 pattern 校验
  - 关系源存在性
- 清理指令输出
- registry 落盘
- cleanup 状态标记

当前明确不做：

- LLM 自由生成业务数据
- 生产数据复制
- 复杂脱敏编排
- 企业级 registry / cleanup manager 全量能力

## 输入

输入 JSON 参考：

```json
{
  "request_id": "req-product-001",
  "project": "default",
  "environment": "test",
  "requirements": [
    {
      "requirement_id": "user_seed",
      "data_type": "user",
      "quantity": 2,
      "fields": [
        {"name": "username", "type": "string", "prefix": "user", "unique": true},
        {"name": "email", "type": "email", "prefix": "buyer", "unique": true},
        {"name": "age", "type": "integer", "min_value": 18, "max_value": 60}
      ]
    }
  ]
}
```

也支持模板驱动：

```json
{
  "request_id": "req-template-001",
  "requirements": [
    {
      "requirement_id": "product_seed",
      "data_type": "product",
      "template_key": "product_basic",
      "quantity": 2,
      "fields": [
        {"name": "status", "type": "enum", "options": ["published"]}
      ]
    }
  ]
}
```

当前内置模板：

- `user_basic`
- `product_basic`
- `order_basic`

## 运行

```bash
python agents/data-generation-agent/src/index.py --input agents/data-generation-agent/examples/input.json
```

指定 registry 路径：

```bash
python agents/data-generation-agent/src/index.py \
  --input agents/data-generation-agent/examples/input.json \
  --registry-path /tmp/data-generation-registry.json
```

标记已清理：

```bash
python agents/data-generation-agent/src/index.py \
  --registry-path /tmp/data-generation-registry.json \
  --mark-cleaned req-product-001
```

查看 registry 治理摘要：

```bash
python agents/data-generation-agent/src/index.py \
  --registry-path /tmp/data-generation-registry.json \
  --registry-summary
```

查看待清理条目：

```bash
python agents/data-generation-agent/src/index.py \
  --registry-path /tmp/data-generation-registry.json \
  --pending-cleanups
```

查看 cleanup 保留期 / 归档候选摘要：

```bash
python agents/data-generation-agent/src/index.py \
  --registry-path /tmp/data-generation-registry.json \
  --cleanup-retention-summary
```

当前默认治理口径：

- `pending` 超过 `7` 天视为超期待清理
- `cleaned` 超过 `30` 天视为可归档候选
- `cleaned` 的年龄优先使用 `cleaned_at`，缺失时回退到 `created_at`

查看模板治理摘要：

```bash
python agents/data-generation-agent/src/index.py \
  --template-summary
```

查看模板版本迁移摘要：

```bash
python agents/data-generation-agent/src/index.py \
  --template-migration-summary
```

当前迁移摘要只做只读治理判断：

- 按 `data_type` 比较模板版本
- 同一 `data_type` 内按语义版本最高值识别推荐模板
- 标记旧版本模板的迁移候选
- 标记默认模板是否落后于当前推荐版本
- 标记无效版本号，避免治理口径漂移

## 输出

输出包括：

- `generated`
- `validations`
- `cleanup_instructions`
- `registry_entry`
- `generation_confidence`

## 下一步

下一阶段只建议继续做这几项：

1. cleanup / registry / template 规则继续丰富
2. 再考虑 AI 建议层
