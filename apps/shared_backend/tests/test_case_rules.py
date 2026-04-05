from shared_backend.case_dictionary import get_dictionary_items
from shared_backend.case_rules import enrich_case_metadata, validate_case_payload, validate_case_title


def test_validate_case_title_rejects_code_like_titles() -> None:
    errors = validate_case_title("ret-query-sm-ai-0001")
    assert errors
    assert any("编码" in item or "中文" in item for item in errors)


def test_validate_case_title_requires_four_semantic_segments() -> None:
    errors = validate_case_title("退货申请页-查询检索-展示订单")
    assert any("4 段语义" in item for item in errors)


def test_validate_case_payload_accepts_structured_case() -> None:
    payload = {
        "id": "atp-web-ret-query-sm-ai-0001",
        "title": "退货申请页-查询检索-输入有效订单号-点击查询-展示订单信息",
        "description": "验证退货申请页在输入有效订单号后可以正常展示可退货订单信息。",
        "status": "ready",
    }
    enriched = enrich_case_metadata(payload)
    errors = validate_case_payload(enriched)
    assert errors == []
    assert enriched["page_code"] == "ret"
    assert enriched["module_code"] == "query"
    assert enriched["status_name"] == "可执行"
    assert enriched["ai_status_name"] == "已生成"


def test_validate_case_payload_rejects_non_chinese_title() -> None:
    payload = {
        "id": "atp-web-ret-query-sm-ai-0001",
        "title": "return-apply-query-case",
        "description": "验证退货申请页查询订单功能。",
    }
    errors = validate_case_payload(enrich_case_metadata(payload))
    assert any("中文" in item or "英文单词" in item for item in errors)


def test_case_dictionary_items_are_loaded_from_data_source() -> None:
    page_items = get_dictionary_items("page")
    source_items = get_dictionary_items("source")
    assert any(item["code"] == "ret" for item in page_items)
    assert any(item["code"] == "fb" for item in source_items)
