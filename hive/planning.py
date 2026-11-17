from __future__ import annotations

from dataclasses import dataclass

from .capabilities import (
    CapabilityEvaluation,
    DEFAULT_MINIMUM_EVIDENCE,
    evaluate_capabilities,
    get_capabilities,
)
from .planner import PlanStep, TaskPlan, build_plan


@dataclass(frozen=True)
class PlanningAssessment:
    """Read-only assessment combining plan structure and capability evidence."""

    plan: TaskPlan
    capability_evaluation: CapabilityEvaluation
    missing_by_step: tuple[tuple[str, str], ...]
    insufficient_by_step: tuple[tuple[str, str], ...]
    minimum_evidence_level: str

    @property
    def ready(self) -> bool:
        return self.plan.ready and self.capability_evaluation.ready

    def to_dict(self) -> dict:
        return {
            "objective": self.plan.objective,
            "ready": self.ready,
            "minimum_evidence_level": self.minimum_evidence_level,
            "ordered_steps": [
                {
                    "step_id": step.step_id,
                    "description": step.description,
                    "depends_on": list(step.depends_on),
                    "required_capabilities": list(
                        step.required_capabilities
                    ),
                }
                for step in self.plan.ordered_steps
            ],
            "capability_evaluation": self.capability_evaluation.to_dict(),
            "missing_by_step": [
                {"step_id": step, "capability": capability}
                for step, capability in self.missing_by_step
            ],
            "insufficient_by_step": [
                {"step_id": step, "capability": capability}
                for step, capability in self.insufficient_by_step
            ],
        }


def assess_plan(
    objective: str,
    steps: list[PlanStep] | tuple[PlanStep, ...],
    *,
    minimum_evidence_level: str = DEFAULT_MINIMUM_EVIDENCE,
    repository_id: int | None = None,
) -> PlanningAssessment:
    """
    Build and assess a plan against registered capability evidence.

    This operation is read-only. It does not authorize actions, create
    approvals, write governance records, or execute plan steps.
    """

    records = get_capabilities(repository_id)

    registered = {record.name for record in records}

    # First validate and dependency-order the proposed plan.
    # Registered capabilities satisfy structural availability here;
    # evidence sufficiency is evaluated separately below.
    plan = build_plan(
        objective,
        steps,
        available_capabilities=registered,
    )

    required = tuple(
        dict.fromkeys(
            capability
            for step in plan.ordered_steps
            for capability in step.required_capabilities
        )
    )

    evaluation = evaluate_capabilities(
        required,
        minimum_evidence_level=minimum_evidence_level,
        repository_id=repository_id,
    )

    missing_names = set(evaluation.missing_capabilities)
    insufficient_names = set(evaluation.insufficient_capabilities)

    missing_by_step = tuple(
        (step.step_id, capability)
        for step in plan.ordered_steps
        for capability in step.required_capabilities
        if capability in missing_names
    )

    insufficient_by_step = tuple(
        (step.step_id, capability)
        for step in plan.ordered_steps
        for capability in step.required_capabilities
        if capability in insufficient_names
    )

    return PlanningAssessment(
        plan=plan,
        capability_evaluation=evaluation,
        missing_by_step=missing_by_step,
        insufficient_by_step=insufficient_by_step,
        minimum_evidence_level=minimum_evidence_level,
    )
