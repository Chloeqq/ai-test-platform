from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PageObjectCreate(BaseModel):
    project_code: str = Field(default="mall", min_length=2, max_length=20)
    client: str = Field(default="web", min_length=2, max_length=10)
    page_code: str = Field(..., min_length=2, max_length=40)
    page_name: str = Field(..., min_length=1, max_length=120)
    page_url: str = Field(default="", max_length=256)
    precondition_state: str = Field(default="", max_length=4000)
    route_pattern: str = Field(default="", max_length=256)
    anchor_config_json: dict[str, Any] = Field(default_factory=dict)
    governance_status: str = Field(default="draft", min_length=1, max_length=20)
    testability_score: int = Field(default=0, ge=0, le=100)
    module_id: int = Field(default=0, ge=0)
    health_status: int = Field(default=1, ge=0, le=1)
    description: str = Field(default="", max_length=4000)
    status: str = Field(default="draft", min_length=1, max_length=20)
    created_by: str = Field(default="admin", max_length=60)


class PageObjectUpdate(BaseModel):
    page_name: str | None = Field(default=None, min_length=1, max_length=120)
    page_url: str | None = Field(default=None, max_length=256)
    precondition_state: str | None = Field(default=None, max_length=4000)
    route_pattern: str | None = Field(default=None, max_length=256)
    anchor_config_json: dict[str, Any] | None = None
    governance_status: str | None = Field(default=None, min_length=1, max_length=20)
    testability_score: int | None = Field(default=None, ge=0, le=100)
    module_id: int | None = Field(default=None, ge=0)
    health_status: int | None = Field(default=None, ge=0, le=1)
    description: str | None = Field(default=None, max_length=4000)
    status: str | None = Field(default=None, min_length=1, max_length=20)


class PageElementCreate(BaseModel):
    element_code: str = Field(..., min_length=2, max_length=80)
    element_name: str = Field(..., min_length=1, max_length=120)
    locator_type: str = Field(..., min_length=1, max_length=30)
    locator_value: str = Field(..., min_length=1, max_length=4000)
    backup_locator: str = Field(default="", max_length=512)
    business_type: str = Field(default="", max_length=40)
    business_domain: str = Field(default="", max_length=40)
    aliases_json: list[Any] = Field(default_factory=list)
    semantic_tags_json: list[Any] = Field(default_factory=list)
    locator_source: str = Field(default="", max_length=20)
    match_strategy: str = Field(default="exact", max_length=20)
    stability_level: str = Field(default="low", max_length=20)
    review_status: str = Field(default="pending", max_length=20)
    origin_candidate_key: str = Field(default="", max_length=120)
    route_scope: str = Field(default="", max_length=256)
    anchor_required: bool = False
    is_key_element: bool = False
    testid_value: str = Field(default="", max_length=120)
    qa_value: str = Field(default="", max_length=120)
    governance_note: str = Field(default="", max_length=4000)
    health_status: int = Field(default=1, ge=0, le=1)
    role: str = Field(default="", max_length=60)
    status: str = Field(default="active", min_length=1, max_length=20)
    is_primary: bool = True
    owner: str = Field(default="", max_length=60)
    changed_by: str = Field(default="admin", max_length=60)
    change_summary: str = Field(default="element created", max_length=2000)


class PageElementUpdate(BaseModel):
    element_code: str | None = Field(default=None, min_length=3, max_length=80)
    element_name: str | None = Field(default=None, min_length=1, max_length=120)
    locator_type: str | None = Field(default=None, min_length=1, max_length=30)
    locator_value: str | None = Field(default=None, min_length=1, max_length=4000)
    backup_locator: str | None = Field(default=None, max_length=512)
    business_type: str | None = Field(default=None, max_length=40)
    business_domain: str | None = Field(default=None, max_length=40)
    aliases_json: list[Any] | None = None
    semantic_tags_json: list[Any] | None = None
    locator_source: str | None = Field(default=None, max_length=20)
    match_strategy: str | None = Field(default=None, max_length=20)
    stability_level: str | None = Field(default=None, max_length=20)
    review_status: str | None = Field(default=None, max_length=20)
    origin_candidate_key: str | None = Field(default=None, max_length=120)
    route_scope: str | None = Field(default=None, max_length=256)
    anchor_required: bool | None = None
    is_key_element: bool | None = None
    testid_value: str | None = Field(default=None, max_length=120)
    qa_value: str | None = Field(default=None, max_length=120)
    governance_note: str | None = Field(default=None, max_length=4000)
    health_status: int | None = Field(default=None, ge=0, le=1)
    role: str | None = Field(default=None, max_length=60)
    status: str | None = Field(default=None, min_length=1, max_length=20)
    is_primary: bool | None = None
    owner: str | None = Field(default=None, max_length=60)
    changed_by: str = Field(default="admin", max_length=60)
    change_summary: str = Field(default="element updated", max_length=2000)


class PageElementVersionCreate(BaseModel):
    changed_by: str = Field(default="admin", max_length=60)
    change_summary: str = Field(default="snapshot created", max_length=2000)


class PageObjectRefCreate(BaseModel):
    reference_type: str = Field(default="test_case", min_length=1, max_length=30)
    reference_key: str = Field(..., min_length=1, max_length=120)
    source: str = Field(default="manual", min_length=1, max_length=40)
    created_by: str = Field(default="admin", max_length=60)


class CandidateGroupPromotePayload(BaseModel):
    element_code: str = Field(..., min_length=3, max_length=80)
    element_name: str = Field(..., min_length=1, max_length=120)
    business_type: str = Field(default="", max_length=40)
    business_domain: str = Field(default="", max_length=40)
    is_key_element: bool = False
    locator_type: str = Field(default="", max_length=30)
    locator_value: str = Field(default="", max_length=4000)
    role: str = Field(default="", max_length=60)
    locator_source: str = Field(default="", max_length=20)
    route_scope: str = Field(default="", max_length=256)
    testid_value: str = Field(default="", max_length=120)
    qa_value: str = Field(default="", max_length=120)
    governance_note: str = Field(default="", max_length=4000)
    operator: str = Field(default="admin", max_length=60)


class CandidateGroupMergePayload(BaseModel):
    target_element_code: str = Field(..., min_length=2, max_length=80)
    review_note: str = Field(default="", max_length=4000)
    operator: str = Field(default="admin", max_length=60)
    write_locator: bool = True


class CandidateRejectPayload(BaseModel):
    review_note: str = Field(..., min_length=1, max_length=4000)
    operator: str = Field(default="admin", max_length=60)


class PageElementBatchDeletePayload(BaseModel):
    element_codes: list[str] = Field(..., min_length=1, max_length=200)


class CandidateGroupBatchDeletePayload(BaseModel):
    group_keys: list[str] = Field(..., min_length=1, max_length=200)


class CandidateElementBatchDeletePayload(BaseModel):
    candidate_keys: list[str] = Field(..., min_length=1, max_length=500)


class RecorderSessionBatchDeletePayload(BaseModel):
    session_ids: list[str] = Field(..., min_length=1, max_length=200)
    delete_artifacts: bool = True
