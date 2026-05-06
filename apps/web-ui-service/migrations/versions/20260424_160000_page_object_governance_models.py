"""page object governance models

Revision ID: 20260424_160000_page_object_governance_models
Revises: 20260408_100500_add_page_object_precondition_state
Create Date: 2026-04-24 16:00:00
"""
from __future__ import annotations

from collections.abc import Iterable

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = "20260424_160000_page_object_governance_models"
down_revision = "20260408_100500_add_page_object_precondition_state"
branch_labels = None
depends_on = None


def _has_table(conn: Connection, table_name: str) -> bool:
    return bool(sa.inspect(conn).has_table(table_name))


def _has_column(conn: Connection, table_name: str, column_name: str) -> bool:
    if not _has_table(conn, table_name):
        return False
    return any(str(item.get("name", "")) == column_name for item in sa.inspect(conn).get_columns(table_name))


def _safe_create_index(index_name: str, table_name: str, columns: list[str], *, unique: bool = False) -> None:
    conn = op.get_bind()
    if not _has_table(conn, table_name):
        return
    existing = {str(item.get("name", "")) for item in sa.inspect(conn).get_indexes(table_name)}
    if index_name in existing:
        return
    op.create_index(index_name, table_name, columns, unique=unique)


def _drop_index_if_exists(index_name: str, table_name: str) -> None:
    conn = op.get_bind()
    if not _has_table(conn, table_name):
        return
    existing = {str(item.get("name", "")) for item in sa.inspect(conn).get_indexes(table_name)}
    if index_name in existing:
        op.drop_index(index_name, table_name=table_name)


def _add_missing_columns(conn: Connection, table_name: str, columns: Iterable[sa.Column]) -> None:
    for column in columns:
        if _has_column(conn, table_name, str(column.name)):
            continue
        op.add_column(table_name, column)


def _drop_column_if_exists(conn: Connection, table_name: str, column_name: str) -> None:
    if _has_column(conn, table_name, column_name):
        op.drop_column(table_name, column_name)


