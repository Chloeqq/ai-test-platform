from __future__ import annotations

import json
import sys
from datetime_compat import UTC
from datetime import datetime
from pathlib import Path
from typing import Any


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agent import DataGenerationAgent  # type: ignore  # noqa: E402
from cleanup_manager import mark_cleaned  # type: ignore  # noqa: E402
from index import main as agent_main  # type: ignore  # noqa: E402
from registry import list_pending_cleanup_entries, summarize_cleanup_retention, summarize_registry_entries  # type: ignore  # noqa: E402
from templates import summarize_template_library, summarize_template_migration  # type: ignore  # noqa: E402


def test_data_generation_agent_generates_records_and_relationships() -> None:
    response = DataGenerationAgent().generate(
        {
            "request_id": "req-1",
            "requirements": [
                {
                    "requirement_id": "user_seed",
                    "data_type": "user",
                    "quantity": 2,
                    "fields": [
                        {"name": "username", "type": "string", "prefix": "user", "unique": True},
                        {"name": "email", "type": "email", "prefix": "buyer", "unique": True},
                    ],
                },
                {
                    "requirement_id": "order_seed",
                    "data_type": "order",
                    "quantity": 2,
                    "relationships": ["user_seed"],
                    "fields": [
                        {"name": "order_no", "type": "string", "prefix": "ord", "unique": True},
                        {"name": "status", "type": "enum", "options": ["draft", "paid"]},
                    ],
                },
            ],
        }
    )

    assert response["version"] == "DataGenerationResponseV1"
    assert len(response["generated"]["user_seed"]) == 2
    assert response["generated"]["order_seed"][0]["relationships"]["user_seed"] == "user_seed-001"
    assert response["generated"]["order_seed"][1]["relationships"]["user_seed"] == "user_seed-002"
    assert response["validations"][0]["passed"] is True
    assert response["cleanup_instructions"][0]["record_ids"] == ["user_seed-001", "user_seed-002"]


def test_data_generation_agent_validates_unique_fields() -> None:
    response = DataGenerationAgent().generate(
        {
            "request_id": "req-dup",
            "requirements": [
                {
                    "requirement_id": "status_seed",
                    "data_type": "status",
                    "quantity": 2,
                    "fields": [
                        {"name": "status", "type": "enum", "options": ["same"], "unique": True},
                    ],
                }
            ],
        }
    )

    assert response["validations"][0]["passed"] is False
    assert "duplicate value" in " ".join(response["validations"][0]["errors"])
    assert response["generation_confidence"] == 0.75


def test_data_generation_agent_applies_template_when_fields_are_empty() -> None:
    response = DataGenerationAgent().generate(
        {
            "request_id": "req-template",
            "requirements": [
                {
                    "requirement_id": "product_seed",
                    "data_type": "product",
                    "template_key": "product_basic",
                    "quantity": 1,
                    "fields": [],
                }
            ],
        }
    )

    record = response["generated"]["product_seed"][0]
    assert record["values"]["product_name"].startswith("product-req-template")
    assert record["values"]["sku"].startswith("sku-req-template")
    assert record["values"]["status"] == "draft"
    assert "resolved template product_basic" in " ".join(response["warnings"])
    assert response["template_summary"]["catalog_version"] == "data-generation-template-catalog.v1"
    assert response["template_summary"]["request_resolved_template_counts"]["product_basic"] == 1
    assert response["template_summary"]["used_template_count"] == 1


def test_data_generation_agent_merges_template_and_requirement_overrides() -> None:
    response = DataGenerationAgent().generate(
        {
            "request_id": "req-override",
            "requirements": [
                {
                    "requirement_id": "user_seed",
                    "data_type": "user",
                    "template_key": "user_basic",
                    "quantity": 1,
                    "fields": [
                        {"name": "username", "type": "string", "prefix": "member", "unique": True},
                        {"name": "tier", "type": "enum", "options": ["silver", "gold"]},
                    ],
                }
            ],
        }
    )

    record = response["generated"]["user_seed"][0]
    assert record["values"]["username"].startswith("member-req-override")
    assert record["values"]["tier"] == "silver"
    assert "email" in record["values"]


