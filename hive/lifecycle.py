from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .governance import (
    ActionRequest,
    Approval,
    Decision,
    ExecutionResult,
    GovernanceGate,
    SourceRecord,
)
from .governance_store import (
    get_plan,
    get_plan_approval,
    record_decision,
    record_execution,
    store_approval,
    store_plan_identity,
)
from .mock_executor import MockExecutor
from .plan_identity import PlanIdentity, create_plan_identity
from .planner import PlanStep
from .planning import (
    DEFAULT_MINIMUM_EVIDENCE,
    PlanningAssessment,
    assess_plan,
)


@dataclass(frozen=True)
class PreparedPlan:
    """A plan assessment paired with its persisted immutable identity."""

    plan_id: str
    assessment: PlanningAssessment
    identity: PlanIdentity


@dataclass(frozen=True)
class LifecycleExecutionResult:
    """Persisted governance outcome and optional mock execution result."""

    plan_id: str
    decision: Decision
    decision_id: str
    execution_result: ExecutionResult | None


def create_persisted_plan(
    objective: str,
    steps: list[PlanStep] | tuple[PlanStep, ...],
    *,
    repository_id: int,
    minimum_evidence_level: str = DEFAULT_MINIMUM_EVIDENCE,
) -> PreparedPlan:
    """
    Assess a plan and persist its immutable repository-scoped identity.

    An unready plan is never persisted by this function.
    """
    assessment = assess_plan(
        objective,
        steps,
        minimum_evidence_level=minimum_evidence_level,
        repository_id=repository_id,
    )

    if not assessment.ready:
        raise ValueError(
            "Plan is not ready: required capabilities or evidence are missing"
        )

    identity = create_plan_identity(assessment, repository_id)
    plan_id = store_plan_identity(identity)

    return PreparedPlan(
        plan_id=plan_id,
        assessment=assessment,
        identity=identity,
    )


def store_plan_approval(
    plan_id: str,
    approval: Approval,
) -> None:
    """Store an approval explicitly linked to an existing plan."""
    if not isinstance(approval, Approval):
        raise TypeError("approval must be an Approval instance")

    if get_plan(plan_id) is None:
        raise ValueError(f"Unknown plan: {plan_id}")

    store_approval(approval, plan_id=plan_id)


def execute_plan_action(
    plan_id: str,
    source: SourceRecord,
    request: ActionRequest,
    approval_id: str,
    gate: GovernanceGate,
    executor: MockExecutor,
    *,
    now: datetime | None = None,
) -> LifecycleExecutionResult:
    """
    Authorize and execute one action within a persisted plan.

    Only approvals linked to plan_id are eligible. The executor independently
    evaluates governance immediately before its mock side effect.

    This coordinates persistence and mock execution; it does not provide an
    atomic transaction spanning SQLite and the in-memory executor.
    """
    if get_plan(plan_id) is None:
        raise ValueError(f"Unknown plan: {plan_id}")

    if type(gate) is not GovernanceGate:
        raise TypeError("A genuine GovernanceGate instance is required")

    if type(executor) is not MockExecutor:
        raise TypeError("Only the MockExecutor is supported by this lifecycle")

    if not isinstance(source, SourceRecord):
        raise TypeError("source must be a SourceRecord instance")

    if not isinstance(request, ActionRequest):
        raise TypeError("request must be an ActionRequest instance")

    approval = get_plan_approval(approval_id, plan_id)

    # Capture the expected decision, then let the executor independently
    # re-evaluate authorization at the execution boundary.
    preliminary_decision = gate.evaluate(
        source,
        request,
        approval,
        now=now,
    )

    outcome = executor.execute_authorized(
        gate,
        source,
        request,
        approval,
        now=now,
    )

    if isinstance(outcome, Decision):
        # HOLD outcomes are persisted, but never create execution records.
        decision = outcome
        execution_result = None
    elif isinstance(outcome, ExecutionResult):
        if preliminary_decision.disposition != "ALLOW":
            raise RuntimeError(
                "Executor returned an execution result without a prior ALLOW"
            )

        decision = preliminary_decision
        execution_result = outcome
    else:
        raise TypeError("Executor returned an unsupported result type")

    decision_id = record_decision(
        decision,
        request,
        source,
        approval=approval,
        plan_id=plan_id,
    )

    if execution_result is not None:
        record_execution(
            execution_result,
            decision.action_digest,
            plan_id=plan_id,
            decision_id=decision_id,
        )

    return LifecycleExecutionResult(
        plan_id=plan_id,
        decision=decision,
        decision_id=decision_id,
        execution_result=execution_result,
    )
