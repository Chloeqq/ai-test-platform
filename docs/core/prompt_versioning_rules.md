# Prompt 版本规范

这份文档定义 Dify 节点 prompt 和平台规则如何版本化。

## 1. 目标

- 让每个节点 prompt 可追踪
- 让规则变更能回溯到具体版本
- 避免 Dify、后端、文档三边各自漂移

## 2. 推荐版本字段

- `version`
- `prompt_version`
- `schema_version`
- `rule_version`
- `knowledge_version`

## 3. 版本约束

- 结构化输出必须带 `version`
- Schema 变更时要升级版本号
- Prompt 变更但输出结构不变时，也建议升级 `prompt_version`
- 同一工作流各节点最好共享一份主版本号

## 4. 变更原则

- 先改文档，再改 prompt，再改代码
- 先补测试，再发布新版本
- 不兼容变更必须保留旧版本一段时间

## 5. Dify 建议

- 每个节点 prompt 顶部写明版本号
- 输出 JSON 里带上 `schema_version`
- 运行结果里记录 `prompt_version`

