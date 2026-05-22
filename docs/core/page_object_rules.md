# 页面对象规范

这份文档定义页面对象、元素代码和别名的统一规则。

相关方案：

- [页面对象 data-testid 清单导入维护实现方案](./page_object_data_testid_import_plan.md)

## 1. 基本原则

- 页面对象必须存在于平台资产中
- 元素必须有稳定 `element_code`
- 别名只用于解析，不用于代替正式命名
- 页面对象缺失时，不允许通过猜测继续生成步骤

## 2. 推荐字段

- `page`
- `elements`
- `selector`
- `type`
- `role`
- `name`
- `aliases`

## 3. 元素命名规则

- `element_code` 必须稳定且可复用
- 同一个元素不要在不同地方使用多个正式编码
- `name` 可以是中文展示名
- `aliases` 只收录实际会出现的别名

## 4. 解析规则

- `selector`、`element_name`、`aliases` 都可以参与解析
- 解析结果必须命中唯一的 `element_code`
- 不能命中时，必须返回未知元素
- 不能把模糊相似度当成正式映射

## 5. 与编译链路的关系

- `shared_backend/element_binding.py` 负责 alias 到 code 的映射
- `shared_backend/execution_compiler.py` 负责把 code 绑定为 selector
- 只有明确绑定成功，步骤才可以执行
