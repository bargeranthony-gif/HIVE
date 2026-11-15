from datetime import datetime, timedelta, timezone

import pytest

from hive.governance import (
    ActionRequest,
    Approval,
    GovernanceGate,
    SourceRecord,
    canonical_action_digest,
    read_source_summary,
)
from hive.mock_executor import MockExecutor, execute_if_allowed


NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)

SOURCE = SourceRecord(
    source_id="SOURCE-001",
    original_text=(
        "Purchase P-001: awaiting owner approval. "
        "No approval has been recorded."
    ),
    target_id="P-001",
    recorded_status="pending",
    approval_recorded=False,
)


def make_request(target="P-001"):
    return ActionRequest(
        actor="synthetic-demo-operator",
        action="set_purchase_status",
        target=target,
        parameters={"status": "approved"},
        scope="purchase:P-001:status",
        environment="isolated-test",
    )


def make_approval(gate, request):
    return Approval(
        approval_id="SYNTHETIC-APPROVAL-001",
        approver_id="SYNTHETIC-OWNER-001",
        action_digest=gate.digest(request),
        scope=request.scope,
        issued_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=10),
    )


def test_t01_contradictory_source_is_held_without_side_effect():
    gate = GovernanceGate(allow_synthetic_approvals=True)
    executor = MockExecutor()
    request = make_request()

    result = execute_if_allowed(gate, executor, SOURCE, request, now=NOW)

    assert result.disposition == "HOLD"
    assert result.approval_state == "UNKNOWN / NOT_RECORDED"
    assert executor.side_effect_count == 0
    assert executor.state == {}
    assert SOURCE.recorded_status == "pending"
    assert SOURCE.original_text.endswith("No approval has been recorded.")


def test_t02_missing_approval_remains_unknown_not_denied():
    gate = GovernanceGate(allow_synthetic_approvals=True)
    decision = gate.evaluate(SOURCE, make_request(), approval=None, now=NOW)

    assert decision.disposition == "HOLD"
    assert decision.approval_state == "UNKNOWN / NOT_RECORDED"
    assert "No approval is inferred" in decision.rationale


def test_read_only_positive_control_preserves_source():
    before = SOURCE
    summary = read_source_summary(SOURCE)

    assert summary["source_id"] == "SOURCE-001"
    assert summary["recorded_status"] == "pending"
    assert summary["approval_state"] == "UNKNOWN / NOT_RECORDED"
    assert SOURCE == before


def test_t03_exact_synthetic_approval_allows_one_mock_action():
    gate = GovernanceGate(allow_synthetic_approvals=True)
    executor = MockExecutor()
    request = make_request()
    approval = make_approval(gate, request)

    result = execute_if_allowed(
        gate, executor, SOURCE, request, approval, now=NOW
    )

    assert result.resulting_status == "approved"
    assert result.side_effect_count == 1
    assert result.replayed is False
    assert executor.state == {"P-001": "approved"}
    assert len(executor.events) == 1

    # The evidence record itself remains unchanged.
    assert SOURCE.recorded_status == "pending"
    assert SOURCE.approval_recorded is False


def test_t04_replay_does_not_repeat_mock_side_effect():
    gate = GovernanceGate(allow_synthetic_approvals=True)
    executor = MockExecutor()
    request = make_request()
    approval = make_approval(gate, request)

    first = execute_if_allowed(
        gate, executor, SOURCE, request, approval, now=NOW
    )
    second = execute_if_allowed(
        gate, executor, SOURCE, request, approval, now=NOW
    )

    assert first.result_id == second.result_id
    assert second.replayed is True
    assert executor.side_effect_count == 1
    assert len(executor.events) == 1


def test_t05_changed_target_invalidates_approval():
    gate = GovernanceGate(allow_synthetic_approvals=True)
    executor = MockExecutor()
    original_request = make_request("P-001")
    approval = make_approval(gate, original_request)

    changed_request = make_request("P-002")

    result = execute_if_allowed(
        gate, executor, SOURCE, changed_request, approval, now=NOW
    )

    assert result.disposition == "HOLD"
    assert executor.side_effect_count == 0
    assert executor.state == {}


def test_synthetic_approval_is_disabled_by_default():
    gate = GovernanceGate()
    request = make_request()
    approval = make_approval(gate, request)

    decision = gate.evaluate(SOURCE, request, approval, now=NOW)

    assert decision.disposition == "HOLD"
    assert decision.approval_state == "UNKNOWN / TEST_APPROVAL_DISABLED"


def test_expired_approval_is_held():
    gate = GovernanceGate(allow_synthetic_approvals=True)
    request = make_request()
    approval = Approval(
        approval_id="EXPIRED-001",
        approver_id="SYNTHETIC-OWNER-001",
        action_digest=gate.digest(request),
        scope=request.scope,
        issued_at=NOW - timedelta(hours=2),
        expires_at=NOW - timedelta(hours=1),
    )

    decision = gate.evaluate(SOURCE, request, approval, now=NOW)

    assert decision.disposition == "HOLD"
    assert decision.approval_state == "EXPIRED"


def test_action_digest_changes_when_parameters_change():
    original = make_request()
    changed = ActionRequest(
        actor=original.actor,
        action=original.action,
        target=original.target,
        parameters={"status": "cancelled"},
        scope=original.scope,
        environment=original.environment,
    )

    assert canonical_action_digest(
        actor=original.actor,
        action=original.action,
        target=original.target,
        parameters=original.parameters,
        scope=original.scope,
        environment=original.environment,
    ) != canonical_action_digest(
        actor=changed.actor,
        action=changed.action,
        target=changed.target,
        parameters=changed.parameters,
        scope=changed.scope,
        environment=changed.environment,
    )


def test_executor_rejects_non_allow_decision():
    gate = GovernanceGate()
    executor = MockExecutor()
    request = make_request()
    decision = gate.evaluate(SOURCE, request, now=NOW)

    with pytest.raises(PermissionError):
        executor.execute(request, decision)

    assert executor.side_effect_count == 0
