from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
import app.models.requirement_document  # noqa: F401  (register table for create_all)
from app.constants.requirement_document import ParseStatus
from app.repositories.requirement_document_repository import RequirementDocumentRepository
from app.services import requirement_document_service as svc


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:", future=True)
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    Base.metadata.create_all(bind=engine)
    session = testing_session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def stub_storage(monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """MinIO 可用且上传成功；记录上传调用参数供断言。"""
    uploaded: list[tuple] = []
    monkeypatch.setattr(svc, "get_minio_client", lambda: object())
    monkeypatch.setattr(
        svc,
        "upload_bytes",
        lambda client, object_key, data, content_type: uploaded.append((object_key, data, content_type)),
    )
    return uploaded


# --------------------------------------------------------------------------- #
# 纯函数：文件名净化 / object_key 生成
# --------------------------------------------------------------------------- #
def test_sanitize_filename_replaces_unsafe_chars() -> None:
    # \w 在 Python(str) 正则下匹配 Unicode，中文被保留；空格/括号/斜杠等替换为 _
    assert svc._sanitize_filename("需求 报告(v2).docx") == "需求_报告_v2_.docx"
    assert svc._sanitize_filename("a b/c*d.pdf") == "a_b_c_d.pdf"
    assert svc._sanitize_filename("") == "document"
    assert svc._sanitize_filename("...") == "document"


def test_build_object_key_format() -> None:
    key = svc._build_object_key("mall", "spec file.md", now=datetime(2026, 7, 11, 14, 30, 25))
    assert key == "mall/20260711_143025_spec_file.md"


def test_content_type_resolved_from_extension(db_session: Session, stub_storage: list[tuple]) -> None:
    svc.upload_and_parse(
        db_session,
        project_code="mall",
        filename="req.docx",
        content=b"# hi",  # 内容无关，只验证 content_type 映射来自扩展名
        content_type="application/octet-stream",  # 浏览器上报的不可靠类型应被覆盖
        username="qa",
    )
    _, _, content_type = stub_storage[-1]
    assert content_type == svc._EXT_CONTENT_TYPE[".docx"]


# --------------------------------------------------------------------------- #
# 编排：happy / partial / failed / storage / disabled
# --------------------------------------------------------------------------- #
def test_upload_and_parse_md_parsed(db_session: Session, stub_storage: list[tuple]) -> None:
    result = svc.upload_and_parse(
        db_session,
        project_code="mall",
        filename="prd.md",
        content=b"# Title\n\nsome body",
        content_type="text/markdown",
        username="qa",
    )
    assert result["parse_status"] == ParseStatus.PARSED
    assert "# Title" in result["parsed_text"]
    assert result["source_type"] == "md"
    assert result["object_key"].startswith("mall/")
    # 落库记录存在且状态一致
    doc = RequirementDocumentRepository(db_session).get_by_id(result["document_id"])
    assert doc is not None
    assert doc.parse_status == ParseStatus.PARSED
    assert doc.created_by == "qa"
    assert doc.file_size == len(b"# Title\n\nsome body")


def test_upload_and_parse_commits_transaction(
    db_session: Session, stub_storage: list[tuple], monkeypatch: pytest.MonkeyPatch
) -> None:
    """写路径必须显式 commit（get_db 不自动提交）；回归 in-memory 同 session 掩盖的落库 bug。"""
    calls = {"n": 0}
    real_commit = db_session.commit

    def _tracked_commit() -> None:
        calls["n"] += 1
        real_commit()

    monkeypatch.setattr(db_session, "commit", _tracked_commit)
    svc.upload_and_parse(
        db_session,
        project_code="mall",
        filename="prd.md",
        content=b"# x\n\nbody",
        content_type="text/markdown",
        username="qa",
    )
    assert calls["n"] >= 1, "upload_and_parse 必须 commit，否则行只 flush 不落库"


def test_upload_and_parse_empty_text_is_partial(db_session: Session, stub_storage: list[tuple]) -> None:
    result = svc.upload_and_parse(
        db_session,
        project_code="mall",
        filename="blank.md",
        content=b"   \n   \n",  # 非空字节但解析不出任何文本
        content_type="text/markdown",
        username=None,
    )
    assert result["parse_status"] == ParseStatus.PARTIAL
    doc = RequirementDocumentRepository(db_session).get_by_id(result["document_id"])
    assert doc is not None and doc.parse_error


def test_upload_and_parse_corrupt_docx_is_failed(db_session: Session, stub_storage: list[tuple]) -> None:
    result = svc.upload_and_parse(
        db_session,
        project_code="mall",
        filename="broken.docx",
        content=b"this is not a zip",  # docx 解析抛 ValueError → failed
        content_type="application/octet-stream",
        username="qa",
    )
    assert result["parse_status"] == ParseStatus.FAILED
    # 存储成功、记录仍保留（不丢失上传），仅解析状态标记失败
    assert len(stub_storage) == 1
    doc = RequirementDocumentRepository(db_session).get_by_id(result["document_id"])
    assert doc is not None and doc.parse_status == ParseStatus.FAILED and doc.parse_error


def test_upload_and_parse_raises_when_minio_disabled(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(svc, "get_minio_client", lambda: None)
    with pytest.raises(RuntimeError, match="MinIO 未启用"):
        svc.upload_and_parse(
            db_session,
            project_code="mall",
            filename="prd.md",
            content=b"# x",
            content_type="text/markdown",
            username="qa",
        )


def test_upload_and_parse_raises_when_storage_unavailable(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(svc, "get_minio_client", lambda: object())

    def _boom(client, object_key, data, content_type):  # noqa: ANN001
        raise OSError("connection refused")  # OSError ∈ StorageError

    monkeypatch.setattr(svc, "upload_bytes", _boom)
    with pytest.raises(RuntimeError, match="存储不可用"):
        svc.upload_and_parse(
            db_session,
            project_code="mall",
            filename="prd.md",
            content=b"# x",
            content_type="text/markdown",
            username="qa",
        )


# --------------------------------------------------------------------------- #
# Repository：get / list（is_deleted 过滤）/ update_parse_result
# --------------------------------------------------------------------------- #
def test_repository_list_filters_deleted_and_by_project(db_session: Session) -> None:
    repo = RequirementDocumentRepository(db_session)
    a = repo.create(
        project_code="mall", filename="a.md", source_type="md",
        object_key="mall/a", file_size=1, parse_status=ParseStatus.PARSED,
    )
    repo.create(
        project_code="mall", filename="b.md", source_type="md",
        object_key="mall/b", file_size=1, parse_status=ParseStatus.PARSED,
    )
    repo.create(
        project_code="other", filename="c.md", source_type="md",
        object_key="other/c", file_size=1, parse_status=ParseStatus.PARSED,
    )
    a.is_deleted = True
    db_session.flush()

    rows = repo.list_by_project("mall")
    assert [r.filename for r in rows] == ["b.md"]  # a 被软删除，other 不同项目
    assert repo.list_by_project("missing") == []


def test_repository_update_parse_result(db_session: Session) -> None:
    repo = RequirementDocumentRepository(db_session)
    doc = repo.create(
        project_code="mall", filename="a.md", source_type="md",
        object_key="mall/a", file_size=1, parse_status=ParseStatus.PENDING,
    )
    updated = repo.update_parse_result(doc.id, ParseStatus.FAILED, "boom")
    assert updated is not None and updated.parse_status == ParseStatus.FAILED and updated.parse_error == "boom"
    assert repo.update_parse_result(999999, ParseStatus.PARSED) is None