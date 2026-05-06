# 📘 代码说明书
## 一句话概括
这段代码用于检查项目中的模块依赖关系，确保没有循环依赖，并且遵守预定义的依赖规则。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| dependency_graph_policy.py | 检查并验证项目中模块间的依赖关系是否符合规定 |

## 🔍 核心函数/类说明
- **`def load_architecture_registry(path: Path = ARCHITECTURE_REGISTRY_PATH) -> dict[str, Any]`**：从指定路径加载架构注册表文件（默认为同目录下的`architecture_registry.yaml`），返回其内容作为字典。
  - 输入：文件路径，默认为当前脚本所在位置的一个特定yaml文件
  - 输出：一个字典，包含从yaml文件读取的数据
  - 大白话解释：就像打开一本书查看里面的内容一样，这个函数负责打开一个配置文件并把里面的信息转换成程序可以理解的形式。
- **`def _detect_cycles(graph: dict[str, set[str]]) -> list[list[str]]`**：检测给定图结构中是否存在环路（循环依赖）。
  - 输入：表示依赖关系的图，键是模块名，值是一个集合，包含了该模块直接依赖的所有其他模块
  - 输出：如果存在环，则返回所有找到的环列表；如果没有环，则返回空列表
  - 大白话解释：想象一下你有一张地图，上面标出了各个城市之间的道路连接情况。这个函数就是用来找出这张地图上是否有任何一条路线会让人绕圈子回到起点。
- **`def validate_dependency_graph(modules: dict[str, list[str]], *, forbidden_edges: set[tuple[str, str]] | None = None) -> None`**：根据提供的模块及其依赖列表以及禁止的依赖边来验证整个依赖图的有效性。
  - 输入：一个字典，键为模块名称，值为其依赖项列表；可选参数`forbidden_edges`指定了不允许存在的依赖关系
  - 输出：无直接输出，但会在发现违反规则时抛出异常
  - 大白话解释：这就像在玩拼图游戏之前先检查所有的拼图块是否都符合条件，比如颜色、形状等。如果发现有不符合条件的拼图块，就停止游戏并报告问题。

## 🧩 调用关系与数据流转
1. `validate_dependency_graph()` 是主入口点，它首先调用自身逻辑处理输入数据。
2. 在内部，`validate_dependency_graph()` 使用 `_detect_cycles()` 来查找可能存在的循环依赖。
3. 如果需要，`load_architecture_registry()` 可以被外部调用来获取架构注册信息，但这不是强制性的步骤。

简单来说，流程如下：
```
[外部调用] -> validate_dependency_graph() -> [可能调用] _detect_cycles()
```

## 💡 值得学习的写法
- 使用了`dataclass`来简化创建不可变对象的过程。
- `_detect_cycles` 函数使用递归和栈来高效地检测图中的环，这种方法既直观又有效。

## ⚠️ 需要注意的地方
- 当尝试读取或解析`architecture_registry.yaml`失败时，`load_architecture_registry`将返回一个空字典而不是抛出错误。这可能会掩盖潜在的问题。
- `validate_dependency_graph`函数假设所有传入的模块名称都是有效的，并且不会对这些名称进行额外验证。因此，在调用此函数前应确保输入数据的质量。