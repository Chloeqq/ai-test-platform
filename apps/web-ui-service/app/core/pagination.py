"""
分页工具模块

支持两种分页模式：
1. 页码分页（Offset-based）- 适合传统分页 UI
2. 游标分页（Cursor-based）- 适合无限滚动
"""

from dataclasses import dataclass, field
from typing import Any, Generic, Optional, TypeVar, cast

from sqlalchemy import Select, func, select

T = TypeVar("T")


@dataclass
class PageMeta:
    """分页元数据"""

    page: int  # 当前页码（1-indexed）
    page_size: int  # 每页数量
    total_items: int  # 总记录数
    total_pages: int  # 总页数

    @property
    def has_prev(self) -> bool:
        """是否有上一页"""
        return self.page > 1

    @property
    def has_next(self) -> bool:
        """是否有下一页"""
        return self.page < self.total_pages

    @property
    def prev_page(self) -> Optional[int]:
        """上一页码"""
        return self.page - 1 if self.has_prev else None

    @property
    def next_page(self) -> Optional[int]:
        """下一页码"""
        return self.page + 1 if self.has_next else None

    @property
    def offset(self) -> int:
        """SQL OFFSET 值"""
        return (self.page - 1) * self.page_size

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "page": self.page,
            "page_size": self.page_size,
            "total_items": self.total_items,
            "total_pages": self.total_pages,
            "has_prev": self.has_prev,
            "has_next": self.has_next,
            "prev_page": self.prev_page,
            "next_page": self.next_page,
        }


@dataclass
class Page(Generic[T]):
    """分页结果"""

    items: list[T]  # 当前页数据
    meta: PageMeta  # 分页元数据
    filters: dict = field(default_factory=dict)  # 筛选条件
    sort: dict = field(default_factory=dict)  # 排序信息

    def to_dict(self) -> dict:
        """转换为字典（用于 API 响应）"""
        return {
            "items": self.items,
            "pagination": self.meta.to_dict(),
            "filters": self.filters,
            "sort": self.sort,
        }


@dataclass
class CursorPage(Generic[T]):
    """游标分页结果（用于无限滚动）"""

    items: list[T]  # 当前页数据
    next_cursor: Optional[str] = None  # 下一页游标
    has_next: bool = False  # 是否有下一页
    total_count: Optional[int] = None  # 总数（可选，性能考虑）


def paginate(
    query: Select,
    db_session,
    page: int = 1,
    page_size: int = 20,
    max_page_size: int = 100,
) -> Page:
    """
    对 SQLAlchemy 查询进行分页

    Args:
        query: SQLAlchemy Select 查询对象
        db_session: 数据库会话
        page: 页码（1-indexed）
        page_size: 每页数量
        max_page_size: 最大每页数量（防止滥用）

    Returns:
        Page 对象

    Example:
        >>> stmt = select(TestCase).order_by(TestCase.created_at.desc())
        >>> page = paginate(stmt, db, page=1, page_size=20)
        >>> response = page.to_dict()
    """
    # 参数验证
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

    return Page(
        items=[item for item in items],
        meta=meta,
    )


def create_cursor(
    item,
    sort_field: str = "id",
    sort_order: str = "desc",
) -> str:
    """
    创建游标值（Base64 编码）

    Args:
        item: 数据项
        sort_field: 排序字段
        sort_order: 排序方向（asc/desc）

    Returns:
        Base64 编码的游标字符串
    """
    import base64
    import json

    value = getattr(item, sort_field, None)
    isoformat_fn = getattr(value, "isoformat", None)
    serialized_value = isoformat_fn() if callable(isoformat_fn) else str(value)
    cursor_data = {
        "value": serialized_value,
        "field": sort_field,
        "order": sort_order,
    }
    cursor_json = json.dumps(cursor_data)
    return base64.b64encode(cursor_json.encode()).decode()


def decode_cursor(cursor: str) -> dict:
    """
    解码游标

    Args:
        cursor: Base64 编码的游标字符串

    Returns:
        解码后的字典
    """
    import base64
    import json

    try:
        cursor_json = base64.b64decode(cursor.encode()).decode()
        return json.loads(cursor_json)
    except Exception:
        return {"value": None, "field": "id", "order": "desc"}


def paginate_cursor(
    query: Select,
    db_session,
    cursor: Optional[str] = None,
    limit: int = 20,
    sort_field: str = "id",
    sort_order: str = "desc",
) -> CursorPage:
    """
    游标分页（适合无限滚动）

    Args:
        query: SQLAlchemy Select 查询对象
        db_session: 数据库会话
        cursor: 上一页返回的游标
        limit: 每页数量
        sort_field: 排序字段
        sort_order: 排序方向

    Returns:
        CursorPage 对象
    """
    limit = min(max(1, limit), 100)

    # 解码游标
    cursor_data = decode_cursor(cursor) if cursor else {"value": None}
    cursor_value = cursor_data.get("value")

    entity = cast(Any, query.column_descriptions[0].get("entity"))
    sort_column = getattr(entity, sort_field)

    # 应用游标条件
    if cursor_value:
        if sort_order == "desc":
            query = query.where(sort_column < cursor_value)
        else:
            query = query.where(sort_column > cursor_value)

    # 获取数据（多取 1 条用于判断是否有下一页）
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    query = query.limit(limit + 1)
    items = list(db_session.execute(query).scalars().all())

    # 判断是否有下一页
    has_next = len(items) > limit
    if has_next:
        items = items[:-1]  # 移除多余的那条

    # 生成下一页游标
    next_cursor = None
    if has_next and items:
        next_cursor = create_cursor(items[-1], sort_field, sort_order)

    return CursorPage(
        items=items,
        next_cursor=next_cursor,
        has_next=has_next,
    )
