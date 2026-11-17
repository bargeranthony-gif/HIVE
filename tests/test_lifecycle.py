import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from hive.capabilities import add_capability
from hive.db import initialize
from hive.governance import (
    ActionRequest,
    Approval,
    GovernanceGate,
    SourceRecord,
)
from hive.mock_executor import MockExecutor
from hive.planner import PlanStep
from hive.repositories import add_repository

from hive.lifecycle import (
    create_persisted_plan,
    execute_plan_action,
    store_plan_approval,
)


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.setenv("HIVE_HOME", str(tmp_path))
    initialize()

    repository_id = add_repository(
        "https://github.com/example/hive-lifecycle"
    )

    add_capability(
        repository_id,
        "browser.inspect",
        description="Browser inspection",
        evidence_level="test_verified",
        evidence="Lifecycle integration test fixture",
    )

    prepared = create_persisted_plan(
        "Inspect a website",
        [
            PlanStep(
                "inspect",
                "Inspect the target website",
                required_capabilities=("browser.inspect",),
            )
        ],
        repository_id=repository_id,
    )

    gate = GovernanceGate(allow_synthetic_approvals=True)
    executor = MockExecutor()

    request = ActionRequest(
        actor="hive-lifecycle-test",
        action="set_purchase_status",
        target="purchase-lifecycle-001",
        parameters={"status": "approved"},
        scope="lifecycle-test",
        environment="synthetic",
    )

    source = SourceRecord(
        source_id="source-lifecycle-001",
        original_text="Synthetic lifecycle test source",
        target_id="purchase-lifecycle-001",
        recorded_status="pending",
        approval_recorded=True,
    )

    now = datetime.now(timezone.utc)

    approval = Approval(
        approval_id="approval-lifecycle-001",
        approver_id="synthetic-test-approver",
        action_digest=gate.digest(request),
        scope=request.scope,
        issued_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(minutes=10),
        issuer_type="synthetic_test_fixture",
    )

    return {
        "repository_id": repository_id,
        "prepared": prepared,
        "gate": gate,
        "executor": executor,
        "request": request,
        "source": source,
        "approval": approval,
        "now": now,
        "database": tmp_path / "hive.db",
    }


def test_plan_is_assessed_and_persisted(environment):
    prepared = environment["prepared"]

    assert prepared.plan_id
    assert prepared.assessment.ready is True
    assert prepared.identity.digest
    assert prepared.identity.repository_id == environment["repository_id"]

    with sqlite3.connect(environment["database"]) as conn:
        row = conn.execute(
            """
            SELECT repository_id, identity_digest, status
            FROM plans
            WHERE plan_id = ?
            """,
            (prepared.plan_id,),
        ).fetchone()

    assert row == (
        environment["repository_id"],
        prepared.identity.digest,
        "draft",
    )


def test_approved_action_executes_and_is_linked_to_plan(environment):
    prepared = environment["prepared"]
    approval = environment["approval"]

    store_plan_approval(prepared.plan_id, approval)

    result = execute_plan_action(
        prepared.plan_id,
        environment["source"],
        environment["request"],
        approval.approval_id,
        environment["gate"],
        environment["executor"],
        now=environment["now"],
    )

    assert result.plan_id == prepared.plan_id
    assert result.decision.disposition == "ALLOW"
    assert result.decision_id
    assert result.execution_result is not None
    assert result.execution_result.resulting_status == "approved"
    assert environment["executor"].side_effect_count == 1

    with sqlite3.connect(environment["database"]) as conn:
        decision = conn.execute(
            """
            SELECT plan_id, disposition, approval_id
            FROM governance_decisions
            WHERE decision_id = ?
            """,
            (result.decision_id,),
        ).fetchone()

        execution = conn.execute(
            """
            SELECT plan_id, decision_id, action_digest, execution_type
            FROM execution_records
            WHERE result_id = ?
            """,
            (result.execution_result.result_id,),
        ).fetchone()

    assert decision == (
        prepared.plan_id,
        "ALLOW",
        approval.approval_id,
    )

    assert execution == (
        prepared.plan_id,
        result.decision_id,
        approval.action_digest,
        "MOCK",
    )


def test_revoked_approval_cannot_execute(environment):
    from hive.governance_store import revoke_approval

    prepared = environment["prepared"]
    approval = environment["approval"]

    store_plan_approval(prepared.plan_id, approval)
    assert revoke_approval(approval.approval_id) is True

    result = execute_plan_action(
        prepared.plan_id,
        environment["source"],
        environment["request"],
        approval.approval_id,
        environment["gate"],
        environment["executor"],
        now=environment["now"],
    )

    assert result.decision.disposition == "HOLD"
    assert result.execution_result is None
    assert environment["executor"].side_effect_count == 0

    with sqlite3.connect(environment["database"]) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM execution_records"
        ).fetchone()[0]

    assert count == 0


def test_action_mismatch_cannot_execute(environment):
    prepared = environment["prepared"]
    approval = environment["approval"]

    store_plan_approval(prepared.plan_id, approval)

    altered_request = ActionRequest(
        actor=environment["request"].actor,
        action=environment["request"].action,
        target=environment["request"].target,
        parameters={"status": "rejected"},
        scope=environment["request"].scope,
        environment=environment["request"].environment,
    )

    result = execute_plan_action(
        prepared.plan_id,
        environment["source"],
        altered_request,
        approval.approval_id,
        environment["gate"],
        environment["executor"],
        now=environment["now"],
    )

    assert result.decision.disposition == "HOLD"
    assert result.execution_result is None
    assert environment["executor"].side_effect_count == 0
