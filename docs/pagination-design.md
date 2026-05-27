# 📄 分页功能设计方案

**创建时间**: 2026-03-22  
**版本**: v1.0  
**状态**: 设计完成，待实现

---

## 📊 目录

1. [需求分析](#需求分析)
2. [设计方案](#设计方案)
3. [后端实现](#后端实现)
4. [前端实现](#前端实现)
5. [使用示例](#使用示例)
6. [性能优化](#性能优化)
7. [验收标准](#验收标准)

---

## 需求分析

### 当前问题

| 问题 | 影响 | 严重度 |
|------|------|--------|
| 无分页，一次性加载所有数据 | 1000+ 条数据响应 >3 秒 | 🔴 高 |
| 前端渲染卡顿 | DOM 节点过多 | 🔴 高 |
| 浪费带宽 | 用户只看前 20 条 | 🟡 中 |
| 无法定位历史数据 | 找不到旧数据 | 🟡 中 |

### 功能需求

- ✅ 支持页码分页（page/page_size）
- ✅ 支持总数统计
- ✅ 支持排序（多字段）
- ✅ 支持筛选条件保持
- ✅ 支持快速跳转
- ✅ 响应式布局

### 性能目标

- 单页加载 <500ms
- 支持 10 万 + 数据量
- 内存占用 <100MB

---

## 设计方案

### 方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **页码分页** | 直观、易实现、可跳转 | 深度分页性能差 | 传统列表、管理后台 |
| **游标分页** | 性能好、适合无限滚动 | 无法跳转、实现复杂 | Feed 流、聊天记录 |
| **混合方案** | 兼顾两者优点 | 实现最复杂 | 大型系统 |

### 选择：**页码分页**（优先实现）

**理由**：
1. 符合管理后台使用习惯
2. 实现简单，维护成本低
3. 用户可快速定位到指定页

---

## 后端实现

### 1. 核心文件

| 文件 | 用途 | 行数 |
|------|------|------|
| `app/core/pagination.py` | 通用分页工具类 | 200 行 |
| `app/routers/test_cases_paginated.py` | 测试用例分页接口 | 180 行 |

### 2. API 设计

#### 请求参数

```http
GET /api/test-cases?page=1&page_size=20&sort=updated_at&order=desc&q=登录&priority=P1
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page` | int | 1 | 页码（1-indexed） |
| `page_size` | int | 20 | 每页数量（1-100） |
| `sort` | string | updated_at | 排序字段 |
| `order` | string | desc | 排序方向（asc/desc） |
| `q` | string | "" | 搜索关键词 |
| `tag` | string | "" | 标签筛选 |
| `priority` | string | "" | 优先级筛选 |
| `creator` | string | "" | 创建者筛选 |

#### 响应结构

```json
{
  "items": [
    {
      "id": 1,
      "name": "商品搜索测试",
      "module": "商品中心",
      "priority": "P1",
      "tags": ["smoke", "web"],
      "creator": "alice",
      "last_execution_result": "passed",
      "updated_at": "2026-03-22T12:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_items": 156,
    "total_pages": 8,
    "has_prev": false,
    "has_next": true,
    "prev_page": null,
    "next_page": 2
  },
  "filters": {
    "tags": ["smoke", "regression", "web"],
    "priorities": ["P0", "P1", "P2"],
    "creators": ["alice", "bob"],
    "last_results": ["passed", "failed", "skipped"]
  },
  "sort": {
    "field": "updated_at",
    "order": "desc"
  }
}
```

### 3. 核心代码

#### 通用分页工具

```python
# app/core/pagination.py
from dataclasses import dataclass
from sqlalchemy import func, Select

@dataclass
class PageMeta:
    """分页元数据"""
    page: int
    page_size: int
    total_items: int
    total_pages: int
    
    @property
    def has_prev(self) -> bool:
        return self.page > 1
    
    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages
    
    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

def paginate(
    query: Select,
    db_session,
    page: int = 1,
    page_size: int = 20,
    max_page_size: int = 100,
) -> Page:
    """对 SQLAlchemy 查询进行分页"""
    page = max(1, page)
    page_size = min(max(1, page_size), max_page_size)
    
    # 获取总数
    total_query = select(func.count()).select_from(query.subquery())
    total_items = db_session.execute(total_query).scalar_one() or 0
    
    # 计算总页数
    total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 1
    
    # 创建分页元数据
    meta = PageMeta(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )
    
    # 应用分页
    paginated_query = query.offset(meta.offset).limit(page_size)
    items = db_session.execute(paginated_query).scalars().all()
    
    return Page(items=items, meta=meta)
```

---

## 前端实现

### 1. 核心文件

| 文件 | 用途 | 行数 |
|------|------|------|
| `pagination.component.js` | 分页组件类 | 250 行 |
| `pagination.component.css` | 分页样式 | 150 行 |

### 2. 组件使用

```html
<!-- HTML 结构 -->
<div id="pagination-container"></div>

<script src="/static/pagination.component.js"></script>
<link rel="stylesheet" href="/static/pagination.component.css">

<script>
  // 初始化分页
  const pagination = new Pagination('#pagination-container', {
    page: 1,
    page_size: 20,
    total_items: 156,
    onChange: (page, page_size) => {
      console.log('页码变化:', page, page_size);
      loadData(page, page_size);
    }
  });
  
  // 更新分页状态
  function updatePagination(data) {
    pagination.update({
      page: data.pagination.page,
      page_size: data.pagination.page_size,
      total_items: data.pagination.total_items
    });
  }
  
  // 加载数据
  async function loadData(page, page_size) {
    const response = await fetch(`/api/test-cases?page=${page}&page_size=${page_size}`);
    const data = await response.json();
    renderTable(data.items);
    updatePagination(data);
  }
</script>
```

### 3. 组件功能

| 功能 | 说明 |
|------|------|
| 页码显示 | 显示当前页和总页数 |
| 上一页/下一页 | 翻页导航 |
| 首页/末页 | 快速跳转 |
| 每页数量选择 | 10/20/50/100 可选 |
| 快速跳转 | 输入页码直接跳转 |
| 总记录数 | 显示共 X 条记录 |
| 响应式 | 移动端自适应 |

---

## 使用示例

### 示例 1：测试用例列表

```python
# 后端
@router.get("")
def list_test_cases(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort: str = Query(default="updated_at"),
    order: str = Query(default="desc"),
    db = Depends(get_db),
) -> dict:
    stmt = select(TestCase).order_by(...)
    page_obj = paginate(stmt, db, page, page_size)
    return page_obj.to_dict()
```

```javascript
// 前端
const pagination = new Pagination('#pagination', {
  page: 1,
  page_size: 20,
  total_items: 156,
  onChange: (page, page_size) => {
    loadCases(page, page_size);
  }
});

async function loadCases(page, page_size) {
  const params = new URLSearchParams({ page, page_size });
  const response = await fetch(`/api/test-cases?${params}`);
  const data = await response.json();
  renderCases(data.items);
  pagination.update(data.pagination);
}
```

### 示例 2：执行记录列表

```python
# 后端（类似）
@router.get("/executions")
def list_executions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db = Depends(get_db),
) -> dict:
    stmt = select(TestCaseExecution).order_by(...)
    page_obj = paginate(stmt, db, page, page_size)
    return page_obj.to_dict()
```

---

## 性能优化

### 1. 数据库优化

#### 添加索引

```sql
-- 常用查询字段添加索引
CREATE INDEX idx_test_case_updated_at ON test_case(updated_at DESC);
CREATE INDEX idx_test_case_priority ON test_case(priority);
CREATE INDEX idx_test_case_module ON test_case(module);
CREATE INDEX idx_test_case_creator ON test_case(creator);

-- 组合索引（针对常用查询组合）
CREATE INDEX idx_test_case_module_priority ON test_case(module, priority);
```

#### 避免深度分页

```python
# ❌ 性能差（OFFSET 很大）
SELECT * FROM test_case OFFSET 10000 LIMIT 20;

# ✅ 性能好（使用游标）
SELECT * FROM test_case 
WHERE updated_at < '2026-03-22' 
ORDER BY updated_at DESC 
LIMIT 20;
```

### 2. 缓存优化

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_cached_page(cache_key: str, page: int, page_size: int):
    """缓存分页结果"""
    # ... 查询逻辑
    return result

# 使用
cache_key = f"test_cases:{filters_hash}"
result = get_cached_page(cache_key, page, page_size)
```

### 3. 前端优化

```javascript
// 防抖处理（避免频繁请求）
function debounce(fn, delay) {
  let timer = null;
  return function(...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

const loadCasesDebounced = debounce(loadCases, 300);

// 预加载下一页
function preloadNextPage() {
  if (pagination.options.has_next) {
    fetch(`/api/test-cases?page=${pagination.options.page + 1}`)
      .then(res => res.json())
      .then(data => {
        // 缓存到内存
        window.pageCache[pagination.options.page + 1] = data;
      });
  }
}
```

---

## 验收标准

### 功能验收

```
□ 页码分页正常工作
□ 上一页/下一页按钮正确禁用
□ 总页数计算正确
□ 每页数量切换正常
□ 快速跳转功能正常
□ 筛选条件保持
□ 排序功能正常
□ 响应式布局正常
```

### 性能验收

```
□ 1000 条数据，首屏加载 <500ms
□ 10000 条数据，首屏加载 <1s
□ 切换页面无明显卡顿
□ 内存占用 <100MB
□ 网络请求次数合理
```

### 兼容性验收

```
□ Chrome 最新版
□ Firefox 最新版
□ Safari 最新版
□ Edge 最新版
□ 移动端浏览器
```

---

## 实施计划

### 第 1 天：后端实现

```
□ 创建 pagination.py 工具类
□ 修改 test_cases 接口（增加分页）
□ 添加单元测试
□ 性能测试（1000/10000 条数据）
```

### 第 2 天：前端实现

```
□ 创建 pagination.component.js
□ 创建 pagination.component.css
□ 集成到测试用例列表页
□ 功能测试
```

### 第 3 天：优化与测试

```
□ 数据库索引优化
□ 前端性能优化
□ 响应式测试
□ 浏览器兼容性测试
□ Bug 修复
```

---

## 扩展方向

### 1. 游标分页（后续）

```python
# 适合无限滚动场景
@router.get("/feed")
def get_feed(
    cursor: str = Query(default=None),
    limit: int = Query(default=20),
    db = Depends(get_db),
):
    page = paginate_cursor(query, db, cursor, limit)
    return {
        "items": page.items,
        "next_cursor": page.next_cursor,
        "has_next": page.has_next
    }
```

### 2. 批量操作

```python
@router.post("/batch")
def batch_operations(
    payload: BatchPayload,
    page_ids: list[int] = Query(default=[]),  # 对指定页操作
    db = Depends(get_db),
):
    # 支持对当前页或指定页批量操作
    pass
```

### 3. 导出功能

```python
@router.get("/export")
def export_cases(
    page: int = Query(default=1),
    page_size: int = Query(default=100),
    format: str = Query(default="csv"),
    db = Depends(get_db),
):
    # 导出指定页或全部数据
    pass
```

---

## 参考资料

- [SQLAlchemy Pagination](https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html#limit-offset)
- [FastAPI Query Parameters](https://fastapi.tiangolo.com/tutorial/query-params/)
- [Web Accessibility: Pagination](https://www.w3.org/WAI/ARIA/apg/patterns/)

---

**文档版本**: v1.0  
**最后更新**: 2026-03-22  
**维护者**: AI Test Platform Team
