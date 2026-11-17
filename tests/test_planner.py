import pytest

from hive.planner import (
    PlanStep,
    PlanValidationError,
    build_plan,
)


def test_plan_orders_steps_by_dependencies():
    steps = [
        PlanStep("deploy", "Deploy the application", ("test",)),
        PlanStep("test", "Run the test suite", ("build",)),
        PlanStep("build", "Build the application"),
    ]

    plan = build_plan("Prepare an application release", steps)

    assert [step.step_id for step in plan.ordered_steps] == [
        "build",
        "test",
        "deploy",
    ]
    assert plan.ready is True


def test_plan_preserves_input_order_when_dependencies_allow():
    steps = [
        PlanStep("first", "First task"),
        PlanStep("second", "Second task"),
        PlanStep("third", "Third task"),
    ]

    plan = build_plan("Complete three tasks", steps)

    assert [step.step_id for step in plan.ordered_steps] == [
        "first",
        "second",
        "third",
    ]


def test_plan_identifies_missing_capabilities():
    steps = [
        PlanStep(
            "research",
            "Research an API",
            required_capabilities=("web_research", "http_client"),
        )
    ]

    plan = build_plan(
        "Research an API integration",
        steps,
        available_capabilities=("web_research",),
    )

    assert plan.ready is False
    assert plan.missing_capabilities == (
        ("research", "http_client"),
    )


def test_plan_is_ready_when_all_capabilities_exist():
    steps = [
        PlanStep(
            "research",
            "Research an API",
            required_capabilities=("web_research",),
        )
    ]

    plan = build_plan(
        "Research an API",
        steps,
        available_capabilities=("web_research",),
    )

    assert plan.ready is True
    assert plan.missing_capabilities == ()


def test_plan_rejects_duplicate_step_ids():
    steps = [
        PlanStep("same", "First task"),
        PlanStep("same", "Second task"),
    ]

    with pytest.raises(PlanValidationError, match="Duplicate step ID"):
        build_plan("Test duplicates", steps)


def test_plan_rejects_unknown_dependencies():
    steps = [
        PlanStep("first", "First task", ("missing",)),
    ]

    with pytest.raises(PlanValidationError, match="Unknown dependency"):
        build_plan("Test unknown dependency", steps)


def test_plan_rejects_dependency_cycles():
    steps = [
        PlanStep("first", "First task", ("second",)),
        PlanStep("second", "Second task", ("first",)),
    ]

    with pytest.raises(PlanValidationError, match="cycle"):
        build_plan("Test dependency cycle", steps)


def test_plan_rejects_empty_objective():
    with pytest.raises(PlanValidationError, match="objective"):
        build_plan(" ", [PlanStep("first", "First task")])


def test_plan_rejects_empty_steps():
    with pytest.raises(PlanValidationError, match="at least one step"):
        build_plan("An objective", [])


def test_plan_serializes_to_dictionary():
    plan = build_plan(
        "Inspect a repository",
        [
            PlanStep(
                "inspect",
                "Inspect repository files",
                required_capabilities=("repository_inspection",),
            )
        ],
        available_capabilities=("repository_inspection",),
    )

    result = plan.to_dict()

    assert result["objective"] == "Inspect a repository"
    assert result["ready"] is True
    assert result["ordered_steps"][0]["step_id"] == "inspect"
    assert result["missing_capabilities"] == []

def test_plan_rejects_unhashable_dependencies():
    steps = [PlanStep("first", "First task", ([],))]
    with pytest.raises(PlanValidationError):
        build_plan("Test invalid dependencies", steps)


def test_plan_rejects_unhashable_required_capabilities():
    steps = [
        PlanStep("first", "First task", required_capabilities=([],))
    ]
    with pytest.raises(PlanValidationError):
        build_plan("Test invalid capabilities", steps)


def test_plan_rejects_string_as_available_capabilities():
    with pytest.raises(PlanValidationError, match="not a string"):
        build_plan(
            "Test capability validation",
            [PlanStep("first", "First task")],
            available_capabilities="web_research",
        )


def test_plan_rejects_invalid_available_capability():
    with pytest.raises(PlanValidationError):
        build_plan(
            "Test invalid capability",
            [PlanStep("first", "First task")],
            available_capabilities=(" ",),
        )


def test_plan_rejects_whitespace_step_ids():
    with pytest.raises(PlanValidationError):
        build_plan(
            "Test whitespace",
            [PlanStep(" first ", "First task")],
        )


def test_plan_rejects_duplicate_dependencies():
    steps = [
        PlanStep("first", "First task", ("second", "second")),
        PlanStep("second", "Second task"),
    ]
    with pytest.raises(PlanValidationError, match="duplicates"):
        build_plan("Test duplicate dependencies", steps)


def test_plan_uses_stable_eligible_step_order():
    steps = [
        PlanStep("first", "First task", ("second",)),
        PlanStep("second", "Second task"),
        PlanStep("third", "Third task"),
    ]
    plan = build_plan("Test stable ordering", steps)
    assert [step.step_id for step in plan.ordered_steps] == [
        "second", "first", "third"
    ]


def test_plan_rejects_non_iterable_available_capabilities():
    with pytest.raises(PlanValidationError, match="iterable"):
        build_plan(
            "Test invalid collection",
            [PlanStep("first", "First task")],
            available_capabilities=None,
        )
