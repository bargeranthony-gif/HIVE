from __future__ import annotations

from dataclasses import dataclass
from .governance import (
    ActionRequest,
    Decision,
    ExecutionResult,
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
        if decision.disposition != "ALLOW":
            raise PermissionError("Execution blocked: decision is not ALLOW.")

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
    gate,
    executor: MockExecutor,
    source,
    request: ActionRequest,
    approval=None,
    *,
    now=None,
):
    """Evaluate first; invoke the mock executor only on ALLOW."""
    decision = gate.evaluate(source, request, approval, now=now)

    if decision.disposition != "ALLOW":
        return decision

    return executor.execute(request, decision)
