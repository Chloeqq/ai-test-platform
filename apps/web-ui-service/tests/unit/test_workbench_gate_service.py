# ruff: noqa: E402
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


WEB_UI_ROOT = Path(__file__).resolve().parents[2]
if str(WEB_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_UI_ROOT))

from app.services import workbench_gate_service as gate_service
from app.services import workbench_state_store as state_store


def test_gate_service_upsert_approve_and_revoke(tmp_path: Path, monkeypatch) -> None:
    gate_file = tmp_path / "execution-gate-decisions.json"
    monkeypatch.setattr(state_store, "EXECUTION_GATE_DECISIONS_FILE", gate_file)
    monkeypatch.setattr(state_store, "WEB_UI_DEFAULT_STATE_DIR", tmp_path)
    monkeypatch.setattr(state_store, "WEB_UI_RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(state_store, "WEB_UI_REPORTING_DIR", tmp_path / "reporting")
    monkeypatch.setattr(state_store, "AI_CASES_ROOT", tmp_path / "ai-generated")
    monkeypatch.setattr(state_store, "ALLURE_SNAPSHOTS_ROOT", tmp_path / "snapshots")
    state_store.ensure_dirs()

    monkeypatch.setattr(gate_service.SETTINGS, "execution_gate_dual_approval_enabled", True, raising=False)
    monkeypatch.setattr(gate_service.SETTINGS, "execution_gate_dual_approval_bypass_roles", ["admin"], raising=False)

    payload = SimpleNamespace(
        project="default",
        run_id="RUN-GATE-UNIT-1",
        case_id="tc-product-001",
        page="product",
        decision="block",
        note="need block",
    )
    actor = {"confirmed_by": "owner", "confirmed_by_role": "qa-lead", "confirmed_by_source": "x-user-name"}

    created = gate_service.upsert_execution_gate_decision(payload, actor=actor)
    assert created["approval_status"] == "pending_second_approval"
    assert created["decided_by"] == "owner"

    approved = gate_service.approve_execution_gate_decision(
        project="default",
        run_id="RUN-GATE-UNIT-1",
        page="product",
        actor={"confirmed_by": "betty", "confirmed_by_role": "admin"},
        note="approved",
    )
    assert approved["approval_status"] == "approved"
    assert approved["second_approver"] == "betty"

    revoked = gate_service.revoke_execution_gate_decision(
        project="default",
        run_id="RUN-GATE-UNIT-1",
        page="product",
        actor={"confirmed_by": "betty", "confirmed_by_role": "admin"},
        note="revoke",
    )
    assert revoked["record_status"] == "revoked"
    assert revoked["revoked_by"] == "betty"

    saved = json.loads(gate_file.read_text(encoding="utf-8"))
    assert saved[0]["record_status"] == "revoked"
    assert saved[0]["approval_status"] == "approved"


def test_gate_service_permission_and_policy_baseline(monkeypatch) -> None:
    monkeypatch.setattr(gate_service.SETTINGS, "execution_gate_decision_privileged_roles", ["admin", "qa-lead"], raising=False)
    monkeypatch.setattr(gate_service.SETTINGS, "execution_gate_dual_approval_enabled", True, raising=False)
    monkeypatch.setattr(gate_service.SETTINGS, "execution_gate_dual_approval_bypass_roles", ["admin", "release-manager"], raising=False)

    gate_service.require_execution_gate_decision_permission({"confirmed_by_role": "qa-lead"}, "allow")
    gate_service.require_execution_gate_decision_permission({"confirmed_by_role": "viewer"}, "manual_review")

    with pytest.raises(Exception):
        gate_service.require_execution_gate_decision_permission({"confirmed_by_role": "viewer"}, "block")

    baseline = gate_service.execution_gate_policy_baseline()
    assert baseline["manual_override_boundary"]["dual_approval"]["enabled"] is True
    assert baseline["manual_override_boundary"]["dual_approval"]["bypass_roles"] == ["admin", "release-manager"]
    assert "manual_review" in baseline["system_decision_rules"]
