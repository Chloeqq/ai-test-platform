"""TestCaseRepository 单元测试。"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.repositories.test_case_repository import TestCaseRepository


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_db: MagicMock) -> TestCaseRepository:
    return TestCaseRepository(mock_db)


def mock_execute_result(mock_db: MagicMock, return_value: list) -> None:
    """Helper: 配置 mock_db.execute 返回指定结果。"""
    result = MagicMock()
    if return_value and hasattr(return_value[0], "case_id"):
        # ORM objects
        result.scalars.return_value.all.return_value = return_value
        result.scalar_one_or_none.return_value = return_value[0] if return_value else None
    else:
        # Scalar values
        result.scalars.return_value.all.return_value = return_value
        result.scalar_one_or_none.return_value = return_value[0] if return_value else None
    mock_db.execute.return_value = result


class TestGetByCaseId:
    def test_returns_none_when_not_found(self, repo: TestCaseRepository, mock_db: MagicMock) -> None:
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result

        assert repo.get_by_case_id("nonexistent") is None

    def test_calls_execute_with_correct_query(self, repo: TestCaseRepository, mock_db: MagicMock) -> None:
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result

        repo.get_by_case_id("atp-web-login-fn-0001")
        assert mock_db.execute.called


class TestListAll:
    def test_returns_empty_list_when_no_records(self, repo: TestCaseRepository, mock_db: MagicMock) -> None:
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = result

        assert repo.list_all() == []


class TestListCaseIds:
    def test_returns_list_of_strings(self, repo: TestCaseRepository, mock_db: MagicMock) -> None:
        mock_db.execute.return_value.all.return_value = [("case-1",), ("case-2",)]

        result = repo.list_case_ids()
        assert result == ["case-1", "case-2"]


class TestListFiltered:
    def test_returns_empty_with_no_filters(self, repo: TestCaseRepository, mock_db: MagicMock) -> None:
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = result

        assert repo.list_filtered() == []


class TestCountAll:
    def test_returns_zero_when_empty(self, repo: TestCaseRepository, mock_db: MagicMock) -> None:
        result = MagicMock()
        result.scalar_one.return_value = 0
        mock_db.execute.return_value = result

        assert repo.count_all() == 0


class TestExistsByCaseId:
    def test_returns_false_when_not_found(self, repo: TestCaseRepository, mock_db: MagicMock) -> None:
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result

        assert repo.exists_by_case_id("nonexistent") is False


class TestListDistinctValues:
    def test_returns_string_list(self, repo: TestCaseRepository, mock_db: MagicMock) -> None:
        mock_db.execute.return_value.all.return_value = [("atp",), ("mall",)]

        result = repo.list_distinct_values(MagicMock())
        assert result == ["atp", "mall"]
