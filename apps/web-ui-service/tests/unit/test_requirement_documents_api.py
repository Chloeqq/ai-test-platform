"""HTTP 层端到端验证：真实驱动 requirement_documents 路由（route→Form→校验→
service 编排→DB 落库→响应/状态码）。MinIO 用 stub，解析用真实 document_parser。

覆盖设计文档《需求文档上传解析方案》第六节 Phase 3 可在无 docker 下验证的部分：
- 上传 md/docx 返回结构化 markdown + 记录入库 + parse_status 正确
- 扩展名白名单 / 空 project_code → 400
- 超限 → 413（client_max_body_size 由 nginx 兜底，app 层再校验）
- MinIO 未启用 / 存储不可用 → 503（非裸 500）
需真实 docker 的部分（MinIO 真对象、nginx 413）在集成环境另跑。
"""
from __future__ import annotations

import io
import zipfile
from collections.abc import Iterator
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.constants.requirement_document import ParseStatus
from app.core.config import get_settings
from app.core.database import Base, get_db
from app.core.security import get_current_user
import app.models.requirement_document  # noqa: F401  (register table)
from app.repositories.requirement_document_repository import RequirementDocumentRepository
from app.routers.requirement_documents import router as requirement_documents_router
from app.services import requirement_document_service as svc

UPLOAD_URL = "/api/workbench/requirement-documents/upload"


def _make_docx(paragraphs: list[str]) -> bytes:
    """最小合法 docx：仅 word/document.xml + 几个段落，供 HTTP 层跑通 docx 分支。"""
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = "".join(f"<w:p><w:r><w:t>{t}</w:t></w:r></w:p>" for t in paragraphs)
    doc_xml = f'<?xml version="1.0"?><w:document xmlns:w="{ns}"><w:body>{body}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", doc_xml)
    return buf.getvalue()


@pytest.fixture()
def client_db(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, Session, list]]:
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)()

    # MinIO stub：可用且上传成功，记录上传参数。
    uploaded: list = []
    monkeypatch.setattr(svc, "get_minio_client", lambda: object())
    monkeypatch.setattr(
        svc,
        "upload_bytes",
        lambda client, object_key, data, content_type: uploaded.append((object_key, data, content_type)),
    )

    app = FastAPI()
    app.include_router(requirement_documents_router)
    # 小上限（1KB）让超限用例便宜；白名单固定 3 种。
    small_settings = get_settings().model_copy(
        update={"requirement_upload_max_bytes": 1024, "requirement_upload_allowed_exts": ".docx,.pdf,.md"}
    )
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_settings] = lambda: small_settings
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(username="qa", role="admin")

    client = TestClient(app)
    try:
        yield client, session, uploaded
    finally:
        client.close()
        session.close()


def test_upload_md_returns_markdown_and_persists(client_db) -> None:
    client, session, uploaded = client_db
    resp = client.post(
        UPLOAD_URL,
        data={"project_code": "mall"},
        files={"file": ("prd.md", b"# Title\n\nbody text", "text/markdown")},
    )
    assert resp.status_code == 200, resp.text
    item = resp.json()["item"]
    assert item["parse_status"] == ParseStatus.PARSED
    assert "# Title" in item["parsed_text"]
    assert item["source_type"] == "md"
    assert item["object_key"].startswith("mall/")
    # 真实落库
    doc = RequirementDocumentRepository(session).get_by_id(item["document_id"])
    assert doc is not None and doc.parse_status == ParseStatus.PARSED and doc.created_by == "qa"
    # content_type 以扩展名权威映射覆盖
    assert uploaded[-1][2] == svc._EXT_CONTENT_TYPE[".md"]


def test_upload_docx_branch_through_http(client_db) -> None:
    client, session, _ = client_db
    content = _make_docx(["需求标题", "正文一段"])
    resp = client.post(
        UPLOAD_URL,
        data={"project_code": "mall"},
        files={"file": ("spec.docx", content, "application/octet-stream")},
    )
    assert resp.status_code == 200, resp.text
    item = resp.json()["item"]
    assert item["source_type"] == "docx"
    assert item["parse_status"] == ParseStatus.PARSED
    assert "正文一段" in item["parsed_text"]


def test_upload_rejects_unknown_extension(client_db) -> None:
    client, _, _ = client_db
    resp = client.post(
        UPLOAD_URL,
        data={"project_code": "mall"},
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400
    assert "不支持" in resp.json()["detail"]


def test_upload_rejects_empty_project_code(client_db) -> None:
    client, _, _ = client_db
    resp = client.post(
        UPLOAD_URL,
        data={"project_code": "  "},
        files={"file": ("prd.md", b"# x", "text/markdown")},
    )
    assert resp.status_code == 400


def test_upload_rejects_oversize(client_db) -> None:
    client, _, _ = client_db
    big = b"x" * 2048  # > 1024 上限
    resp = client.post(
        UPLOAD_URL,
        data={"project_code": "mall"},
        files={"file": ("big.md", big, "text/markdown")},
    )
    assert resp.status_code == 413


def test_upload_minio_disabled_returns_503(client_db, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _, _ = client_db
    monkeypatch.setattr(svc, "get_minio_client", lambda: None)
    resp = client.post(
        UPLOAD_URL,
        data={"project_code": "mall"},
        files={"file": ("prd.md", b"# x", "text/markdown")},
    )
    assert resp.status_code == 503
    assert "MinIO" in resp.json()["detail"]


def test_upload_storage_unavailable_returns_503(client_db, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _, _ = client_db

    def _boom(client_, object_key, data, content_type):  # noqa: ANN001
        raise OSError("connection refused")  # OSError ∈ StorageError

    monkeypatch.setattr(svc, "upload_bytes", _boom)
    resp = client.post(
        UPLOAD_URL,
        data={"project_code": "mall"},
        files={"file": ("prd.md", b"# x", "text/markdown")},
    )
    assert resp.status_code == 503
    assert "存储不可用" in resp.json()["detail"]