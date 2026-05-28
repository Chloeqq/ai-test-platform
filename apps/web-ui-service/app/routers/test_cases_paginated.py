"""
测试用例管理 - 分页版本

对比原版 test_cases.py 的改进：
1. 增加分页支持
2. 增加排序支持
3. 优化性能（只查询需要的字段）
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.core.database import get_db
from app.core.pagination import Page, paginate
from app.models.test_case import TestCase
from app.repositories.test_case_repository import TestCaseRepository
router = APIRouter(prefix="/api/test-cases", tags=["test-cases"])


def _to_list_item(case: TestCase) -> dict[str, Any]:
    """转换为列表项 DTO"""
    return {
        "id": case.id,
        "name": case.name,
        "product_line": case.product_line,
        "module": case.module,
        "priority": case.priority,
        "tags": list(case.tags or []),
        "creator": case.creator,
        "last_execution_result": case.last_execution_result,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
    }


@router.get("")
def list_test_cases(
    # 分页参数
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    
    # 排序参数
    sort: str = Query(default="updated_at", description="排序字段"),
    order: str = Query(default="desc", regex="^(asc|desc)$", description="排序方向"),
    
    # 筛选参数
    q: str = Query(default="", description="搜索关键词"),
    tag: str = Query(default="", description="标签筛选"),
    priority: str = Query(default="", description="优先级"),
    creator: str = Query(default="", description="创建者"),
    last_result: str = Query(default="", description="最后执行结果"),
    product_line: str = Query(default="", description="产品线"),
    module: str = Query(default="", description="模块"),
    
    db = Depends(get_db),
) -> dict[str, Any]:
    """
    获取测试用例列表（分页版）
    
    **分页说明**：
    - page: 页码，从 1 开始
    - page_size: 每页数量，最大 100
    
    **排序说明**：
    - sort: 排序字段（id, name, priority, updated_at, created_at）
    - order: 排序方向（asc, desc）
    
    **筛选说明**：
    - q: 模糊搜索（名称、模块）
    - tag: 精确匹配标签
    - 其他：精确匹配
    """
    # 构建基础查询
    stmt = select(TestCase)
    
    # 应用筛选
    if q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            (TestCase.name.like(term)) | 
            (TestCase.module.like(term))
        )
    
    if priority.strip():
        stmt = stmt.where(TestCase.priority == priority.strip())
    
    if creator.strip():
        stmt = stmt.where(TestCase.creator == creator.strip())
    
    if last_result.strip():
        stmt = stmt.where(TestCase.last_execution_result == last_result.strip())
    
    if product_line.strip():
        stmt = stmt.where(TestCase.product_line == product_line.strip())
    
    if module.strip():
        stmt = stmt.where(TestCase.module == module.strip())
    
    # 应用排序
    sort_column = getattr(TestCase, sort, TestCase.updated_at)
    if order == "desc":
        stmt = stmt.order_by(sort_column.desc(), TestCase.id.desc())
    else:
        stmt = stmt.order_by(sort_column.asc(), TestCase.id.asc())
    
    # 执行分页查询
    page_obj: Page = paginate(
        query=stmt,
        db_session=db,
        page=page,
        page_size=page_size,
        max_page_size=100,
    )
    
    # 获取筛选器选项（用于前端下拉框）
    # tags 是 JSON 数组列，需在内存中展开扁平化去重，无法用 DB 层 DISTINCT
    tags = sorted({
        tag_item
        for case in db.execute(select(TestCase.tags)).all()
        for tag_item in (case[0] or [])
        if str(tag_item).strip()
    })
    
    repo = TestCaseRepository(db)
    creators = sorted(repo.list_distinct_values(TestCase.creator))
    priorities = sorted(repo.list_distinct_values(TestCase.priority))
    last_results = sorted(repo.list_distinct_values(TestCase.last_execution_result))
    
    # 应用标签筛选（在内存中，因为 tags 是数组类型）
    items = [_to_list_item(case) for case in page_obj.items]
    if tag.strip():
        tag_filter = tag.strip()
        items = [item for item in items if tag_filter in item["tags"]]
        
        # 更新总数
        page_obj.meta.total_items = len(items)
        page_obj.meta.total_pages = (len(items) + page_size - 1) // page_size if len(items) > 0 else 1
    
    # 构建响应
    response = page_obj.to_dict()
    response["filters"] = {
        "tags": tags,
        "priorities": priorities,
        "creators": creators,
        "last_results": last_results,
    }
    response["sort"] = {
        "field": sort,
        "order": order,
    }
    
    return response


@router.get("/stats")
def get_case_stats(
    db = Depends(get_db),
) -> dict[str, Any]:
    """
    获取测试用例统计信息
    
    用于仪表盘展示，不需要分页
    """
    repo = TestCaseRepository(db)
    total = repo.count_all()
    priority_stats = repo.count_grouped_by(TestCase.priority)
    result_stats = repo.count_grouped_by(TestCase.last_execution_result)
    
    return {
        "total": total,
        "by_priority": {
            item[0]: item[1] 
            for item in priority_stats 
            if item[0]
        },
        "by_result": {
            item[0]: item[1] 
            for item in result_stats 
            if item[0]
        },
    }
