"""document_parser 纯函数测试：内存生成 docx/pdf/md 样本，无外部文件依赖。"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pytest

app_root = Path(__file__).resolve().parents[2]
if str(app_root) not in sys.path:
    sys.path.insert(0, str(app_root))

from app.services.document_parser import parse_document

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


# --------------------------------------------------------------------------
# 内存生成最小 docx（stdlib zipfile，零第三方依赖）
# --------------------------------------------------------------------------
def _p(text: str, *, outline: int | None = None, style: str | None = None) -> str:
    ppr = ""
    if outline is not None:
        ppr += f'<w:outlineLvl w:val="{outline}"/>'
    if style is not None:
        ppr += f'<w:pStyle w:val="{style}"/>'
    ppr_xml = f"<w:pPr>{ppr}</w:pPr>" if ppr else ""
    return f'<w:p>{ppr_xml}<w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'


def _table(rows: list[list[str]]) -> str:
    tr_xml = ""
    for row in rows:
        tc_xml = "".join(
            f'<w:tc><w:p><w:r><w:t xml:space="preserve">{cell}</w:t></w:r></w:p></w:tc>'
            for cell in row
        )
        tr_xml += f"<w:tr>{tc_xml}</w:tr>"
    return f"<w:tbl>{tr_xml}</w:tbl>"


def _make_docx(body_inner: str, *, styles_xml: str | None = None) -> bytes:
    document_xml = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<w:document xmlns:w="{_W_NS}"><w:body>{body_inner}</w:body></w:document>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        zf.writestr("word/document.xml", document_xml)
        if styles_xml is not None:
            zf.writestr("word/styles.xml", styles_xml)
    return buf.getvalue()


def _make_pdf(text: str) -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


# --------------------------------------------------------------------------
# docx
# --------------------------------------------------------------------------
class TestParseDocx:
    def test_outline_level_heading(self) -> None:
        # outlineLvl 0 → 一级标题(#)，1 → 二级(##)
        body = _p("概述", outline=0) + _p("正文内容") + _p("背景", outline=1)
        md = parse_document(_make_docx(body), "spec.docx")
        assert "# 概述" in md
        assert "## 背景" in md
        assert "正文内容" in md

    def test_style_based_heading_fallback(self) -> None:
        # 无 outlineLvl，仅 pStyle → 走 styles.xml basedOn 链
        styles = (
            f'<?xml version="1.0"?><w:styles xmlns:w="{_W_NS}">'
            f'<w:style w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>'
            f'<w:style w:styleId="MyTitle"><w:basedOn w:val="Heading1"/><w:name w:val="Custom"/></w:style>'
            f"</w:styles>"
        )
        body = _p("自定义标题", style="MyTitle") + _p("段落")
        md = parse_document(_make_docx(body, styles_xml=styles), "spec.docx")
        assert "# 自定义标题" in md
        assert "段落" in md

    def test_outline_level_preferred_over_style(self) -> None:
        # 同时有 outlineLvl 与 pStyle 时优先 outlineLvl
        styles = (
            f'<?xml version="1.0"?><w:styles xmlns:w="{_W_NS}">'
            f'<w:style w:styleId="Heading1"><w:name w:val="heading 1"/></w:style></w:styles>'
        )
        body = _p("标题", outline=2, style="Heading1")  # outline=2 → ###
        md = parse_document(_make_docx(body, styles_xml=styles), "spec.docx")
        assert "### 标题" in md

    def test_table_to_gfm(self) -> None:
        body = _table([["字段", "类型"], ["名称", "字符串"]])
        md = parse_document(_make_docx(body), "spec.docx")
        assert "| 字段 | 类型 |" in md
        assert "| --- | --- |" in md
        assert "| 名称 | 字符串 |" in md

    def test_empty_docx_returns_empty(self) -> None:
        md = parse_document(_make_docx(""), "empty.docx")
        assert md == ""

    def test_corrupt_docx_raises_valueerror(self) -> None:
        with pytest.raises(ValueError):
            parse_document(b"not a zip file", "broken.docx")


# --------------------------------------------------------------------------
# pdf
# --------------------------------------------------------------------------
class TestParsePdf:
    def test_extracts_text(self) -> None:
        # PDF 默认字体无 CJK 字形，用 ASCII 文本验证 get_text() 抽取能力
        md = parse_document(_make_pdf("Login flow overview"), "spec.pdf")
        assert "Login flow overview" in md

    def test_corrupt_pdf_raises_valueerror(self) -> None:
        with pytest.raises(ValueError):
            parse_document(b"%PDF-broken", "broken.pdf")


# --------------------------------------------------------------------------
# md / txt
# --------------------------------------------------------------------------
class TestParseMarkdown:
    def test_heading_and_paragraph(self) -> None:
        md = parse_document(b"# \xe6\xa0\x87\xe9\xa2\x98\n\xe6\xad\xa3\xe6\x96\x87", "req.md")
        assert md == "# 标题\n\n正文"

    def test_txt_treated_as_plain_lines(self) -> None:
        md = parse_document("第一行\n第二行".encode("utf-8"), "notes.txt")
        assert "第一行" in md
        assert "第二行" in md


# --------------------------------------------------------------------------
# dispatch
# --------------------------------------------------------------------------
class TestDispatch:
    def test_unsupported_extension_raises(self) -> None:
        with pytest.raises(ValueError, match="不支持"):
            parse_document(b"dummy", "data.xlsx")

    def test_legacy_doc_raises_with_hint(self) -> None:
        with pytest.raises(ValueError, match="doc"):
            parse_document(b"dummy", "old.doc")
