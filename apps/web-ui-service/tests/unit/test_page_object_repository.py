"""PageObjectRepository 单元测试。"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.repositories.page_object_repository import PageObjectRepository


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_db: MagicMock) -> PageObjectRepository:
    return PageObjectRepository(mock_db)


def _scalar_result(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _scalars_result(values):
    r = MagicMock()
    r.scalars.return_value.all.return_value = list(values)
    return r


class TestGetById:
    def test_returns_none_when_not_found(self, repo, mock_db):
        mock_db.execute.return_value = _scalar_result(None)
        assert repo.get_by_id(999) is None

    def test_calls_execute(self, repo, mock_db):
        mock_db.execute.return_value = _scalar_result(None)
        repo.get_by_id(1)
        assert mock_db.execute.called


class TestGetByIdentity:
    def test_returns_none_when_not_found(self, repo, mock_db):
        mock_db.execute.return_value = _scalar_result(None)
        assert repo.get_by_identity("atp", "web", "nonexistent") is None


class TestListByProjectAndPageCodes:
    def test_returns_empty_list_when_no_codes(self, repo, mock_db):
        assert repo.list_by_project_and_page_codes("atp", "web", []) == []

    def test_returns_empty_list_when_no_results(self, repo, mock_db):
        mock_db.execute.return_value = _scalars_result([])
        assert repo.list_by_project_and_page_codes("atp", "web", ["login"]) == []


class TestListElementsByPageObjectId:
    def test_returns_empty_list(self, repo, mock_db):
        mock_db.execute.return_value = _scalars_result([])
        assert repo.list_elements_by_page_object_id(1) == []


class TestGetElementByCode:
    def test_returns_none_when_not_found(self, repo, mock_db):
        mock_db.execute.return_value = _scalar_result(None)
        assert repo.get_element_by_code(1, "nonexistent") is None


class TestCountElements:
    def test_returns_zero_when_empty(self, repo, mock_db):
        r = MagicMock()
        r.scalar_one.return_value = 0
        mock_db.execute.return_value = r
        assert repo.count_elements_by_page_object_id(1) == 0


class TestCascadeDelete:
    def test_does_not_raise(self, repo, mock_db):
        mock_db.execute.return_value = MagicMock()
        repo.cascade_delete_element(1)

    def test_skips_empty_list(self, repo, mock_db):
        repo.bulk_cascade_delete_elements([])
        assert not mock_db.execute.called
