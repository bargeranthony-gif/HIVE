from __future__ import annotations

from datetime import datetime

from .governance import (
    ActionRequest,
    Decision,
    ExecutionResult,
    GovernanceGate,
)


class MockExecutor:
    """In-memory executor. It cannot perform real-world actions."""

    def __init__(self):
        self.state: dict[str, str] = {}
        self.side_effect_count = 0
        self.events: list[dict] = []
        self._completed: dict[str, ExecutionResult] = {}

    def execute(
        self,
        request: ActionRequest,
        decision: Decision,
    ) -> ExecutionResult:
        """Reject direct execution based on caller-supplied decisions."""
        if decision.disposition != "ALLOW":
            raise PermissionError(
                "Execution blocked: decision is not ALLOW."
            )

        raise PermissionError(
            "Direct execution using a supplied Decision is prohibited. "
            "Use execute_if_allowed() so authorization is evaluated "
            "at the execution boundary."
        )

    def execute_authorized(
        self,
        gate: GovernanceGate,
        source,
        request: ActionRequest,
        approval=None,
        *,
        now: datetime | None = None,
    ) -> Decision | ExecutionResult:
        """Evaluate authorization immediately before the mock side effect."""

        # Require the actual gate implementation, not an object that merely
        # imitates its evaluate() method.
        if type(gate) is not GovernanceGate:
            raise TypeError("A genuine GovernanceGate instance is required.")

        decision = gate.evaluate(
            source,
            request,
            approval,
            now=now,
        )

        if decision.disposition != "ALLOW":
            return decision

        # Defense in depth: ensure the decision covers this exact request.
        expected_digest = gate.digest(request)
        if decision.action_digest != expected_digest:
            raise PermissionError(
                "Execution blocked: action digest does not match request."
            )

        return self._execute_allowed(request, decision)

    def _execute_allowed(
        self,
        request: ActionRequest,
        decision: Decision,
    ) -> ExecutionResult:
        """Internal execution path, reached only after gate evaluation."""

        if decision.action_digest in self._completed:
            previous = self._completed[decision.action_digest]
            return ExecutionResult(
                result_id=previous.result_id,
                target=previous.target,
                resulting_status=previous.resulting_status,
                side_effect_count=self.side_effect_count,
                replayed=True,
            )

        self.side_effect_count += 1
        self.state[request.target] = str(request.parameters["status"])

        result = ExecutionResult(
            result_id=f"MOCK-{self.side_effect_count:04d}",
            target=request.target,
            resulting_status=self.state[request.target],
            side_effect_count=self.side_effect_count,
            replayed=False,
        )

        self._completed[decision.action_digest] = result

        self.events.append({
            "result_id": result.result_id,
            "target": result.target,
            "status": result.resulting_status,
            "action_digest": decision.action_digest,
            "side_effect_count": self.side_effect_count,
        })

        return result


def execute_if_allowed(
    gate: GovernanceGate,
    executor: MockExecutor,
    source,
    request: ActionRequest,
    approval=None,
    *,
    now: datetime | None = None,
):
    """Evaluate authorization at the executor boundary before execution."""
    return executor.execute_authorized(
        gate,
        source,
        request,
        approval,
        now=now,
    )