def test_data_generation_agent_normalizes_request_tags_and_warns_on_duplicates() -> None:
    response = DataGenerationAgent().generate(
        {
            "request_id": "req-tags",
            "requirements": [
                {
                    "requirement_id": "user_seed",
                    "data_type": "user",
                    "template_key": "user_basic",
                    "quantity": 1,
                    "tags": [" Smoke ", "smoke", "VIP User"],
                }
            ],
        }
    )

    template_summary = response["template_summary"]
    warnings = " ".join(response["warnings"])
    assert template_summary["request_tag_counts"]["smoke"] == 2
    assert template_summary["request_tag_counts"]["vip-user"] == 1
    assert template_summary["request_unique_tag_count"] == 2
    assert template_summary["request_tag_warnings"]
    assert "duplicate tag collapsed: smoke" in warnings
    assert "VIP User -> vip-user" in warnings


def test_data_generation_agent_validates_pattern_and_email_shape() -> None:
    response = DataGenerationAgent().generate(
        {
            "request_id": "req-pattern",
            "requirements": [
                {
                    "requirement_id": "account_seed",
                    "data_type": "account",
                    "quantity": 1,
                    "fields": [
                        {"name": "code", "type": "string", "prefix": "acct", "pattern": r"^CODE-\d+$"},
                        {"name": "email", "type": "email", "prefix": "invalid email"},
                    ],
                }
            ],
        }
    )

    assert response["validations"][0]["passed"] is False
    errors = " ".join(response["validations"][0]["errors"])
    assert "does not match pattern" in errors
    assert "invalid email" in errors


def test_data_generation_agent_validates_missing_relationship_source() -> None:
    response = DataGenerationAgent().generate(
        {
            "request_id": "req-rel",
            "requirements": [
                {
                    "requirement_id": "order_seed",
                    "data_type": "order",
                    "quantity": 1,
                    "relationships": ["user_seed"],
                    "fields": [
                        {"name": "order_no", "type": "string", "prefix": "ord", "unique": True},
                    ],
                }
            ],
        }
    )

    assert response["validations"][0]["passed"] is False
    assert "missing relationship source user_seed" in " ".join(response["validations"][0]["errors"])


def test_data_generation_agent_warns_on_invalid_pattern_and_empty_enum_options() -> None:
    response = DataGenerationAgent().generate(
        {
            "request_id": "req-warn",
            "requirements": [
                {
                    "requirement_id": "misc_seed",
                    "data_type": "misc",
                    "quantity": 1,
                    "fields": [
                        {"name": "slug", "type": "string", "prefix": "slug", "pattern": r"[invalid"},
                        {"name": "state", "type": "enum", "options": []},
                    ],
                }
            ],
        }
    )

    warnings = " ".join(response["validations"][0]["warnings"])
    assert "pattern is invalid" in warnings
    assert "enum options are empty" in warnings


