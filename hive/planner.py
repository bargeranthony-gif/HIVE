from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


class PlanValidationError(ValueError):
    """Raised when a proposed task plan is structurally invalid."""


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    description: str
    depends_on: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class TaskPlan:
    objective: str
    ordered_steps: tuple[PlanStep, ...]
    missing_capabilities: tuple[tuple[str, str], ...]

    @property
    def ready(self) -> bool:
        return not self.missing_capabilities

    def to_dict(self) -> dict:
        return {
            "objective": self.objective,
            "ready": self.ready,
            "ordered_steps": [
                {
                    "step_id": step.step_id,
                    "description": step.description,
                    "depends_on": list(step.depends_on),
                    "required_capabilities": list(step.required_capabilities),
                }
                for step in self.ordered_steps
            ],
            "missing_capabilities": [
                {"step_id": step_id, "capability": capability}
                for step_id, capability in self.missing_capabilities
            ],
        }


def _validate_name(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PlanValidationError(f"{label} must be a non-empty string")
    if value != value.strip():
        raise PlanValidationError(
            f"{label} cannot contain surrounding whitespace"
        )
    return value


def _validate_tuple(values: object, label: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise PlanValidationError(f"{label} must be a tuple")
    validated = tuple(_validate_name(value, label) for value in values)
    if len(set(validated)) != len(validated):
        raise PlanValidationError(f"{label} cannot contain duplicates")
    return validated


def _validate_available_capabilities(
    values: Iterable[str],
) -> frozenset[str]:
    if isinstance(values, (str, bytes)):
        raise PlanValidationError(
            "Available capabilities must be a collection, not a string"
        )
    try:
        capabilities = tuple(values)
    except TypeError as exc:
        raise PlanValidationError(
            "Available capabilities must be iterable"
        ) from exc
    return frozenset(
        _validate_name(value, "Available capability")
        for value in capabilities
    )


def build_plan(
    objective: str,
    steps: Iterable[PlanStep],
    available_capabilities: Iterable[str] = (),
) -> TaskPlan:
    """
    Validate and dependency-order a proposed task plan.

    This function only constructs a plan. It does not execute actions,
    authorize operations, or modify external systems.
    """
    objective = _validate_name(objective, "objective")

    try:
        steps = tuple(steps)
    except TypeError as exc:
        raise PlanValidationError(
            "Steps must be an iterable collection"
        ) from exc

    if not steps:
        raise PlanValidationError(
            "A plan must contain at least one step"
        )

    if not all(isinstance(step, PlanStep) for step in steps):
        raise PlanValidationError(
            "Every plan step must be a PlanStep instance"
        )

    step_by_id = {}

    for step in steps:
        _validate_name(step.step_id, "Step ID")
        if step.step_id in step_by_id:
            raise PlanValidationError(f"Duplicate step ID: {step.step_id}")

        _validate_name(step.description, f"Description for step {step.step_id}")
        _validate_tuple(step.depends_on, f"Dependencies for step {step.step_id}")
        _validate_tuple(
            step.required_capabilities,
            f"Required capabilities for step {step.step_id}",
        )
        step_by_id[step.step_id] = step

    for step in steps:
        for dependency in step.depends_on:
            if dependency == step.step_id:
                raise PlanValidationError(
                    f"Step {step.step_id} cannot depend on itself"
                )
            if dependency not in step_by_id:
                raise PlanValidationError(
                    f"Unknown dependency '{dependency}' in step {step.step_id}"
                )

    # Stable topological ordering: earliest eligible input step first.
    remaining = list(steps)
    ordered = []
    completed = set()

    while remaining:
        ready_step = next(
            (
                step for step in remaining
                if all(dep in completed for dep in step.depends_on)
            ),
            None,
        )
        if ready_step is None:
            unresolved = ", ".join(step.step_id for step in remaining)
            raise PlanValidationError(
                f"Dependency cycle detected among: {unresolved}"
            )
        ordered.append(ready_step)
        completed.add(ready_step.step_id)
        remaining.remove(ready_step)

    available = _validate_available_capabilities(available_capabilities)

    missing = tuple(
        (step.step_id, capability)
        for step in ordered
        for capability in step.required_capabilities
        if capability not in available
    )

    return TaskPlan(
        objective=objective,
        ordered_steps=tuple(ordered),
        missing_capabilities=missing,
    )
