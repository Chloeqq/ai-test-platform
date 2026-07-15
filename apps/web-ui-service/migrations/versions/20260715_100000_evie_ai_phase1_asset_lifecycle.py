"""Add EvieAi Phase 1 natural-language asset lifecycle persistence.

Revision ID: 20260715_100000
Revises: 20260713_121000
Create Date: 2026-07-15 10:00:00.000000

The data-normalization helpers in this revision are frozen migration-local
implementations.  They must not import the evolving application ORM, policies,
settings, or services.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from collections import defaultdict
from collections.abc import Mapping

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260715_100000"
down_revision = "20260713_121000"
branch_labels = None
depends_on = None

_USER_PUBLIC_ID_PATTERN = re.compile(r"^usr_[0-9a-f]{32}$")
_SOURCE_TYPE_REQUIREMENT = "requirement"
_SOURCE_TYPE_MANUAL = "manual"
_SOURCE_TYPE_CHECK = "source_type IN ('requirement', 'manual')"
_REVIEW_STATUS_CHECK = "pending", "approved", "rejected"
_OPERATION_TYPES = (
    "create_asset",
    "create_version",
    "restore_historical_version",
    "review_asset",
    "delete_asset",
    "restore_asset",
)
_AUDIT_EVENT_TYPES = (
    "asset_created",
    "exact_duplicate_reused",
    "source_added",
    "version_created",
    "version_restored",
    "review_changed",
    "asset_deleted",
    "asset_restored",
)
_REVIEW_ACTIONS = "approve", "reject", "reopen"
_NEW_TABLES = {
    "test_asset_requirement_sources",
    "test_asset_idempotency_records",
    "test_asset_content_claims",
    "test_asset_review_records",
    "test_asset_audit_events",
}


def _sql_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _normalize_text_field(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    without_trailing_space = "\n".join(
        line.rstrip() for line in normalized.split("\n")
    )
    return without_trailing_space.strip()


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("optional text value is not a string")
    return _normalize_text_field(value)


def _json_string_list(value: object, *, field_name: str) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{field_name} is not valid JSON") from exc
    if not isinstance(value, list) or not all(
        isinstance(item, str) for item in value
    ):
        raise ValueError(f"{field_name} is not a list of strings")
    return value


def _content_payload(row: Mapping[str, object]) -> dict[str, object]:
    title = row["title"]
    expected_result = row["expected_result"]
    if not isinstance(title, str) or not isinstance(expected_result, str):
        raise ValueError("required content text is not a string")
    natural_steps = _json_string_list(
        row["natural_steps"], field_name="natural_steps"
    )
    tags = _json_string_list(row["tags"], field_name="tags")
    normalized_tags = sorted(
        {
            normalized_tag
            for tag in tags
            if (normalized_tag := _normalize_text_field(tag))
        }
    )
    return {
        "title": _normalize_text_field(title),
        "precondition": _normalize_optional_text(row["precondition"]),
        "natural_steps": [_normalize_text_field(step) for step in natural_steps],
        "expected_result": _normalize_text_field(expected_result),
        "priority": _normalize_optional_text(row["priority"]),
        "tags": normalized_tags,
    }


def _canonical_json_bytes(payload: Mapping[str, object]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _content_fingerprint(row: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical_json_bytes(_content_payload(row))).hexdigest()


def _constraint_names(items: list[dict[str, object]]) -> set[str]:
    return {str(item["name"]) for item in items if item.get("name")}


def _assert_upgrade_preconditions(bind: sa.Connection) -> list[dict[str, object]]:
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    required_tables = {
        "users",
        "requirements",
        "requirement_versions",
        "test_assets",
        "test_asset_versions",
        "test_asset_sources",
    }
    missing_tables = sorted(required_tables - existing_tables)
    if missing_tables:
        raise RuntimeError(
            "EvieAi Phase 1 preflight failed: missing required tables "
            f"{missing_tables}"
        )
    existing_new_tables = sorted(_NEW_TABLES & existing_tables)
    if existing_new_tables:
        raise RuntimeError(
            "EvieAi Phase 1 preflight failed: partial target schema exists "
            f"{existing_new_tables}"
        )

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "user_public_id" in user_columns:
        raise RuntimeError(
            "EvieAi Phase 1 preflight failed: users.user_public_id already exists"
        )

    source_columns = {
        str(column["name"])
        for column in inspector.get_columns("test_asset_sources")
    }
    expected_source_columns = {
        "id",
        "test_asset_source_id",
        "test_asset_pk",
        "requirement_pk",
        "requirement_version_pk",
        "source_identity_hash",
        "created_at",
        "created_by",
    }
    if source_columns != expected_source_columns:
        raise RuntimeError(
            "EvieAi Phase 1 preflight failed: test_asset_sources is not at the "
            "approved Phase 0 shape"
        )

    source_foreign_keys = _constraint_names(
        inspector.get_foreign_keys("test_asset_sources")
    )
    required_source_foreign_keys = {
        "fk_test_asset_sources_test_asset_pk_test_assets",
        "fk_test_asset_sources_requirement_pk_requirements",
        "fk_test_asset_sources_req_version_pk_requirement_versions",
    }
    if source_foreign_keys != required_source_foreign_keys:
        raise RuntimeError(
            "EvieAi Phase 1 preflight failed: test_asset_sources foreign keys "
            "do not match the approved Phase 0 shape"
        )

    source_rows = [
        dict(row)
        for row in bind.execute(
            sa.text(
                """
                SELECT
                    source.id,
                    source.test_asset_source_id,
                    source.requirement_pk,
                    source.requirement_version_pk,
                    requirement_version.requirement_pk AS actual_requirement_pk
                FROM test_asset_sources AS source
                LEFT JOIN requirement_versions AS requirement_version
                  ON requirement_version.id = source.requirement_version_pk
                ORDER BY source.id
                """
            )
        ).mappings()
    ]
    invalid_sources = [
        str(row["test_asset_source_id"])
        for row in source_rows
        if row["actual_requirement_pk"] is None
        or row["actual_requirement_pk"] != row["requirement_pk"]
    ]
    if invalid_sources:
        raise RuntimeError(
            "EvieAi Phase 1 preflight failed: Requirement source ownership is "
            f"invalid for public IDs {invalid_sources}"
        )

    return source_rows


def _active_content_claims(bind: sa.Connection) -> list[dict[str, object]]:
    rows = bind.execute(
        sa.text(
            """
            SELECT
                asset.id AS test_asset_pk,
                asset.test_asset_id,
                asset.project_code,
                asset.current_version_pk,
                version.id AS version_pk,
                version.test_asset_pk AS version_test_asset_pk,
                version.title,
                version.precondition,
                version.natural_steps,
                version.expected_result,
                version.priority,
                version.tags
            FROM test_assets AS asset
            LEFT JOIN test_asset_versions AS version
              ON version.id = asset.current_version_pk
            WHERE asset.deleted_at IS NULL
            ORDER BY asset.project_code, asset.test_asset_id
            """
        )
    ).mappings()

    claims: list[dict[str, object]] = []
    invalid_assets: list[str] = []
    fingerprint_failures: list[str] = []
    for row in rows:
        public_id = str(row["test_asset_id"])
        if (
            row["current_version_pk"] is None
            or row["version_pk"] is None
            or row["version_test_asset_pk"] != row["test_asset_pk"]
        ):
            invalid_assets.append(public_id)
            continue
        try:
            fingerprint = _content_fingerprint(row)
        except (TypeError, ValueError, json.JSONDecodeError):
            fingerprint_failures.append(public_id)
            continue
        claims.append(
            {
                "test_asset_pk": int(row["test_asset_pk"]),
                "test_asset_id": public_id,
                "project_code": str(row["project_code"]),
                "content_fingerprint": fingerprint,
            }
        )

    if invalid_assets:
        raise RuntimeError(
            "EvieAi Phase 1 preflight failed: active assets have an invalid current "
            f"version; asset public IDs={invalid_assets}"
        )
    if fingerprint_failures:
        raise RuntimeError(
            "EvieAi Phase 1 preflight failed: content fingerprint cannot be "
            f"computed; asset public IDs={fingerprint_failures}"
        )

    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for claim in claims:
        groups[
            (str(claim["project_code"]), str(claim["content_fingerprint"]))
        ].append(str(claim["test_asset_id"]))
    duplicates = [
        (project_code, public_ids)
        for (project_code, _fingerprint), public_ids in groups.items()
        if len(public_ids) > 1
    ]
    if duplicates:
        diagnostics = [
            {"project_code": project_code, "test_asset_ids": public_ids}
            for project_code, public_ids in duplicates
        ]
        raise RuntimeError(
            "EvieAi Phase 1 preflight failed: exact duplicate active assets exist; "
            f"groups={diagnostics}"
        )
    return claims


def _add_user_public_ids(bind: sa.Connection) -> None:
    op.add_column(
        "users",
        sa.Column("user_public_id", sa.String(length=64), nullable=True),
    )
    user_ids = [
        int(row[0])
        for row in bind.execute(sa.text("SELECT id FROM users ORDER BY id"))
    ]
    generated_ids: set[str] = set()
    for user_id in user_ids:
        public_id = f"usr_{uuid.uuid4().hex}"
        while public_id in generated_ids:
            public_id = f"usr_{uuid.uuid4().hex}"
        generated_ids.add(public_id)
        bind.execute(
            sa.text(
                "UPDATE users SET user_public_id = :user_public_id WHERE id = :user_id"
            ),
            {"user_public_id": public_id, "user_id": user_id},
        )

    public_ids = [
        row[0]
        for row in bind.execute(
            sa.text("SELECT user_public_id FROM users ORDER BY id")
        )
    ]
    if len(public_ids) != len(set(public_ids)) or any(
        not isinstance(public_id, str)
        or _USER_PUBLIC_ID_PATTERN.fullmatch(public_id) is None
        for public_id in public_ids
    ):
        raise RuntimeError("EvieAi Phase 1 user_public_id backfill validation failed")

    recreate = "always" if bind.dialect.name == "sqlite" else "auto"
    with op.batch_alter_table("users", recreate=recreate) as batch:
        batch.alter_column(
            "user_public_id",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        batch.create_unique_constraint(
            "uq_users_user_public_id",
            ["user_public_id"],
        )


def _generalize_test_asset_sources(
    bind: sa.Connection,
    source_rows: list[dict[str, object]],
) -> None:
    op.add_column(
        "test_asset_sources",
        sa.Column("source_type", sa.String(length=20), nullable=True),
    )
    bind.execute(
        sa.text(
            "UPDATE test_asset_sources SET source_type = :source_type "
            "WHERE source_type IS NULL"
        ),
        {"source_type": _SOURCE_TYPE_REQUIREMENT},
    )

    recreate = "always" if bind.dialect.name == "sqlite" else "auto"
    with op.batch_alter_table("test_asset_sources", recreate=recreate) as batch:
        batch.alter_column(
            "source_type",
            existing_type=sa.String(length=20),
            nullable=False,
        )
        batch.drop_index("ix_test_asset_sources_requirement_pk")
        batch.drop_index("ix_test_asset_sources_requirement_version_pk")
        batch.drop_constraint(
            "fk_test_asset_sources_requirement_pk_requirements",
            type_="foreignkey",
        )
        batch.drop_constraint(
            "fk_test_asset_sources_req_version_pk_requirement_versions",
            type_="foreignkey",
        )
        batch.drop_column("requirement_pk")
        batch.drop_column("requirement_version_pk")
        batch.create_check_constraint(
            "ck_test_asset_sources_source_type",
            _SOURCE_TYPE_CHECK,
        )
        batch.create_index(
            "ix_test_asset_sources_test_asset_pk",
            ["test_asset_pk"],
            unique=False,
        )
        batch.create_index(
            "ix_test_asset_sources_source_type",
            ["source_type"],
            unique=False,
        )

    op.create_table(
        "test_asset_requirement_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("test_asset_source_pk", sa.Integer(), nullable=False),
        sa.Column("requirement_pk", sa.Integer(), nullable=False),
        sa.Column("requirement_version_pk", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["test_asset_source_pk"],
            ["test_asset_sources.id"],
            name="fk_test_asset_req_sources_source_pk_sources",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requirement_pk"],
            ["requirements.id"],
            name="fk_test_asset_req_sources_requirement_pk_requirements",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requirement_version_pk"],
            ["requirement_versions.id"],
            name="fk_test_asset_req_sources_req_version_pk_req_versions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_test_asset_requirement_sources"),
        sa.UniqueConstraint(
            "test_asset_source_pk",
            name="uq_test_asset_requirement_sources_source_pk",
        ),
    )
    op.create_index(
        "ix_test_asset_req_sources_requirement_pk",
        "test_asset_requirement_sources",
        ["requirement_pk"],
        unique=False,
    )
    op.create_index(
        "ix_test_asset_req_sources_requirement_version_pk",
        "test_asset_requirement_sources",
        ["requirement_version_pk"],
        unique=False,
    )
    if source_rows:
        requirement_sources = sa.table(
            "test_asset_requirement_sources",
            sa.column("test_asset_source_pk", sa.Integer()),
            sa.column("requirement_pk", sa.Integer()),
            sa.column("requirement_version_pk", sa.Integer()),
        )
        op.bulk_insert(
            requirement_sources,
            [
                {
                    "test_asset_source_pk": int(row["id"]),
                    "requirement_pk": int(row["requirement_pk"]),
                    "requirement_version_pk": int(row["requirement_version_pk"]),
                }
                for row in source_rows
            ],
        )


def _create_phase1_tables(claims: list[dict[str, object]]) -> None:
    operation_values = _sql_values(_OPERATION_TYPES)
    review_status_values = _sql_values(_REVIEW_STATUS_CHECK)
    review_action_values = _sql_values(_REVIEW_ACTIONS)
    audit_event_values = _sql_values(_AUDIT_EVENT_TYPES)

    op.create_table(
        "test_asset_idempotency_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_code", sa.String(length=20), nullable=False),
        sa.Column("operation_type", sa.String(length=40), nullable=False),
        sa.Column("actor_or_client_id", sa.String(length=120), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("result_http_status", sa.Integer(), nullable=True),
        sa.Column("result_type", sa.String(length=64), nullable=True),
        sa.Column("test_asset_id", sa.String(length=64), nullable=True),
        sa.Column("test_asset_version_id", sa.String(length=64), nullable=True),
        sa.Column("test_asset_review_record_id", sa.String(length=64), nullable=True),
        sa.Column("created", sa.Boolean(), nullable=True),
        sa.Column("reused_existing", sa.Boolean(), nullable=True),
        sa.Column("changed", sa.Boolean(), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"operation_type IN ({operation_values})",
            name="ck_test_asset_idempotency_operation_type",
        ),
        sa.CheckConstraint(
            "generation >= 1",
            name="ck_test_asset_idempotency_generation",
        ),
        sa.CheckConstraint(
            "result_http_status IS NULL OR "
            "(result_http_status >= 100 AND result_http_status <= 599)",
            name="ck_test_asset_idempotency_http_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_test_asset_idempotency_records"),
        sa.UniqueConstraint(
            "project_code",
            "operation_type",
            "actor_or_client_id",
            "idempotency_key",
            name="uq_test_asset_idempotency_scope_key",
        ),
    )
    op.create_index(
        "ix_test_asset_idempotency_expires_at",
        "test_asset_idempotency_records",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_test_asset_idempotency_completed_at",
        "test_asset_idempotency_records",
        ["completed_at"],
        unique=False,
    )

    op.create_table(
        "test_asset_content_claims",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("test_asset_pk", sa.Integer(), nullable=False),
        sa.Column("project_code", sa.String(length=20), nullable=False),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["test_asset_pk"],
            ["test_assets.id"],
            name="fk_test_asset_content_claims_asset_pk_test_assets",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_test_asset_content_claims"),
        sa.UniqueConstraint(
            "project_code",
            "content_fingerprint",
            name="uq_test_asset_content_claims_project_fingerprint",
        ),
        sa.UniqueConstraint(
            "test_asset_pk",
            name="uq_test_asset_content_claims_test_asset_pk",
        ),
    )
    op.create_index(
        "ix_test_asset_content_claims_fingerprint",
        "test_asset_content_claims",
        ["content_fingerprint"],
        unique=False,
    )
    if claims:
        claim_table = sa.table(
            "test_asset_content_claims",
            sa.column("test_asset_pk", sa.Integer()),
            sa.column("project_code", sa.String(length=20)),
            sa.column("content_fingerprint", sa.String(length=64)),
        )
        op.bulk_insert(
            claim_table,
            [
                {
                    "test_asset_pk": claim["test_asset_pk"],
                    "project_code": claim["project_code"],
                    "content_fingerprint": claim["content_fingerprint"],
                }
                for claim in claims
            ],
        )

    op.create_table(
        "test_asset_review_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("test_asset_review_record_id", sa.String(length=64), nullable=False),
        sa.Column("test_asset_pk", sa.Integer(), nullable=False),
        sa.Column("test_asset_version_pk", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=False),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("review_action", sa.String(length=20), nullable=False),
        sa.Column("reviewer", sa.String(length=120), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(length=120), nullable=True),
        sa.Column("correlation_id", sa.String(length=120), nullable=True),
        sa.Column("operation_type", sa.String(length=40), nullable=False),
        sa.Column("idempotency_scope_hash", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=False),
        sa.Column("idempotency_generation", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"from_status IN ({review_status_values})",
            name="ck_test_asset_reviews_from_status",
        ),
        sa.CheckConstraint(
            f"to_status IN ({review_status_values})",
            name="ck_test_asset_reviews_to_status",
        ),
        sa.CheckConstraint(
            f"review_action IN ({review_action_values})",
            name="ck_test_asset_reviews_action",
        ),
        sa.CheckConstraint(
            "operation_type IN ('review_asset')",
            name="ck_test_asset_reviews_operation_type",
        ),
        sa.CheckConstraint(
            "idempotency_generation >= 1",
            name="ck_test_asset_reviews_idempotency_generation",
        ),
        sa.ForeignKeyConstraint(
            ["test_asset_pk"],
            ["test_assets.id"],
            name="fk_test_asset_reviews_asset_pk_test_assets",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["test_asset_version_pk"],
            ["test_asset_versions.id"],
            name="fk_test_asset_reviews_version_pk_asset_versions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_test_asset_review_records"),
        sa.UniqueConstraint(
            "test_asset_review_record_id",
            name="uq_test_asset_review_records_public_id",
        ),
    )
    op.create_index(
        "ix_test_asset_reviews_asset_pk",
        "test_asset_review_records",
        ["test_asset_pk"],
        unique=False,
    )
    op.create_index(
        "ix_test_asset_reviews_version_pk",
        "test_asset_review_records",
        ["test_asset_version_pk"],
        unique=False,
    )
    op.create_index(
        "ix_test_asset_reviews_reviewed_at",
        "test_asset_review_records",
        ["reviewed_at"],
        unique=False,
    )

    op.create_table(
        "test_asset_audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("test_asset_audit_event_id", sa.String(length=64), nullable=False),
        sa.Column("test_asset_pk", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("request_id", sa.String(length=120), nullable=True),
        sa.Column("correlation_id", sa.String(length=120), nullable=True),
        sa.Column("operation_type", sa.String(length=40), nullable=False),
        sa.Column("idempotency_scope_hash", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=False),
        sa.Column("idempotency_generation", sa.Integer(), nullable=False),
        sa.Column("related_test_asset_version_id", sa.String(length=64), nullable=True),
        sa.Column("related_test_asset_source_id", sa.String(length=64), nullable=True),
        sa.Column("related_review_record_id", sa.String(length=64), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("before_state_summary", sa.JSON(), nullable=True),
        sa.Column("after_state_summary", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"event_type IN ({audit_event_values})",
            name="ck_test_asset_audit_events_event_type",
        ),
        sa.CheckConstraint(
            f"operation_type IN ({operation_values})",
            name="ck_test_asset_audit_events_operation_type",
        ),
        sa.CheckConstraint(
            "idempotency_generation >= 1",
            name="ck_test_asset_audit_idempotency_generation",
        ),
        sa.ForeignKeyConstraint(
            ["test_asset_pk"],
            ["test_assets.id"],
            name="fk_test_asset_audit_events_asset_pk_test_assets",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_test_asset_audit_events"),
        sa.UniqueConstraint(
            "test_asset_audit_event_id",
            name="uq_test_asset_audit_events_public_id",
        ),
    )
    op.create_index(
        "ix_test_asset_audit_events_asset_pk",
        "test_asset_audit_events",
        ["test_asset_pk"],
        unique=False,
    )
    op.create_index(
        "ix_test_asset_audit_events_event_type",
        "test_asset_audit_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        "ix_test_asset_audit_events_created_at",
        "test_asset_audit_events",
        ["created_at"],
        unique=False,
    )


def _assert_phase1_source_backfill(bind: sa.Connection, expected_count: int) -> None:
    source_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM test_asset_sources")
    ).scalar_one()
    requirement_source_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM test_asset_requirement_sources")
    ).scalar_one()
    invalid_count = bind.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM test_asset_requirement_sources AS child
            JOIN test_asset_sources AS source
              ON source.id = child.test_asset_source_pk
            JOIN requirement_versions AS version
              ON version.id = child.requirement_version_pk
            WHERE source.source_type <> :source_type
               OR version.requirement_pk <> child.requirement_pk
            """
        ),
        {"source_type": _SOURCE_TYPE_REQUIREMENT},
    ).scalar_one()
    if (
        source_count != expected_count
        or requirement_source_count != expected_count
        or invalid_count != 0
    ):
        raise RuntimeError(
            "EvieAi Phase 1 Requirement source backfill validation failed"
        )