def test_data_generation_agent_persists_registry_entry(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    response = DataGenerationAgent(registry_path=registry_path).generate(
        {
            "request_id": "req-registry",
            "project": "demo",
            "requirements": [
                {
                    "requirement_id": "user_seed",
                    "data_type": "user",
                    "template_key": "user_basic",
                    "quantity": 2,
                }
            ],
        }
    )

    assert response["registry_entry"]["request_id"] == "req-registry"
    assert response["registry_entry"]["cleanup_status"] == "pending"
    saved = json.loads(registry_path.read_text(encoding="utf-8"))
    assert saved[0]["request_id"] == "req-registry"
    assert saved[0]["total_records"] == 2
    assert saved[0]["status"] == "generated"


def test_cleanup_manager_marks_registry_entry_cleaned(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    DataGenerationAgent(registry_path=registry_path).generate(
        {
            "request_id": "req-clean",
            "requirements": [
                {
                    "requirement_id": "user_seed",
                    "data_type": "user",
                    "template_key": "user_basic",
                    "quantity": 1,
                }
            ],
        }
    )

    updated = mark_cleaned(registry_path=registry_path, request_id="req-clean")
    assert updated is not None
    assert updated["cleanup_status"] == "cleaned"
    assert updated["status"] == "cleaned"
    assert updated["cleaned_at"]
    saved = json.loads(registry_path.read_text(encoding="utf-8"))
    assert saved[0]["cleanup_status"] == "cleaned"
    assert saved[0]["cleaned_at"]


def test_registry_summary_reports_pending_and_cleaned_entries(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    agent = DataGenerationAgent(registry_path=registry_path)
    agent.generate(
        {
            "request_id": "req-summary-1",
            "project": "demo",
            "environment": "staging",
            "requirements": [
                {
                    "requirement_id": "user_seed",
                    "data_type": "user",
                    "template_key": "user_basic",
                    "quantity": 1,
                }
            ],
        }
    )
    agent.generate(
        {
            "request_id": "req-summary-2",
            "project": "demo",
            "environment": "staging",
            "requirements": [
                {
                    "requirement_id": "status_seed",
                    "data_type": "status",
                    "quantity": 2,
                    "fields": [
                        {"name": "status", "type": "enum", "options": ["same"], "unique": True},
                    ],
                }
            ],
        }
    )
    mark_cleaned(registry_path=registry_path, request_id="req-summary-2")

    summary = summarize_registry_entries(registry_path)

    assert summary["total_entries"] == 2
    assert summary["pending_cleanup_count"] == 1
    assert summary["cleaned_count"] == 1
    assert summary["generated_with_errors_count"] == 0
    assert summary["project_counts"]["demo"] == 2
    assert summary["environment_counts"]["staging"] == 2
    assert summary["cleanup_status_counts"]["pending"] == 1
    assert summary["cleanup_status_counts"]["cleaned"] == 1
    assert summary["oldest_pending_request_id"] == "req-summary-1"


def test_pending_cleanup_entries_reports_queue_order(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    agent = DataGenerationAgent(registry_path=registry_path)
    agent.generate(
        {
            "request_id": "req-pending-1",
            "project": "demo",
            "requirements": [
                {
                    "requirement_id": "user_seed",
                    "data_type": "user",
                    "template_key": "user_basic",
                    "quantity": 1,
                }
            ],
        }
    )
    agent.generate(
        {
            "request_id": "req-pending-2",
            "project": "demo",
            "requirements": [
                {
                    "requirement_id": "product_seed",
                    "data_type": "product",
                    "template_key": "product_basic",
                    "quantity": 1,
                }
            ],
        }
    )
    mark_cleaned(registry_path=registry_path, request_id="req-pending-2")

    pending = list_pending_cleanup_entries(registry_path)

    assert pending["pending_items_count"] == 1
    assert pending["pending_cleanup_ratio"] == 0.5
    assert pending["oldest_pending_item"]["request_id"] == "req-pending-1"
    assert pending["pending_items"][0]["request_id"] == "req-pending-1"
    assert pending["pending_items"][0]["cleanup_status"] == "pending"
    assert pending["pending_items"][0]["age_seconds"] is not None


def test_cleanup_retention_summary_reports_overdue_pending_and_archive_candidates(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps(
            [
                {
                    "request_id": "req-overdue-pending",
                    "project": "demo",
                    "environment": "staging",
                    "status": "generated",
                    "cleanup_status": "pending",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "cleaned_at": "",
                    "total_records": 2,
                    "requirement_ids": ["user_seed"],
                },
                {
                    "request_id": "req-archive-cleaned",
                    "project": "demo",
                    "environment": "staging",
                    "status": "cleaned",
                    "cleanup_status": "cleaned",
                    "created_at": "2026-01-05T00:00:00+00:00",
                    "cleaned_at": "2026-01-10T00:00:00+00:00",
                    "total_records": 1,
                    "requirement_ids": ["product_seed"],
                },
                {
                    "request_id": "req-fresh-cleaned",
                    "project": "demo",
                    "environment": "staging",
                    "status": "cleaned",
                    "cleanup_status": "cleaned",
                    "created_at": "2026-03-15T00:00:00+00:00",
                    "cleaned_at": "2026-03-19T00:00:00+00:00",
                    "total_records": 1,
                    "requirement_ids": ["order_seed"],
                },
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = summarize_cleanup_retention(
        registry_path,
        pending_retention_days=7,
        cleaned_archive_days=30,
        now=datetime(2026, 3, 22, 0, 0, 0, tzinfo=UTC),
    )

    assert summary["retention_policy"]["pending_retention_days"] == 7
    assert summary["retention_policy"]["cleaned_archive_days"] == 30
    assert summary["overdue_pending_count"] == 1
    assert summary["archive_candidate_count"] == 1
    assert summary["oldest_overdue_pending_item"]["request_id"] == "req-overdue-pending"
    assert summary["oldest_archive_candidate_item"]["request_id"] == "req-archive-cleaned"
    assert summary["overdue_pending_items"][0]["age_anchor"] == "created_at"
    assert summary["archive_candidate_items"][0]["age_anchor"] == "cleaned_at"
    assert summary["archive_candidate_ratio"] == 0.5


def test_template_summary_reports_versions_and_tags() -> None:
    summary = summarize_template_library()

    assert summary["catalog_version"] == "data-generation-template-catalog.v1"
    assert summary["tag_rule"] == "trim + lowercase + spaces/underscores to hyphen + dedup"
    assert summary["total_templates"] == 3
    assert summary["version_counts"]["1.0.0"] == 3
    assert summary["tag_counts"]["template"] == 3
    assert summary["tag_counts"]["user"] == 1
    assert summary["default_template_by_data_type"]["product"] == "product_basic"
    assert summary["tag_warnings"] == []


def test_template_migration_summary_reports_outdated_templates_and_default_drift() -> None:
    summary = summarize_template_migration(
        template_library={
            "user_basic": {
                "version": "1.0.0",
                "data_type": "user",
                "tags": ["template", "user"],
                "fields": [{"name": "username"}],
            },
            "user_enterprise": {
                "version": "1.2.0",
                "data_type": "user",
                "tags": ["template", "user"],
                "fields": [{"name": "username"}, {"name": "tier"}],
            },
            "product_basic": {
                "version": "invalid",
                "data_type": "product",
                "tags": ["template", "product"],
                "fields": [{"name": "sku"}],
            },
        },
        default_template_by_data_type={
            "user": "user_basic",
            "product": "product_basic",
        },
    )

    assert summary["data_type_latest_versions"]["user"] == "1.2.0"
    assert summary["data_type_recommended_templates"]["user"] == "user_enterprise"
    assert summary["migration_candidate_count"] == 1
    assert summary["migration_candidates"][0]["template_key"] == "user_basic"
    assert summary["migration_candidates"][0]["recommended_template_key"] == "user_enterprise"
    assert summary["default_template_drift_count"] == 1
    assert summary["default_template_drift_items"][0]["default_template_key"] == "user_basic"
    assert summary["invalid_version_template_count"] == 1
    assert summary["invalid_version_items"][0]["template_key"] == "product_basic"
    assert summary["version_warnings"]


def test_cli_template_summary_prints_catalog_summary(tmp_path: Path, capsys: Any) -> None:
    registry_path = tmp_path / "registry.json"
    exit_code = agent_main(["--registry-path", str(registry_path), "--template-summary"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["catalog_version"] == "data-generation-template-catalog.v1"
    assert payload["total_templates"] == 3
    assert payload["tag_counts"]["template"] == 3


def test_cli_template_migration_summary_prints_governance_snapshot(tmp_path: Path, capsys: Any) -> None:
    registry_path = tmp_path / "registry.json"
    exit_code = agent_main(["--registry-path", str(registry_path), "--template-migration-summary"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["catalog_version"] == "data-generation-template-catalog.v1"
    assert payload["migration_candidate_count"] == 0
    assert payload["default_template_drift_count"] == 0
    assert payload["invalid_version_template_count"] == 0


def test_cli_cleanup_retention_summary_prints_governance_snapshot(tmp_path: Path, capsys: Any) -> None:
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps(
            [
                {
                    "request_id": "req-overdue",
                    "project": "demo",
                    "environment": "test",
                    "status": "generated",
                    "cleanup_status": "pending",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "cleaned_at": "",
                    "total_records": 1,
                    "requirement_ids": ["user_seed"],
                }
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = agent_main(["--registry-path", str(registry_path), "--cleanup-retention-summary"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["retention_policy"]["pending_retention_days"] == 7
    assert payload["overdue_pending_count"] == 1
    assert payload["archive_candidate_count"] == 0
