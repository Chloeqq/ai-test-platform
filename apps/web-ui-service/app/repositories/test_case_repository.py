"""TestCase 聚合根的 Repository。

覆盖模型：TestCase, TestCaseExecution, TestCaseVersion,
          TestCaseStep, TestCaseDefect, TestCaseTreeNode。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select

from app.models.test_case import (
    TestCase,
    TestCaseDefect,
    TestCaseExecution,
    TestCaseStep,
    TestCaseTreeNode,
    TestCaseVersion,
)

from .base import BaseRepository


class TestCaseRepository(BaseRepository):
    """TestCase 聚合根的数据访问层。"""
    __test__ = False  # 不是 pytest 测试类

    # ---- TestCase 基础查询 ----

    def get_by_id(self, case_pk: int) -> TestCase | None:
        return self.db.execute(
            select(TestCase).where(TestCase.id == case_pk)
        ).scalar_one_or_none()

    def get_by_case_id(self, case_id: str) -> TestCase | None:
        return self.db.execute(
            select(TestCase).where(TestCase.case_id == case_id)
        ).scalar_one_or_none()

    def get_by_case_id_and_project(self, case_id: str, project_code: str) -> TestCase | None:
        return self.db.execute(
            select(TestCase).where(
                TestCase.case_id == case_id,
                TestCase.project_code == project_code,
            )
        ).scalar_one_or_none()

    def list_all(self) -> list[TestCase]:
        return list(
            self.db.execute(select(TestCase).order_by(TestCase.id.asc())).scalars().all()
        )

    def list_by_project(self, project_code: str) -> list[TestCase]:
        return list(
            self.db.execute(
                select(TestCase)
                .where(TestCase.project_code == project_code)
                .order_by(TestCase.updated_at.desc())
            ).scalars().all()
        )

    def list_by_ids(self, ids: list[int]) -> list[TestCase]:
        if not ids:
            return []
        return list(
            self.db.execute(
                select(TestCase).where(TestCase.id.in_(ids))
            ).scalars().all()
        )

    def list_case_ids(self, exclude_ids: list[int] | None = None) -> list[str]:
        stmt = select(TestCase.case_id)
        if exclude_ids:
            stmt = stmt.where(TestCase.id.notin_(exclude_ids))
        return [row[0] for row in self.db.execute(stmt).all()]

    def list_case_id_and_id_pairs(self, ids: list[int]) -> list[tuple[int, str]]:
        """返回 [(id, case_id), ...] 用于批量映射。"""
        if not ids:
            return []
        return list(
            self.db.execute(
                select(TestCase.id, TestCase.case_id).where(TestCase.id.in_(ids))
            ).all()
        )

    def list_case_id_and_id_pairs_by_case_ids(
        self, project_code: str, case_ids: list[str]
    ) -> list[tuple[int, str]]:
        """返回 [(id, case_id), ...] 按 project_code + case_id 字符串筛选。"""
        if not case_ids:
            return []
        return list(
            self.db.execute(
                select(TestCase.id, TestCase.case_id)
                .where(TestCase.project_code == project_code)
                .where(TestCase.case_id.in_(case_ids))
                .order_by(TestCase.id.asc())
            ).all()
        )

    def list_all_case_id_pairs_by_project(self, project_code: str) -> list[tuple[int, str]]:
        """返回某个项目所有 TestCase 的 [(id, case_id), ...] 映射。"""
        return list(
            self.db.execute(
                select(TestCase.id, TestCase.case_id)
                .where(TestCase.project_code == project_code)
                .order_by(TestCase.id.asc())
            ).all()
        )

    def count_all(self) -> int:
        return self.db.execute(
            select(func.count()).select_from(TestCase)
        ).scalar_one()

    def count_grouped_by(self, column: Any) -> list[tuple[Any, int]]:
        """按指定列分组统计，返回 [(value, count), ...]。"""
        return list(
            self.db.execute(
                select(column, func.count()).select_from(TestCase).group_by(column)
            ).all()
        )

    def exists_by_case_id(self, case_id: str) -> bool:
        return self.db.execute(
            select(TestCase.id).where(TestCase.case_id == case_id)
        ).scalar_one_or_none() is not None

    # ---- 按多条件筛选 ----

    def list_filtered(
        self,
        *,
        project_code: str | None = None,
        page_code: str | None = None,
        priority: str | None = None,
        status: str | None = None,
        exclude_status: str | None = None,
        case_type: str | None = None,
        source: str | None = None,
        creator: str | None = None,
        last_execution_result: str | None = None,
        module_code: str | None = None,
        test_type: str | None = None,
        product_line: str | None = None,
        module: str | None = None,
        order_by: Any = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[TestCase]:
        stmt = select(TestCase)
        if project_code:
            stmt = stmt.where(TestCase.project_code == project_code)
        if page_code:
            stmt = stmt.where(TestCase.page_code == page_code)
        if priority:
            stmt = stmt.where(TestCase.priority == priority)
        if status:
            stmt = stmt.where(TestCase.status == status)
        if exclude_status:
            stmt = stmt.where(TestCase.status != exclude_status)
        if case_type:
            stmt = stmt.where(TestCase.case_type == case_type)
        if source:
            stmt = stmt.where(TestCase.source == source)
        if creator:
            stmt = stmt.where(TestCase.creator == creator)
        if last_execution_result:
            stmt = stmt.where(TestCase.last_execution_result == last_execution_result)
        if module_code:
            stmt = stmt.where(TestCase.module_code == module_code)
        if test_type:
            stmt = stmt.where(TestCase.test_type == test_type)
        if product_line:
            stmt = stmt.where(TestCase.product_line == product_line)
        if module:
            stmt = stmt.where(TestCase.module == module)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        return list(self.db.execute(stmt).scalars().all())

    # ---- 字典/枚举查询 ----

    def list_distinct_values(self, column: Any) -> list[str]:
        """返回某列的去重值列表，用于下拉选项。"""
        rows = self.db.execute(select(func.distinct(column))).all()
        return [str(row[0] or "") for row in rows if row[0]]

    # ---- TestCaseExecution ----

    def get_execution_by_id(self, execution_id: int) -> TestCaseExecution | None:
        return self.db.execute(
            select(TestCaseExecution).where(TestCaseExecution.id == execution_id)
        ).scalar_one_or_none()

    def list_executions_by_case_ids(
        self, case_ids: list[int], *, order_desc: bool = True
    ) -> list[TestCaseExecution]:
        if not case_ids:
            return []
        order = TestCaseExecution.executed_at.desc() if order_desc else TestCaseExecution.executed_at.asc()
        return list(
            self.db.execute(
                select(TestCaseExecution)
                .where(TestCaseExecution.case_id.in_(case_ids))
                .order_by(order)
            ).scalars().all()
        )

    def list_all_executions_ordered(self) -> list[TestCaseExecution]:
        return list(
            self.db.execute(
                select(TestCaseExecution).order_by(TestCaseExecution.executed_at.desc())
            ).scalars().all()
        )

    def get_latest_execution_map(self, case_ids: list[int]) -> dict[int, TestCaseExecution]:
        """返回 {case_id: 最新一次执行记录} 的映射。"""
        if not case_ids:
            return {}
        subq = (
            select(
                TestCaseExecution.case_id,
                func.max(TestCaseExecution.id).label("max_id"),
            )
            .where(TestCaseExecution.case_id.in_(case_ids))
            .group_by(TestCaseExecution.case_id)
            .subquery()
        )
        rows = (
            self.db.execute(
                select(TestCaseExecution).join(
                    subq, TestCaseExecution.id == subq.c.max_id
                )
            )
            .scalars()
            .all()
        )
        return {row.case_id: row for row in rows}

    # ---- TestCaseVersion ----

    def list_versions_by_case_id(
        self, case_id: int, *, limit: int | None = None
    ) -> list[TestCaseVersion]:
        stmt = (
            select(TestCaseVersion)
            .where(TestCaseVersion.case_id == case_id)
            .order_by(TestCaseVersion.version_no.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_latest_version_no(self, case_id: int) -> int | None:
        row = self.db.execute(
            select(func.max(TestCaseVersion.version_no))
            .where(TestCaseVersion.case_id == case_id)
        ).scalar_one_or_none()
        return row

    def get_latest_version_nos(self, case_ids: list[int]) -> dict[int, int]:
        """返回 {case_id: max(version_no)} 批量映射。"""
        if not case_ids:
            return {}
        rows = (
            self.db.execute(
                select(
                    TestCaseVersion.case_id,
                    func.max(TestCaseVersion.version_no).label("max_ver"),
                )
                .where(TestCaseVersion.case_id.in_(case_ids))
                .group_by(TestCaseVersion.case_id)
            )
            .all()
        )
        return {row[0]: row[1] for row in rows}

    # ---- TestCaseStep ----

    def delete_steps_by_case_id(self, case_id: int) -> None:
        self.db.execute(delete(TestCaseStep).where(TestCaseStep.case_id == case_id))

    # ---- TestCaseDefect ----

    def list_defects_by_case_id(self, case_id: int) -> list[TestCaseDefect]:
        return list(
            self.db.execute(
                select(TestCaseDefect)
                .where(TestCaseDefect.case_id == case_id)
                .order_by(TestCaseDefect.created_at.desc())
            ).scalars().all()
        )

    # ---- Execution (extended) ----

    def list_executions_by_case_id(
        self, case_id: int, limit: int | None = None
    ) -> list[TestCaseExecution]:
        stmt = (
            select(TestCaseExecution)
            .where(TestCaseExecution.case_id == case_id)
            .order_by(
                TestCaseExecution.executed_at.desc(),
                TestCaseExecution.id.desc(),
            )
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_execution_by_report_url_like(
        self, case_id: int, url_pattern: str
    ) -> TestCaseExecution | None:
        return self.db.execute(
            select(TestCaseExecution).where(
                TestCaseExecution.case_id == case_id,
                TestCaseExecution.report_url.like(url_pattern),
            )
        ).scalar_one_or_none()

    def get_latest_execution_ids_grouped_by_case(
        self, case_ids: list[int] | None = None
    ) -> list[tuple[int, int]]:
        """返回 [(case_id, max_execution_id), ...]"""
        stmt = select(
            TestCaseExecution.case_id,
            func.max(TestCaseExecution.id),
        )
        if case_ids:
            stmt = stmt.where(TestCaseExecution.case_id.in_(case_ids))
        stmt = stmt.group_by(TestCaseExecution.case_id)
        return list(self.db.execute(stmt).all())

    def list_executions_by_ids(
        self, execution_ids: list[int]
    ) -> list[TestCaseExecution]:
        if not execution_ids:
            return []
        return list(
            self.db.execute(
                select(TestCaseExecution).where(
                    TestCaseExecution.id.in_(execution_ids)
                )
            ).scalars().all()
        )

    # ---- Tags ----

    def list_all_tags(self) -> list[str]:
        """展开所有 TestCase 的 tags JSON 数组，返回去重列表。"""
        rows = self.db.execute(select(TestCase.tags)).all()
        result: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for tag in row[0] or []:
                tag_str = str(tag).strip()
                if tag_str and tag_str not in seen:
                    seen.add(tag_str)
                    result.append(tag_str)
        return result

    # ---- Version (extended) ----

    def get_version_by_case_id_and_no(
        self, case_id: int, version_no: int
    ) -> TestCaseVersion | None:
        return self.db.execute(
            select(TestCaseVersion).where(
                TestCaseVersion.case_id == case_id,
                TestCaseVersion.version_no == version_no,
            )
        ).scalar_one_or_none()

    # ---- ID mapping ----

    def list_id_by_case_ids(
        self, case_ids: list[str]
    ) -> list[tuple[str, int]]:
        """返回 [(case_id, id), ...]"""
        if not case_ids:
            return []
        return list(
            self.db.execute(
                select(TestCase.case_id, TestCase.id).where(
                    TestCase.case_id.in_(case_ids)
                )
            ).all()
        )

    def list_by_ids_ordered(self, ids: list[int]) -> list[TestCase]:
        if not ids:
            return []
        return list(
            self.db.execute(
                select(TestCase)
                .where(TestCase.id.in_(ids))
                .order_by(TestCase.id.asc())
            ).scalars().all()
        )

    def list_id_and_case_id_by_project_and_product_line(
        self,
        *,
        project_code: str,
        product_line: str,
        module: str | None = None,
    ) -> list[tuple[int, str]]:
        stmt = select(TestCase.id, TestCase.case_id).where(
            TestCase.project_code == project_code,
            TestCase.product_line == product_line,
        )
        if module:
            stmt = stmt.where(TestCase.module == module)
        return list(self.db.execute(stmt).all())

    # ---- TestCaseTreeNode ----

    def get_tree_node(
        self, project_code: str, product_line: str, module: str
    ) -> TestCaseTreeNode | None:
        return self.db.execute(
            select(TestCaseTreeNode).where(
                TestCaseTreeNode.project_code == project_code,
                TestCaseTreeNode.product_line == product_line,
                TestCaseTreeNode.module == module,
            )
        ).scalar_one_or_none()

    def list_all_tree_nodes(self) -> list[TestCaseTreeNode]:
        return list(
            self.db.execute(
                select(TestCaseTreeNode).order_by(
                    TestCaseTreeNode.project_code,
                    TestCaseTreeNode.product_line,
                    TestCaseTreeNode.module,
                )
            ).scalars().all()
        )