def upgrade() -> None:
    bind = op.get_bind()
    source_rows = _assert_upgrade_preconditions(bind)
    claims = _active_content_claims(bind)

    _add_user_public_ids(bind)
    _generalize_test_asset_sources(bind, source_rows)
    _create_phase1_tables(claims)
    _assert_phase1_source_backfill(bind, len(source_rows))


def _downgrade_blockers(bind: sa.Connection) -> list[str]:
    blockers: list[str] = []
    if bind.execute(sa.text("SELECT COUNT(*) FROM users")).scalar_one():
        blockers.append("users contain stable public identities")
    if bind.execute(
        sa.text("SELECT COUNT(*) FROM test_asset_review_records")
    ).scalar_one():
        blockers.append("review history exists")
    if bind.execute(
        sa.text("SELECT COUNT(*) FROM test_asset_audit_events")
    ).scalar_one():
        blockers.append("audit history exists")
    if bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM test_asset_sources "
            "WHERE source_type <> :requirement"
        ),
        {"requirement": _SOURCE_TYPE_REQUIREMENT},
    ).scalar_one():
        blockers.append("non-Requirement sources exist")
    if bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM test_asset_idempotency_records "
            "WHERE actor_or_client_id LIKE 'user:usr_%'"
        )
    ).scalar_one():
        blockers.append("public actor idempotency history exists")
    if bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM test_asset_sources "
            "WHERE created_by LIKE 'user:usr_%'"
        )
    ).scalar_one():
        blockers.append("public actor source history exists")

    source_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM test_asset_sources")
    ).scalar_one()
    child_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM test_asset_requirement_sources")
    ).scalar_one()
    invalid_source_count = bind.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM test_asset_sources AS source
            LEFT JOIN test_asset_requirement_sources AS child
              ON child.test_asset_source_pk = source.id
            LEFT JOIN requirement_versions AS version
              ON version.id = child.requirement_version_pk
            WHERE source.source_type <> :requirement
               OR child.id IS NULL
               OR version.id IS NULL
               OR version.requirement_pk <> child.requirement_pk
            """
        ),
        {"requirement": _SOURCE_TYPE_REQUIREMENT},
    ).scalar_one()
    if source_count != child_count or invalid_source_count:
        blockers.append("source main/subtype facts are inconsistent")
    return blockers


def _restore_phase0_sources(bind: sa.Connection) -> None:
    source_rows = [
        dict(row)
        for row in bind.execute(
            sa.text(
                """
                SELECT
                    source.id,
                    child.requirement_pk,
                    child.requirement_version_pk
                FROM test_asset_sources AS source
                JOIN test_asset_requirement_sources AS child
                  ON child.test_asset_source_pk = source.id
                ORDER BY source.id
                """
            )
        ).mappings()
    ]
    op.drop_index(
        "ix_test_asset_req_sources_requirement_version_pk",
        table_name="test_asset_requirement_sources",
    )
    op.drop_index(
        "ix_test_asset_req_sources_requirement_pk",
        table_name="test_asset_requirement_sources",
    )
    op.drop_table("test_asset_requirement_sources")

    op.add_column(
        "test_asset_sources",
        sa.Column("requirement_pk", sa.Integer(), nullable=True),
    )
    op.add_column(
        "test_asset_sources",
        sa.Column("requirement_version_pk", sa.Integer(), nullable=True),
    )
    for row in source_rows:
        bind.execute(
            sa.text(
                """
                UPDATE test_asset_sources
                SET requirement_pk = :requirement_pk,
                    requirement_version_pk = :requirement_version_pk
                WHERE id = :source_id
                """
            ),
            {
                "source_id": row["id"],
                "requirement_pk": row["requirement_pk"],
                "requirement_version_pk": row["requirement_version_pk"],
            },
        )

    with op.batch_alter_table(
        "test_asset_sources",
        recreate="always",
        partial_reordering=(
            (
                "id",
                "test_asset_source_id",
                "test_asset_pk",
                "requirement_pk",
                "requirement_version_pk",
                "source_identity_hash",
                "created_at",
                "created_by",
            ),
        ),
    ) as batch:
        batch.alter_column(
            "requirement_pk",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch.alter_column(
            "requirement_version_pk",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch.drop_index("ix_test_asset_sources_test_asset_pk")
        batch.drop_index("ix_test_asset_sources_source_type")
        batch.drop_constraint(
            "ck_test_asset_sources_source_type",
            type_="check",
        )
        batch.drop_column("source_type")
        batch.create_foreign_key(
            "fk_test_asset_sources_requirement_pk_requirements",
            "requirements",
            ["requirement_pk"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_foreign_key(
            "fk_test_asset_sources_req_version_pk_requirement_versions",
            "requirement_versions",
            ["requirement_version_pk"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index(
            "ix_test_asset_sources_requirement_pk",
            ["requirement_pk"],
            unique=False,
        )
        batch.create_index(
            "ix_test_asset_sources_requirement_version_pk",
            ["requirement_version_pk"],
            unique=False,
        )


def _remove_user_public_ids(bind: sa.Connection) -> None:
    recreate = "always" if bind.dialect.name == "sqlite" else "auto"
    with op.batch_alter_table("users", recreate=recreate) as batch:
        batch.drop_constraint("uq_users_user_public_id", type_="unique")
        batch.drop_column("user_public_id")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _NEW_TABLES.issubset(set(inspector.get_table_names())):
        raise RuntimeError(
            "EvieAi Phase 1 downgrade refused: target schema is incomplete"
        )
    blockers = _downgrade_blockers(bind)
    if blockers:
        raise RuntimeError(
            "EvieAi Phase 1 downgrade refused to prevent business data loss: "
            + "; ".join(blockers)
        )

    _restore_phase0_sources(bind)
    op.drop_index(
        "ix_test_asset_audit_events_created_at",
        table_name="test_asset_audit_events",
    )
    op.drop_index(
        "ix_test_asset_audit_events_event_type",
        table_name="test_asset_audit_events",
    )
    op.drop_index(
        "ix_test_asset_audit_events_asset_pk",
        table_name="test_asset_audit_events",
    )
    op.drop_table("test_asset_audit_events")
    op.drop_index(
        "ix_test_asset_reviews_reviewed_at",
        table_name="test_asset_review_records",
    )
    op.drop_index(
        "ix_test_asset_reviews_version_pk",
        table_name="test_asset_review_records",
    )
    op.drop_index(
        "ix_test_asset_reviews_asset_pk",
        table_name="test_asset_review_records",
    )
    op.drop_table("test_asset_review_records")
    op.drop_index(
        "ix_test_asset_content_claims_fingerprint",
        table_name="test_asset_content_claims",
    )
    op.drop_table("test_asset_content_claims")
    op.drop_index(
        "ix_test_asset_idempotency_completed_at",
        table_name="test_asset_idempotency_records",
    )
    op.drop_index(
        "ix_test_asset_idempotency_expires_at",
        table_name="test_asset_idempotency_records",
    )
    op.drop_table("test_asset_idempotency_records")
    _remove_user_public_ids(bind)