def _create_candidate_groups_table() -> None:
    op.create_table(
        "page_object_candidate_groups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_code", sa.String(length=20), nullable=False, server_default="mall"),
        sa.Column("client", sa.String(length=10), nullable=False, server_default="web"),
        sa.Column("page_code", sa.String(length=40), nullable=False),
        sa.Column("group_key", sa.String(length=160), nullable=False),
        sa.Column("proposed_element_code", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("proposed_element_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("business_type_guess", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("business_domain_guess", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("quality_tier", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("max_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("session_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recommended_action", sa.String(length=20), nullable=False, server_default="review"),
        sa.Column("promotion_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("route_scope", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("top_locator_source", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("top_locator_type", sa.String(length=30), nullable=False, server_default=""),
        sa.Column("top_locator_value", sa.Text(), nullable=False, server_default=""),
        sa.Column("top_role", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("risk_tags_json", sa.JSON(), nullable=True),
        sa.Column("sample_texts_json", sa.JSON(), nullable=True),
        sa.Column("matched_existing_element_code", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("reviewed_by", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("latest_session_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "project_code",
            "client",
            "page_code",
            "group_key",
            name="uq_page_object_candidate_groups_identity",
        ),
    )


def _create_candidate_elements_table() -> None:
    op.create_table(
        "page_object_candidate_elements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_code", sa.String(length=20), nullable=False, server_default="mall"),
        sa.Column("client", sa.String(length=10), nullable=False, server_default="web"),
        sa.Column("page_code", sa.String(length=40), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("candidate_key", sa.String(length=120), nullable=False),
        sa.Column("group_key", sa.String(length=160), nullable=False),
        sa.Column("raw_locator_type", sa.String(length=30), nullable=False, server_default=""),
        sa.Column("raw_locator_value", sa.Text(), nullable=False, server_default=""),
        sa.Column("raw_role", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("raw_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("dom_signature", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("route", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("step_hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quality_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quality_tier", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("risk_tags_json", sa.JSON(), nullable=True),
        sa.Column("recommended_action", sa.String(length=20), nullable=False, server_default="review"),
        sa.Column("candidate_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("ingest_block_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("proposed_element_code", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("proposed_element_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("business_type_guess", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("probe_status", sa.String(length=20), nullable=False, server_default="unknown"),
        sa.Column("probe_match_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("probe_visible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("probe_interactable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("merged_to_element_code", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("promoted_element_code", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("reviewed_by", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("session_id", "candidate_key", name="uq_page_object_candidate_elements_identity"),
    )


def _create_element_locators_table() -> None:
    op.create_table(
        "page_element_locators",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("page_element_id", sa.Integer(), sa.ForeignKey("page_elements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("locator_type", sa.String(length=30), nullable=False, server_default=""),
        sa.Column("locator_value", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("role", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("locator_source", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("health_status", sa.String(length=20), nullable=False, server_default="unknown"),
        sa.Column("verification_status", sa.String(length=20), nullable=False, server_default="unknown"),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=60), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "page_element_id",
            "locator_type",
            "locator_value",
            "role",
            name="uq_page_element_locators_identity",
        ),
    )


def _create_governance_logs_table() -> None:
    op.create_table(
        "page_object_governance_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_code", sa.String(length=20), nullable=False, server_default="mall"),
        sa.Column("client", sa.String(length=10), nullable=False, server_default="web"),
        sa.Column("page_code", sa.String(length=40), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("entity_key", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("action", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("before_payload", sa.JSON(), nullable=True),
        sa.Column("after_payload", sa.JSON(), nullable=True),
        sa.Column("operator", sa.String(length=60), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def _create_indexes() -> None:
    for table_name, columns in [
        ("page_object_candidate_groups", ["project_code"]),
        ("page_object_candidate_groups", ["client"]),
        ("page_object_candidate_groups", ["page_code"]),
        ("page_object_candidate_groups", ["group_key"]),
        ("page_object_candidate_groups", ["quality_tier"]),
        ("page_object_candidate_groups", ["promotion_status"]),
        ("page_object_candidate_groups", ["latest_session_id"]),
        ("page_object_candidate_groups", ["reviewed_at"]),
        ("page_object_candidate_groups", ["created_at"]),
        ("page_object_candidate_groups", ["updated_at"]),
    ]:
        _safe_create_index(f"ix_{table_name}_{'_'.join(columns)}", table_name, columns)

    _safe_create_index(
        "ix_page_object_candidate_groups_page_status",
        "page_object_candidate_groups",
        ["project_code", "client", "page_code", "promotion_status"],
    )
    _safe_create_index(
        "ix_page_object_candidate_groups_page_quality",
        "page_object_candidate_groups",
        ["project_code", "client", "page_code", "quality_tier"],
    )
    _safe_create_index(
        "ix_page_object_candidate_groups_matched_element",
        "page_object_candidate_groups",
        ["matched_existing_element_code"],
    )

    for table_name, columns in [
        ("page_object_candidate_elements", ["project_code"]),
        ("page_object_candidate_elements", ["client"]),
        ("page_object_candidate_elements", ["page_code"]),
        ("page_object_candidate_elements", ["session_id"]),
        ("page_object_candidate_elements", ["candidate_key"]),
        ("page_object_candidate_elements", ["group_key"]),
        ("page_object_candidate_elements", ["quality_score"]),
        ("page_object_candidate_elements", ["recommended_action"]),
        ("page_object_candidate_elements", ["candidate_status"]),
        ("page_object_candidate_elements", ["reviewed_at"]),
        ("page_object_candidate_elements", ["created_at"]),
        ("page_object_candidate_elements", ["updated_at"]),
    ]:
        _safe_create_index(f"ix_{table_name}_{'_'.join(columns)}", table_name, columns)

    _safe_create_index(
        "ix_page_object_candidate_elements_page_status",
        "page_object_candidate_elements",
        ["project_code", "client", "page_code", "candidate_status"],
    )
    _safe_create_index("ix_page_element_locators_page_element_id", "page_element_locators", ["page_element_id"])
    _safe_create_index("ix_page_element_locators_health_status", "page_element_locators", ["health_status"])
    _safe_create_index(
        "ix_page_element_locators_verification_status",
        "page_element_locators",
        ["verification_status"],
    )
    _safe_create_index("ix_page_element_locators_last_verified_at", "page_element_locators", ["last_verified_at"])
    _safe_create_index("ix_page_element_locators_created_at", "page_element_locators", ["created_at"])
    _safe_create_index("ix_page_element_locators_updated_at", "page_element_locators", ["updated_at"])

    _safe_create_index("ix_page_object_governance_logs_project_code", "page_object_governance_logs", ["project_code"])
    _safe_create_index("ix_page_object_governance_logs_client", "page_object_governance_logs", ["client"])
    _safe_create_index("ix_page_object_governance_logs_page_code", "page_object_governance_logs", ["page_code"])
    _safe_create_index(
        "ix_page_object_governance_logs_page",
        "page_object_governance_logs",
        ["project_code", "client", "page_code"],
    )
    _safe_create_index(
        "ix_page_object_governance_logs_entity",
        "page_object_governance_logs",
        ["entity_type", "entity_key"],
    )
    _safe_create_index("ix_page_object_governance_logs_action", "page_object_governance_logs", ["action"])
    _safe_create_index("ix_page_object_governance_logs_created_at", "page_object_governance_logs", ["created_at"])

    _safe_create_index("ix_page_objects_governance_status", "page_objects", ["governance_status"])
    _safe_create_index(
        "ix_page_elements_page_object_review_status",
        "page_elements",
        ["page_object_id", "review_status"],
    )
    _safe_create_index(
        "ix_page_elements_page_object_business_type",
        "page_elements",
        ["page_object_id", "business_type"],
    )
    _safe_create_index(
        "ix_page_elements_page_object_stability_level",
        "page_elements",
        ["page_object_id", "stability_level"],
    )
    _safe_create_index(
        "ix_page_elements_page_object_locator_source",
        "page_elements",
        ["page_object_id", "locator_source"],
    )
    _safe_create_index(
        "ix_page_elements_page_object_testid_value",
        "page_elements",
        ["page_object_id", "testid_value"],
    )


def _mark_legacy_dirty_elements() -> None:
    conn = op.get_bind()
    if not _has_table(conn, "page_elements"):
        return
    op.execute(
        sa.text(
            """
            UPDATE page_elements
            SET review_status = 'pending',
                stability_level = 'low',
                governance_note = CASE
                    WHEN governance_note IS NULL OR governance_note = ''
                    THEN 'legacy dirty element naming detected; pending governance review'
                    ELSE governance_note
                END
            WHERE lower(element_code) LIKE '%css%'
               OR lower(element_code) LIKE '%xpath%'
               OR lower(element_code) LIKE '%path%'
               OR lower(element_code) LIKE '%nth%'
               OR lower(element_code) LIKE '%index%'
               OR lower(element_code) LIKE '%text%'
               OR lower(element_code) LIKE '%---%'
            """
        )
    )


def upgrade() -> None:
    conn = op.get_bind()
    _add_missing_columns(
        conn,
        "page_objects",
        [
            sa.Column("route_pattern", sa.String(length=256), nullable=False, server_default=""),
            sa.Column("anchor_config_json", sa.JSON(), nullable=True),
            sa.Column("governance_status", sa.String(length=20), nullable=False, server_default="draft"),
            sa.Column("testability_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("key_element_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("approved_element_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("candidate_pending_count", sa.Integer(), nullable=False, server_default="0"),
        ],
    )
    _add_missing_columns(
        conn,
        "page_elements",
        [
            sa.Column("business_type", sa.String(length=40), nullable=False, server_default=""),
            sa.Column("business_domain", sa.String(length=40), nullable=False, server_default=""),
            sa.Column("aliases_json", sa.JSON(), nullable=True),
            sa.Column("semantic_tags_json", sa.JSON(), nullable=True),
            sa.Column("locator_source", sa.String(length=20), nullable=False, server_default=""),
            sa.Column("match_strategy", sa.String(length=20), nullable=False, server_default="exact"),
            sa.Column("stability_level", sa.String(length=20), nullable=False, server_default="low"),
            sa.Column("review_status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("origin_candidate_key", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("route_scope", sa.String(length=256), nullable=False, server_default=""),
            sa.Column("anchor_required", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_key_element", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("testid_value", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("qa_value", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("governance_note", sa.Text(), nullable=False, server_default=""),
        ],
    )
    if not _has_table(conn, "page_object_candidate_groups"):
        _create_candidate_groups_table()
    if not _has_table(conn, "page_object_candidate_elements"):
        _create_candidate_elements_table()
    if not _has_table(conn, "page_element_locators"):
        _create_element_locators_table()
    if not _has_table(conn, "page_object_governance_logs"):
        _create_governance_logs_table()
    _create_indexes()
    _mark_legacy_dirty_elements()


def downgrade() -> None:
    conn = op.get_bind()
    for index_name, table_name in [
        ("ix_page_elements_page_object_review_status", "page_elements"),
        ("ix_page_elements_page_object_business_type", "page_elements"),
        ("ix_page_elements_page_object_stability_level", "page_elements"),
        ("ix_page_elements_page_object_locator_source", "page_elements"),
        ("ix_page_elements_page_object_testid_value", "page_elements"),
        ("ix_page_objects_governance_status", "page_objects"),
    ]:
        _drop_index_if_exists(index_name, table_name)
    for table_name in [
        "page_object_governance_logs",
        "page_element_locators",
        "page_object_candidate_elements",
        "page_object_candidate_groups",
    ]:
        if _has_table(conn, table_name):
            op.drop_table(table_name)
    for column_name in [
        "business_type",
        "business_domain",
        "aliases_json",
        "semantic_tags_json",
        "locator_source",
        "match_strategy",
        "stability_level",
        "review_status",
        "origin_candidate_key",
        "route_scope",
        "anchor_required",
        "is_key_element",
        "testid_value",
        "qa_value",
        "governance_note",
    ]:
        _drop_column_if_exists(conn, "page_elements", column_name)
    for column_name in [
        "route_pattern",
        "anchor_config_json",
        "governance_status",
        "testability_score",
        "key_element_count",
        "approved_element_count",
        "candidate_pending_count",
    ]:
        _drop_column_if_exists(conn, "page_objects", column_name)
